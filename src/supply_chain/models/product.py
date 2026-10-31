"""
product.py — Product master domain model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from supply_chain.models.common import EntityBase, require_nonempty
from supply_chain.models.enums import ProductStatus


@dataclass
class Product(EntityBase):
    """
    Finished product master definition.
    PK: product_id (PROD-<6-digit>)
    """
    _pk_name: ClassVar[str] = "product_id"

    product_id:      str
    product_name:    str
    product_type:    str
    unit_of_measure: str
    status:          ProductStatus
    created_at:      datetime
    updated_at:      datetime

    def __post_init__(self) -> None:
        require_nonempty(self.product_id, "product_id")
        require_nonempty(self.product_name, "product_name")
        require_nonempty(self.product_type, "product_type")
        require_nonempty(self.unit_of_measure, "unit_of_measure")
        self._mark_initialized()
