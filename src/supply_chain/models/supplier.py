"""
supplier.py — Supplier domain model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar, Optional, Sequence

from supply_chain.models.common import (
    EntityBase,
    freeze_string_tuple,
    require_date_order,
    require_nonempty,
)
from supply_chain.models.enums import SupplierStatus


@dataclass
class Supplier(EntityBase):
    """
    Supplier master record.
    PK: supplier_id (SUP-<6-digit>)
    """
    _pk_name: ClassVar[str] = "supplier_id"

    supplier_id:     str
    supplier_name:   str
    location:        str
    material_types:  Sequence[str]
    status:          SupplierStatus
    effective_start: date
    effective_end:   Optional[date]
    created_at:      datetime
    updated_at:      datetime

    def __post_init__(self) -> None:
        require_nonempty(self.supplier_id, "supplier_id")
        require_nonempty(self.supplier_name, "supplier_name")
        require_nonempty(self.location, "location")
        object.__setattr__(
            self,
            "material_types",
            freeze_string_tuple(self.material_types, "material_types"),
        )
        require_date_order(self.effective_start, self.effective_end)
        self._mark_initialized()
