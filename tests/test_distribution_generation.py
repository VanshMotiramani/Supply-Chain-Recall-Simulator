"""
test_distribution_generation.py — Block 4 test suite for downstream distribution,
shipments, customer deliveries, inventory ledger tracking, and supply chain genealogy.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
import pytest

from supply_chain.generators import (
    MasterDataConfig,
    MasterDataset,
    ProductionConfig,
    ProductionDataset,
    DistributionConfig,
    DistributionDataset,
    generate_master_data,
    generate_production_data,
    generate_distribution_data,
)
from supply_chain.models import (
    validate_id,
    Delivery,
    Shipment,
    InventoryMovement,
    InventoryLedger,
    FinishedLot,
    Warehouse,
    Customer,
)
from supply_chain.models.enums import (
    SupplierStatus,
    WarehouseStatus,
    CustomerStatus,
    ShipmentStatus,
    DeliveryStatus,
    MovementType,
)


# ---------------------------------------------------------------------------
# Module Fixtures (Starter scale for rapid test suite execution)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def starter_master() -> MasterDataset:
    return generate_master_data(MasterDataConfig.for_starter(seed=20261022))


@pytest.fixture(scope="module")
def starter_production(starter_master: MasterDataset) -> ProductionDataset:
    return generate_production_data(starter_master, ProductionConfig.for_starter(seed=20261022))


@pytest.fixture(scope="module")
def starter_distribution(
    starter_master: MasterDataset, starter_production: ProductionDataset
) -> DistributionDataset:
    return generate_distribution_data(
        starter_master, starter_production, DistributionConfig.for_starter(seed=20261022)
    )


# ---------------------------------------------------------------------------
# 1. Configuration Validation & Fail-Fast
# ---------------------------------------------------------------------------

class TestDistributionConfig:
    def test_starter_config_defaults(self) -> None:
        cfg = DistributionConfig.for_starter()
        assert cfg.delivery_count == 200
        assert cfg.min_delivery_qty == 10
        assert cfg.max_delivery_qty == 40
        assert cfg.min_lines_per_shipment == 1
        assert cfg.max_lines_per_shipment == 4
        assert cfg.seed == 20261022
        assert cfg.base_date == date(2026, 1, 1)

    def test_full_config_defaults(self) -> None:
        cfg = DistributionConfig.for_full()
        assert cfg.delivery_count == 20_000
        assert cfg.min_delivery_qty == 10
        assert cfg.max_delivery_qty == 40
        assert cfg.min_lines_per_shipment == 1
        assert cfg.max_lines_per_shipment == 4
        assert cfg.seed == 20261022
        assert cfg.base_date == date(2026, 1, 1)

    def test_invalid_parameters_raise(self) -> None:
        with pytest.raises(ValueError, match="delivery_count must be > 0"):
            DistributionConfig(delivery_count=0)

        with pytest.raises(ValueError, match="delivery_count must be > 0"):
            DistributionConfig(delivery_count=-10)

        with pytest.raises(ValueError, match="min_delivery_qty must be > 0"):
            DistributionConfig(min_delivery_qty=0)

        with pytest.raises(ValueError, match="min_delivery_qty must be > 0"):
            DistributionConfig(min_delivery_qty=-5)

        with pytest.raises(ValueError, match="max_delivery_qty .* cannot be less than"):
            DistributionConfig(min_delivery_qty=50, max_delivery_qty=40)

        with pytest.raises(ValueError, match="min_lines_per_shipment must be > 0"):
            DistributionConfig(min_lines_per_shipment=0)

        with pytest.raises(ValueError, match="max_lines_per_shipment .* cannot be less than"):
            DistributionConfig(min_lines_per_shipment=5, max_lines_per_shipment=3)


class TestDistributionFailFast:
    def test_missing_warehouses_raises(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        empty_master = MasterDataset(
            suppliers=starter_master.suppliers,
            products=starter_master.products,
            boms=starter_master.boms,
            bom_lines=starter_master.bom_lines,
            warehouses=[],
            customers=starter_master.customers,
        )
        with pytest.raises(ValueError, match="No warehouses found"):
            generate_distribution_data(empty_master, starter_production)

    def test_no_active_warehouses_raises(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        inactive_warehouses = [
            Warehouse(
                warehouse_id=w.warehouse_id,
                name=w.name,
                location=w.location,
                status=WarehouseStatus.INACTIVE,
            )
            for w in starter_master.warehouses
        ]
        master_with_inactive = MasterDataset(
            suppliers=starter_master.suppliers,
            products=starter_master.products,
            boms=starter_master.boms,
            bom_lines=starter_master.bom_lines,
            warehouses=inactive_warehouses,
            customers=starter_master.customers,
        )
        with pytest.raises(ValueError, match="No active warehouses available"):
            generate_distribution_data(master_with_inactive, starter_production)

    def test_missing_customers_raises(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        empty_customers = MasterDataset(
            suppliers=starter_master.suppliers,
            products=starter_master.products,
            boms=starter_master.boms,
            bom_lines=starter_master.bom_lines,
            warehouses=starter_master.warehouses,
            customers=[],
        )
        with pytest.raises(ValueError, match="No customers found"):
            generate_distribution_data(empty_customers, starter_production)

    def test_no_active_customers_raises(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        inactive_customers = [
            Customer(
                customer_id=c.customer_id,
                customer_name=c.customer_name,
                location=c.location,
                contact_email=c.contact_email,
                status=CustomerStatus.INACTIVE,
            )
            for c in starter_master.customers
        ]
        master_with_inactive_cust = MasterDataset(
            suppliers=starter_master.suppliers,
            products=starter_master.products,
            boms=starter_master.boms,
            bom_lines=starter_master.bom_lines,
            warehouses=starter_master.warehouses,
            customers=inactive_customers,
        )
        with pytest.raises(ValueError, match="No active customers available"):
            generate_distribution_data(master_with_inactive_cust, starter_production)

    def test_no_finished_lots_raises(self, starter_master: MasterDataset) -> None:
        empty_prod = ProductionDataset(
            material_lots=[],
            production_orders=[],
            lot_consumptions=[],
            finished_lots=[],
        )
        with pytest.raises(ValueError, match="No finished lots available"):
            generate_distribution_data(starter_master, empty_prod)

    def test_insufficient_total_inventory_raises(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        # Requesting far more deliveries than available inventory can satisfy
        excessive_cfg = DistributionConfig(delivery_count=50_000, min_delivery_qty=100, max_delivery_qty=150)
        with pytest.raises(ValueError, match="Insufficient total finished goods inventory"):
            generate_distribution_data(starter_master, starter_production, excessive_cfg)

    def test_stock_exhaustion_during_dispatch_raises_descriptively(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        # Sizing delivery_count just above total available units to force mid-generation exhaustion
        total_qty = sum(lot.quantity for lot in starter_production.finished_lots)
        # Sizing with high min_delivery_qty such that lots deplete rapidly
        cfg = DistributionConfig(
            delivery_count=len(starter_production.finished_lots) * 10,
            min_delivery_qty=80,
            max_delivery_qty=120,
        )
        with pytest.raises(ValueError, match="(Insufficient total finished goods inventory|Insufficient available inventory across all warehouses)"):
            generate_distribution_data(starter_master, starter_production, cfg)


# ---------------------------------------------------------------------------
# 2. Delivery Quantity Semantics and Recovery Distinction
# ---------------------------------------------------------------------------

class TestDeliveryQuantitySemantics:
    def test_delivery_schema_has_no_delivered_qty_field(
        self, starter_distribution: DistributionDataset
    ) -> None:
        """
        Confirm Delivery schema has shipped_qty and status == DELIVERED, but no delivered_qty field.
        In the clean baseline, all shipped units are delivered in full.
        """
        for dlv in starter_distribution.deliveries:
            assert hasattr(dlv, "shipped_qty")
            assert hasattr(dlv, "delivered_date")
            assert hasattr(dlv, "status")
            assert not hasattr(dlv, "delivered_qty"), (
                "Schema should not define a separate delivered_qty field; "
                "DeliveryStatus.DELIVERED implies full delivery of shipped_qty."
            )
            assert dlv.status == DeliveryStatus.DELIVERED
            assert dlv.delivered_date is not None
            assert dlv.shipped_qty > 0

    def test_recovery_quantities_tracked_only_in_ledger_not_delivery_status(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        """
        Recovery quantities must be tracked strictly through InventoryMovement(MovementType.RECOVERY)
        in the InventoryLedger, never implicitly inferred from Delivery.status.
        Uses an isolated distribution instance to avoid polluting shared fixtures.
        """
        dist = generate_distribution_data(
            starter_master, starter_production, DistributionConfig.for_starter(seed=999)
        )
        ledger = dist.inventory_ledger
        dlv = dist.deliveries[0]

        # Verify initial clean baseline has 0 recovery
        bal_before = ledger.get_lot_balance(dlv.fin_lot_id)
        assert bal_before.recovered_qty == 0

        # Changing delivery status alone does not alter ledger
        dlv.status = DeliveryStatus.RECALLED
        bal_after_status_change = ledger.get_lot_balance(dlv.fin_lot_id)
        assert bal_after_status_change.recovered_qty == 0, (
            "Recovered quantity must not be inferred from DeliveryStatus!"
        )

        # Resolve parent shipment using delivery's shipment_id
        shipment_map = {s.shipment_id: s for s in dist.shipments}
        assert dlv.shipment_id in shipment_map, f"Delivery references unknown shipment {dlv.shipment_id}"
        parent_shipment = shipment_map[dlv.shipment_id]
        assert parent_shipment.shipment_id == dlv.shipment_id, (
            "Parent shipment ID must match delivery shipment_id"
        )
        wh_id = parent_shipment.warehouse_id

        bal_wh_before = ledger.get_balance(wh_id, dlv.fin_lot_id)
        assert bal_wh_before.recovered_qty == 0
        assert bal_wh_before.quarantined_qty == 0

        # Record explicit RECOVERY movement in ledger to verify authoritative accounting
        recovery_qty = min(10, dlv.shipped_qty)
        recovery_mvt = InventoryMovement(
            movement_id="INV-999999",
            warehouse_id=wh_id,
            fin_lot_id=dlv.fin_lot_id,
            movement_type=MovementType.RECOVERY,
            quantity=recovery_qty,
            reference_id="REC-TEST-000001",
            movement_date=date(2026, 6, 1),
        )
        ledger.apply(recovery_mvt, allow_negative=False)

        bal_wh_after = ledger.get_balance(wh_id, dlv.fin_lot_id)
        # Recovered and quarantined balances increase by recovered units
        assert bal_wh_after.recovered_qty == bal_wh_before.recovered_qty + recovery_qty
        assert bal_wh_after.quarantined_qty == bal_wh_before.quarantined_qty + recovery_qty
        # Physical on-hand increases as units return to the warehouse
        assert bal_wh_after.on_hand_qty == bal_wh_before.on_hand_qty + recovery_qty
        # Available is unchanged because quarantined units cannot be sold/dispatched
        assert bal_wh_after.available_qty == bal_wh_before.available_qty
        # Net shipped decreases by the recovered quantity
        assert bal_wh_after.shipped_qty == bal_wh_before.shipped_qty - recovery_qty

    def test_no_conflation_between_shipped_delivered_and_recovered(
        self, starter_distribution: DistributionDataset
    ) -> None:
        """
        Verify that shipped_qty, on_hand_qty, available_qty, and recovered_qty are maintained
        as distinct arithmetic quantities without conflation.
        """
        ledger = starter_distribution.inventory_ledger
        for dlv in starter_distribution.deliveries[:10]:
            bal = ledger.get_lot_balance(dlv.fin_lot_id)
            assert bal.shipped_qty > 0
            assert bal.available_qty >= 0
            # Clean baseline: zero recovery, zero disposal, zero quarantine
            assert bal.recovered_qty == 0
            assert bal.quarantined_qty == 0
            assert bal.disposed_qty == 0


# ---------------------------------------------------------------------------
# 3. Starter Scale Counts, IDs, and Schema Conformance
# ---------------------------------------------------------------------------

class TestStarterScaleDistribution:
    def test_exact_entity_counts(
        self, starter_production: ProductionDataset, starter_distribution: DistributionDataset
    ) -> None:
        # Deliveries must hit exact target
        assert len(starter_distribution.deliveries) == 200

        # Movement count must equal finished_lots (RECEIPT) + deliveries (SHIPMENT)
        expected_movements = len(starter_production.finished_lots) + 200
        assert len(starter_distribution.inventory_movements) == expected_movements
        assert len(starter_distribution.inventory_ledger.all_movements) == expected_movements

        # Shipments: multi-line shipments with 1-4 lines each
        assert 50 <= len(starter_distribution.shipments) <= 200

    def test_id_conformance(self, starter_distribution: DistributionDataset) -> None:
        # Shipments: SHP-2026-\d{6}
        for shp in starter_distribution.shipments:
            assert validate_id("Shipment", shp.shipment_id), f"Invalid shipment ID: {shp.shipment_id}"

        # Deliveries: DEL-2026-\d{6}
        for dlv in starter_distribution.deliveries:
            assert validate_id("Delivery", dlv.delivery_id), f"Invalid delivery ID: {dlv.delivery_id}"

        # Movements: INV-\d{6}
        for mvt in starter_distribution.inventory_movements:
            assert validate_id("InventoryMovement", mvt.movement_id), f"Invalid movement ID: {mvt.movement_id}"

    def test_unique_primary_keys(self, starter_distribution: DistributionDataset) -> None:
        shipment_ids = [s.shipment_id for s in starter_distribution.shipments]
        assert len(shipment_ids) == len(set(shipment_ids)), "Duplicate shipment IDs detected"

        delivery_ids = [d.delivery_id for d in starter_distribution.deliveries]
        assert len(delivery_ids) == len(set(delivery_ids)), "Duplicate delivery IDs detected"

        movement_ids = [m.movement_id for m in starter_distribution.inventory_movements]
        assert len(movement_ids) == len(set(movement_ids)), "Duplicate movement IDs detected"

    def test_statuses_and_quantities(self, starter_distribution: DistributionDataset) -> None:
        for shp in starter_distribution.shipments:
            assert shp.status == ShipmentStatus.DELIVERED
            assert isinstance(shp.ship_date, date)

        for dlv in starter_distribution.deliveries:
            assert dlv.status == DeliveryStatus.DELIVERED
            assert dlv.delivered_date is not None
            assert isinstance(dlv.delivered_date, date)
            assert 10 <= dlv.shipped_qty <= 40


# ---------------------------------------------------------------------------
# 4. Strengthened Referential Integrity and Shipment Line Rules
# ---------------------------------------------------------------------------

class TestReferentialIntegrity:
    def test_shipment_references(
        self, starter_master: MasterDataset, starter_distribution: DistributionDataset
    ) -> None:
        active_wh_map = {w.warehouse_id: w for w in starter_master.warehouses}
        active_cust_map = {c.customer_id: c for c in starter_master.customers}

        for shp in starter_distribution.shipments:
            assert shp.warehouse_id in active_wh_map, f"Shipment references invalid warehouse {shp.warehouse_id}"
            assert active_wh_map[shp.warehouse_id].status == WarehouseStatus.ACTIVE

            assert shp.customer_id in active_cust_map, f"Shipment references invalid customer {shp.customer_id}"
            assert active_cust_map[shp.customer_id].status == CustomerStatus.ACTIVE

    def test_delivery_references(
        self, starter_production: ProductionDataset, starter_distribution: DistributionDataset
    ) -> None:
        valid_shp_ids = {s.shipment_id for s in starter_distribution.shipments}
        valid_lot_ids = {l.fin_lot_id for l in starter_production.finished_lots}

        for dlv in starter_distribution.deliveries:
            assert dlv.shipment_id in valid_shp_ids, f"Delivery references unknown shipment {dlv.shipment_id}"
            assert dlv.fin_lot_id in valid_lot_ids, f"Delivery references unknown finished lot {dlv.fin_lot_id}"

    def test_delivery_lines_inherit_shipment_context(
        self, starter_distribution: DistributionDataset
    ) -> None:
        """
        Verify that all delivery lines in a shipment correspond to inventory movements
        originating from that shipment's warehouse_id and reference_id.
        """
        shipment_map = {s.shipment_id: s for s in starter_distribution.shipments}
        mvt_by_shp: dict[str, list[InventoryMovement]] = {}
        for m in starter_distribution.inventory_movements:
            if m.movement_type == MovementType.SHIPMENT:
                mvt_by_shp.setdefault(m.reference_id, []).append(m)

        lines_by_shp: dict[str, list[Delivery]] = {}
        for dlv in starter_distribution.deliveries:
            lines_by_shp.setdefault(dlv.shipment_id, []).append(dlv)

        for shp_id, lines in lines_by_shp.items():
            shp = shipment_map[shp_id]
            mvts = mvt_by_shp[shp_id]
            assert len(lines) == len(mvts)

            # All movements under this shipment must be from the shipment's warehouse
            for m in mvts:
                assert m.warehouse_id == shp.warehouse_id
                assert m.movement_date == shp.ship_date

    def test_one_to_one_match_between_delivery_lines_and_shipment_movements(
        self, starter_distribution: DistributionDataset
    ) -> None:
        """
        Every inventory shipment movement matches exactly one delivery line's lot,
        quantity, warehouse, and shipment reference.
        """
        shipment_map = {s.shipment_id: s for s in starter_distribution.shipments}
        delivery_map = {d.delivery_id: d for d in starter_distribution.deliveries}

        shipment_mvts = [
            m for m in starter_distribution.inventory_movements
            if m.movement_type == MovementType.SHIPMENT
        ]
        assert len(shipment_mvts) == len(starter_distribution.deliveries)

        # Index delivery lines by (shipment_id, fin_lot_id, quantity)
        delivery_keys = [
            (d.shipment_id, d.fin_lot_id, d.shipped_qty)
            for d in starter_distribution.deliveries
        ]
        movement_keys = [
            (m.reference_id, m.fin_lot_id, m.quantity)
            for m in shipment_mvts
        ]

        assert sorted(delivery_keys) == sorted(movement_keys)

        for m in shipment_mvts:
            shp = shipment_map[m.reference_id]
            assert m.warehouse_id == shp.warehouse_id
            assert m.movement_date == shp.ship_date

    def test_shipment_line_count_bounds_and_final_shipment_rule(
        self, starter_distribution: DistributionDataset
    ) -> None:
        """
        Every shipment has a line count within [min_lines_per_shipment, max_lines_per_shipment],
        except possibly the final shipment if remaining < min_lines_per_shipment.
        """
        # Group deliveries by shipment
        shp_lines: dict[str, list[Delivery]] = {}
        for dlv in starter_distribution.deliveries:
            shp_lines.setdefault(dlv.shipment_id, []).append(dlv)

        shipments = starter_distribution.shipments
        total_shipments = len(shipments)

        for idx, shp in enumerate(shipments):
            lines = shp_lines[shp.shipment_id]
            is_final = (idx == total_shipments - 1)

            if not is_final:
                # All non-final shipments must be within [1, 4]
                assert 1 <= len(lines) <= 4, (
                    f"Non-final shipment {shp.shipment_id} has {len(lines)} lines (expected 1-4)"
                )
            else:
                # Final shipment can have remaining deliveries
                assert 1 <= len(lines) <= 4

            # Distinct lots per shipment
            lot_ids = [line.fin_lot_id for line in lines]
            assert len(lot_ids) == len(set(lot_ids)), f"Duplicate finished lots on shipment {shp.shipment_id}"

    def test_final_shipment_line_count_rule_targeted(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        """
        Targeted test where delivery_count = 5, min_lines = 3, max_lines = 4.
        Shipment 1 will have 3 or 4 lines; final shipment will have remaining lines (< 3).
        """
        cfg = DistributionConfig(
            delivery_count=5,
            min_lines_per_shipment=3,
            max_lines_per_shipment=4,
            min_delivery_qty=10,
            max_delivery_qty=20,
        )
        dist = generate_distribution_data(starter_master, starter_production, cfg)
        assert len(dist.deliveries) == 5

        lines_by_shp: dict[str, list[Delivery]] = {}
        for d in dist.deliveries:
            lines_by_shp.setdefault(d.shipment_id, []).append(d)

        shipments = dist.shipments
        assert len(shipments) == 2

        # First shipment must be within [3, 4]
        assert 3 <= len(lines_by_shp[shipments[0].shipment_id]) <= 4

        # Final shipment must have exact remaining count (5 - first shipment lines), which is 1 or 2
        first_count = len(lines_by_shp[shipments[0].shipment_id])
        final_count = len(lines_by_shp[shipments[1].shipment_id])
        assert final_count == 5 - first_count
        assert final_count < 3


# ---------------------------------------------------------------------------
# 5. Inventory Conservation and Ledger Reconciliation
# ---------------------------------------------------------------------------

class TestInventoryLedgerReconciliation:
    def test_movement_types_and_counts(
        self, starter_production: ProductionDataset, starter_distribution: DistributionDataset
    ) -> None:
        mvts = starter_distribution.inventory_movements
        receipt_mvts = [m for m in mvts if m.movement_type == MovementType.RECEIPT]
        shipment_mvts = [m for m in mvts if m.movement_type == MovementType.SHIPMENT]

        assert len(receipt_mvts) == len(starter_production.finished_lots)
        assert len(shipment_mvts) == len(starter_distribution.deliveries)
        assert len(receipt_mvts) + len(shipment_mvts) == len(mvts)

    def test_lot_quantity_conservation(
        self, starter_production: ProductionDataset, starter_distribution: DistributionDataset
    ) -> None:
        """
        Quantity conservation invariant (B.2, B.3, B.5):
        For every finished lot:
          on_hand_qty + shipped_qty == lot.quantity
          available_qty == on_hand_qty (clean baseline has 0 quarantine)
          available_qty >= 0
          quarantined_qty == 0
          recovered_qty == 0
          disposed_qty == 0
        """
        ledger = starter_distribution.inventory_ledger

        # Sum shipped quantities per finished lot from delivery line items
        delivery_shipped: dict[str, int] = {}
        for dlv in starter_distribution.deliveries:
            delivery_shipped[dlv.fin_lot_id] = delivery_shipped.get(dlv.fin_lot_id, 0) + dlv.shipped_qty

        for lot in starter_production.finished_lots:
            bal = ledger.get_lot_balance(lot.fin_lot_id)

            assert bal.available_qty >= 0, f"Negative available quantity for lot {lot.fin_lot_id}"
            assert bal.on_hand_qty >= 0, f"Negative on-hand quantity for lot {lot.fin_lot_id}"
            assert bal.quarantined_qty == 0, f"Baseline should have 0 quarantine for lot {lot.fin_lot_id}"
            assert bal.recovered_qty == 0, f"Baseline should have 0 recovery for lot {lot.fin_lot_id}"
            assert bal.disposed_qty == 0, f"Baseline should have 0 disposal for lot {lot.fin_lot_id}"

            # In clean baseline, available == on_hand
            assert bal.available_qty == bal.on_hand_qty

            # Conservation equation: on_hand + shipped == produced quantity
            assert (
                bal.on_hand_qty + bal.shipped_qty == lot.quantity
            ), f"Quantity mismatch for lot {lot.fin_lot_id}: {bal.on_hand_qty} + {bal.shipped_qty} != {lot.quantity}"

            # Delivered quantity matches ledger shipped quantity
            expected_shipped = delivery_shipped.get(lot.fin_lot_id, 0)
            assert bal.shipped_qty == expected_shipped

    def test_warehouse_level_reconciliation(
        self, starter_master: MasterDataset, starter_distribution: DistributionDataset
    ) -> None:
        ledger = starter_distribution.inventory_ledger
        for wh in starter_master.warehouses:
            # Check all movements recorded for this warehouse
            wh_movements = [m for m in starter_distribution.inventory_movements if m.warehouse_id == wh.warehouse_id]
            receipt_qty = sum(m.quantity for m in wh_movements if m.movement_type == MovementType.RECEIPT)
            shipment_qty = sum(m.quantity for m in wh_movements if m.movement_type == MovementType.SHIPMENT)

            # Available across all lots in this warehouse
            lot_ids_in_wh = {m.fin_lot_id for m in wh_movements}
            total_avail = sum(ledger.get_balance(wh.warehouse_id, l_id).available_qty for l_id in lot_ids_in_wh)
            total_on_hand = sum(ledger.get_balance(wh.warehouse_id, l_id).on_hand_qty for l_id in lot_ids_in_wh)

            assert total_on_hand == receipt_qty - shipment_qty
            assert total_avail == total_on_hand
            assert total_avail >= 0


# ---------------------------------------------------------------------------
# 6. Chronological Causality
# ---------------------------------------------------------------------------

class TestChronologicalCausality:
    def test_produced_before_shipped_before_delivered(
        self, starter_production: ProductionDataset, starter_distribution: DistributionDataset
    ) -> None:
        lot_map = {l.fin_lot_id: l for l in starter_production.finished_lots}
        shipment_map = {s.shipment_id: s for s in starter_distribution.shipments}

        for dlv in starter_distribution.deliveries:
            lot = lot_map[dlv.fin_lot_id]
            shp = shipment_map[dlv.shipment_id]

            # Invariant: lot.produced_date < shipment.ship_date <= delivery.delivered_date
            assert lot.produced_date < shp.ship_date, (
                f"Lot {lot.fin_lot_id} produced {lot.produced_date} after/on ship_date {shp.ship_date}"
            )
            assert shp.ship_date <= dlv.delivered_date, (
                f"Shipment ship_date {shp.ship_date} after delivered_date {dlv.delivered_date}"
            )

    def test_movement_dates_align_with_lifecycle(
        self, starter_production: ProductionDataset, starter_distribution: DistributionDataset
    ) -> None:
        lot_map = {l.fin_lot_id: l for l in starter_production.finished_lots}
        shipment_map = {s.shipment_id: s for s in starter_distribution.shipments}

        for mvt in starter_distribution.inventory_movements:
            if mvt.movement_type == MovementType.RECEIPT:
                # Receipt date matches lot produced date
                lot = lot_map[mvt.fin_lot_id]
                assert mvt.movement_date == lot.produced_date
            elif mvt.movement_type == MovementType.SHIPMENT:
                # Shipment movement date matches shipment ship_date
                shp = shipment_map[mvt.reference_id]
                assert mvt.movement_date == shp.ship_date


# ---------------------------------------------------------------------------
# 7. Bidirectional Traceability / Genealogy
# ---------------------------------------------------------------------------

class TestBidirectionalGenealogy:
    def test_backward_trace_from_delivery_to_supplier(
        self,
        starter_master: MasterDataset,
        starter_production: ProductionDataset,
        starter_distribution: DistributionDataset,
    ) -> None:
        """
        Full backward trace:
        Delivery -> FinishedLot -> ProductionOrder -> LotConsumption -> MaterialLot -> Supplier.
        """
        lot_map = {l.fin_lot_id: l for l in starter_production.finished_lots}
        po_map = {p.wo_id: p for p in starter_production.production_orders}
        raw_lot_map = {r.lot_id: r for r in starter_production.material_lots}
        supplier_map = {s.supplier_id: s for s in starter_master.suppliers}

        consumptions_by_po: dict[str, list] = {}
        for c in starter_production.lot_consumptions:
            consumptions_by_po.setdefault(c.wo_id, []).append(c)

        # Trace every single delivery backward
        for dlv in starter_distribution.deliveries:
            fin_lot = lot_map[dlv.fin_lot_id]
            po = po_map[fin_lot.wo_id]
            consumptions = consumptions_by_po[po.wo_id]
            assert len(consumptions) >= 2, f"PO {po.wo_id} has insufficient lot consumptions"

            for cons in consumptions:
                raw_lot = raw_lot_map[cons.raw_lot_id]
                supplier = supplier_map[raw_lot.supplier_id]
                assert supplier.supplier_id.startswith("SUP-")
                assert supplier.status == SupplierStatus.ACTIVE

    def test_forward_trace_from_finished_lot_to_customer(
        self,
        starter_master: MasterDataset,
        starter_production: ProductionDataset,
        starter_distribution: DistributionDataset,
    ) -> None:
        """
        Full forward trace:
        FinishedLot -> Deliveries -> Shipments -> Customers.
        """
        shipment_map = {s.shipment_id: s for s in starter_distribution.shipments}
        customer_map = {c.customer_id: c for c in starter_master.customers}

        deliveries_by_lot: dict[str, list[Delivery]] = {}
        for dlv in starter_distribution.deliveries:
            deliveries_by_lot.setdefault(dlv.fin_lot_id, []).append(dlv)

        for lot in starter_production.finished_lots:
            dlvs = deliveries_by_lot.get(lot.fin_lot_id, [])
            for dlv in dlvs:
                shp = shipment_map[dlv.shipment_id]
                cust = customer_map[shp.customer_id]
                assert cust.customer_id.startswith("CUST-")
                assert cust.status == CustomerStatus.ACTIVE

    def test_customer_resolves_strictly_through_shipment(
        self,
        starter_master: MasterDataset,
        starter_distribution: DistributionDataset,
    ) -> None:
        """
        Verify every delivery resolves to a customer strictly through its parent shipment.
        """
        shipment_map = {s.shipment_id: s for s in starter_distribution.shipments}
        customer_ids = {c.customer_id for c in starter_master.customers}

        for dlv in starter_distribution.deliveries:
            shp = shipment_map[dlv.shipment_id]
            assert shp.customer_id in customer_ids


# ---------------------------------------------------------------------------
# 8. Complete Canonical Record Determinism
# ---------------------------------------------------------------------------

class TestDistributionDeterminism:
    def test_complete_canonical_records_match_with_identical_seed(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        """
        Compare complete logical records across two runs with identical configuration and seed.
        """
        cfg = DistributionConfig.for_starter(seed=20261022)
        dist_a = generate_distribution_data(starter_master, starter_production, cfg)
        dist_b = generate_distribution_data(starter_master, starter_production, cfg)

        # 1. Complete Shipment records
        canonical_shp_a = [
            (s.shipment_id, s.customer_id, s.warehouse_id, s.status, s.ship_date)
            for s in dist_a.shipments
        ]
        canonical_shp_b = [
            (s.shipment_id, s.customer_id, s.warehouse_id, s.status, s.ship_date)
            for s in dist_b.shipments
        ]
        assert canonical_shp_a == canonical_shp_b

        # 2. Complete Delivery records
        canonical_dlv_a = [
            (d.delivery_id, d.shipment_id, d.fin_lot_id, d.shipped_qty, d.status, d.delivered_date)
            for d in dist_a.deliveries
        ]
        canonical_dlv_b = [
            (d.delivery_id, d.shipment_id, d.fin_lot_id, d.shipped_qty, d.status, d.delivered_date)
            for d in dist_b.deliveries
        ]
        assert canonical_dlv_a == canonical_dlv_b

        # 3. Complete InventoryMovement records
        canonical_mvt_a = [
            (m.movement_id, m.warehouse_id, m.fin_lot_id, m.movement_type, m.quantity, m.reference_id, m.movement_date)
            for m in dist_a.inventory_movements
        ]
        canonical_mvt_b = [
            (m.movement_id, m.warehouse_id, m.fin_lot_id, m.movement_type, m.quantity, m.reference_id, m.movement_date)
            for m in dist_b.inventory_movements
        ]
        assert canonical_mvt_a == canonical_mvt_b

        # 4. Warehouse-specific balance breakdown across all (warehouse_id, fin_lot_id) pairs
        for w in starter_master.warehouses:
            for lot in starter_production.finished_lots:
                bal_wh_a = dist_a.inventory_ledger.get_balance(w.warehouse_id, lot.fin_lot_id)
                bal_wh_b = dist_b.inventory_ledger.get_balance(w.warehouse_id, lot.fin_lot_id)
                assert bal_wh_a == bal_wh_b

        # 5. Aggregate lot balance records across all finished lots
        for lot in starter_production.finished_lots:
            bal_a = dist_a.inventory_ledger.get_lot_balance(lot.fin_lot_id)
            bal_b = dist_b.inventory_ledger.get_lot_balance(lot.fin_lot_id)
            assert bal_a == bal_b

    def test_different_seeds_produce_divergent_results(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        dist_1 = generate_distribution_data(
            starter_master, starter_production, DistributionConfig.for_starter(seed=101)
        )
        dist_2 = generate_distribution_data(
            starter_master, starter_production, DistributionConfig.for_starter(seed=202)
        )

        divergences = sum(
            1 for s1, s2 in zip(dist_1.shipments, dist_2.shipments)
            if s1.customer_id != s2.customer_id or s1.ship_date != s2.ship_date
        )
        assert divergences > 0


# ---------------------------------------------------------------------------
# 9. Full Scale Integration & Inventory Reconciliation
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def full_datasets() -> tuple[MasterDataset, ProductionDataset, DistributionDataset]:
    master = generate_master_data(MasterDataConfig.for_full(seed=20261022))
    prod = generate_production_data(master, ProductionConfig.for_full(seed=20261022))
    dist = generate_distribution_data(master, prod, DistributionConfig.for_full(seed=20261022))
    return master, prod, dist


class TestFullScaleDistribution:
    def test_full_scale_counts(
        self, full_datasets: tuple[MasterDataset, ProductionDataset, DistributionDataset]
    ) -> None:
        master, prod, dist = full_datasets

        assert len(master.suppliers) == 500
        assert len(prod.material_lots) == 10_000
        assert len(prod.production_orders) == 5_000
        assert len(prod.finished_lots) == 8_000

        # Mandatory Block 4 target: exactly 20,000 deliveries
        assert len(dist.deliveries) == 20_000

        # Inventory movements: 8,000 receipts + 20,000 shipments = 28,000
        assert len(dist.inventory_movements) == 28_000
        assert len(dist.inventory_ledger.all_movements) == 28_000

    def test_full_scale_reconciliation(
        self, full_datasets: tuple[MasterDataset, ProductionDataset, DistributionDataset]
    ) -> None:
        _, prod, dist = full_datasets
        ledger = dist.inventory_ledger

        # Reconcile all 8,000 finished lots
        for lot in prod.finished_lots:
            bal = ledger.get_lot_balance(lot.fin_lot_id)
            assert bal.available_qty >= 0
            assert bal.on_hand_qty >= 0
            assert bal.quarantined_qty == 0
            assert bal.on_hand_qty + bal.shipped_qty == lot.quantity

    def test_full_scale_chronology(
        self, full_datasets: tuple[MasterDataset, ProductionDataset, DistributionDataset]
    ) -> None:
        _, prod, dist = full_datasets
        lot_map = {l.fin_lot_id: l for l in prod.finished_lots}
        shipment_map = {s.shipment_id: s for s in dist.shipments}

        for dlv in dist.deliveries:
            lot = lot_map[dlv.fin_lot_id]
            shp = shipment_map[dlv.shipment_id]
            assert lot.produced_date < shp.ship_date <= dlv.delivered_date
