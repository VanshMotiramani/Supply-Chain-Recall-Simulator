"""
Supplier enums.
"""

from enum import StrEnum


class SupplierStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    INACTIVE = "INACTIVE"
