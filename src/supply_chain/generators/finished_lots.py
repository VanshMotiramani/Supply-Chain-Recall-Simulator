"""
finished_lots.py — Synthetic Finished Goods Lot generator.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Sequence
import numpy as np

from supply_chain.generators.config import ProductionConfig
from supply_chain.models import FinishedLot, IDFactory, ProductionOrder
from supply_chain.models.enums import FinishedLotStatus


def generate_finished_lots(
    production_orders: Sequence[ProductionOrder],
    config: ProductionConfig,
    rng: np.random.Generator,
    id_factory: IDFactory,
) -> list[FinishedLot]:
    """
    Generate deterministic finished goods lots from completed production orders.

    Rules & Guarantees (Challenge Requirement 5 & Decision D-03):
      - Unique ID generated via IDFactory: FINLOT-2026-<6-digit>.
      - Full mode target: exactly 8,000 finished lots from 5,000 production orders.
      - Exactly two_lot_order_count orders produce 2 finished lots (3,000 in full mode).
      - Exactly one_lot_order_count orders produce 1 finished lot (2,000 in full mode).
      - In starter mode, this split scales proportionally via config properties.
      - Invariant: The sum of finished lot quantities for any production order
        strictly equals that order's actual_good_output_qty.
      - Each finished lot has positive integer quantity.
      - produced_date aligns with po.actual_end.
      - Status is FinishedLotStatus.AVAILABLE.
    """
    two_lot_orders_count = config.two_lot_order_count
    finished_lots: list[FinishedLot] = []

    for idx, po in enumerate(production_orders):
        actual_good = po.actual_good_output_qty
        produced_date = po.actual_end or po.planned_end
        created_at = datetime.combine(produced_date, time(17, 30), tzinfo=timezone.utc)

        if idx < two_lot_orders_count:
            # Produces exactly 2 finished lots
            lot1_qty = actual_good // 2
            lot2_qty = actual_good - lot1_qty

            lot1 = FinishedLot(
                fin_lot_id=id_factory.next(),
                wo_id=po.wo_id,
                quantity=lot1_qty,
                produced_date=produced_date,
                status=FinishedLotStatus.AVAILABLE,
                created_at=created_at,
                updated_at=created_at,
            )
            lot2 = FinishedLot(
                fin_lot_id=id_factory.next(),
                wo_id=po.wo_id,
                quantity=lot2_qty,
                produced_date=produced_date,
                status=FinishedLotStatus.AVAILABLE,
                created_at=created_at,
                updated_at=created_at,
            )
            finished_lots.extend([lot1, lot2])
        else:
            # Produces exactly 1 finished lot
            lot = FinishedLot(
                fin_lot_id=id_factory.next(),
                wo_id=po.wo_id,
                quantity=actual_good,
                produced_date=produced_date,
                status=FinishedLotStatus.AVAILABLE,
                created_at=created_at,
                updated_at=created_at,
            )
            finished_lots.append(lot)

    return finished_lots
