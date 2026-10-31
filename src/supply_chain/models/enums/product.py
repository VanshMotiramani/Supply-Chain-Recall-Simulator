"""
Product and BOM enums.
"""

from enum import StrEnum


class ProductStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISCONTINUED = "DISCONTINUED"


class BOMStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SUPERSEDED = "SUPERSEDED"
