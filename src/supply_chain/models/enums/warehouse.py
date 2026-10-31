"""
Warehouse and inventory movement enums.
"""

from enum import StrEnum


class WarehouseStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class MovementType(StrEnum):
    RECEIPT = "RECEIPT"
    SHIPMENT = "SHIPMENT"
    QUARANTINE = "QUARANTINE"
    RELEASE = "RELEASE"
    DISPOSAL = "DISPOSAL"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    RECOVERY = "RECOVERY"
