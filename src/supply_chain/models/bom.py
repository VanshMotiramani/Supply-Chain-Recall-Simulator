"""
bom.py — Bill of Materials (BOM) domain model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar, Optional

from supply_chain.models.common import (
    EntityBase,
    require_date_order,
    require_nonempty,
    require_positive,
)
from supply_chain.models.enums import BOMStatus


@dataclass
class BOM(EntityBase):
    """
    Bill of Materials header.
    PK: bom_id (BOM-<6-digit>)
    FK: product_id -> Product.product_id
    """
    _pk_name: ClassVar[str] = "bom_id"

    bom_id:          str
    product_id:      str
    version:         int
    effective_start: date
    effective_end:   Optional[date]
    status:          BOMStatus
    created_at:      datetime
    updated_at:      datetime

    def __post_init__(self) -> None:
        require_nonempty(self.bom_id, "bom_id")
        require_nonempty(self.product_id, "product_id")
        require_positive(self.version, "version")
        require_date_order(self.effective_start, self.effective_end)
        self._mark_initialized()


@dataclass
class BOMLine:
    """
    Bridge table: BOM components.
    PK: composite (bom_id, line_no)
    """
    bom_id:            str
    line_no:           int
    material_type:     str
    quantity_per_unit: int
    unit_of_measure:   str
    created_at:        datetime

    def __post_init__(self) -> None:
        require_nonempty(self.bom_id, "bom_id")
        require_positive(self.line_no, "line_no")
        require_nonempty(self.material_type, "material_type")
        require_positive(self.quantity_per_unit, "quantity_per_unit")
        require_nonempty(self.unit_of_measure, "unit_of_measure")
