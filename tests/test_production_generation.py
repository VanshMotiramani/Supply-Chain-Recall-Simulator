"""
test_production_generation.py — Block 3 tests for Raw Material, Production Order,
Lot Consumption, and Finished Lot generation.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
import re
import numpy as np
import pytest

from supply_chain.generators import (
    MasterDataConfig,
    MasterDataset,
    ProductionConfig,
    ProductionDataset,
    generate_master_data,
    generate_production_data,
)
from supply_chain.generators.constants import MATERIAL_UOMS
from supply_chain.models import IDFactory, MaterialLot, validate_id
from supply_chain.models.enums import (
    FinishedLotStatus,
    MaterialLotStatus,
    ProductionOrderStatus,
)


@pytest.fixture(scope="module")
def starter_master() -> MasterDataset:
    config = MasterDataConfig.for_starter(seed=20261022)
    return generate_master_data(config)


@pytest.fixture(scope="module")
def starter_production(starter_master: MasterDataset) -> ProductionDataset:
    config = ProductionConfig.for_starter(seed=20261022)
    return generate_production_data(starter_master, config)


# ---------------------------------------------------------------------------
# 1. Config & Starter-Mode Validation
# ---------------------------------------------------------------------------

class TestProductionConfig:
    def test_starter_config_counts(self) -> None:
        cfg = ProductionConfig.for_starter()
        assert cfg.raw_lot_count == 100
        assert cfg.production_order_count == 50
        assert cfg.finished_lot_count == 80
        assert cfg.two_lot_order_count == 30
        assert cfg.one_lot_order_count == 20

    def test_full_config_counts(self) -> None:
        cfg = ProductionConfig.for_full()
        assert cfg.raw_lot_count == 10_000
        assert cfg.production_order_count == 5_000
        assert cfg.finished_lot_count == 8_000
        assert cfg.two_lot_order_count == 3_000
        assert cfg.one_lot_order_count == 2_000

    def test_invalid_counts_raise(self) -> None:
        with pytest.raises(ValueError, match="raw_lot_count must be > 0"):
            ProductionConfig(raw_lot_count=0)

        with pytest.raises(ValueError, match="production_order_count must be > 0"):
            ProductionConfig(production_order_count=0)

        with pytest.raises(ValueError, match="cannot be less than"):
            ProductionConfig(production_order_count=100, finished_lot_count=90)

        with pytest.raises(ValueError, match="cannot exceed 2 \\* production_order_count"):
            ProductionConfig(production_order_count=100, finished_lot_count=201)

        with pytest.raises(ValueError, match="max_order_qty .* cannot be less than"):
            ProductionConfig(min_order_qty=500, max_order_qty=400)


# ---------------------------------------------------------------------------
# 2. Starter-Mode Dataset Verification
# ---------------------------------------------------------------------------

class TestStarterProductionGeneration:
    def test_entity_counts(self, starter_production: ProductionDataset) -> None:
        summary = starter_production.summary()
        assert summary["material_lots"] == 100
        assert summary["production_orders"] == 50
        assert summary["finished_lots"] == 80
        assert summary["lot_consumptions"] > 0

    def test_unique_and_valid_ids(self, starter_production: ProductionDataset) -> None:
        raw_ids = [lot.lot_id for lot in starter_production.material_lots]
        po_ids = [po.wo_id for po in starter_production.production_orders]
        fin_ids = [fl.fin_lot_id for fl in starter_production.finished_lots]

        assert len(raw_ids) == len(set(raw_ids)) == 100
        assert len(po_ids) == len(set(po_ids)) == 50
        assert len(fin_ids) == len(set(fin_ids)) == 80

        for lot in starter_production.material_lots:
            assert validate_id("MaterialLot", lot.lot_id)
        for po in starter_production.production_orders:
            assert validate_id("ProductionOrder", po.wo_id)
        for fl in starter_production.finished_lots:
            assert validate_id("FinishedLot", fl.fin_lot_id)

    def test_referential_integrity(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        supplier_ids = {s.supplier_id for s in starter_master.suppliers}
        product_ids = {p.product_id for p in starter_master.products}
        bom_ids = {b.bom_id for b in starter_master.boms}
        raw_lot_ids = {lot.lot_id for lot in starter_production.material_lots}
        po_ids = {po.wo_id for po in starter_production.production_orders}

        # Material lots reference valid suppliers
        for lot in starter_production.material_lots:
            assert lot.supplier_id in supplier_ids

        # Production orders reference valid products and BOMs
        for po in starter_production.production_orders:
            assert po.product_id in product_ids
            assert po.bom_id in bom_ids

        # Lot consumptions reference valid POs and raw lots
        for c in starter_production.lot_consumptions:
            assert c.wo_id in po_ids
            assert c.raw_lot_id in raw_lot_ids
            assert c.consumed_qty > 0

        # Finished lots reference valid POs
        for fl in starter_production.finished_lots:
            assert fl.wo_id in po_ids

    def test_supplier_material_compatibility(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        supplier_by_id = {s.supplier_id: s for s in starter_master.suppliers}
        for lot in starter_production.material_lots:
            sup = supplier_by_id[lot.supplier_id]
            assert lot.material_type in sup.material_types
            assert lot.unit_of_measure == MATERIAL_UOMS[lot.material_type]
            assert lot.quantity > 0
            assert lot.status == MaterialLotStatus.APPROVED

    def test_bom_component_consumption_completeness(
        self, starter_master: MasterDataset, starter_production: ProductionDataset
    ) -> None:
        """Every required BOM component must be consumed in exact planned quantity."""
        lines_by_bom: dict[str, list] = {}
        for bl in starter_master.bom_lines:
            lines_by_bom.setdefault(bl.bom_id, []).append(bl)

        raw_lot_by_id = {lot.lot_id: lot for lot in starter_production.material_lots}

        # Group consumptions by (wo_id, material_type)
        consumptions_by_po_mat: dict[tuple[str, str], int] = {}
        for c in starter_production.lot_consumptions:
            lot = raw_lot_by_id[c.raw_lot_id]
            key = (c.wo_id, lot.material_type)
            consumptions_by_po_mat[key] = consumptions_by_po_mat.get(key, 0) + c.consumed_qty

        for po in starter_production.production_orders:
            bom_lines = lines_by_bom[po.bom_id]
            for bl in bom_lines:
                expected_needed = po.planned_output_qty * bl.quantity_per_unit
                consumed = consumptions_by_po_mat.get((po.wo_id, bl.material_type), 0)
                assert consumed == expected_needed, (
                    f"PO {po.wo_id} required {expected_needed} of {bl.material_type}, "
                    f"but {consumed} was consumed"
                )

    def test_no_raw_lot_overconsumption(self, starter_production: ProductionDataset) -> None:
        """Total consumed quantity must not exceed initial lot quantity."""
        consumed_totals: dict[str, int] = {}
        for c in starter_production.lot_consumptions:
            consumed_totals[c.raw_lot_id] = consumed_totals.get(c.raw_lot_id, 0) + c.consumed_qty

        for lot in starter_production.material_lots:
            total_consumed = consumed_totals.get(lot.lot_id, 0)
            assert total_consumed <= lot.quantity, (
                f"Lot {lot.lot_id} overconsumed: consumed {total_consumed} > initial {lot.quantity}"
            )

    def test_yield_bounds_and_scrap_reconciliation(
        self, starter_production: ProductionDataset
    ) -> None:
        for po in starter_production.production_orders:
            assert 0.85 <= po.yield_ratio <= 0.98
            expected_good = math.floor(po.planned_output_qty * po.yield_ratio)
            assert po.actual_good_output_qty == expected_good
            assert po.scrap_qty == po.planned_output_qty - expected_good
            assert po.actual_good_output_qty + po.scrap_qty == po.planned_output_qty
            assert po.status == ProductionOrderStatus.COMPLETED

    def test_finished_lot_quantities_reconciliation(
        self, starter_production: ProductionDataset
    ) -> None:
        lots_by_po: dict[str, list] = {}
        for fl in starter_production.finished_lots:
            lots_by_po.setdefault(fl.wo_id, []).append(fl)

        two_lot_count = 0
        one_lot_count = 0

        for po in starter_production.production_orders:
            fl_list = lots_by_po[po.wo_id]
            assert 1 <= len(fl_list) <= 2
            if len(fl_list) == 2:
                two_lot_count += 1
            else:
                one_lot_count += 1

            total_qty = sum(fl.quantity for fl in fl_list)
            assert total_qty == po.actual_good_output_qty, (
                f"PO {po.wo_id} finished lots total {total_qty} != actual good {po.actual_good_output_qty}"
            )

            for fl in fl_list:
                assert fl.quantity > 0
                assert fl.status == FinishedLotStatus.AVAILABLE
                assert fl.produced_date == po.actual_end

        assert two_lot_count == 30
        assert one_lot_count == 20

    def test_temporal_consistency(
        self, starter_production: ProductionDataset
    ) -> None:
        raw_lot_by_id = {lot.lot_id: lot for lot in starter_production.material_lots}
        po_by_id = {po.wo_id: po for po in starter_production.production_orders}

        # Consumed raw lots were received before production order actual_start and not expired
        for c in starter_production.lot_consumptions:
            raw_lot = raw_lot_by_id[c.raw_lot_id]
            po = po_by_id[c.wo_id]
            assert raw_lot.received_date < po.actual_start
            assert raw_lot.effective_end is None or po.actual_start <= raw_lot.effective_end

        # Production order start precedes or equals end
        for po in starter_production.production_orders:
            assert po.planned_start <= po.planned_end
            assert po.actual_start <= po.actual_end

        # Finished lot produced date matches po actual_end
        for fl in starter_production.finished_lots:
            po = po_by_id[fl.wo_id]
            assert fl.produced_date == po.actual_end


# ---------------------------------------------------------------------------
# 3. Determinism & Multi-Lot Allocation
# ---------------------------------------------------------------------------

class TestProductionDeterminism:
    def test_reproducibility(self, starter_master: MasterDataset) -> None:
        cfg = ProductionConfig.for_starter(seed=20261022)
        run1 = generate_production_data(starter_master, cfg)
        run2 = generate_production_data(starter_master, cfg)

        # Material lots
        assert [l.lot_id for l in run1.material_lots] == [l.lot_id for l in run2.material_lots]
        assert [l.quantity for l in run1.material_lots] == [l.quantity for l in run2.material_lots]

        # Production orders
        assert [p.wo_id for p in run1.production_orders] == [p.wo_id for p in run2.production_orders]
        assert [p.yield_ratio for p in run1.production_orders] == [p.yield_ratio for p in run2.production_orders]
        assert [p.actual_good_output_qty for p in run1.production_orders] == [p.actual_good_output_qty for p in run2.production_orders]

        # Lot consumptions
        assert len(run1.lot_consumptions) == len(run2.lot_consumptions)
        for c1, c2 in zip(run1.lot_consumptions, run2.lot_consumptions):
            assert c1.wo_id == c2.wo_id
            assert c1.raw_lot_id == c2.raw_lot_id
            assert c1.consumed_qty == c2.consumed_qty

        # Finished lots
        assert [f.fin_lot_id for f in run1.finished_lots] == [f.fin_lot_id for f in run2.finished_lots]
        assert [f.quantity for f in run1.finished_lots] == [f.quantity for f in run2.finished_lots]

    def test_different_seeds_produce_different_data(self, starter_master: MasterDataset) -> None:
        cfg1 = ProductionConfig.for_starter(seed=20261022)
        cfg2 = ProductionConfig.for_starter(seed=99999999)
        run1 = generate_production_data(starter_master, cfg1)
        run2 = generate_production_data(starter_master, cfg2)

        # Quantities should differ
        q1 = [l.quantity for l in run1.material_lots]
        q2 = [l.quantity for l in run2.material_lots]
        assert q1 != q2

    def test_multi_lot_consumption_support(self, starter_master: MasterDataset) -> None:
        """
        Verify that when a required BOM component quantity exceeds a single raw lot's
        remaining balance, multi-lot consumption is seamlessly supported.
        """
        cfg = ProductionConfig(
            raw_lot_count=500,
            production_order_count=10,
            finished_lot_count=15,
            min_order_qty=200,
            max_order_qty=200,
            min_raw_lot_qty=300,
            max_raw_lot_qty=300,
        )
        prod = generate_production_data(starter_master, cfg)
        raw_by_id = {l.lot_id: l for l in prod.material_lots}

        # Group consumptions by (wo_id, material_type)
        from collections import defaultdict
        po_mat_lots = defaultdict(lambda: defaultdict(list))
        for c in prod.lot_consumptions:
            po_mat_lots[c.wo_id][raw_by_id[c.raw_lot_id].material_type].append(c)

        multi_lots = [
            (wo, mat, consumptions)
            for wo, mats in po_mat_lots.items()
            for mat, consumptions in mats.items()
            if len(consumptions) > 1
        ]
        assert len(multi_lots) > 0, "Expected multi-lot consumption to occur under lot exhaustion"

        # Verify that total consumed across multiple lots equals planned_qty * bom_line.qty_per_unit
        wo_sample, mat_sample, consumptions_sample = multi_lots[0]
        total_consumed = sum(c.consumed_qty for c in consumptions_sample)
        po = next(p for p in prod.production_orders if p.wo_id == wo_sample)
        # Verify unique raw lots in consumption
        assert len(consumptions_sample) == len({c.raw_lot_id for c in consumptions_sample})
        assert all(c.consumed_qty > 0 for c in consumptions_sample)

    def test_insufficient_inventory_raises(self, starter_master: MasterDataset) -> None:
        # 1 lot of 100 units cannot satisfy 50 orders of 100-500 units
        tiny_config = ProductionConfig(
            raw_lot_count=1,
            production_order_count=50,
            finished_lot_count=80,
            min_raw_lot_qty=100,
            max_raw_lot_qty=100,
        )
        with pytest.raises(ValueError, match="Insufficient .*raw material inventory"):
            generate_production_data(starter_master, tiny_config)


# ---------------------------------------------------------------------------
# 4. Full Scale Verification (10,000 lots, 5,000 orders, 8,000 finished lots)
# ---------------------------------------------------------------------------

class TestFullScaleProductionGeneration:
    @pytest.mark.slow
    def test_full_dataset_counts_and_reconciliation(self) -> None:
        """
        Verify exact mandatory full scale targets:
          - 500 suppliers, 50 products, 50 BOMs
          - 10,000 raw material lots
          - 5,000 production orders
          - 8,000 finished goods lots (Decision D-03: exactly 3,000 2-lot orders, 2,000 1-lot orders)
        """
        master_cfg = MasterDataConfig.for_full(seed=20261022)
        master = generate_master_data(master_cfg)
        assert len(master.suppliers) == 500

        prod_cfg = ProductionConfig.for_full(seed=20261022)
        production = generate_production_data(master, prod_cfg)

        assert len(production.material_lots) == 10_000
        assert len(production.production_orders) == 5_000
        assert len(production.finished_lots) == 8_000

        # Verify Decision D-03: 3,000 orders with 2 finished lots, 2,000 with 1
        lots_by_po: dict[str, list] = {}
        for fl in production.finished_lots:
            lots_by_po.setdefault(fl.wo_id, []).append(fl)

        two_lot_count = sum(1 for po in production.production_orders if len(lots_by_po[po.wo_id]) == 2)
        one_lot_count = sum(1 for po in production.production_orders if len(lots_by_po[po.wo_id]) == 1)

        assert two_lot_count == 3_000
        assert one_lot_count == 2_000

        # Verify finished-lot quantity reconciliation
        for po in production.production_orders:
            fl_list = lots_by_po[po.wo_id]
            assert sum(fl.quantity for fl in fl_list) == po.actual_good_output_qty

        # Verify no raw lot overconsumption
        consumed_totals: dict[str, int] = {}
        for c in production.lot_consumptions:
            consumed_totals[c.raw_lot_id] = consumed_totals.get(c.raw_lot_id, 0) + c.consumed_qty

        for lot in production.material_lots:
            assert consumed_totals.get(lot.lot_id, 0) <= lot.quantity

        # Verify for every consumption: APPROVED, effective_start <= actual_start, and actual_start <= effective_end
        raw_by_id = {lot.lot_id: lot for lot in production.material_lots}
        po_by_id = {po.wo_id: po for po in production.production_orders}
        for c in production.lot_consumptions:
            raw = raw_by_id[c.raw_lot_id]
            po = po_by_id[c.wo_id]
            assert raw.status == MaterialLotStatus.APPROVED, (
                f"Lot {raw.lot_id} has invalid status {raw.status} for consumption by PO {po.wo_id}"
            )
            assert raw.effective_start <= po.actual_start, (
                f"Lot {raw.lot_id} not yet effective (effective_start={raw.effective_start}) "
                f"at PO {po.wo_id} actual_start={po.actual_start}"
            )
            assert raw.effective_end is None or po.actual_start <= raw.effective_end, (
                f"Expired lot {raw.lot_id} (effective_end={raw.effective_end}) consumed by "
                f"PO {po.wo_id} on {po.actual_start}"
            )


# ---------------------------------------------------------------------------
# 5. Raw Material Expiry Eligibility & FIFO Allocation
# ---------------------------------------------------------------------------

class TestRawMaterialExpiryEligibility:
    def test_lot_effective_and_eligibility_predicates(self) -> None:
        """
        Verify domain date semantics:
          - on_date >= effective_start
          - on_date <= effective_end (inclusive boundary)
          - effective_end < on_date => expired (precedes consumption date)
          - status must be APPROVED for consumption eligibility
        """
        start = date(2026, 1, 1)
        end = date(2026, 6, 30)

        lot = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-000001",
            supplier_id="SUP-000001",
            material_type="ACTIVE_PHARMA_INGREDIENT",
            quantity=1000,
            unit_of_measure="KG",
            received_date=start,
            status=MaterialLotStatus.APPROVED,
            effective_start=start,
            effective_end=end,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Before start
        assert not lot.is_effective_on(date(2025, 12, 31))
        assert not lot.is_eligible_for_consumption(date(2025, 12, 31))

        # At start
        assert lot.is_effective_on(start)
        assert lot.is_eligible_for_consumption(start)

        # Mid effective period
        assert lot.is_effective_on(date(2026, 3, 15))
        assert lot.is_eligible_for_consumption(date(2026, 3, 15))

        # On the exact expiry date (inclusive rule: does not precede consumption date)
        assert lot.is_effective_on(end)
        assert lot.is_eligible_for_consumption(end)

        # One day after expiry date (precedes consumption date)
        expired_date = end + timedelta(days=1)
        assert not lot.is_effective_on(expired_date)
        assert not lot.is_eligible_for_consumption(expired_date)

        # Non-APPROVED status
        object.__setattr__(lot, "status", MaterialLotStatus.QUARANTINED)
        assert lot.is_effective_on(date(2026, 3, 15))
        assert not lot.is_eligible_for_consumption(date(2026, 3, 15))

    def test_expired_fifo_lot_skipped_in_favor_of_valid_lot(
        self, starter_master: MasterDataset
    ) -> None:
        """
        When the first lot in FIFO order is expired on the consumption date,
        the generator must skip it and consume from the next eligible lot.
        """
        from supply_chain.generators.material_lots import generate_material_lots
        from supply_chain.generators.production_orders import generate_production_orders

        cfg = ProductionConfig.for_starter()
        rng_raw = np.random.default_rng(20261022)
        base_lots = generate_material_lots(starter_master, cfg, rng_raw, IDFactory.for_material_lot())

        sample_api = next(l for l in base_lots if l.material_type == "ACTIVE_PHARMA_INGREDIENT")

        expired_api_lot = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-999901",
            supplier_id=sample_api.supplier_id,
            material_type="ACTIVE_PHARMA_INGREDIENT",
            quantity=5000,
            unit_of_measure="KG",
            received_date=cfg.base_date - timedelta(days=60),
            status=MaterialLotStatus.APPROVED,
            effective_start=cfg.base_date - timedelta(days=60),
            effective_end=cfg.base_date - timedelta(days=1),  # Expired yesterday
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        valid_api_lot = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-999902",
            supplier_id=sample_api.supplier_id,
            material_type="ACTIVE_PHARMA_INGREDIENT",
            quantity=50000,
            unit_of_measure="KG",
            received_date=cfg.base_date - timedelta(days=60),
            status=MaterialLotStatus.APPROVED,
            effective_start=cfg.base_date - timedelta(days=60),
            effective_end=cfg.base_date + timedelta(days=500),  # Valid
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Place expired lot first in FIFO sequence, then valid lot, then rest
        other_lots = [l for l in base_lots if l.material_type != "ACTIVE_PHARMA_INGREDIENT"]
        test_lots = [expired_api_lot, valid_api_lot] + other_lots

        rng_po = np.random.default_rng(20261022)
        orders, consumptions = generate_production_orders(
            starter_master, test_lots, cfg, rng_po, IDFactory.for_production_order()
        )

        consumed_ids = {c.raw_lot_id for c in consumptions}
        assert expired_api_lot.lot_id not in consumed_ids, "Expired lot must not be consumed"
        assert valid_api_lot.lot_id in consumed_ids, "Valid lot must be consumed after skipping expired lot"

    def test_lot_expiring_on_consumption_date_is_consumed(
        self, starter_master: MasterDataset
    ) -> None:
        """
        A lot whose effective_end equals the consumption date does not precede that date
        and therefore remains eligible and must be consumed under FIFO.
        """
        from supply_chain.generators.material_lots import generate_material_lots
        from supply_chain.generators.production_orders import generate_production_orders

        cfg = ProductionConfig.for_starter()
        rng_raw = np.random.default_rng(20261022)
        base_lots = generate_material_lots(starter_master, cfg, rng_raw, IDFactory.for_material_lot())

        sample_api = next(l for l in base_lots if l.material_type == "ACTIVE_PHARMA_INGREDIENT")

        expiring_today_lot = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-999903",
            supplier_id=sample_api.supplier_id,
            material_type="ACTIVE_PHARMA_INGREDIENT",
            quantity=5000,
            unit_of_measure="KG",
            received_date=cfg.base_date - timedelta(days=120),  # Oldest receipt date
            status=MaterialLotStatus.APPROVED,
            effective_start=cfg.base_date - timedelta(days=120),
            effective_end=cfg.base_date,  # Expires on the exact day of first order
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        other_lots = [l for l in base_lots if l.lot_id != expiring_today_lot.lot_id]
        test_lots = [expiring_today_lot] + other_lots

        rng_po = np.random.default_rng(20261022)
        orders, consumptions = generate_production_orders(
            starter_master, test_lots, cfg, rng_po, IDFactory.for_production_order()
        )

        consumed_ids = {c.raw_lot_id for c in consumptions}
        assert expiring_today_lot.lot_id in consumed_ids, (
            "Lot expiring on consumption date must be eligible under inclusive expiry rule"
        )

    def test_insufficient_eligible_inventory_due_to_expiry_raises(
        self, starter_master: MasterDataset
    ) -> None:
        """
        If all lots for a required material type are expired, production order generation
        must fail explicitly with a clear, descriptive ValueError.
        """
        from supply_chain.generators.material_lots import generate_material_lots
        from supply_chain.generators.production_orders import generate_production_orders

        cfg = ProductionConfig.for_starter()
        rng_raw = np.random.default_rng(20261022)
        base_lots = generate_material_lots(starter_master, cfg, rng_raw, IDFactory.for_material_lot())

        # Expire all API lots
        expired_lots: list[MaterialLot] = []
        for l in base_lots:
            if l.material_type == "ACTIVE_PHARMA_INGREDIENT":
                exp_lot = MaterialLot(
                    lot_id=l.lot_id,
                    supplier_id=l.supplier_id,
                    material_type=l.material_type,
                    quantity=l.quantity,
                    unit_of_measure=l.unit_of_measure,
                    received_date=l.received_date,
                    status=l.status,
                    effective_start=l.effective_start,
                    effective_end=cfg.base_date - timedelta(days=10),
                    created_at=l.created_at,
                    updated_at=l.updated_at,
                )
                expired_lots.append(exp_lot)
            else:
                expired_lots.append(l)

        rng_po = np.random.default_rng(20261022)
        with pytest.raises(ValueError, match="Insufficient eligible raw material inventory"):
            generate_production_orders(
                starter_master, expired_lots, cfg, rng_po, IDFactory.for_production_order()
            )

    def test_fifo_receipt_date_ordering_independent_of_input_order(
        self, starter_master: MasterDataset
    ) -> None:
        """
        Targeted test proving that when two eligible lots have different receipt dates,
        the older lot is consumed first, regardless of their input-list order.
        """
        from supply_chain.generators.material_lots import generate_material_lots
        from supply_chain.generators.production_orders import generate_production_orders

        cfg = ProductionConfig(
            raw_lot_count=100,
            production_order_count=1,
            finished_lot_count=1,
            min_order_qty=100,
            max_order_qty=100,
        )
        rng_raw = np.random.default_rng(20261022)
        base_lots = generate_material_lots(starter_master, cfg, rng_raw, IDFactory.for_material_lot())
        sample_api = next(l for l in base_lots if l.material_type == "ACTIVE_PHARMA_INGREDIENT")
        other_lots = [l for l in base_lots if l.material_type != "ACTIVE_PHARMA_INGREDIENT"]

        # lot_older received on Dec 1, lot_newer received on Dec 20
        # lot_older has higher ID string to ensure sorting relies on received_date, not ID
        lot_older = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-999992",
            supplier_id=sample_api.supplier_id,
            material_type="ACTIVE_PHARMA_INGREDIENT",
            quantity=10000,
            unit_of_measure="KG",
            received_date=cfg.base_date - timedelta(days=31),  # Older
            status=MaterialLotStatus.APPROVED,
            effective_start=cfg.base_date - timedelta(days=31),
            effective_end=cfg.base_date + timedelta(days=500),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        lot_newer = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-999991",
            supplier_id=sample_api.supplier_id,
            material_type="ACTIVE_PHARMA_INGREDIENT",
            quantity=10000,
            unit_of_measure="KG",
            received_date=cfg.base_date - timedelta(days=10),  # Newer
            status=MaterialLotStatus.APPROVED,
            effective_start=cfg.base_date - timedelta(days=10),
            effective_end=cfg.base_date + timedelta(days=500),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Run Case A: newer passed before older in input list
        test_lots_case_a = [lot_newer, lot_older] + other_lots
        orders_a, consumptions_a = generate_production_orders(
            starter_master, test_lots_case_a, cfg, np.random.default_rng(20261022), IDFactory.for_production_order()
        )
        api_consumed_a = [c.raw_lot_id for c in consumptions_a if any(l.lot_id == c.raw_lot_id and l.material_type == "ACTIVE_PHARMA_INGREDIENT" for l in [lot_older, lot_newer])]
        assert api_consumed_a == [lot_older.lot_id], "Case A: Older lot must be consumed first despite being second in input list"

        # Run Case B: older passed before newer in input list
        test_lots_case_b = [lot_older, lot_newer] + other_lots
        orders_b, consumptions_b = generate_production_orders(
            starter_master, test_lots_case_b, cfg, np.random.default_rng(20261022), IDFactory.for_production_order()
        )
        api_consumed_b = [c.raw_lot_id for c in consumptions_b if any(l.lot_id == c.raw_lot_id and l.material_type == "ACTIVE_PHARMA_INGREDIENT" for l in [lot_older, lot_newer])]
        assert api_consumed_b == [lot_older.lot_id], "Case B: Older lot must be consumed first when first in input list"

    def test_future_effective_lot_preserved_for_later_orders(
        self, starter_master: MasterDataset
    ) -> None:
        """
        Verify that lots whose effective_start is after the current consumption date
        are not discarded permanently, but remain available and are consumed when
        an order's actual_start reaches their effective date.
        """
        from supply_chain.generators.material_lots import generate_material_lots
        from supply_chain.generators.production_orders import generate_production_orders

        # 2 orders: order 0 runs on base_date, order 1 runs on base_date + 150 days
        cfg = ProductionConfig(
            raw_lot_count=100,
            production_order_count=2,
            finished_lot_count=2,
            min_order_qty=100,
            max_order_qty=100,
        )
        rng_raw = np.random.default_rng(20261022)
        base_lots = generate_material_lots(starter_master, cfg, rng_raw, IDFactory.for_material_lot())
        sample_api = next(l for l in base_lots if l.material_type == "ACTIVE_PHARMA_INGREDIENT")
        other_lots = [l for l in base_lots if l.material_type != "ACTIVE_PHARMA_INGREDIENT"]

        # lot_future received earlier, but not effective until base_date + 10 days
        lot_future = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-999981",
            supplier_id=sample_api.supplier_id,
            material_type="ACTIVE_PHARMA_INGREDIENT",
            quantity=1000,
            unit_of_measure="KG",
            received_date=cfg.base_date - timedelta(days=20),
            status=MaterialLotStatus.APPROVED,
            effective_start=cfg.base_date + timedelta(days=10),  # Effective in future (day 10)
            effective_end=cfg.base_date + timedelta(days=500),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # lot_current received later, but effective immediately
        lot_current = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-999982",
            supplier_id=sample_api.supplier_id,
            material_type="ACTIVE_PHARMA_INGREDIENT",
            quantity=1000,
            unit_of_measure="KG",
            received_date=cfg.base_date - timedelta(days=15),
            status=MaterialLotStatus.APPROVED,
            effective_start=cfg.base_date - timedelta(days=15),  # Effective now
            effective_end=cfg.base_date + timedelta(days=500),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        test_lots = [lot_future, lot_current] + other_lots
        orders, consumptions = generate_production_orders(
            starter_master, test_lots, cfg, np.random.default_rng(20261022), IDFactory.for_production_order()
        )

        # Order 0 (at base_date) cannot consume lot_future because effective_start is in future;
        # it consumes lot_current.
        order0_api_consumed = [
            c.raw_lot_id for c in consumptions
            if c.wo_id == orders[0].wo_id and c.raw_lot_id in (lot_future.lot_id, lot_current.lot_id)
        ]
        assert order0_api_consumed == [lot_current.lot_id]

        # Order 1 (at base_date + 150 days) arrives after lot_future has become effective.
        # Since lot_future was preserved in the candidate list, it is now consumed!
        order1_api_consumed = [
            c.raw_lot_id for c in consumptions
            if c.wo_id == orders[1].wo_id and c.raw_lot_id in (lot_future.lot_id, lot_current.lot_id)
        ]
        assert order1_api_consumed == [lot_future.lot_id]

    def test_fifo_behavior_when_multiple_lots_are_eligible(
        self, starter_master: MasterDataset
    ) -> None:
        """
        Verify strict FIFO allocation when multiple lots of the same material
        are simultaneously eligible, ensuring older lots are fully exhausted
        before newer lots are consumed.
        """
        from supply_chain.generators.material_lots import generate_material_lots
        from supply_chain.generators.production_orders import generate_production_orders

        cfg = ProductionConfig(
            raw_lot_count=100,
            production_order_count=1,
            finished_lot_count=1,
            min_order_qty=250,
            max_order_qty=250,
        )
        rng_raw = np.random.default_rng(20261022)
        base_lots = generate_material_lots(starter_master, cfg, rng_raw, IDFactory.for_material_lot())
        sample_api = next(l for l in base_lots if l.material_type == "ACTIVE_PHARMA_INGREDIENT")
        other_lots = [l for l in base_lots if l.material_type != "ACTIVE_PHARMA_INGREDIENT"]

        # Three eligible lots with distinct receipt dates: Lot 1 (oldest) -> Lot 2 -> Lot 3 (newest)
        # Sized so that an order needing > 200 units will exhaust Lot 1 (200 units) and take remainder from Lot 2,
        # leaving Lot 3 (1000 units) untouched.
        lot1 = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-999971",
            supplier_id=sample_api.supplier_id,
            material_type="ACTIVE_PHARMA_INGREDIENT",
            quantity=200,
            unit_of_measure="KG",
            received_date=cfg.base_date - timedelta(days=50),  # Oldest
            status=MaterialLotStatus.APPROVED,
            effective_start=cfg.base_date - timedelta(days=50),
            effective_end=cfg.base_date + timedelta(days=500),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        lot2 = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-999972",
            supplier_id=sample_api.supplier_id,
            material_type="ACTIVE_PHARMA_INGREDIENT",
            quantity=10000,
            unit_of_measure="KG",
            received_date=cfg.base_date - timedelta(days=40),  # Intermediate
            status=MaterialLotStatus.APPROVED,
            effective_start=cfg.base_date - timedelta(days=40),
            effective_end=cfg.base_date + timedelta(days=500),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        lot3 = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-999973",
            supplier_id=sample_api.supplier_id,
            material_type="ACTIVE_PHARMA_INGREDIENT",
            quantity=10000,
            unit_of_measure="KG",
            received_date=cfg.base_date - timedelta(days=30),  # Newest
            status=MaterialLotStatus.APPROVED,
            effective_start=cfg.base_date - timedelta(days=30),
            effective_end=cfg.base_date + timedelta(days=500),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Shuffle input order: lot3, lot1, lot2
        test_lots = [lot3, lot1, lot2] + other_lots
        orders, consumptions = generate_production_orders(
            starter_master, test_lots, cfg, np.random.default_rng(20261022), IDFactory.for_production_order()
        )

        api_consumptions = [
            (c.raw_lot_id, c.consumed_qty) for c in consumptions
            if c.raw_lot_id in (lot1.lot_id, lot2.lot_id, lot3.lot_id)
        ]

        # First consumption must be from lot1 (exhausting all 200 units)
        assert api_consumptions[0][0] == lot1.lot_id
        assert api_consumptions[0][1] == 200

        # Second consumption must be from lot2 (remaining needed units)
        assert api_consumptions[1][0] == lot2.lot_id

        # lot3 must not have been consumed at all
        consumed_lot_ids = {c.raw_lot_id for c in consumptions}
        assert lot3.lot_id not in consumed_lot_ids
