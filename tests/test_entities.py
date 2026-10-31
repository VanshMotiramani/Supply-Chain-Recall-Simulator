"""
test_entities.py — Unit tests for entity dataclass construction and validation.

Coverage (D.1, D.2, D.3, D.4, D.5, C.6):
  - Happy-path creation of each entity with valid fields.
  - Field-level validation: rejects empty strings, negative quantities, date inversions.
  - Primary key immutability enforcement: cannot mutate PK after instantiation.
  - Collection immutability: Supplier.material_types converted to immutable tuple.
  - Delivery date/status consistency: PENDING requires None, DELIVERED requires date.
  - ProductionOrder yield and scrap invariants.
  - Constrained enums on RecallAction (action_type, disposition).
"""

import pytest
from datetime import date, datetime

from supply_chain.models import (
    Supplier,
    MaterialLot,
    Product,
    BOM,
    BOMLine,
    ProductionOrder,
    LotConsumption,
    AnomalousLotConsumption,
    FinishedLot,
    Warehouse,
    Shipment,
    Customer,
    Delivery,
    RecallCase,
    RecallAction,
    EventLog,
)
from supply_chain.models.enums import (
    SupplierStatus,
    MaterialLotStatus,
    ProductStatus,
    BOMStatus,
    ProductionOrderStatus,
    FinishedLotStatus,
    WarehouseStatus,
    ShipmentStatus,
    CustomerStatus,
    DeliveryStatus,
    RecallCaseStatus,
    RecallActionStatus,
    RecallActionType,
    RecallDisposition,
    NotificationChannel,
    RecallTriggerEntityType,
    EventType,
)

NOW = datetime(2026, 3, 15, 8, 0, 0)
TODAY = date(2026, 3, 15)


class TestSupplierEntity:
    def test_valid_supplier(self):
        s = Supplier(
            supplier_id="SUP-000001",
            supplier_name="Acme Chemicals",
            location="Mumbai",
            material_types=["RAW_CHEMICAL"],
            status=SupplierStatus.ACTIVE,
            effective_start=TODAY,
            effective_end=None,
            created_at=NOW,
            updated_at=NOW,
        )
        assert s.supplier_id == "SUP-000001"
        assert s.material_types == ("RAW_CHEMICAL",)

    def test_pk_immutability(self):
        s = Supplier(
            supplier_id="SUP-000001",
            supplier_name="Acme Chemicals",
            location="Mumbai",
            material_types=["RAW_CHEMICAL"],
            status=SupplierStatus.ACTIVE,
            effective_start=TODAY,
            effective_end=None,
            created_at=NOW,
            updated_at=NOW,
        )
        with pytest.raises(AttributeError, match="Cannot mutate immutable primary key"):
            s.supplier_id = "SUP-999999"

    def test_material_types_immutable_tuple(self):
        raw_list = ["CHEM_A", "CHEM_B"]
        s = Supplier(
            supplier_id="SUP-000001",
            supplier_name="Acme Chemicals",
            location="Mumbai",
            material_types=raw_list,
            status=SupplierStatus.ACTIVE,
            effective_start=TODAY,
            effective_end=None,
            created_at=NOW,
            updated_at=NOW,
        )
        # Mutating original list must not affect entity
        raw_list.append("CHEM_C")
        assert s.material_types == ("CHEM_A", "CHEM_B")
        # Attempting in-place mutation of tuple raises TypeError
        with pytest.raises(TypeError):
            s.material_types[0] = "MODIFIED"  # type: ignore

    def test_empty_supplier_id_raises(self):
        with pytest.raises(ValueError, match="supplier_id"):
            Supplier(
                supplier_id="",
                supplier_name="X",
                location="Y",
                material_types=["A"],
                status=SupplierStatus.ACTIVE,
                effective_start=TODAY,
                effective_end=None,
                created_at=NOW,
                updated_at=NOW,
            )

    def test_empty_material_types_raises(self):
        with pytest.raises(ValueError, match="material_types"):
            Supplier(
                supplier_id="SUP-000001",
                supplier_name="X",
                location="Y",
                material_types=[],
                status=SupplierStatus.ACTIVE,
                effective_start=TODAY,
                effective_end=None,
                created_at=NOW,
                updated_at=NOW,
            )

    def test_effective_end_before_start_raises(self):
        with pytest.raises(ValueError, match="effective_end"):
            Supplier(
                supplier_id="SUP-000001",
                supplier_name="X",
                location="Y",
                material_types=["A"],
                status=SupplierStatus.ACTIVE,
                effective_start=date(2026, 5, 1),
                effective_end=date(2026, 4, 1),
                created_at=NOW,
                updated_at=NOW,
            )


