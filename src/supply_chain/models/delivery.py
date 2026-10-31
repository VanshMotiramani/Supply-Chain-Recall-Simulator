"""
delivery.py — Delivery line item domain model.

QUANTITY AND ALLOCATION DISTINCTIONS (C.3, C.6):
================================================
- Allocation: Reservation of stock from a warehouse's available balance for a planned shipment.
- Shipped Quantity (shipped_qty): The quantity physically dispatched from the warehouse
  under a Shipment (reflected in an InventoryMovement of type SHIPMENT).
- Delivered Quantity: The quantity received by the customer upon delivery confirmation.
  When Delivery.status == DELIVERED, shipped_qty has been confirmed delivered.

DATES AND STATUS CONSISTENCY:
- PENDING deliveries must have delivered_date = None.
- DELIVERED deliveries must have a non-null delivered_date.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import ClassVar, Optional

from supply_chain.models.common import (
    EntityBase,
    require_nonempty,
    require_positive,
    utc_now,
)
from supply_chain.models.enums import DeliveryStatus


@dataclass
class Delivery(EntityBase):
    """
    Delivery line item linking a finished lot to a shipment.
    PK: delivery_id (DEL-2026-<6-digit>)
    FK: shipment_id -> Shipment.shipment_id, fin_lot_id -> FinishedLot.fin_lot_id
    """
    _pk_name: ClassVar[str] = "delivery_id"

    delivery_id:    str
    shipment_id:    str
    fin_lot_id:     str
    shipped_qty:    int
    status:         DeliveryStatus
    delivered_date: Optional[date] = None
    created_at:     datetime = field(default_factory=utc_now)
    updated_at:     datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.delivery_id, "delivery_id")
        require_nonempty(self.shipment_id, "shipment_id")
        require_nonempty(self.fin_lot_id, "fin_lot_id")
        require_positive(self.shipped_qty, "shipped_qty")

        if self.status == DeliveryStatus.DELIVERED and self.delivered_date is None:
            raise ValueError("delivered_date is required when delivery status is DELIVERED")
        if self.status == DeliveryStatus.PENDING and self.delivered_date is not None:
            raise ValueError("delivered_date must be None when delivery status is PENDING")

        self._mark_initialized()
