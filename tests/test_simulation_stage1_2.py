"""
test_simulation_stage1_2.py — Test suite for Block 5 Stage 1 & Stage 2.

Verifies:
  1. Configuration defaults, presets, and validation.
  2. Ground truth registry operations and separation from discrepancy findings.
  3. Ground truth metadata immutability and defensive copying.
  4. Discrepancy finding and report typing and aggregations.
  5. Deep baseline isolation: mutating simulation state (ledger, deliveries, shipments,
     consumptions, movements) leaves baseline datasets completely unaltered across all fields.
  6. Immutability of source datasets under pure traceability calls.
  7. Pure traceability traversals:
     - Forward trace from raw material lot.
     - Forward trace from finished product lot.
     - Backward trace from delivery line item (both with production and with omitted production).
     - Backward trace from finished product lot.
     - Multi-delivery customer deduplication.
     - Safe handling of dangling / missing references (including EC-1 simulation).
     - Determinism and immutability.
"""

from collections.abc import Mapping
import copy
from datetime import date
import pytest

from supply_chain.generators.config import (
    DistributionConfig,
    MasterDataConfig,
    ProductionConfig,
)
from supply_chain.generators.distribution import generate_distribution_data
from supply_chain.generators.master import generate_master_data
from supply_chain.generators.production_pipeline import generate_production_data
from supply_chain.models import InventoryMovement
from supply_chain.models.enums import DeliveryStatus, MovementType, ShipmentStatus
from supply_chain.models.production_order import AnomalousLotConsumption
from supply_chain.simulation import (
    AnomalyRecord,
    AnomalyType,
    BackwardDeliveryTrace,
    BackwardFinishedLotTrace,
    DiscrepancyCategory,
    DiscrepancyFinding,
    DiscrepancyReport,
    ForwardFinishedLotTrace,
    ForwardMaterialLotTrace,
    GroundTruthRegistry,
    RecallMetricsResult,
    RecallSimulationConfig,
    SimulationDataset,
    create_simulation_dataset,
    trace_backward_from_delivery,
    trace_backward_from_finished_lot,
    trace_forward_from_finished_lot,
    trace_forward_from_material_lot,
)


# ---------------------------------------------------------------------------
# Shared Test Fixture (Starter Scale)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def starter_baseline():
    """Generate deterministic starter baseline dataset for Stage 1 & 2 tests."""
    master = generate_master_data(MasterDataConfig.for_starter(seed=20261022))
    production = generate_production_data(master, ProductionConfig.for_starter(seed=20261022))
    distribution = generate_distribution_data(master, production, DistributionConfig.for_starter(seed=20261022))
    return master, production, distribution


# ---------------------------------------------------------------------------
# 1. Configuration Tests
# ---------------------------------------------------------------------------

class TestRecallSimulationConfig:
    def test_default_config(self):
        cfg = RecallSimulationConfig()
        assert cfg.seed == 20261022
        assert cfg.inject_ec1 is True
        assert cfg.inject_ec2 is True
        assert cfg.inject_ec3 is True
        assert cfg.inject_ec4 is True
        assert cfg.ec2_excess_qty == 15
        assert cfg.has_anomalies is True

    def test_clean_baseline_preset(self):
        cfg = RecallSimulationConfig.clean_baseline()
        assert cfg.has_anomalies is False
        assert not cfg.inject_ec1
        assert not cfg.inject_ec2
        assert not cfg.inject_ec3
        assert not cfg.inject_ec4

    def test_invalid_parameters_raise(self):
        with pytest.raises(ValueError, match="seed must be a non-negative integer"):
            RecallSimulationConfig(seed=-1)

        with pytest.raises(ValueError, match="ec2_excess_qty must be a positive integer"):
            RecallSimulationConfig(ec2_excess_qty=0)

        with pytest.raises(ValueError, match="ec2_excess_qty must be a positive integer"):
            RecallSimulationConfig(ec2_excess_qty=-5)

        with pytest.raises(TypeError, match="inject_ec1 must be a boolean"):
            RecallSimulationConfig(inject_ec1="true")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. Ground Truth Registry & Metadata Immutability Tests
