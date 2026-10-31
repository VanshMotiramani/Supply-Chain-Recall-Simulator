"""
distribution.py — Downstream distribution generator (Shipments, Deliveries, and Inventory Movements).

Block 4 Requirements:
  - Generate clean baseline distribution connecting FinishedLot -> Warehouse -> Shipment/Delivery -> Customer.
  - Exactly 20,000 delivery records in full mode (configurable for starter mode).
  - Multi-line shipments (1 to 4 delivery lines per shipment from the same source warehouse).
  - Authoritative inventory tracking via InventoryMovement (RECEIPT for production output, SHIPMENT for dispatches).
  - Reconcile physical on-hand, available, and shipped quantities via InventoryLedger.
  - Strict chronological causality: lot.produced_date < shipment.ship_date <= delivery.delivered_date.
  - Full bidirectional traceability (Delivery -> FinishedLot -> ProductionOrder -> RawLot -> Supplier,
    and FinishedLot -> Deliveries -> Shipments -> Customers).
  - Seeded determinism using independent NumPy SeedSequence streams.
  - Clean baseline: zero anomaly injection (no EC-1, EC-2, EC-3, or EC-4 in this block).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Sequence
import numpy as np

from supply_chain.generators.config import (
    MasterDataset,
    ProductionDataset,
    DistributionConfig,
    DistributionDataset,
)
from supply_chain.models import (
    Shipment,
    Delivery,
    InventoryMovement,
    InventoryLedger,
    FinishedLot,
    Warehouse,
    Customer,
    IDFactory,
)
from supply_chain.models.enums import (
    WarehouseStatus,
    CustomerStatus,
    ShipmentStatus,
    DeliveryStatus,
    MovementType,
)


def generate_distribution_data(
    master: MasterDataset,
    production: ProductionDataset,
    config: DistributionConfig | None = None,
) -> DistributionDataset:
    """
    Generate deterministic downstream distribution data for the supply chain simulation.

    Args:
        master: Master data containing active warehouses and customers.
        production: Production dataset containing finished goods lots.
        config: Distribution configuration (defaults to DistributionConfig.for_full()).

    Returns:
        DistributionDataset containing shipments, deliveries, inventory movements, and ledger.

    Raises:
        ValueError: If prerequisites are missing or available inventory cannot satisfy demand.
    """
    if config is None:
        config = DistributionConfig.for_full()

    # 1. Validate master and production prerequisites
    if not master.warehouses:
        raise ValueError("No warehouses found in master dataset.")
    active_warehouses: list[Warehouse] = [
        w for w in master.warehouses if w.status == WarehouseStatus.ACTIVE
    ]
    if not active_warehouses:
        raise ValueError("No active warehouses available for inventory storage.")

    if not master.customers:
        raise ValueError("No customers found in master dataset.")
    active_customers: list[Customer] = [
        c for c in master.customers if c.status == CustomerStatus.ACTIVE
    ]
    if not active_customers:
        raise ValueError("No active customers available for shipments.")

    if not production.finished_lots:
        raise ValueError("No finished lots available in production dataset.")

    # Validate inventory sufficiency
    total_finished_qty = sum(lot.quantity for lot in production.finished_lots)
    min_required_qty = config.delivery_count * config.min_delivery_qty
    if total_finished_qty < min_required_qty:
        raise ValueError(
            f"Insufficient total finished goods inventory ({total_finished_qty} units) "
            f"to satisfy {config.delivery_count} deliveries with minimum quantity "
            f"{config.min_delivery_qty} (required at least {min_required_qty} units)."
        )

    # 2. Setup deterministic random streams and ID factories
    ss = np.random.SeedSequence(config.seed)
    receipt_seed, dispatch_seed = ss.spawn(2)
    receipt_rng = np.random.default_rng(receipt_seed)
    dispatch_rng = np.random.default_rng(dispatch_seed)

    inv_factory = IDFactory.for_inventory_movement(start=1)
    shp_factory = IDFactory.for_shipment(start=1)
    del_factory = IDFactory.for_delivery(start=1)

    ledger = InventoryLedger()
    all_movements: list[InventoryMovement] = []
    shipments: list[Shipment] = []
    deliveries: list[Delivery] = []

    # 3. Warehouse Receipt Placement
    # Assign each finished lot to an active warehouse and record initial RECEIPT movement
    wh_lots: dict[str, list[FinishedLot]] = {w.warehouse_id: [] for w in active_warehouses}
    num_warehouses = len(active_warehouses)

    for lot in production.finished_lots:
        wh_idx = int(receipt_rng.integers(0, num_warehouses))
        wh = active_warehouses[wh_idx]

        mvt = InventoryMovement(
            movement_id=inv_factory.next(),
            warehouse_id=wh.warehouse_id,
            fin_lot_id=lot.fin_lot_id,
            movement_type=MovementType.RECEIPT,
            quantity=lot.quantity,
            reference_id=lot.wo_id,
            movement_date=lot.produced_date,
        )
        ledger.apply(mvt, allow_negative=False)
        all_movements.append(mvt)
        wh_lots[wh.warehouse_id].append(lot)

    # Track eligible finished lots per warehouse that have available stock >= min_delivery_qty
    wh_eligible_lots: dict[str, list[FinishedLot]] = {
        w_id: [lot for lot in lots if lot.quantity >= config.min_delivery_qty]
        for w_id, lots in wh_lots.items()
    }

    # 4. Outbound Shipments & Customer Deliveries Generation
    deliveries_generated = 0
    target_deliveries = config.delivery_count
    num_customers = len(active_customers)
    wh_keys = [w.warehouse_id for w in active_warehouses]
    wh_round_robin_idx = 0

    while deliveries_generated < target_deliveries:
        remaining = target_deliveries - deliveries_generated
        # Effective minimum lines: config.min_lines_per_shipment, or remaining if smaller (final shipment)
        effective_min_lines = min(config.min_lines_per_shipment, remaining)

        # Find next warehouse with sufficient eligible stock using round-robin scan
        wh_id: str | None = None
        for _ in range(num_warehouses):
            candidate_wh_id = wh_keys[wh_round_robin_idx % num_warehouses]
            wh_round_robin_idx += 1
            # Clean any stale lots whose balance dropped below min_delivery_qty
            wh_eligible_lots[candidate_wh_id] = [
                lot for lot in wh_eligible_lots[candidate_wh_id]
                if ledger.get_balance(candidate_wh_id, lot.fin_lot_id).available_qty >= config.min_delivery_qty
            ]
            if len(wh_eligible_lots[candidate_wh_id]) >= effective_min_lines:
                wh_id = candidate_wh_id
                break

        if wh_id is None:
            raise ValueError(
                f"Insufficient available inventory across all warehouses to fulfill "
                f"target delivery count ({target_deliveries}). "
                f"Only generated {deliveries_generated} deliveries before stock exhaustion."
            )

        eligible_list = wh_eligible_lots[wh_id]

        # Determine number of lines for this shipment:
        # Must be in [effective_min_lines, min(config.max_lines_per_shipment, remaining, len(eligible_list))]
        max_possible_lines = min(config.max_lines_per_shipment, remaining, len(eligible_list))
        lines_count = int(dispatch_rng.integers(effective_min_lines, max_possible_lines + 1))

        # Sample lines_count distinct finished lots from this warehouse
        chosen_indices = dispatch_rng.choice(len(eligible_list), size=lines_count, replace=False)
        chosen_lots = [eligible_list[idx] for idx in chosen_indices]

        # Select customer
        cust_idx = int(dispatch_rng.integers(0, num_customers))
        customer = active_customers[cust_idx]

        # Calculate dispatch parameters for each line item
        line_specs: list[dict] = []
        for lot in chosen_lots:
            bal = ledger.get_balance(wh_id, lot.fin_lot_id)
            avail = bal.available_qty
            max_alloc = min(config.max_delivery_qty, avail)
            shipped_qty = int(dispatch_rng.integers(config.min_delivery_qty, max_alloc + 1))

            # Dispatch delay: 1 to 7 days after lot production date
            dispatch_delay = int(dispatch_rng.integers(1, 8))
            earliest_ship_date = lot.produced_date + timedelta(days=dispatch_delay)

            line_specs.append({
                "lot": lot,
                "shipped_qty": shipped_qty,
                "earliest_ship_date": earliest_ship_date,
            })

        # Shipment ship_date must be after all constituent lots' produced dates
        shipment_ship_date = max(spec["earliest_ship_date"] for spec in line_specs)

        # Create Shipment
        shipment_id = shp_factory.next()
        shipment = Shipment(
            shipment_id=shipment_id,
            customer_id=customer.customer_id,
            warehouse_id=wh_id,
            status=ShipmentStatus.DELIVERED,
            ship_date=shipment_ship_date,
        )
        shipments.append(shipment)

        # Create Delivery and InventoryMovement for each line
        for spec in line_specs:
            lot = spec["lot"]
            qty = spec["shipped_qty"]

            # Transit time: 1 to 3 days after ship_date
            transit_days = int(dispatch_rng.integers(1, 4))
            delivered_date = shipment_ship_date + timedelta(days=transit_days)

            delivery_id = del_factory.next()
            delivery = Delivery(
                delivery_id=delivery_id,
                shipment_id=shipment_id,
                fin_lot_id=lot.fin_lot_id,
                shipped_qty=qty,
                status=DeliveryStatus.DELIVERED,
                delivered_date=delivered_date,
            )
            deliveries.append(delivery)
            deliveries_generated += 1

            # InventoryMovement of type SHIPMENT
            mvt = InventoryMovement(
                movement_id=inv_factory.next(),
                warehouse_id=wh_id,
                fin_lot_id=lot.fin_lot_id,
                movement_type=MovementType.SHIPMENT,
                quantity=qty,
                reference_id=shipment_id,
                movement_date=shipment_ship_date,
            )
            ledger.apply(mvt, allow_negative=False)
            all_movements.append(mvt)

            # Check if lot available balance dropped below min_delivery_qty
            rem_avail = ledger.get_balance(wh_id, lot.fin_lot_id).available_qty
            if rem_avail < config.min_delivery_qty:
                if lot in wh_eligible_lots[wh_id]:
                    wh_eligible_lots[wh_id].remove(lot)

    return DistributionDataset(
        shipments=shipments,
        deliveries=deliveries,
        inventory_movements=all_movements,
        inventory_ledger=ledger,
    )
