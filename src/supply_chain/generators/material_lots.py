"""
material_lots.py — Synthetic Raw Material Lot generator.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import numpy as np

from supply_chain.generators.config import MasterDataset, ProductionConfig
from supply_chain.generators.constants import (
    ACTIVE_INGREDIENT_MATERIAL,
    MATERIAL_TYPES,
    MATERIAL_UOMS,
)
from supply_chain.models import IDFactory, MaterialLot
from supply_chain.models.enums import MaterialLotStatus, SupplierStatus


def generate_material_lots(
    master: MasterDataset,
    config: ProductionConfig,
    rng: np.random.Generator,
    id_factory: IDFactory,
) -> list[MaterialLot]:
    """
    Generate deterministic raw material lots (10,000 in full mode).

    Guarantees:
      - Unique ID generated via IDFactory: RAWLOT-<supplier_id>-2026-<6-digit>.
      - Every lot references an active supplier that genuinely supplies its material type.
      - Material types are distributed across the full 13-material catalog.
      - Quantities are strictly positive integers with correct UOMs from MATERIAL_UOMS.
      - Received and effective dates precede manufacturing dates to ensure causality.
      - Status is APPROVED (available for consumption).
    """
    active_suppliers = [s for s in master.suppliers if s.status == SupplierStatus.ACTIVE]
    if not active_suppliers:
        raise ValueError("Cannot generate material lots: master dataset contains no active suppliers")

    # Index active suppliers by material type
    suppliers_by_material: dict[str, list] = {
        m: [s for s in active_suppliers if m in s.material_types] for m in MATERIAL_TYPES
    }
    for m, sup_list in suppliers_by_material.items():
        if not sup_list:
            raise ValueError(f"No active supplier available for material type {m!r}")

    material_lots: list[MaterialLot] = []
    num_materials = len(MATERIAL_TYPES)

    for i in range(config.raw_lot_count):
        # Round-robin selection of material type ensures balanced distribution
        mat_type = MATERIAL_TYPES[i % num_materials]
        candidate_suppliers = suppliers_by_material[mat_type]

        # Deterministic supplier assignment cycling across available suppliers
        supplier = candidate_suppliers[(i // num_materials) % len(candidate_suppliers)]

        lot_id = id_factory.next(supplier_id=supplier.supplier_id)
        if mat_type == ACTIVE_INGREDIENT_MATERIAL:
            min_q = int(config.min_raw_lot_qty * 1.5)
            max_q = int(config.max_raw_lot_qty * 2.0)
            qty = int(rng.integers(min_q, max_q, endpoint=True))
        else:
            qty = int(rng.integers(config.min_raw_lot_qty, config.max_raw_lot_qty, endpoint=True))
        uom = MATERIAL_UOMS[mat_type]

        # Received prior to base date (between 15 and 90 days prior)
        days_prior = int(rng.integers(15, 90))
        received_date = config.base_date - timedelta(days=days_prior)
        effective_start = received_date

        # Shelf life / expiration: 12 to 24 months after receipt
        shelf_life_days = int(rng.integers(365, 730))
        effective_end = received_date + timedelta(days=shelf_life_days)

        created_at = datetime.combine(received_date, time(8, 0), tzinfo=timezone.utc)

        lot = MaterialLot(
            lot_id=lot_id,
            supplier_id=supplier.supplier_id,
            material_type=mat_type,
            quantity=qty,
            unit_of_measure=uom,
            received_date=received_date,
            status=MaterialLotStatus.APPROVED,
            effective_start=effective_start,
            effective_end=effective_end,
            created_at=created_at,
            updated_at=created_at,
        )
        material_lots.append(lot)

    return material_lots
