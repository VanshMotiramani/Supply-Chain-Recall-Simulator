"""
suppliers.py — Synthetic Supplier entity generator.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Sequence
import numpy as np
from faker import Faker

from supply_chain.generators.config import MasterDataConfig
from supply_chain.generators.constants import MATERIAL_TYPES
from supply_chain.models import IDFactory, Supplier
from supply_chain.models.enums import SupplierStatus


def generate_suppliers(
    config: MasterDataConfig,
    rng: np.random.Generator,
    fake: Faker,
    id_factory: IDFactory,
) -> list[Supplier]:
    """
    Generate deterministic Supplier master records.

    Guarantees:
      - Each supplier provides a subset of valid material types from MATERIAL_TYPES.
      - Round-robin primary material assignment ensures all material types in MATERIAL_TYPES
        are assigned.
      - When supplier_count >= len(MATERIAL_TYPES), the initial round-robin cohort
        (i < len(MATERIAL_TYPES)) is guaranteed ACTIVE, ensuring 100% active coverage
        for all catalog material types in default starter and full modes.
      - Subsequent suppliers follow a realistic distribution (96% ACTIVE, 4% SUSPENDED).
    """
    suppliers: list[Supplier] = []
    num_materials = len(MATERIAL_TYPES)

    for i in range(config.supplier_count):
        sup_id = id_factory.next()
        name = f"{fake.company()} {fake.company_suffix()}"
        location = f"{fake.city()}, {fake.country()}"

        # Ensure guaranteed round-robin primary material plus 0-2 supplementary materials
        primary_material = MATERIAL_TYPES[i % num_materials]
        extra_count = int(rng.integers(0, 3))
        extra_pool = [m for m in MATERIAL_TYPES if m != primary_material]
        extra_materials = rng.choice(extra_pool, size=extra_count, replace=False).tolist()

        selected_materials = sorted([primary_material] + extra_materials)

        # Draw random float to keep RNG stream synchronized
        rand_status = float(rng.random())

        # The initial cohort covering all catalog materials is guaranteed ACTIVE
        if i < num_materials:
            status = SupplierStatus.ACTIVE
        else:
            status = (
                SupplierStatus.ACTIVE
                if rand_status < 0.96
                else SupplierStatus.SUSPENDED
            )

        # Established 30 to 730 days before base date
        days_prior = int(rng.integers(30, 730))
        effective_start = config.base_date - timedelta(days=days_prior)
        created_at = datetime.combine(effective_start, time(8, 0), tzinfo=timezone.utc)

        supplier = Supplier(
            supplier_id=sup_id,
            supplier_name=name,
            location=location,
            material_types=selected_materials,
            status=status,
            effective_start=effective_start,
            effective_end=None,
            created_at=created_at,
            updated_at=created_at,
        )
        suppliers.append(supplier)

    return suppliers
