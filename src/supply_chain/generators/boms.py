"""
boms.py — Synthetic Bill of Materials (BOM) and BOMLine generator.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Sequence
import numpy as np

from supply_chain.generators.config import MasterDataConfig
from supply_chain.generators.constants import (
    ACTIVE_INGREDIENT_MATERIAL,
    DOSAGE_FORM_PACKAGING,
    MATERIAL_TYPES,
    MATERIAL_UOMS,
)
from supply_chain.models import BOM, BOMLine, IDFactory, Product
from supply_chain.models.enums import BOMStatus


def generate_boms(
    products: Sequence[Product],
    config: MasterDataConfig,
    rng: np.random.Generator,
    id_factory: IDFactory,
) -> tuple[list[BOM], list[BOMLine]]:
    """
    Generate deterministic BOM headers and component BOMLines for each product.

    Meaningful BOM Composition Rules (Review Fix 1):
      - Every BOM must contain at least one ACTIVE_PHARMA_INGREDIENT.
      - Every BOM must contain at least one packaging component appropriate to
        the product's dosage form (from DOSAGE_FORM_PACKAGING).
      - Mandatory components (active ingredient + packaging) are selected first.
      - Any additional components up to num_lines are sampled without replacement
        from remaining catalog materials.
      - min_lines_per_bom and max_lines_per_bom are strictly enforced.
      - Raises ValueError if a valid BOM cannot be generated under the configuration.
    """
    if config.min_lines_per_bom < 2:
        raise ValueError(
            f"Cannot generate valid BOM: min_lines_per_bom must be at least 2 "
            f"(requires active ingredient and packaging), got {config.min_lines_per_bom}"
        )
    if config.max_lines_per_bom > len(MATERIAL_TYPES):
        raise ValueError(
            f"Cannot generate valid BOM: max_lines_per_bom ({config.max_lines_per_bom}) "
            f"exceeds available unique material types ({len(MATERIAL_TYPES)})"
        )

    boms: list[BOM] = []
    bom_lines: list[BOMLine] = []

    for product in products:
        bom_id = id_factory.next()

        # Effective start aligned with product creation date
        effective_start = product.created_at.date()
        created_at = datetime.combine(effective_start, time(9, 30), tzinfo=timezone.utc)

        bom = BOM(
            bom_id=bom_id,
            product_id=product.product_id,
            version=1,
            effective_start=effective_start,
            effective_end=None,
            status=BOMStatus.APPROVED,
            created_at=created_at,
            updated_at=created_at,
        )
        boms.append(bom)

        # 1. Resolve packaging options for the product's dosage form
        packaging_candidates = DOSAGE_FORM_PACKAGING.get(product.product_type)
        if not packaging_candidates:
            raise ValueError(
                f"Cannot generate BOM for product {product.product_id}: "
                f"unrecognized product type {product.product_type!r} with no packaging mapping"
            )

        # Select mandatory packaging component deterministically
        chosen_packaging = str(rng.choice(packaging_candidates))

        # Mandatory components: Active ingredient + compatible packaging
        mandatory = [ACTIVE_INGREDIENT_MATERIAL, chosen_packaging]

        # 2. Determine line count within configured range
        num_lines = int(
            rng.integers(config.min_lines_per_bom, config.max_lines_per_bom, endpoint=True)
        )

        # 3. Sample additional components without replacement
        extra_count = num_lines - len(mandatory)
        extra_pool = [m for m in MATERIAL_TYPES if m not in mandatory]

        if extra_count > len(extra_pool):
            raise ValueError(
                f"Cannot generate {num_lines} unique BOM lines: requested {extra_count} "
                f"extra components, but only {len(extra_pool)} remain available in catalog"
            )

        extra_materials = (
            rng.choice(extra_pool, size=extra_count, replace=False).tolist()
            if extra_count > 0
            else []
        )

        selected_materials = mandatory + extra_materials

        # 4. Generate BOMLine records
        for line_no, mat_type in enumerate(selected_materials, start=1):
            qty_per_unit = int(rng.integers(1, 5, endpoint=True))
            uom = MATERIAL_UOMS.get(mat_type, "UNIT")

            line = BOMLine(
                bom_id=bom_id,
                line_no=line_no,
                material_type=mat_type,
                quantity_per_unit=qty_per_unit,
                unit_of_measure=uom,
                created_at=created_at,
            )
            bom_lines.append(line)

    return boms, bom_lines
