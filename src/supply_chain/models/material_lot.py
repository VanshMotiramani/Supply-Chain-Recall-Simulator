"""
material_lot.py — Raw material lot domain model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar, Optional

from supply_chain.models.common import (
    EntityBase,
    require_date_order,
    require_nonempty,
    require_non_negative,
)
from supply_chain.models.enums import MaterialLotStatus


@dataclass
class MaterialLot(EntityBase):
    """
    Raw material lot received from a supplier.
    PK: lot_id (RAWLOT-<supplier_id>-2026-<6-digit>)
    FK: supplier_id -> Supplier.supplier_id
    """
    _pk_name: ClassVar[str] = "lot_id"

    lot_id:          str
    supplier_id:     str
    material_type:   str
    quantity:        int
    unit_of_measure: str
    received_date:   date
    status:          MaterialLotStatus
    effective_start: date
    effective_end:   Optional[date]
    created_at:      datetime
    updated_at:      datetime

    def __post_init__(self) -> None:
        require_nonempty(self.lot_id, "lot_id")
        require_nonempty(self.supplier_id, "supplier_id")
        require_nonempty(self.material_type, "material_type")
        require_non_negative(self.quantity, "quantity")
        require_nonempty(self.unit_of_measure, "unit_of_measure")
        require_date_order(self.effective_start, self.effective_end)
        self._mark_initialized()

    def is_effective_on(self, on_date: date) -> bool:
        """
        Check if the lot is within its effective date range on on_date (inclusive).

        Rules:
          - on_date >= effective_start
          - on_date <= effective_end (if effective_end is defined)
        """
        if on_date < self.effective_start:
            return False
        if self.effective_end is not None and on_date > self.effective_end:
            return False
        return True

    def is_eligible_for_consumption(self, on_date: date) -> bool:
        """
        Check if the lot is eligible for production consumption on on_date.

        A lot is eligible if and only if:
          - Its lifecycle status is APPROVED.
          - Its effective-end / expiry date does not precede on_date (inclusive boundary:
            a lot expiring on on_date remains eligible on that date).
          - Its effective-start date is on or before on_date.
        """
        return self.status == MaterialLotStatus.APPROVED and self.is_effective_on(on_date)

