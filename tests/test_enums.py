"""
test_enums.py — Unit tests for lifecycle FSM transitions and enum serialization.

Coverage:
  - validate_transition() accepts all documented valid transitions.
  - validate_transition() rejects all invalid / backward transitions.
  - Terminal states raise ValueError for any transition.
  - Unknown entity type raises KeyError.
  - All Enum members serialize cleanly as str values.
"""

import pytest

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
    MovementType,
    NotificationChannel,
    EventType,
    RecallTriggerEntityType,
)
from supply_chain.models.lifecycle import validate_transition


def _ok(entity_type, from_s, to_s):
    validate_transition(entity_type, from_s, to_s)


def _fail(entity_type, from_s, to_s):
    with pytest.raises(ValueError):
        validate_transition(entity_type, from_s, to_s)


class TestSupplierFSM:
    def test_active_to_suspended(self):  _ok("Supplier", SupplierStatus.ACTIVE, SupplierStatus.SUSPENDED)
    def test_active_to_inactive(self):   _ok("Supplier", SupplierStatus.ACTIVE, SupplierStatus.INACTIVE)
    def test_suspended_to_active(self):  _ok("Supplier", SupplierStatus.SUSPENDED, SupplierStatus.ACTIVE)
    def test_inactive_terminal(self):    _fail("Supplier", SupplierStatus.INACTIVE, SupplierStatus.ACTIVE)


class TestMaterialLotFSM:
    def test_received_to_approved(self):      _ok("MaterialLot", MaterialLotStatus.RECEIVED, MaterialLotStatus.APPROVED)
    def test_received_to_rejected(self):      _ok("MaterialLot", MaterialLotStatus.RECEIVED, MaterialLotStatus.REJECTED)
    def test_approved_to_consumed(self):      _ok("MaterialLot", MaterialLotStatus.APPROVED, MaterialLotStatus.CONSUMED)
    def test_approved_to_quarantined(self):   _ok("MaterialLot", MaterialLotStatus.APPROVED, MaterialLotStatus.QUARANTINED)
    def test_quarantined_to_disposed(self):   _ok("MaterialLot", MaterialLotStatus.QUARANTINED, MaterialLotStatus.DISPOSED)
    def test_quarantined_to_released(self):   _ok("MaterialLot", MaterialLotStatus.QUARANTINED, MaterialLotStatus.RELEASED)
    def test_released_to_approved(self):      _ok("MaterialLot", MaterialLotStatus.RELEASED, MaterialLotStatus.APPROVED)
    def test_consumed_terminal(self):         _fail("MaterialLot", MaterialLotStatus.CONSUMED, MaterialLotStatus.APPROVED)
    def test_disposed_terminal(self):         _fail("MaterialLot", MaterialLotStatus.DISPOSED, MaterialLotStatus.APPROVED)
    def test_approved_to_received_invalid(self): _fail("MaterialLot", MaterialLotStatus.APPROVED, MaterialLotStatus.RECEIVED)
    def test_rejected_to_approved_invalid(self): _fail("MaterialLot", MaterialLotStatus.REJECTED, MaterialLotStatus.APPROVED)


class TestProductionOrderFSM:
    def test_planned_to_in_progress(self):   _ok("ProductionOrder", ProductionOrderStatus.PLANNED, ProductionOrderStatus.IN_PROGRESS)
    def test_planned_to_cancelled(self):     _ok("ProductionOrder", ProductionOrderStatus.PLANNED, ProductionOrderStatus.CANCELLED)
    def test_in_progress_to_completed(self): _ok("ProductionOrder", ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.COMPLETED)
    def test_in_progress_to_cancelled(self): _ok("ProductionOrder", ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.CANCELLED)
    def test_completed_terminal(self):       _fail("ProductionOrder", ProductionOrderStatus.COMPLETED, ProductionOrderStatus.PLANNED)
    def test_planned_to_completed_skip(self): _fail("ProductionOrder", ProductionOrderStatus.PLANNED, ProductionOrderStatus.COMPLETED)


class TestFinishedLotFSM:
    def test_produced_to_available(self):       _ok("FinishedLot", FinishedLotStatus.PRODUCED, FinishedLotStatus.AVAILABLE)
    def test_available_to_shipped(self):        _ok("FinishedLot", FinishedLotStatus.AVAILABLE, FinishedLotStatus.SHIPPED)
    def test_available_to_quarantined(self):    _ok("FinishedLot", FinishedLotStatus.AVAILABLE, FinishedLotStatus.QUARANTINED)
    def test_shipped_to_quarantined(self):      _ok("FinishedLot", FinishedLotStatus.SHIPPED, FinishedLotStatus.QUARANTINED)
    def test_quarantined_to_disposed(self):     _ok("FinishedLot", FinishedLotStatus.QUARANTINED, FinishedLotStatus.DISPOSED)
    def test_quarantined_to_released(self):     _ok("FinishedLot", FinishedLotStatus.QUARANTINED, FinishedLotStatus.RELEASED)
    def test_released_to_available(self):       _ok("FinishedLot", FinishedLotStatus.RELEASED, FinishedLotStatus.AVAILABLE)
    def test_disposed_terminal(self):           _fail("FinishedLot", FinishedLotStatus.DISPOSED, FinishedLotStatus.AVAILABLE)
    def test_produced_to_shipped_skip(self):    _fail("FinishedLot", FinishedLotStatus.PRODUCED, FinishedLotStatus.SHIPPED)
    def test_available_to_disposed_direct(self): _fail("FinishedLot", FinishedLotStatus.AVAILABLE, FinishedLotStatus.DISPOSED)


