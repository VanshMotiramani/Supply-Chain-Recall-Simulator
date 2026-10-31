"""
Production and finished lot enums.
"""

from enum import StrEnum


class ProductionOrderStatus(StrEnum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class FinishedLotStatus(StrEnum):
    """
    High-level quality and commercial lifecycle state of the finished lot entity.
    Quantity distribution across warehouses is tracked authoritatively by inventory movements.
    """
    PRODUCED = "PRODUCED"
    AVAILABLE = "AVAILABLE"
    SHIPPED = "SHIPPED"
    QUARANTINED = "QUARANTINED"
    DISPOSED = "DISPOSED"
    RELEASED = "RELEASED"