class TestMaterialLotEntity:
    def test_valid_lot(self):
        lot = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-000001",
            supplier_id="SUP-000001",
            material_type="RAW_CHEMICAL",
            quantity=1000,
            unit_of_measure="KG",
            received_date=TODAY,
            status=MaterialLotStatus.APPROVED,
            effective_start=TODAY,
            effective_end=None,
            created_at=NOW,
            updated_at=NOW,
        )
        assert lot.quantity == 1000

    def test_pk_immutability(self):
        lot = MaterialLot(
            lot_id="RAWLOT-SUP-000001-2026-000001",
            supplier_id="SUP-000001",
            material_type="RAW_CHEMICAL",
            quantity=1000,
            unit_of_measure="KG",
            received_date=TODAY,
            status=MaterialLotStatus.APPROVED,
            effective_start=TODAY,
            effective_end=None,
            created_at=NOW,
            updated_at=NOW,
        )
        with pytest.raises(AttributeError, match="Cannot mutate immutable primary key"):
            lot.lot_id = "RAWLOT-SUP-000001-2026-999999"

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError, match="quantity"):
            MaterialLot(
                lot_id="RAWLOT-SUP-000001-2026-000001",
                supplier_id="SUP-000001",
                material_type="RAW_CHEMICAL",
                quantity=-1,
                unit_of_measure="KG",
                received_date=TODAY,
                status=MaterialLotStatus.APPROVED,
                effective_start=TODAY,
                effective_end=None,
                created_at=NOW,
                updated_at=NOW,
            )


class TestProductionOrderEntity:
    def _make_po(self, planned=100, yield_ratio=0.90):
        actual_good = int(planned * yield_ratio)
        scrap = planned - actual_good
        return ProductionOrder(
            wo_id="WO-2026-000001",
            product_id="PROD-000001",
            bom_id="BOM-000001",
            planned_output_qty=planned,
            yield_ratio=yield_ratio,
            actual_good_output_qty=actual_good,
            scrap_qty=scrap,
            status=ProductionOrderStatus.COMPLETED,
            planned_start=TODAY,
            planned_end=TODAY,
        )

    def test_valid_po_yield_and_scrap(self):
        po = self._make_po(planned=200, yield_ratio=0.85)
        assert po.actual_good_output_qty == 170
        assert po.scrap_qty == 30

    def test_pk_immutability(self):
        po = self._make_po(planned=200, yield_ratio=0.85)
        with pytest.raises(AttributeError, match="Cannot mutate immutable primary key"):
            po.wo_id = "WO-2026-999999"

    def test_yield_out_of_range_raises(self):
        with pytest.raises(ValueError, match="yield_ratio"):
            self._make_po(planned=100, yield_ratio=0.84)
        with pytest.raises(ValueError, match="yield_ratio"):
            self._make_po(planned=100, yield_ratio=0.99)

    def test_mismatched_actual_good_raises(self):
        with pytest.raises(ValueError, match="actual_good_output_qty"):
            ProductionOrder(
                wo_id="WO-2026-000001",
                product_id="PROD-000001",
                bom_id="BOM-000001",
                planned_output_qty=100,
                yield_ratio=0.90,
                actual_good_output_qty=95,  # must be 90
                scrap_qty=5,
                status=ProductionOrderStatus.COMPLETED,
                planned_start=TODAY,
                planned_end=TODAY,
            )


