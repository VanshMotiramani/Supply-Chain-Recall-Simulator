"""
config.py — Configuration parameters for the supply chain recall simulation (Block 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RecallSimulationConfig:
    """
    Configuration parameters controlling the deterministic recall simulation and edge-case injection.

    Attributes:
        seed: Deterministic random seed (default: 20261022).
        inject_ec1: Whether to inject EC-1 (Consumption references nonexistent raw material lot).
        inject_ec2: Whether to inject EC-2 (Quantity over-shipment creating negative available stock).
        inject_ec3: Whether to inject EC-3 (Missed downstream customer notification in recall action).
        inject_ec4: Whether to inject EC-4 (Unquarantined recalled stock leaked to commercial inventory).
        ec2_excess_qty: Incremental units to over-ship in EC-2 (default: 15, must be > 0).
        target_material_lot_id: Explicit raw lot target for recall scenario (None = deterministic auto-selection).
        target_finished_lot_id: Explicit finished lot target (None = deterministic auto-selection).
        target_delivery_id: Explicit delivery target for EC-2 over-shipment (None = deterministic auto-selection).
        target_warehouse_id: Explicit warehouse target for EC-4 leak (None = deterministic auto-selection).
        target_customer_id: Explicit customer target for EC-3 omitted notice (None = deterministic auto-selection).
    """
    seed: int = 20261022
    inject_ec1: bool = True
    inject_ec2: bool = True
    inject_ec3: bool = True
    inject_ec4: bool = True
    ec2_excess_qty: int = 15

    # Optional explicit targets for repeatable unit testing
    target_material_lot_id: Optional[str] = None
    target_finished_lot_id: Optional[str] = None
    target_delivery_id: Optional[str] = None
    target_warehouse_id: Optional[str] = None
    target_customer_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.seed, int) or self.seed < 0:
            raise ValueError(f"seed must be a non-negative integer, got {self.seed}")
        if not isinstance(self.ec2_excess_qty, int) or self.ec2_excess_qty <= 0:
            raise ValueError(f"ec2_excess_qty must be a positive integer (> 0), got {self.ec2_excess_qty}")
        for flag_name, flag_val in (
            ("inject_ec1", self.inject_ec1),
            ("inject_ec2", self.inject_ec2),
            ("inject_ec3", self.inject_ec3),
            ("inject_ec4", self.inject_ec4),
        ):
            if not isinstance(flag_val, bool):
                raise TypeError(f"{flag_name} must be a boolean, got {type(flag_val).__name__}")

    @property
    def has_anomalies(self) -> bool:
        """Return True if any edge case anomaly is scheduled for injection."""
        return self.inject_ec1 or self.inject_ec2 or self.inject_ec3 or self.inject_ec4

    @classmethod
    def for_starter(cls, seed: int = 20261022) -> RecallSimulationConfig:
        """Preset for starter scale simulation."""
        return cls(
            seed=seed,
            inject_ec1=True,
            inject_ec2=True,
            inject_ec3=True,
            inject_ec4=True,
            ec2_excess_qty=15,
        )

    @classmethod
    def for_full(cls, seed: int = 20261022) -> RecallSimulationConfig:
        """Preset for full scale simulation."""
        return cls(
            seed=seed,
            inject_ec1=True,
            inject_ec2=True,
            inject_ec3=True,
            inject_ec4=True,
            ec2_excess_qty=15,
        )

    @classmethod
    def clean_baseline(cls, seed: int = 20261022) -> RecallSimulationConfig:
        """Preset for a clean recall simulation with zero injected anomalies."""
        return cls(
            seed=seed,
            inject_ec1=False,
            inject_ec2=False,
            inject_ec3=False,
            inject_ec4=False,
            ec2_excess_qty=15,
        )