# ---------------------------------------------------------------------------

class TestGroundTruthRegistry:
    def test_register_and_query(self):
        registry = GroundTruthRegistry()
        rec1 = AnomalyRecord(
            anomaly_id="ANOM-EC1-001",
            edge_case_code="EC-1",
            anomaly_type=AnomalyType.MISSING_INPUT_LOT,
            target_entity_type="ProductionOrder",
            target_entity_id="WO-2026-000001",
            expected_outcome="Dangling foreign key reference in consumption",
        )
        rec2 = AnomalyRecord(
            anomaly_id="ANOM-EC2-001",
            edge_case_code="EC-2",
            anomaly_type=AnomalyType.QUANTITY_OVER_SHIPMENT,
            target_entity_type="Delivery",
            target_entity_id="DEL-2026-000001",
            intended_quantity=15,
            expected_outcome="Negative available inventory balance",
        )

        registry.register(rec1)
        registry.register(rec2)

        assert registry.count() == 2
        assert registry.get_by_id("ANOM-EC1-001") == rec1
        assert registry.get_by_id("NONEXISTENT") is None

        ec1_records = registry.get_by_edge_case("EC-1")
        assert len(ec1_records) == 1
        assert ec1_records[0].anomaly_id == "ANOM-EC1-001"

        ec2_records = registry.get_by_type(AnomalyType.QUANTITY_OVER_SHIPMENT)
        assert len(ec2_records) == 1
        assert ec2_records[0].intended_quantity == 15

        summary = registry.summary()
        assert summary == {"EC-1": 1, "EC-2": 1}

    def test_duplicate_registration_raises(self):
        registry = GroundTruthRegistry()
        rec = AnomalyRecord(
            anomaly_id="ANOM-DUP",
            edge_case_code="EC-1",
            anomaly_type=AnomalyType.MISSING_INPUT_LOT,
            target_entity_type="ProductionOrder",
            target_entity_id="WO-2026-000001",
        )
        registry.register(rec)
        with pytest.raises(ValueError, match="Duplicate anomaly_id registered"):
            registry.register(rec)

    def test_invalid_anomaly_record_raises(self):
        with pytest.raises(ValueError, match="anomaly_id cannot be empty"):
            AnomalyRecord(
                anomaly_id="",
                edge_case_code="EC-1",
                anomaly_type=AnomalyType.MISSING_INPUT_LOT,
                target_entity_type="Order",
                target_entity_id="WO-1",
            )

    def test_anomaly_record_metadata_immutability(self):
        """
        Fix 3: Verify AnomalyRecord.metadata is defensively copied and read-only.
        External mutation of the original dictionary cannot change the registered record,
        and direct assignment to record.metadata raises TypeError.
        """
        orig_dict = {"scenario": "batch_recall", "severity_hint": "HIGH"}
        rec = AnomalyRecord(
            anomaly_id="ANOM-IMMUTABLE-01",
            edge_case_code="EC-2",
            anomaly_type=AnomalyType.QUANTITY_OVER_SHIPMENT,
            target_entity_type="Delivery",
            target_entity_id="DEL-2026-000001",
            intended_quantity=15,
            metadata=orig_dict,
        )

        assert isinstance(rec.metadata, Mapping)
        assert rec.metadata["scenario"] == "batch_recall"
        assert rec.metadata["severity_hint"] == "HIGH"

        # 1. External dictionary mutation must NOT affect rec.metadata
        orig_dict["scenario"] = "MUTATED"
        orig_dict["new_key"] = "SHOULD_NOT_EXIST"
        assert rec.metadata["scenario"] == "batch_recall"
        assert "new_key" not in rec.metadata

        # 2. Direct modification of rec.metadata must be blocked
        with pytest.raises(TypeError):
            rec.metadata["scenario"] = "HACKED"  # type: ignore[index]

        with pytest.raises(TypeError):
            rec.metadata["injected_key"] = 123  # type: ignore[index]

        # 3. Default omitted metadata is an empty read-only mapping
        default_rec = AnomalyRecord(
            anomaly_id="ANOM-IMMUTABLE-02",
            edge_case_code="EC-1",
            anomaly_type=AnomalyType.MISSING_INPUT_LOT,
            target_entity_type="ProductionOrder",
            target_entity_id="WO-1",
        )
        assert len(default_rec.metadata) == 0
        with pytest.raises(TypeError):
            default_rec.metadata["foo"] = "bar"  # type: ignore[index]


