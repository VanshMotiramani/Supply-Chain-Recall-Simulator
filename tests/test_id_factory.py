"""
test_id_factory.py — Unit tests for IDFactory and ID-format validation.

Coverage:
  - All 14 factory constructors generate the correct prefix and padding.
  - Counters increment correctly across multiple calls.
  - MaterialLot IDs embed the supplier_id correctly.
  - validate_id() returns True for valid IDs and False for invalid ones.
  - issued_count property tracks how many IDs have been issued.
  - reset() enables clean counter resets between runs.
  - Overflow protection rejects values exceeding 999999.
"""

import pytest

from supply_chain.models.id_factory import (
    IDFactory,
    validate_id,
)


class TestIDFormatsFirst:
    """Each factory's first ID must match its documented pattern."""

    def test_supplier_first(self):
        f = IDFactory.for_supplier()
        assert f.next() == "SUP-000001"

    def test_material_lot_first(self):
        f = IDFactory.for_material_lot()
        sup_id = "SUP-000001"
        result = f.next(supplier_id=sup_id)
        assert result == "RAWLOT-SUP-000001-2026-000001"

    def test_product_first(self):
        assert IDFactory.for_product().next() == "PROD-000001"

    def test_bom_first(self):
        assert IDFactory.for_bom().next() == "BOM-000001"

    def test_production_order_first(self):
        assert IDFactory.for_production_order().next() == "WO-2026-000001"

    def test_finished_lot_first(self):
        assert IDFactory.for_finished_lot().next() == "FINLOT-2026-000001"

    def test_warehouse_first(self):
        assert IDFactory.for_warehouse().next() == "WHS-000001"

    def test_inventory_movement_first(self):
        assert IDFactory.for_inventory_movement().next() == "INV-000001"

    def test_shipment_first(self):
        assert IDFactory.for_shipment().next() == "SHP-2026-000001"

    def test_customer_first(self):
        assert IDFactory.for_customer().next() == "CUST-000001"

    def test_delivery_first(self):
        assert IDFactory.for_delivery().next() == "DEL-2026-000001"

    def test_recall_case_first(self):
        assert IDFactory.for_recall_case().next() == "REC-2026-000001"

    def test_recall_action_first(self):
        assert IDFactory.for_recall_action().next() == "RACT-2026-000001"

    def test_event_log_first(self):
        assert IDFactory.for_event_log().next() == "EVT-000001"


class TestCounterBehaviour:
    """Counter must increment monotonically, zero-pad correctly, and handle resets."""

    def test_supplier_increments(self):
        f = IDFactory.for_supplier()
        ids = [f.next() for _ in range(5)]
        assert ids == [
            "SUP-000001", "SUP-000002", "SUP-000003",
            "SUP-000004", "SUP-000005",
        ]

    def test_padding_at_boundary(self):
        f = IDFactory.for_supplier(start=999999)
        assert f.next() == "SUP-999999"

    def test_overflow_protection_raises(self):
        f = IDFactory.for_supplier(start=999999)
        f.next()  # reaches 999999
        with pytest.raises(OverflowError, match="exceeded maximum 6-digit capacity"):
            f.next()

    def test_invalid_start_values_raise(self):
        with pytest.raises(ValueError, match="Initial counter"):
            IDFactory.for_supplier(start=0)
        with pytest.raises(ValueError, match="Initial counter"):
            IDFactory.for_supplier(start=1000000)

    def test_reset_counter(self):
        f = IDFactory.for_supplier()
        assert f.next() == "SUP-000001"
        assert f.next() == "SUP-000002"
        f.reset(1)
        assert f.next() == "SUP-000001"

    def test_reset_invalid_value_raises(self):
        f = IDFactory.for_supplier()
        with pytest.raises(ValueError, match="Reset start"):
            f.reset(0)

    def test_issued_count_zero_before_first(self):
        f = IDFactory.for_supplier()
        assert f.issued_count == 0

    def test_issued_count_after_calls(self):
        f = IDFactory.for_supplier()
        for _ in range(10):
            f.next()
        assert f.issued_count == 10

    def test_production_order_increments(self):
        f = IDFactory.for_production_order()
        assert f.next() == "WO-2026-000001"
        assert f.next() == "WO-2026-000002"

    def test_recall_case_increments(self):
        f = IDFactory.for_recall_case()
        ids = [f.next() for _ in range(3)]
        assert ids == ["REC-2026-000001", "REC-2026-000002", "REC-2026-000003"]

    def test_recall_action_increments(self):
        f = IDFactory.for_recall_action()
        ids = [f.next() for _ in range(3)]
        assert ids == ["RACT-2026-000001", "RACT-2026-000002", "RACT-2026-000003"]


class TestMaterialLotID:
    """Supplier ID must be embedded correctly in the lot ID."""

    def test_different_suppliers_different_prefixes(self):
        f = IDFactory.for_material_lot()
        id1 = f.next(supplier_id="SUP-000001")
        id2 = f.next(supplier_id="SUP-000002")
        assert id1 == "RAWLOT-SUP-000001-2026-000001"
        assert id2 == "RAWLOT-SUP-000002-2026-000002"

    def test_same_supplier_increments(self):
        f = IDFactory.for_material_lot()
        ids = [f.next(supplier_id="SUP-000042") for _ in range(3)]
        assert ids == [
            "RAWLOT-SUP-000042-2026-000001",
            "RAWLOT-SUP-000042-2026-000002",
            "RAWLOT-SUP-000042-2026-000003",
        ]


class TestValidateID:
    """validate_id must correctly accept valid IDs and reject malformed ones."""

    @pytest.mark.parametrize("entity_type,valid_id", [
        ("Supplier",          "SUP-000001"),
        ("MaterialLot",       "RAWLOT-SUP-000001-2026-000001"),
        ("Product",           "PROD-000001"),
        ("BOM",               "BOM-000001"),
        ("ProductionOrder",   "WO-2026-000001"),
        ("FinishedLot",       "FINLOT-2026-000001"),
        ("Warehouse",         "WHS-000001"),
        ("InventoryMovement", "INV-000001"),
        ("Shipment",          "SHP-2026-000001"),
        ("Customer",          "CUST-000001"),
        ("Delivery",          "DEL-2026-000001"),
        ("RecallCase",        "REC-2026-000001"),
        ("RecallAction",      "RACT-2026-000001"),
        ("EventLog",          "EVT-000001"),
    ])
    def test_valid_ids(self, entity_type, valid_id):
        assert validate_id(entity_type, valid_id) is True

    @pytest.mark.parametrize("entity_type,bad_id", [
        ("Supplier",        "sup-000001"),
        ("Supplier",        "SUP-1"),
        ("Supplier",        "SUP-0000001"),
        ("Supplier",        ""),
        ("ProductionOrder", "WO-2025-000001"),
        ("FinishedLot",     "FINLOT-2025-000001"),
        ("Shipment",        "SHP-000001"),
        ("RecallCase",      "REC-000001"),
        ("RecallAction",    "RCT-2026-000001"),
        ("MaterialLot",     "RAWLOT-000001-2026-000001"),
    ])
    def test_invalid_ids(self, entity_type, bad_id):
        assert validate_id(entity_type, bad_id) is False

    def test_unknown_entity_raises(self):
        with pytest.raises(KeyError):
            validate_id("UnknownEntity", "WHATEVER-000001")
