"""
models.py — Simulation dataset container, discrepancy findings, reports, and metrics.

Defines the isolated runtime container for simulation execution and the typed
discrepancy reporting structures that decouple detector findings from ground truth.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional, Sequence

from supply_chain.generators.config import (
    DistributionDataset,
    MasterDataset,
    ProductionDataset,
)
from supply_chain.models import (
    Delivery,
    InventoryLedger,
    InventoryMovement,
    LotConsumption,
    RecallAction,
    RecallCase,
    Shipment,
)
from supply_chain.models.common import utc_now
from supply_chain.models.production_order import AnomalousLotConsumption
from supply_chain.simulation.config import RecallSimulationConfig
from supply_chain.simulation.ground_truth import GroundTruthRegistry


# ---------------------------------------------------------------------------
# Discrepancy Findings & Reports (Detector Outputs)
# ---------------------------------------------------------------------------

class DiscrepancyCategory(StrEnum):
    """Categorization of discrepancies identified by audit / detection services."""
    BROKEN_FOREIGN_KEY = "BROKEN_FOREIGN_KEY"                         # EC-1
    NEGATIVE_INVENTORY = "NEGATIVE_INVENTORY"                         # EC-2 (ledger available < 0)
    OVER_SHIPMENT_VARIANCE = "OVER_SHIPMENT_VARIANCE"                 # EC-2 (dispatch exceeds legitimacy)
    UNNOTIFIED_CUSTOMER = "UNNOTIFIED_CUSTOMER"                       # EC-3 (omitted notification)
    COMMERCIAL_EXPOSURE = "COMMERCIAL_EXPOSURE"                       # EC-4 (unquarantined recalled stock)
    INVENTORY_CONSERVATION_VARIANCE = "INVENTORY_CONSERVATION_VARIANCE"  # Conservation check failure


@dataclass(frozen=True)
class DiscrepancyFinding:
    """
    Immutable individual discrepancy finding produced by a detector or auditor.

    Attributes:
        finding_id: Unique identifier for this finding.
        category: DiscrepancyCategory enum value.
        entity_type: Name of the problematic entity (e.g., 'LotConsumption', 'Delivery').
        entity_id: Primary key or identifier of the offending entity.
        severity: Severity level ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW').
        discrepancy_qty: Measured quantity discrepancy (if applicable, e.g., 15 for EC-2).
        details: Human-readable explanation of the discrepancy.
        detected_at: Timestamp of detection.
        metadata: Additional contextual details.
    """
    finding_id: str
    category: DiscrepancyCategory
    entity_type: str
    entity_id: str
    severity: str = "HIGH"
    discrepancy_qty: Optional[int] = None
    details: str = ""
    detected_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.finding_id:
            raise ValueError("finding_id cannot be empty")
        if not self.entity_id:
            raise ValueError("entity_id cannot be empty")
        if self.severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            raise ValueError(f"Invalid severity '{self.severity}', must be CRITICAL, HIGH, MEDIUM, or LOW")


@dataclass(frozen=True)
class DiscrepancyReport:
    """
    Consolidated discrepancy report containing all detector findings.
    """
    findings: tuple[DiscrepancyFinding, ...]
    generated_at: datetime = field(default_factory=utc_now)

    def by_category(self, category: DiscrepancyCategory) -> tuple[DiscrepancyFinding, ...]:
        """Filter findings by discrepancy category."""
        return tuple(f for f in self.findings if f.category == category)

    def by_severity(self, severity: str) -> tuple[DiscrepancyFinding, ...]:
        """Filter findings by severity level."""
        return tuple(f for f in self.findings if f.severity == severity)

    def has_critical(self) -> bool:
        """Return True if any finding has CRITICAL severity."""
        return any(f.severity == "CRITICAL" for f in self.findings)

    def total_findings(self) -> int:
        """Total number of findings in this report."""
        return len(self.findings)

    def summary(self) -> dict[str, int]:
        """Return counts of findings grouped by category."""
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.category.value] = counts.get(f.category.value, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Recall Metric Result Container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecallMetricsResult:
    """
    Quantitative metrics measuring recall effectiveness, ledger reconciliation, and detector accuracy.

    Attributes:
        notification_coverage: Fraction of affected customers notified (0.0 to 1.0).
        quarantine_coverage: Fraction of affected finished stock quarantined (0.0 to 1.0).
        recovery_rate: Fraction of shipped affected stock successfully recovered (0.0 to 1.0).
        inventory_conservation_variance: Conservation variance: on_hand + net_shipped + disposed - produced.
        overshipment_discrepancy: Difference between cumulative net shipments and legitimate availability.
        precision: Detector precision against ground truth anomalies.
        recall: Detector recall against ground truth anomalies.
        f1_score: Harmonic mean of precision and recall.
        metadata: Additional diagnostic metrics.
    """
    notification_coverage: Optional[float] = None
    quarantine_coverage: Optional[float] = None
    recovery_rate: Optional[float] = None
    inventory_conservation_variance: int = 0
    overshipment_discrepancy: int = 0
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Simulation Dataset Container & Baseline Isolation
# ---------------------------------------------------------------------------

@dataclass
class SimulationDataset:
    """
    Authoritative runtime container for Block 5 recall simulation and anomaly injection.

    Design Principle (Baseline Isolation):
      - Master, production, and distribution datasets from Blocks 2-4 serve as the
        immutable reference baseline.
      - Any entity collection subject to mutation or extension during recall simulation
        (inventory ledger, delivery line items, lot consumptions, shipments, inventory movements,
        recall cases, recall actions) is isolated within this container.
      - Mutating `simulation.inventory_ledger` or `simulation.deliveries` has zero side-effects
        on the underlying baseline datasets.
    """
    master: MasterDataset
    production: ProductionDataset
    distribution: DistributionDataset

    # Isolated mutable collections for simulation execution
    lot_consumptions: list[LotConsumption | AnomalousLotConsumption]
    deliveries: list[Delivery]
    shipments: list[Shipment]
    inventory_movements: list[InventoryMovement]
    inventory_ledger: InventoryLedger

    # Simulation-specific headers and audit trails
    recall_cases: list[RecallCase] = field(default_factory=list)
    recall_actions: list[RecallAction] = field(default_factory=list)

    # Authoritative ground-truth registry of injected anomalies
    ground_truth: GroundTruthRegistry = field(default_factory=GroundTruthRegistry)

    # Configuration for this run
    config: RecallSimulationConfig = field(default_factory=RecallSimulationConfig)

    def summary(self) -> dict[str, int]:
        """Return counts of entities in this simulation dataset."""
        return {
            "suppliers": len(self.master.suppliers),
            "products": len(self.master.products),
            "warehouses": len(self.master.warehouses),
            "customers": len(self.master.customers),
            "material_lots": len(self.production.material_lots),
            "production_orders": len(self.production.production_orders),
            "lot_consumptions": len(self.lot_consumptions),
            "finished_lots": len(self.production.finished_lots),
            "shipments": len(self.shipments),
            "deliveries": len(self.deliveries),
            "inventory_movements": len(self.inventory_movements),
            "ledger_movements": len(self.inventory_ledger.all_movements),
            "recall_cases": len(self.recall_cases),
            "recall_actions": len(self.recall_actions),
            "injected_anomalies": self.ground_truth.count(),
        }


def create_simulation_dataset(
    master: MasterDataset,
    production: ProductionDataset,
    distribution: DistributionDataset,
    config: RecallSimulationConfig | None = None,
) -> SimulationDataset:
    """
    Create a fresh SimulationDataset, strictly isolating mutable structures from baseline.

    Isolation Guarantees:
      - `lot_consumptions`: Shallow-copied elements in a new list, enabling EC-1 appending
        or modification without mutating `production.lot_consumptions`.
      - `deliveries`: Each `Delivery` object is copied into a new list, so EC-2 quantity
        over-shipment mutations do not alter `distribution.deliveries`.
      - `shipments`: Copied into a new list.
      - `inventory_movements`: Copied into a new list, ready for appending new movements.
      - `inventory_ledger`: Deep-copied from `distribution.inventory_ledger`, ensuring all
        running slot counters and recorded movements are decoupled.
      - `master` and `production` (material_lots, finished_lots, etc.) are preserved intact.

    Args:
        master: Baseline master data.
        production: Baseline production data.
        distribution: Baseline distribution data.
        config: Simulation configuration (defaults to clean default config).

    Returns:
        SimulationDataset ready for pure traceability or isolated anomaly injection.
    """
    cfg = config or RecallSimulationConfig()

    isolated_consumptions: list[LotConsumption | AnomalousLotConsumption] = [
        copy.copy(c) for c in production.lot_consumptions
    ]
    isolated_deliveries: list[Delivery] = [
        copy.copy(d) for d in distribution.deliveries
    ]
    isolated_shipments: list[Shipment] = [
        copy.copy(s) for s in distribution.shipments
    ]
    isolated_movements: list[InventoryMovement] = [
        copy.copy(m) for m in distribution.inventory_movements
    ]
    isolated_ledger: InventoryLedger = copy.deepcopy(distribution.inventory_ledger)

    return SimulationDataset(
        master=master,
        production=production,
        distribution=distribution,
        lot_consumptions=isolated_consumptions,
        deliveries=isolated_deliveries,
        shipments=isolated_shipments,
        inventory_movements=isolated_movements,
        inventory_ledger=isolated_ledger,
        recall_cases=[],
        recall_actions=[],
        ground_truth=GroundTruthRegistry(),
        config=cfg,
    )
