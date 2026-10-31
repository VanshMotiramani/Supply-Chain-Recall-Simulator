"""
Shipment, customer, and delivery enums.
"""

from enum import StrEnum


class CustomerStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ShipmentStatus(StrEnum):
    """
    Shipment lifecycle states.
    PARTIALLY_RECALLED is omitted per D-12 (whole-lot / whole-shipment recall scope).
    """
    CREATED = "CREATED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    RECALLED = "RECALLED"


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    RECALLED = "RECALLED"
    QUARANTINED = "QUARANTINED"