# ---------------------------------------------------------------------------
# 3. Discrepancy Findings and Report Tests
# ---------------------------------------------------------------------------

class TestDiscrepancyFindingsAndReport:
    def test_discrepancy_report_filtering_and_summary(self):
        f1 = DiscrepancyFinding(
            finding_id="F-001",
            category=DiscrepancyCategory.BROKEN_FOREIGN_KEY,
            entity_type="LotConsumption",
            entity_id="WO-2026-000001",
            severity="CRITICAL",
            details="Raw lot RAWLOT-INVALID does not exist",
        )
        f2 = DiscrepancyFinding(
            finding_id="F-002",
            category=DiscrepancyCategory.NEGATIVE_INVENTORY,
            entity_type="WarehouseLot",
            entity_id="WH-001:FINLOT-2026-000001",
            severity="HIGH",
            discrepancy_qty=-15,
            details="Available stock is -15",
        )
        report = DiscrepancyReport(findings=(f1, f2))

        assert report.total_findings() == 2
        assert report.has_critical() is True
        assert len(report.by_category(DiscrepancyCategory.BROKEN_FOREIGN_KEY)) == 1
        assert len(report.by_severity("HIGH")) == 1
        assert report.summary() == {
            "BROKEN_FOREIGN_KEY": 1,
            "NEGATIVE_INVENTORY": 1,
        }

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError, match="Invalid severity 'EXTREME'"):
            DiscrepancyFinding(
                finding_id="F-BAD",
                category=DiscrepancyCategory.BROKEN_FOREIGN_KEY,
                entity_type="Order",
                entity_id="WO-1",
                severity="EXTREME",
            )


# ---------------------------------------------------------------------------
# 4. Critical Baseline Isolation Tests
# ---------------------------------------------------------------------------

