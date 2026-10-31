"""
warehouses.py — Synthetic Warehouse entity generator.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import numpy as np
from faker import Faker

from supply_chain.generators.config import MasterDataConfig
from supply_chain.models import IDFactory, Warehouse
from supply_chain.models.enums import WarehouseStatus

_FACILITY_TYPES: tuple[str, ...] = (
    "Central Distribution Center",
    "Regional Logistics Depot",
    "Cold-Chain Storage Terminal",
    "Air Cargo Transit Hub",
    "Consolidated Fulfillment Warehouse",
)


def generate_warehouses(
    config: MasterDataConfig,
    rng: np.random.Generator,
    fake: Faker,
    id_factory: IDFactory,
) -> list[Warehouse]:
    """
    Generate deterministic Warehouse storage facilities.
    """
    warehouses: list[Warehouse] = []
    num_facility_types = len(_FACILITY_TYPES)

    for i in range(config.warehouse_count):
        whs_id = id_factory.next()
        city = fake.city()
        facility_type = _FACILITY_TYPES[i % num_facility_types]
        name = f"{city} {facility_type}"
        location = f"{city}, {fake.country()}"

        status = WarehouseStatus.ACTIVE

        days_prior = int(rng.integers(180, 700))
        created_date = config.base_date - timedelta(days=days_prior)
        created_at = datetime.combine(created_date, time(7, 0), tzinfo=timezone.utc)

        warehouse = Warehouse(
            warehouse_id=whs_id,
            name=name,
            location=location,
            status=status,
            created_at=created_at,
            updated_at=created_at,
        )
        warehouses.append(warehouse)

    return warehouses
