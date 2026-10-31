"""
MaterialLot enums.
"""

from enum import StrEnum


class MaterialLotStatus(StrEnum):
    RECEIVED = "RECEIVED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONSUMED = "CONSUMED"
    QUARANTINED = "QUARANTINED"
    DISPOSED = "DISPOSED"
    RELEASED = "RELEASED"