class TestBaselineIsolation:
    def test_mutations_on_simulation_dataset_leave_baseline_100_percent_intact(self, starter_baseline):
        """
        Fix 2: Deep baseline immutability test.
        Snapshots ALL fields of baseline deliveries, shipments, consumptions, inventory movements,
        and all warehouse-lot ledger balances. Mutates the corresponding simulation collections,
        and verifies that the baseline snapshots remain completely identical.
        """
        master, prod, dist = starter_baseline

        # --- Comprehensive Baseline Snapshots ---
        # 1. All fields of all deliveries
        baseline_deliveries_snapshot = tuple(
            (
                d.delivery_id,
                d.shipment_id,
                d.fin_lot_id,
                d.shipped_qty,
                d.status,
                d.delivered_date,
                d.created_at,
                d.updated_at,
            )
            for d in dist.deliveries
        )

        # 2. All fields of all shipments
        baseline_shipments_snapshot = tuple(
            (
                s.shipment_id,
                s.customer_id,
                s.warehouse_id,
                s.status,
                s.ship_date,
                s.created_at,
                s.updated_at,
            )
            for s in dist.shipments
        )

        # 3. All fields of all production consumptions
        baseline_consumptions_snapshot = tuple(
            (c.wo_id, c.raw_lot_id, c.consumed_qty, c.created_at)
            for c in prod.lot_consumptions
        )

        # 4. All fields of all baseline inventory movements
        baseline_movements_snapshot = tuple(
            (
                m.movement_id,
                m.warehouse_id,
                m.fin_lot_id,
                m.movement_type,
                m.quantity,
                m.reference_id,
                m.movement_date,
                m.created_at,
            )
            for m in dist.inventory_movements
        )

        # 5. Every single warehouse/finished-lot balance in the ledger across all 6 quantities
        baseline_balances_snapshot: dict[tuple[str, str], tuple[int, int, int, int, int, int]] = {}
        for (w_id, l_id) in dist.inventory_ledger._records:
            bal = dist.inventory_ledger.get_balance(w_id, l_id)
            baseline_balances_snapshot[(w_id, l_id)] = (
                bal.on_hand_qty,
                bal.available_qty,
                bal.quarantined_qty,
                bal.shipped_qty,
                bal.recovered_qty,
                bal.disposed_qty,
            )

        # 6. All recorded movements in the baseline ledger
        baseline_ledger_movements_snapshot = tuple(
            (
                m.movement_id,
                m.warehouse_id,
                m.fin_lot_id,
                m.movement_type,
                m.quantity,
                m.reference_id,
                m.movement_date,
                m.created_at,
            )
            for m in dist.inventory_ledger.all_movements
        )

        # --- Create Simulation Dataset ---
        sim = create_simulation_dataset(master, prod, dist)

        # --- Perform Aggressive Mutations on Simulation State ---
        # 1. Mutate Delivery in simulation across multiple fields
        target_delivery = sim.deliveries[0]
        target_delivery.shipped_qty += 50
        target_delivery.status = DeliveryStatus.PENDING
        target_delivery.delivered_date = None

        # 2. Mutate Shipment in simulation
        target_shipment = sim.shipments[0]
        target_shipment.status = ShipmentStatus.RECALLED

        # 3. Mutate Consumption and append anomalous consumption
        sim.lot_consumptions[0].consumed_qty += 300
        fake_anomaly = AnomalousLotConsumption(
            wo_id="WO-2026-999999",
            raw_lot_id="RAWLOT-FAKE-999999",
            consumed_qty=100,
        )
        sim.lot_consumptions.append(fake_anomaly)

        # 4. Mutate inventory movements collection
        sim.inventory_movements[0].quantity += 200
        extra_movement = InventoryMovement(
            movement_id="INV-EXTRA-001",
            warehouse_id=dist.shipments[0].warehouse_id,
            fin_lot_id=dist.deliveries[0].fin_lot_id,
            movement_type=MovementType.RECEIPT,
            quantity=500,
            reference_id="WO-EXTRA",
            movement_date=dist.deliveries[0].delivered_date or date(2026, 6, 1),
        )
        sim.inventory_movements.append(extra_movement)

        # 5. Apply multiple movements to the simulation ledger
        # Over-shipment driving balance negative:
        w_id = dist.shipments[0].warehouse_id
        lot_id = dist.deliveries[0].fin_lot_id
        over_ship_mov = InventoryMovement(
            movement_id="INV-999999",
            warehouse_id=w_id,
            fin_lot_id=lot_id,
            movement_type=MovementType.SHIPMENT,
            quantity=99999,
            reference_id="SHP-2026-999999",
            movement_date=date(2026, 6, 1),
        )
        sim.inventory_ledger.apply(over_ship_mov, allow_negative=True)

        # --- Verify Baseline Is 100% Unaltered Across Every Field ---
        # 1. Deliveries: All fields match snapshot
        current_deliveries = tuple(
            (
                d.delivery_id,
                d.shipment_id,
                d.fin_lot_id,
                d.shipped_qty,
                d.status,
                d.delivered_date,
                d.created_at,
                d.updated_at,
            )
            for d in dist.deliveries
        )
        assert current_deliveries == baseline_deliveries_snapshot

        # 2. Shipments: All fields match snapshot
        current_shipments = tuple(
            (
                s.shipment_id,
                s.customer_id,
                s.warehouse_id,
                s.status,
                s.ship_date,
                s.created_at,
                s.updated_at,
            )
            for s in dist.shipments
        )
        assert current_shipments == baseline_shipments_snapshot

        # 3. Consumptions: All fields match snapshot
        current_consumptions = tuple(
            (c.wo_id, c.raw_lot_id, c.consumed_qty, c.created_at)
            for c in prod.lot_consumptions
        )
        assert current_consumptions == baseline_consumptions_snapshot

        # 4. Inventory movements: All fields match snapshot
        current_movements = tuple(
            (
                m.movement_id,
                m.warehouse_id,
                m.fin_lot_id,
                m.movement_type,
                m.quantity,
                m.reference_id,
                m.movement_date,
                m.created_at,
            )
            for m in dist.inventory_movements
        )
        assert current_movements == baseline_movements_snapshot

        # 5. Ledger balances: Every single warehouse/lot balance matches snapshot
        for (w_key, l_key), expected_balance in baseline_balances_snapshot.items():
            bal = dist.inventory_ledger.get_balance(w_key, l_key)
            actual_balance = (
                bal.on_hand_qty,
                bal.available_qty,
                bal.quarantined_qty,
                bal.shipped_qty,
                bal.recovered_qty,
                bal.disposed_qty,
            )
            assert actual_balance == expected_balance
            assert actual_balance[1] >= 0  # Available is strictly non-negative in baseline!

        # 6. Ledger recorded movements: All match snapshot
        current_ledger_movements = tuple(
            (
                m.movement_id,
                m.warehouse_id,
                m.fin_lot_id,
                m.movement_type,
                m.quantity,
                m.reference_id,
                m.movement_date,
                m.created_at,
            )
            for m in dist.inventory_ledger.all_movements
        )
        assert current_ledger_movements == baseline_ledger_movements_snapshot

        # 7. Confirm mutations were successfully applied to simulation dataset
        assert sim.deliveries[0].shipped_qty == baseline_deliveries_snapshot[0][3] + 50
        assert sim.deliveries[0].status == DeliveryStatus.PENDING
        assert sim.deliveries[0].delivered_date is None
        assert sim.shipments[0].status == ShipmentStatus.RECALLED
        assert len(sim.lot_consumptions) == len(baseline_consumptions_snapshot) + 1
        assert len(sim.inventory_movements) == len(baseline_movements_snapshot) + 1
        assert len(sim.inventory_ledger.all_movements) == len(baseline_ledger_movements_snapshot) + 1
        sim_bal = sim.inventory_ledger.get_balance(w_id, lot_id)
        assert sim_bal.available_qty < 0

    def test_traceability_calls_do_not_mutate_baseline_datasets(self, starter_baseline):
        """
        Verify that running all pure traceability functions does not alter
        any collection or entity in the source datasets.
        """
        master, prod, dist = starter_baseline

        delivery_count_pre = len(dist.deliveries)
        shipment_count_pre = len(dist.shipments)
        consumption_count_pre = len(prod.lot_consumptions)
        movement_count_pre = len(dist.inventory_movements)
        ledger_count_pre = len(dist.inventory_ledger.all_movements)

        # Run forward and backward traces multiple times
        sample_raw = prod.material_lots[0].lot_id
        sample_fin = prod.finished_lots[0].fin_lot_id
        sample_del = dist.deliveries[0].delivery_id

        _ = trace_forward_from_material_lot(sample_raw, prod, dist, master)
        _ = trace_forward_from_finished_lot(sample_fin, dist, prod, master)
        _ = trace_backward_from_delivery(sample_del, dist, prod, master)
        _ = trace_backward_from_finished_lot(sample_fin, prod, master)

        assert len(dist.deliveries) == delivery_count_pre
        assert len(dist.shipments) == shipment_count_pre
        assert len(prod.lot_consumptions) == consumption_count_pre
        assert len(dist.inventory_movements) == movement_count_pre
        assert len(dist.inventory_ledger.all_movements) == ledger_count_pre


