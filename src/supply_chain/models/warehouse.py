"""
warehouse.py — Warehouse master domain model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

from supply_chain.models.common import EntityBase, require_nonempty, utc_now
from supply_chain.models.enums import WarehouseStatus


@dataclass
class Warehouse(EntityBase):
    """
    Physical warehouse/facility record.
    PK: warehouse_id (WHS-<6-digit>)
    """
    _pk_name: ClassVar[str] = "warehouse_id"

    warehouse_id: str
    name:         str
    location:     str
    status:       WarehouseStatus
    created_at:   datetime = field(default_factory=utc_now)
    updated_at:   datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.warehouse_id, "warehouse_id")
        require_nonempty(self.name, "name")
        require_nonempty(self.location, "location")
        self._mark_initialized()
