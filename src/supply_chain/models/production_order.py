"""
production_order.py — Production order and raw material consumption models.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import ClassVar, Optional

from supply_chain.models.common import (
    EntityBase,
    require_date_order,
    require_nonempty,
    require_non_negative,
    require_positive,
    utc_now,
)
from supply_chain.models.enums import ProductionOrderStatus


@dataclass
class ProductionOrder(EntityBase):
    """
    Work order / Production order record.
    PK: wo_id (WO-2026-<6-digit>)
    FK: product_id -> Product.product_id, bom_id -> BOM.bom_id

    Yield and Scrap Accounting (D-02, QA-04):
      - yield_ratio is in range [0.85, 0.98].
      - actual_good_output_qty = math.floor(planned_output_qty * yield_ratio).
      - scrap_qty = planned_output_qty - actual_good_output_qty.
      - All yield loss is treated strictly as scrap quantity.
      - Total FinishedLot output quantities for this order must sum to actual_good_output_qty.
    """
    _pk_name: ClassVar[str] = "wo_id"

    wo_id:                  str
    product_id:             str
    bom_id:                 str
    planned_output_qty:     int
    yield_ratio:            float
    actual_good_output_qty: int
    scrap_qty:              int
    status:                 ProductionOrderStatus
    planned_start:          date
    planned_end:            date
    actual_start:           Optional[date] = None
    actual_end:             Optional[date] = None
    created_at:             datetime = field(default_factory=utc_now)
    updated_at:             datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.wo_id, "wo_id")
        require_nonempty(self.product_id, "product_id")
        require_nonempty(self.bom_id, "bom_id")
        require_positive(self.planned_output_qty, "planned_output_qty")
        require_non_negative(self.actual_good_output_qty, "actual_good_output_qty")
        require_non_negative(self.scrap_qty, "scrap_qty")

        if not (0.85 <= self.yield_ratio <= 0.98):
            raise ValueError(f"yield_ratio must be in [0.85, 0.98], got {self.yield_ratio}")

        expected_good = math.floor(self.planned_output_qty * self.yield_ratio)
        if self.actual_good_output_qty != expected_good:
            raise ValueError(
                f"actual_good_output_qty ({self.actual_good_output_qty}) != "
                f"floor(planned_output_qty * yield_ratio) ({expected_good})"
            )

        expected_scrap = self.planned_output_qty - self.actual_good_output_qty
        if self.scrap_qty != expected_scrap:
            raise ValueError(
                f"scrap_qty ({self.scrap_qty}) must equal "
                f"planned_output_qty - actual_good_output_qty ({expected_scrap})"
            )

        require_date_order(self.planned_start, self.planned_end, "planned_start", "planned_end")
        if self.actual_start is not None and self.actual_end is not None:
            require_date_order(self.actual_start, self.actual_end, "actual_start", "actual_end")

        self._mark_initialized()


@dataclass
class LotConsumption:
    """
    Bridge table: consumption of a MaterialLot in a ProductionOrder.
    PK: composite (wo_id, raw_lot_id)
    """
    wo_id:        str
    raw_lot_id:   str
    consumed_qty: int
    created_at:   datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.wo_id, "wo_id")
        require_nonempty(self.raw_lot_id, "raw_lot_id")
        require_positive(self.consumed_qty, "consumed_qty")


@dataclass
class AnomalousLotConsumption:
    """
    Controlled fixture record for EC-1:
    A consumption link referencing a raw_lot_id that does not exist in MaterialLot.
    Preserved separately from the baseline operational dataset.
    """
    wo_id:          str
    raw_lot_id:     str
    consumed_qty:   int
    is_anomaly:     bool = True
    edge_case_code: str = "EC-1"
    created_at:     datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.wo_id, "wo_id")
        require_nonempty(self.raw_lot_id, "raw_lot_id")
        require_positive(self.consumed_qty, "consumed_qty")
        if not self.is_anomaly:
            raise ValueError("AnomalousLotConsumption.is_anomaly must be True")