# ---------------------------------------------------------------------------
# 5. Pure Traceability Traversal Tests
# ---------------------------------------------------------------------------

class TestTraceabilityTraversals:
    def test_forward_trace_from_material_lot(self, starter_baseline):
        master, prod, dist = starter_baseline
        sample_raw_lot = prod.material_lots[0]

        trace = trace_forward_from_material_lot(
            material_lot_id=sample_raw_lot.lot_id,
            production=prod,
            distribution=dist,
            master=master,
        )

        assert isinstance(trace, ForwardMaterialLotTrace)
        assert trace.material_lot_id == sample_raw_lot.lot_id
        assert len(trace.missing_references) == 0

        # Orders should consume this lot
        assert len(trace.production_order_ids) > 0
        for wo_id in trace.production_order_ids:
            assert any(c.wo_id == wo_id and c.raw_lot_id == sample_raw_lot.lot_id for c in prod.lot_consumptions)

        # Finished lots should be produced by those orders
        for fin_lot_id in trace.finished_lot_ids:
            fin_lot = next(f for f in prod.finished_lots if f.fin_lot_id == fin_lot_id)
            assert fin_lot.wo_id in trace.production_order_ids

        # Deliveries should carry those finished lots
        for d_id in trace.delivery_ids:
            deliv = next(d for d in dist.deliveries if d.delivery_id == d_id)
            assert deliv.fin_lot_id in trace.finished_lot_ids

        # Customers should match the parent shipments
        shipments_by_id = {s.shipment_id: s for s in dist.shipments}
        expected_customers = {
            shipments_by_id[d.shipment_id].customer_id
            for d in dist.deliveries
            if d.delivery_id in trace.delivery_ids
        }
        assert set(trace.affected_customer_ids) == expected_customers
        # Verify deduplication and sorting
        assert list(trace.affected_customer_ids) == sorted(expected_customers)

    def test_forward_trace_from_finished_lot(self, starter_baseline):
        master, prod, dist = starter_baseline
        delivered_fin_lot_id = dist.deliveries[0].fin_lot_id

        trace = trace_forward_from_finished_lot(
            fin_lot_id=delivered_fin_lot_id,
            distribution=dist,
            production=prod,
            master=master,
        )

        assert isinstance(trace, ForwardFinishedLotTrace)
        assert trace.fin_lot_id == delivered_fin_lot_id
        assert len(trace.delivery_ids) >= 1
        assert len(trace.shipment_ids) >= 1
        assert len(trace.affected_customer_ids) >= 1
        assert len(trace.missing_references) == 0

    def test_backward_trace_from_delivery(self, starter_baseline):
        master, prod, dist = starter_baseline
        sample_delivery = dist.deliveries[0]

        trace = trace_backward_from_delivery(
            delivery_id=sample_delivery.delivery_id,
            distribution=dist,
            production=prod,
            master=master,
        )

        assert isinstance(trace, BackwardDeliveryTrace)
        assert trace.delivery_id == sample_delivery.delivery_id
        assert trace.shipment_id == sample_delivery.shipment_id
        assert trace.fin_lot_id == sample_delivery.fin_lot_id
        assert trace.wo_id is not None
        assert trace.product_id is not None
        assert len(trace.raw_lot_ids) > 0
        assert len(trace.supplier_ids) > 0
        assert len(trace.missing_references) == 0

        # Verify parent shipment and customer
        parent_shipment = next(s for s in dist.shipments if s.shipment_id == sample_delivery.shipment_id)
        assert trace.customer_id == parent_shipment.customer_id

    def test_backward_trace_from_delivery_with_omitted_production(self, starter_baseline):
        """
        Fix 1: Calling trace_backward_from_delivery() with DistributionDataset
        and production=None returns a documented partial trace without throwing an AttributeError.
        """
        master, _, dist = starter_baseline
        sample_delivery = dist.deliveries[0]
        parent_shipment = next(s for s in dist.shipments if s.shipment_id == sample_delivery.shipment_id)

        trace = trace_backward_from_delivery(
            delivery_id=sample_delivery.delivery_id,
            distribution=dist,
            production=None,
            master=master,
        )

        assert isinstance(trace, BackwardDeliveryTrace)
        assert trace.delivery_id == sample_delivery.delivery_id
        # Distribution fields must be fully and accurately resolved
        assert trace.shipment_id == sample_delivery.shipment_id
        assert trace.customer_id == parent_shipment.customer_id
        assert trace.fin_lot_id == sample_delivery.fin_lot_id

        # Production genealogy fields must be None / empty
        assert trace.wo_id is None
        assert trace.product_id is None
        assert trace.raw_lot_ids == ()
        assert trace.supplier_ids == ()

        # Missing reference must clearly document that production context was omitted
        assert any("Production dataset omitted" in ref for ref in trace.missing_references)

    def test_backward_trace_from_delivery_with_single_simulation_dataset(self, starter_baseline):
        """
        Fix 1: Calling trace_backward_from_delivery() with a single SimulationDataset
        automatically resolves both distribution and production contexts without error.
        """
        master, prod, dist = starter_baseline
        sim = create_simulation_dataset(master, prod, dist)
        sample_delivery = sim.deliveries[0]

        trace = trace_backward_from_delivery(
            delivery_id=sample_delivery.delivery_id,
            distribution=sim,
        )

        assert isinstance(trace, BackwardDeliveryTrace)
        assert trace.delivery_id == sample_delivery.delivery_id
        assert trace.shipment_id == sample_delivery.shipment_id
        assert trace.fin_lot_id == sample_delivery.fin_lot_id
        assert trace.wo_id is not None
        assert trace.product_id is not None
        assert len(trace.raw_lot_ids) > 0
        assert len(trace.supplier_ids) > 0
        assert len(trace.missing_references) == 0

    def test_trace_invalid_dataset_types_raise_type_error(self, starter_baseline):
        """
        Fix 1: Passing inappropriate dataset types raises TypeError rather than AttributeError.
        """
        master, prod, dist = starter_baseline
        with pytest.raises(TypeError, match="distribution must be a DistributionDataset or SimulationDataset"):
            trace_backward_from_delivery("DEL-001", distribution="not_a_dataset")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="production must be a ProductionDataset or SimulationDataset"):
            trace_backward_from_delivery("DEL-001", distribution=dist, production=12345)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="production must be a ProductionDataset or SimulationDataset"):
            trace_forward_from_material_lot("RAW-001", production="not_prod")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="distribution must be a DistributionDataset or SimulationDataset"):
            trace_forward_from_finished_lot("FIN-001", distribution="not_dist")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="production must be a ProductionDataset or SimulationDataset"):
            trace_backward_from_finished_lot("FIN-001", production="not_prod")  # type: ignore[arg-type]

    def test_backward_trace_from_finished_lot(self, starter_baseline):
        master, prod, _ = starter_baseline
        sample_fin_lot = prod.finished_lots[0]

        trace = trace_backward_from_finished_lot(
            fin_lot_id=sample_fin_lot.fin_lot_id,
            production=prod,
            master=master,
        )

        assert isinstance(trace, BackwardFinishedLotTrace)
        assert trace.fin_lot_id == sample_fin_lot.fin_lot_id
        assert trace.wo_id == sample_fin_lot.wo_id
        assert trace.product_id is not None
        assert len(trace.raw_lot_ids) > 0
        assert len(trace.supplier_ids) > 0
        assert len(trace.missing_references) == 0

    def test_trace_with_simulation_dataset_polymorphism(self, starter_baseline):
        master, prod, dist = starter_baseline
        sim = create_simulation_dataset(master, prod, dist)

        sample_raw_lot = prod.material_lots[0]
        trace = trace_forward_from_material_lot(
            material_lot_id=sample_raw_lot.lot_id,
            production=sim,
        )
        assert isinstance(trace, ForwardMaterialLotTrace)
        assert trace.material_lot_id == sample_raw_lot.lot_id

    def test_missing_reference_handling_does_not_crash(self, starter_baseline):
        """
        Verify that nonexistent entities produce clean diagnostic messages
        in missing_references rather than throwing uncaught exceptions.
        """
        master, prod, dist = starter_baseline

        # 1. Nonexistent raw lot
        fwd_raw = trace_forward_from_material_lot(
            material_lot_id="RAWLOT-DOES-NOT-EXIST",
            production=prod,
            distribution=dist,
        )
        assert "MaterialLot not found: RAWLOT-DOES-NOT-EXIST" in fwd_raw.missing_references
        assert fwd_raw.production_order_ids == ()
        assert fwd_raw.affected_customer_ids == ()

        # 2. Nonexistent finished lot
        fwd_fin = trace_forward_from_finished_lot(
            fin_lot_id="FINLOT-DOES-NOT-EXIST",
            distribution=dist,
            production=prod,
        )
        assert "FinishedLot not found: FINLOT-DOES-NOT-EXIST" in fwd_fin.missing_references
        assert fwd_fin.delivery_ids == ()

        # 3. Nonexistent delivery
        bwd_del = trace_backward_from_delivery(
            delivery_id="DEL-DOES-NOT-EXIST",
            distribution=dist,
            production=prod,
        )
        assert "Delivery not found: DEL-DOES-NOT-EXIST" in bwd_del.missing_references
        assert bwd_del.shipment_id is None

        # 4. Nonexistent finished lot backward
        bwd_fin = trace_backward_from_finished_lot(
            fin_lot_id="FINLOT-DOES-NOT-EXIST",
            production=prod,
        )
        assert "FinishedLot not found: FINLOT-DOES-NOT-EXIST" in bwd_fin.missing_references
        assert bwd_fin.wo_id is None

    def test_ec1_anomalous_lot_consumption_handling(self, starter_baseline):
        """
        EC-1 Test: A consumption record references a raw_lot_id that does not exist.
        The backward trace should capture the missing raw lot ID in raw_lot_ids,
        and report it in missing_references without throwing KeyError/AttributeError.
        """
        master, prod, dist = starter_baseline
        sim = create_simulation_dataset(master, prod, dist)

        # Pick a target finished lot and its work order
        target_delivery = sim.deliveries[0]
        target_fin_lot_id = target_delivery.fin_lot_id
        target_fin_lot = next(f for f in prod.finished_lots if f.fin_lot_id == target_fin_lot_id)
        target_wo_id = target_fin_lot.wo_id

        # Inject EC-1 anomalous consumption into simulation
        ec1_raw_lot_id = "RAWLOT-SUP-999-2026-999999"
        anomalous_consumption = AnomalousLotConsumption(
            wo_id=target_wo_id,
            raw_lot_id=ec1_raw_lot_id,
            consumed_qty=50,
        )
        sim.lot_consumptions.append(anomalous_consumption)

        # Trace backward from delivery
        trace = trace_backward_from_delivery(
            delivery_id=target_delivery.delivery_id,
            distribution=sim,
            production=sim,
        )

        assert ec1_raw_lot_id in trace.raw_lot_ids
        assert f"MaterialLot not found: {ec1_raw_lot_id}" in trace.missing_references

        # Trace backward from finished lot
        fin_trace = trace_backward_from_finished_lot(
            fin_lot_id=target_fin_lot_id,
            production=sim,
        )
        assert ec1_raw_lot_id in fin_trace.raw_lot_ids
        assert f"MaterialLot not found: {ec1_raw_lot_id}" in fin_trace.missing_references

    def test_genealogy_determinism(self, starter_baseline):
        """Verify that identical runs produce identical, byte-for-byte consistent traces."""
        master, prod, dist = starter_baseline
        raw_lot_id = prod.material_lots[0].lot_id

        trace1 = trace_forward_from_material_lot(raw_lot_id, prod, dist, master)
        trace2 = trace_forward_from_material_lot(raw_lot_id, prod, dist, master)

        assert trace1 == trace2
        assert trace1.production_order_ids == trace2.production_order_ids
        assert trace1.affected_customer_ids == trace2.affected_customer_ids
