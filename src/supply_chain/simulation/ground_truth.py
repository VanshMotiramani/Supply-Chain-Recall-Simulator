"""
ground_truth.py — Authoritative ground truth registry for injected simulation anomalies.

Ground truth records capture exactly what anomalies were intentionally injected,
their target entities, and intended delta quantities. This registry remains strictly
separate from detector discrepancy findings so verification metrics (precision, recall,
coverage) can compare detector outputs against ground truth without contamination.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Optional


class AnomalyType(StrEnum):
    """Controlled edge-case anomaly categories defined in Block 5."""
    MISSING_INPUT_LOT = "MISSING_INPUT_LOT"                                # EC-1
    QUANTITY_OVER_SHIPMENT = "QUANTITY_OVER_SHIPMENT"                      # EC-2
    MISSED_CUSTOMER_NOTIFICATION = "MISSED_CUSTOMER_NOTIFICATION"          # EC-3
    UNQUARANTINED_RECALLED_INVENTORY = "UNQUARANTINED_RECALLED_INVENTORY"  # EC-4


@dataclass(frozen=True)
class AnomalyRecord:
    """
    Immutable specification of an intentionally injected anomaly.

    Attributes:
        anomaly_id: Unique identifier for this anomaly injection (e.g., ANOM-EC1-001).
        edge_case_code: Label of the edge case ("EC-1", "EC-2", "EC-3", "EC-4").
        anomaly_type: Enum category of the anomaly.
        target_entity_type: Type name of the targeted entity (e.g. "ProductionOrder", "Delivery").
        target_entity_id: Primary key of the targeted entity.
        intended_quantity: Injected quantity delta or count (e.g., 15 for EC-2 excess quantity).
        expected_outcome: Description of the expected system state / discrepancy.
        metadata: Read-only mapping of additional contextual attributes.
    """
    anomaly_id: str
    edge_case_code: str
    anomaly_type: AnomalyType
    target_entity_type: str
    target_entity_id: str
    intended_quantity: Optional[int] = None
    expected_outcome: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.anomaly_id:
            raise ValueError("anomaly_id cannot be empty")
        if not self.edge_case_code:
            raise ValueError("edge_case_code cannot be empty")
        if not self.target_entity_id:
            raise ValueError("target_entity_id cannot be empty")

        # Defensively copy and wrap in read-only MappingProxyType for complete immutability
        raw_meta = self.metadata if self.metadata is not None else {}
        object.__setattr__(self, "metadata", MappingProxyType(dict(raw_meta)))


class GroundTruthRegistry:
    """
    Authoritative container for all injected anomaly records in a simulation run.
    """

    def __init__(self) -> None:
        self._records: dict[str, AnomalyRecord] = {}

    def register(self, record: AnomalyRecord) -> None:
        """
        Register an injected anomaly record.

        Raises:
            ValueError: If an anomaly with the same anomaly_id is already registered.
        """
        if record.anomaly_id in self._records:
            raise ValueError(f"Duplicate anomaly_id registered: {record.anomaly_id}")
        self._records[record.anomaly_id] = record

    def get_by_id(self, anomaly_id: str) -> Optional[AnomalyRecord]:
        """Lookup an anomaly record by its unique ID."""
        return self._records.get(anomaly_id)

    def get_by_edge_case(self, edge_case_code: str) -> tuple[AnomalyRecord, ...]:
        """Return all anomalies matching an edge case code (e.g., 'EC-1')."""
        return tuple(r for r in self._records.values() if r.edge_case_code == edge_case_code)

    def get_by_type(self, anomaly_type: AnomalyType) -> tuple[AnomalyRecord, ...]:
        """Return all anomalies matching a specific anomaly type."""
        return tuple(r for r in self._records.values() if r.anomaly_type == anomaly_type)

    def all_records(self) -> tuple[AnomalyRecord, ...]:
        """Return an immutable tuple of all registered anomaly records."""
        return tuple(self._records.values())

    def count(self) -> int:
        """Total number of registered anomalies."""
        return len(self._records)

    def summary(self) -> dict[str, int]:
        """Return counts of registered anomalies grouped by edge case code."""
        counts: dict[str, int] = {}
        for r in self._records.values():
            counts[r.edge_case_code] = counts.get(r.edge_case_code, 0) + 1
        return counts