class TestShipmentFSM:
    """Shipment transitions — PARTIALLY_RECALLED removed per D-12 (whole-lot recall)."""
    def test_created_to_shipped(self):     _ok("Shipment", ShipmentStatus.CREATED, ShipmentStatus.SHIPPED)
    def test_shipped_to_delivered(self):   _ok("Shipment", ShipmentStatus.SHIPPED, ShipmentStatus.DELIVERED)
    def test_delivered_to_recalled(self):  _ok("Shipment", ShipmentStatus.DELIVERED, ShipmentStatus.RECALLED)
    def test_recalled_terminal(self):      _fail("Shipment", ShipmentStatus.RECALLED, ShipmentStatus.DELIVERED)
    def test_created_to_delivered_skip(self): _fail("Shipment", ShipmentStatus.CREATED, ShipmentStatus.DELIVERED)


class TestRecallCaseFSM:
    def test_open_to_in_progress(self):      _ok("RecallCase", RecallCaseStatus.OPEN, RecallCaseStatus.IN_PROGRESS)
    def test_open_to_cancelled(self):        _ok("RecallCase", RecallCaseStatus.OPEN, RecallCaseStatus.CANCELLED)
    def test_in_progress_to_closed(self):    _ok("RecallCase", RecallCaseStatus.IN_PROGRESS, RecallCaseStatus.CLOSED)
    def test_in_progress_to_cancelled(self): _ok("RecallCase", RecallCaseStatus.IN_PROGRESS, RecallCaseStatus.CANCELLED)
    def test_closed_terminal(self):          _fail("RecallCase", RecallCaseStatus.CLOSED, RecallCaseStatus.OPEN)
    def test_open_to_closed_skip(self):      _fail("RecallCase", RecallCaseStatus.OPEN, RecallCaseStatus.CLOSED)


class TestRecallActionFSM:
    def test_notified_to_quarantine_requested(self):
        _ok("RecallAction", RecallActionStatus.NOTIFIED, RecallActionStatus.QUARANTINE_REQUESTED)

    def test_quarantine_requested_to_recovered(self):
        _ok("RecallAction", RecallActionStatus.QUARANTINE_REQUESTED, RecallActionStatus.RECOVERED)

    def test_recovered_to_disposed(self):
        _ok("RecallAction", RecallActionStatus.RECOVERED, RecallActionStatus.DISPOSED)

    def test_recovered_to_released(self):
        _ok("RecallAction", RecallActionStatus.RECOVERED, RecallActionStatus.RELEASED)

    def test_disposed_to_completed(self):
        _ok("RecallAction", RecallActionStatus.DISPOSED, RecallActionStatus.COMPLETED)

    def test_released_to_completed(self):
        _ok("RecallAction", RecallActionStatus.RELEASED, RecallActionStatus.COMPLETED)

    def test_notified_to_completed_skip(self):
        _fail("RecallAction", RecallActionStatus.NOTIFIED, RecallActionStatus.COMPLETED)

    def test_completed_terminal(self):
        _fail("RecallAction", RecallActionStatus.COMPLETED, RecallActionStatus.NOTIFIED)


class TestDeliveryFSM:
    def test_pending_to_delivered(self):       _ok("Delivery", DeliveryStatus.PENDING, DeliveryStatus.DELIVERED)
    def test_delivered_to_recalled(self):      _ok("Delivery", DeliveryStatus.DELIVERED, DeliveryStatus.RECALLED)
    def test_delivered_to_quarantined(self):   _ok("Delivery", DeliveryStatus.DELIVERED, DeliveryStatus.QUARANTINED)
    def test_quarantined_to_recalled(self):    _ok("Delivery", DeliveryStatus.QUARANTINED, DeliveryStatus.RECALLED)
    def test_recalled_terminal(self):          _fail("Delivery", DeliveryStatus.RECALLED, DeliveryStatus.DELIVERED)
    def test_pending_to_recalled_skip(self):   _fail("Delivery", DeliveryStatus.PENDING, DeliveryStatus.RECALLED)


class TestUnknownEntity:
    def test_raises_key_error(self):
        with pytest.raises(KeyError, match="Unknown entity type"):
            validate_transition("GhostEntity", SupplierStatus.ACTIVE, SupplierStatus.INACTIVE)


class TestEnumStringValues:
    """All enums must serialize cleanly as standard strings."""

    @pytest.mark.parametrize("enum_cls,expected_value", [
        (SupplierStatus.ACTIVE,                "ACTIVE"),
        (MaterialLotStatus.QUARANTINED,        "QUARANTINED"),
        (ProductionOrderStatus.COMPLETED,      "COMPLETED"),
        (FinishedLotStatus.AVAILABLE,          "AVAILABLE"),
        (ShipmentStatus.RECALLED,              "RECALLED"),
        (RecallCaseStatus.CLOSED,              "CLOSED"),
        (RecallActionStatus.COMPLETED,         "COMPLETED"),
        (RecallActionType.QUARANTINE,          "QUARANTINE"),
        (RecallDisposition.DISPOSED,           "DISPOSED"),
        (MovementType.QUARANTINE,              "QUARANTINE"),
        (NotificationChannel.EMAIL,            "EMAIL"),
        (EventType.QUARANTINE_FAILURE,         "QUARANTINE_FAILURE"),
        (RecallTriggerEntityType.MATERIAL_LOT, "MATERIAL_LOT"),
    ])
    def test_str_value(self, enum_cls, expected_value):
        assert str(enum_cls) == expected_value
        assert enum_cls == expected_value