class TestFinishedLot:
    def test_valid_finished_lot_without_warehouse(self):
        """FinishedLot does not contain warehouse_id (tracked via InventoryMovement)."""
        fl = FinishedLot(
            fin_lot_id="FINLOT-2026-000001",
            wo_id="WO-2026-000001",
            quantity=90,
            produced_date=TODAY,
            status=FinishedLotStatus.AVAILABLE,
        )
        assert fl.fin_lot_id == "FINLOT-2026-000001"
        assert fl.quantity == 90

    def test_pk_immutability(self):
        fl = FinishedLot(
            fin_lot_id="FINLOT-2026-000001",
            wo_id="WO-2026-000001",
            quantity=90,
            produced_date=TODAY,
            status=FinishedLotStatus.AVAILABLE,
        )
        with pytest.raises(AttributeError, match="Cannot mutate immutable primary key"):
            fl.fin_lot_id = "FINLOT-2026-999999"


class TestDelivery:
    def test_valid_pending_delivery(self):
        """Pending delivery must have delivered_date = None."""
        d = Delivery(
            delivery_id="DEL-2026-000001",
            shipment_id="SHP-2026-000001",
            fin_lot_id="FINLOT-2026-000001",
            shipped_qty=50,
            status=DeliveryStatus.PENDING,
            delivered_date=None,
        )
        assert d.delivered_date is None

    def test_pending_delivery_with_date_raises(self):
        with pytest.raises(ValueError, match="delivered_date must be None"):
            Delivery(
                delivery_id="DEL-2026-000001",
                shipment_id="SHP-2026-000001",
                fin_lot_id="FINLOT-2026-000001",
                shipped_qty=50,
                status=DeliveryStatus.PENDING,
                delivered_date=TODAY,
            )

    def test_valid_delivered_delivery(self):
        """Delivered delivery must have delivered_date set."""
        d = Delivery(
            delivery_id="DEL-2026-000001",
            shipment_id="SHP-2026-000001",
            fin_lot_id="FINLOT-2026-000001",
            shipped_qty=50,
            status=DeliveryStatus.DELIVERED,
            delivered_date=TODAY,
        )
        assert d.delivered_date == TODAY

    def test_delivered_delivery_missing_date_raises(self):
        with pytest.raises(ValueError, match="delivered_date is required"):
            Delivery(
                delivery_id="DEL-2026-000001",
                shipment_id="SHP-2026-000001",
                fin_lot_id="FINLOT-2026-000001",
                shipped_qty=50,
                status=DeliveryStatus.DELIVERED,
                delivered_date=None,
            )


class TestRecallEntities:
    def test_valid_recall_case(self):
        rc = RecallCase(
            recall_id="REC-2026-000001",
            trigger_entity_type=RecallTriggerEntityType.MATERIAL_LOT,
            trigger_entity_id="RAWLOT-SUP-000001-2026-000001",
            reason="Contamination detected",
            status=RecallCaseStatus.OPEN,
            opened_date=TODAY,
            closed_date=None,
        )
        assert rc.recall_id == "REC-2026-000001"

    def test_closed_before_opened_raises(self):
        with pytest.raises(ValueError, match="closed_date"):
            RecallCase(
                recall_id="REC-2026-000001",
                trigger_entity_type=RecallTriggerEntityType.FINISHED_LOT,
                trigger_entity_id="FINLOT-2026-000001",
                reason="Test",
                status=RecallCaseStatus.CLOSED,
                opened_date=date(2026, 6, 15),
                closed_date=date(2026, 6, 1),
            )

    def test_recall_action_with_constrained_enums(self):
        ra = RecallAction(
            action_id="RACT-2026-000001",
            recall_id="REC-2026-000001",
            delivery_id="DEL-2026-000001",
            action_type=RecallActionType.QUARANTINE,
            notification_channel=NotificationChannel.EMAIL,
            status=RecallActionStatus.QUARANTINE_REQUESTED,
            disposition=RecallDisposition.DISPOSED,
        )
        assert ra.action_type == RecallActionType.QUARANTINE
        assert ra.disposition == RecallDisposition.DISPOSED
