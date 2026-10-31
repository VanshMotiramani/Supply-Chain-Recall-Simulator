"""
production_orders.py — Synthetic Production Order and Raw Material Consumption generator.
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, time, timedelta, timezone
import heapq
import math
from typing import Sequence
import numpy as np

from supply_chain.generators.config import MasterDataset, ProductionConfig
from supply_chain.models import IDFactory, LotConsumption, MaterialLot, ProductionOrder
from supply_chain.models.enums import BOMStatus, MaterialLotStatus, ProductionOrderStatus


class _LotInventoryTracker:
    """Internal helper tracking remaining consumable quantity for a MaterialLot."""
    __slots__ = ("lot", "remaining_qty")

    def __init__(self, lot: MaterialLot) -> None:
        self.lot = lot
        self.remaining_qty = lot.quantity


def generate_production_orders(
    master: MasterDataset,
    material_lots: Sequence[MaterialLot],
    config: ProductionConfig,
    rng: np.random.Generator,
    id_factory: IDFactory,
) -> tuple[list[ProductionOrder], list[LotConsumption]]:
    """
    Generate deterministic production orders and BOM component consumption records.

    Rules & Guarantees:
      - Unique ID generated via IDFactory: WO-2026-<6-digit>.
      - References a valid product and its approved BOM header.
      - planned_output_qty is strictly positive, sampled from [min_order_qty, max_order_qty].
      - yield_ratio is deterministic in [0.85, 0.98] (D-02).
      - actual_good_output_qty = math.floor(planned_output_qty * yield_ratio).
      - scrap_qty = planned_output_qty - actual_good_output_qty.
      - Dates are chronologically ordered, with planned/actual start subsequent to
        material lot receipt dates.
      - Every BOM component required by the order is consumed.
      - True FIFO Allocation & Deferred-Candidate Strategy:
        - Candidate lots for each material type are queued in pending_deques ordered by
          effective_start ascending (with received_date and lot_id tie-breakers).
        - As production dates advance monotonically, pending lots whose effective_start <= actual_start
          are activated into an available_heaps priority queue keyed by (received_date, lot_id).
        - Future-effective older lots are preserved in pending_deques without being discarded or
          blocking currently effective later lots.
        - Expired lots (effective_end < actual_start) are evicted upon reaching the top of available_heaps.
        - Total runtime complexity across the simulation: O(L log L + M) where L is total candidate
          lots and M is total consumption events. Eliminates unbounded repeated scanning of future candidates.
      - Multi-lot consumption occurs smoothly when a required component quantity
        exceeds a single lot's remaining balance.
      - Invariant: No raw material lot is ever overconsumed (sum(consumed) <= lot.quantity).
    """
    # 1. Index products with approved BOMs and valid BOMLines
    bom_by_product = {
        b.product_id: b for b in master.boms if b.status == BOMStatus.APPROVED
    }
    lines_by_bom: dict[str, list] = defaultdict(list)
    for bl in master.bom_lines:
        lines_by_bom[bl.bom_id].append(bl)

    eligible_products = [
        p for p in master.products
        if p.product_id in bom_by_product and lines_by_bom[bom_by_product[p.product_id].bom_id]
    ]
    if not eligible_products:
        raise ValueError(
            "Cannot generate production orders: master dataset contains no products "
            "with approved BOMs and BOM lines"
        )

    # 2. Partition candidate lots by material type in a deferred-candidate queue structure
    # Sorted by (effective_start, received_date, lot_id) ascending
    pending_by_material: dict[str, list[_LotInventoryTracker]] = defaultdict(list)
    for lot in sorted(material_lots, key=lambda l: (l.effective_start, l.received_date, l.lot_id)):
        if lot.status == MaterialLotStatus.APPROVED:
            pending_by_material[lot.material_type].append(_LotInventoryTracker(lot))

    pending_deques: dict[str, deque[_LotInventoryTracker]] = {
        mat: deque(trackers) for mat, trackers in pending_by_material.items()
    }
    # available_heaps holds active candidate tuples: (received_date, lot_id, tracker)
    available_heaps: dict[str, list[tuple]] = defaultdict(list)

    production_orders: list[ProductionOrder] = []
    lot_consumptions: list[LotConsumption] = []

    num_eligible_products = len(eligible_products)

    for i in range(config.production_order_count):
        wo_id = id_factory.next()
        product = eligible_products[i % num_eligible_products]
        bom = bom_by_product[product.product_id]
        bom_lines = lines_by_bom[bom.bom_id]

        planned_qty = int(rng.integers(config.min_order_qty, config.max_order_qty, endpoint=True))
        yield_ratio = round(float(rng.uniform(0.85, 0.98)), 4)
        actual_good = math.floor(planned_qty * yield_ratio)
        scrap = planned_qty - actual_good

        # Schedule orders smoothly throughout 2026
        day_offset = (i * 300) // max(1, config.production_order_count)
        jitter = int(rng.integers(0, 3))
        planned_start = config.base_date + timedelta(days=day_offset + jitter)
        duration = int(rng.integers(1, 5, endpoint=True))
        planned_end = planned_start + timedelta(days=duration)
        actual_start = planned_start
        actual_end = planned_end

        created_at = datetime.combine(planned_start, time(8, 0), tzinfo=timezone.utc)
        updated_at = datetime.combine(actual_end, time(17, 0), tzinfo=timezone.utc)
        consumption_time = datetime.combine(actual_start, time(9, 0), tzinfo=timezone.utc)

        po = ProductionOrder(
            wo_id=wo_id,
            product_id=product.product_id,
            bom_id=bom.bom_id,
            planned_output_qty=planned_qty,
            yield_ratio=yield_ratio,
            actual_good_output_qty=actual_good,
            scrap_qty=scrap,
            status=ProductionOrderStatus.COMPLETED,
            planned_start=planned_start,
            planned_end=planned_end,
            actual_start=actual_start,
            actual_end=actual_end,
            created_at=created_at,
            updated_at=updated_at,
        )
        production_orders.append(po)

        # 3. Consume BOM components
        for line in bom_lines:
            mat_type = line.material_type
            qty_needed = planned_qty * line.quantity_per_unit

            p_deque = pending_deques.get(mat_type)
            a_heap = available_heaps[mat_type]

            # Activate candidate lots whose effective_start <= actual_start
            if p_deque:
                while p_deque and p_deque[0].lot.effective_start <= actual_start:
                    tr = p_deque.popleft()
                    # Skip pushing lots already permanently expired prior to activation
                    if tr.lot.effective_end is not None and tr.lot.effective_end < actual_start:
                        continue
                    heapq.heappush(a_heap, (tr.lot.received_date, tr.lot.lot_id, tr))

            # Consume in strict FIFO order from available heap
            while qty_needed > 0:
                # Evict exhausted or expired candidate lots from the top of the heap
                while a_heap:
                    rec_date, lot_id, tr = a_heap[0]
                    if tr.remaining_qty <= 0:
                        heapq.heappop(a_heap)
                    elif tr.lot.effective_end is not None and tr.lot.effective_end < actual_start:
                        heapq.heappop(a_heap)  # Expired on actual_start
                    elif not tr.lot.is_eligible_for_consumption(actual_start):
                        heapq.heappop(a_heap)  # Unapproved or outside effective range
                    else:
                        break

                if not a_heap:
                    raise ValueError(
                        f"Insufficient eligible raw material inventory for material type {mat_type!r} "
                        f"on consumption date {actual_start}: needed {qty_needed} more units"
                    )

                rec_date, lot_id, tracker = a_heap[0]
                take_qty = min(qty_needed, tracker.remaining_qty)
                tracker.remaining_qty -= take_qty
                qty_needed -= take_qty

                consumption = LotConsumption(
                    wo_id=wo_id,
                    raw_lot_id=tracker.lot.lot_id,
                    consumed_qty=take_qty,
                    created_at=consumption_time,
                )
                lot_consumptions.append(consumption)

                if tracker.remaining_qty == 0:
                    heapq.heappop(a_heap)

    return production_orders, lot_consumptions
