"""
production_pipeline.py — Production data generation pipeline orchestrator.
"""

from __future__ import annotations

import numpy as np

from supply_chain.generators.config import MasterDataset, ProductionConfig, ProductionDataset
from supply_chain.generators.finished_lots import generate_finished_lots
from supply_chain.generators.material_lots import generate_material_lots
from supply_chain.generators.production_orders import generate_production_orders
from supply_chain.models import IDFactory


def generate_production_data(
    master: MasterDataset,
    config: ProductionConfig | None = None,
) -> ProductionDataset:
    """
    Generate the complete synthetic production dataset:
      1. Raw Material Lots (10,000 in full mode)
      2. Production Orders (5,000 in full mode) & BOM Lot Consumptions
      3. Finished Goods Lots (8,000 in full mode)

    Uses independent deterministic random streams (via SeedSequence) so that
    different stages maintain reproducible generation without cross-stage interference.
    """
    if config is None:
        config = ProductionConfig()

    root_ss = np.random.SeedSequence(config.seed)
    child_seeds = root_ss.spawn(3)

    # 1. Raw Material Lots
    rng_raw = np.random.default_rng(child_seeds[0])
    id_raw = IDFactory.for_material_lot()
    material_lots = generate_material_lots(master, config, rng_raw, id_raw)

    # 2. Production Orders & Lot Consumptions
    rng_po = np.random.default_rng(child_seeds[1])
    id_po = IDFactory.for_production_order()
    production_orders, lot_consumptions = generate_production_orders(
        master, material_lots, config, rng_po, id_po
    )

    # 3. Finished Goods Lots
    rng_fin = np.random.default_rng(child_seeds[2])
    id_fin = IDFactory.for_finished_lot()
    finished_lots = generate_finished_lots(
        production_orders, config, rng_fin, id_fin
    )

    return ProductionDataset(
        material_lots=material_lots,
        production_orders=production_orders,
        lot_consumptions=lot_consumptions,
        finished_lots=finished_lots,
    )
