"""
customer.py — Customer domain model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

from supply_chain.models.common import EntityBase, require_nonempty, utc_now
from supply_chain.models.enums import CustomerStatus


@dataclass
class Customer(EntityBase):
    """
    Customer master record.
    PK: customer_id (CUST-<6-digit>)
    """
    _pk_name: ClassVar[str] = "customer_id"

    customer_id:   str
    customer_name: str
    location:      str
    contact_email: str
    status:        CustomerStatus
    created_at:    datetime = field(default_factory=utc_now)
    updated_at:    datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.customer_id, "customer_id")
        require_nonempty(self.customer_name, "customer_name")
        require_nonempty(self.location, "location")
        require_nonempty(self.contact_email, "contact_email")
        self._mark_initialized()
