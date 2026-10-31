"""
customers.py — Synthetic Customer entity generator.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import numpy as np
from faker import Faker

from supply_chain.generators.config import MasterDataConfig
from supply_chain.models import Customer, IDFactory
from supply_chain.models.enums import CustomerStatus

_CUSTOMER_TYPES: tuple[str, ...] = (
    "General Hospital",
    "Health System",
    "Medical Center",
    "Pharmaceutical Distributors",
    "Apothecary Network",
)


def generate_customers(
    config: MasterDataConfig,
    rng: np.random.Generator,
    fake: Faker,
    id_factory: IDFactory,
) -> list[Customer]:
    """
    Generate deterministic Customer recipient records.
    """
    customers: list[Customer] = []
    num_cust_types = len(_CUSTOMER_TYPES)

    for i in range(config.customer_count):
        cust_id = id_factory.next()
        cust_type = _CUSTOMER_TYPES[i % num_cust_types]
        name = f"{fake.last_name()} {cust_type}"
        location = f"{fake.city()}, {fake.country()}"
        email = f"logistics@{fake.domain_name()}"

        # Status: 97% ACTIVE, 3% INACTIVE
        status = (
            CustomerStatus.ACTIVE
            if rng.random() < 0.97
            else CustomerStatus.INACTIVE
        )

        days_prior = int(rng.integers(60, 400))
        created_date = config.base_date - timedelta(days=days_prior)
        created_at = datetime.combine(created_date, time(8, 30), tzinfo=timezone.utc)

        customer = Customer(
            customer_id=cust_id,
            customer_name=name,
            location=location,
            contact_email=email,
            status=status,
            created_at=created_at,
            updated_at=created_at,
        )
        customers.append(customer)

    return customers
