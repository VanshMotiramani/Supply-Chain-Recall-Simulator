"""
finished_lot.py — Finished lot domain model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import ClassVar

from supply_chain.models.common import (
    EntityBase,
    require_nonempty,
    require_positive,
    utc_now,
)
from supply_chain.models.enums import FinishedLotStatus


@dataclass
class FinishedLot(EntityBase):
    """
    Finished product lot resulting from a ProductionOrder.
    PK: fin_lot_id (FINLOT-2026-<6-digit>)
    FK: wo_id -> ProductionOrder.wo_id

    Design Note (B.1, C.2):
      - FinishedLot.status represents the overall quality and commercial disposition
        of the lot as an entity (e.g., PRODUCED, AVAILABLE, QUARANTINED, RECALLED, DISPOSED).
      - Warehouse location and quantity distribution (available vs quarantined vs shipped)
        are tracked authoritatively via InventoryMovement records, removing competing
        warehouse assignment from FinishedLot.
    """
    _pk_name: ClassVar[str] = "fin_lot_id"

    fin_lot_id:    str
    wo_id:         str
    quantity:      int
    produced_date: date
    status:        FinishedLotStatus
    created_at:    datetime = field(default_factory=utc_now)
    updated_at:    datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.fin_lot_id, "fin_lot_id")
        require_nonempty(self.wo_id, "wo_id")
        require_positive(self.quantity, "quantity")
        self._mark_initialized()
