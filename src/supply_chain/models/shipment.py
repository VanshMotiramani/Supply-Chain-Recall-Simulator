"""
shipment.py — Shipment domain model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import ClassVar

from supply_chain.models.common import EntityBase, require_nonempty, utc_now
from supply_chain.models.enums import ShipmentStatus


@dataclass
class Shipment(EntityBase):
    """
    Outbound shipment header to a customer.
    PK: shipment_id (SHP-2026-<6-digit>)
    FK: customer_id -> Customer.customer_id, warehouse_id -> Warehouse.warehouse_id
    """
    _pk_name: ClassVar[str] = "shipment_id"

    shipment_id:  str
    customer_id:  str
    warehouse_id: str
    status:       ShipmentStatus
    ship_date:    date
    created_at:   datetime = field(default_factory=utc_now)
    updated_at:   datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.shipment_id, "shipment_id")
        require_nonempty(self.customer_id, "customer_id")
        require_nonempty(self.warehouse_id, "warehouse_id")
        self._mark_initialized()
