"""
products.py — Synthetic Product entity generator.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import numpy as np
from faker import Faker

from supply_chain.generators.config import MasterDataConfig
from supply_chain.generators.constants import PRODUCT_CATALOG
from supply_chain.models import IDFactory, Product
from supply_chain.models.enums import ProductStatus

_DOSAGE_STRENGTHS: tuple[str, ...] = ("50mg/mL", "100mg/mL", "250mg", "500mg", "10mg/mL")


def generate_products(
    config: MasterDataConfig,
    rng: np.random.Generator,
    fake: Faker,
    id_factory: IDFactory,
) -> list[Product]:
    """
    Generate deterministic Product master records across diverse pharmaceutical types.
    """
    products: list[Product] = []
    num_types = len(PRODUCT_CATALOG)

    for i in range(config.product_count):
        prod_id = id_factory.next()
        cat = PRODUCT_CATALOG[i % num_types]
        strength = _DOSAGE_STRENGTHS[i % len(_DOSAGE_STRENGTHS)]

        # Semi-synthetic therapeutic compound name
        compound_prefix = fake.word().capitalize()
        prod_name = f"{compound_prefix} {strength} {cat['prefix']}"

        # Status: 96% ACTIVE, 4% DISCONTINUED
        status = (
            ProductStatus.ACTIVE
            if rng.random() < 0.96
            else ProductStatus.DISCONTINUED
        )

        days_prior = int(rng.integers(60, 500))
        created_date = config.base_date - timedelta(days=days_prior)
        created_at = datetime.combine(created_date, time(9, 0), tzinfo=timezone.utc)

        product = Product(
            product_id=prod_id,
            product_name=prod_name,
            product_type=cat["type"],
            unit_of_measure=cat["uom"],
            status=status,
            created_at=created_at,
            updated_at=created_at,
        )
        products.append(product)

    return products
