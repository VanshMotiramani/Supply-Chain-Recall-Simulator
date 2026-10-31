"""
test_inventory.py — Tests for inventory movements, balances, and ledger accounting.

Coverage (B.2, B.3, B.4, B.5):
  - receipt -> shipment
  - receipt -> quarantine -> release
  - receipt -> quarantine -> disposal (guarantee: no double-subtraction)
  - transfers between warehouses
  - detection and rejection of negative balances (over-shipment, over-transfer, over-release)
  - multiple shipments cannot allocate beyond available stock
  - allow_negative flag for controlled EC-2 anomaly
"""

import pytest
from datetime import date, datetime

from supply_chain.models.enums import MovementType
from supply_chain.models.inventory import (
    InventoryLedger,
    InventoryMovement,
)

NOW = datetime(2026, 3, 15, 10, 0, 0)
TODAY = date(2026, 3, 15)


def _make_mvmt(
    mvmt_id: str,
    whs_id: str,
    lot_id: str,
    m_type: MovementType,
    qty: int,
    ref: str = "REF-001",
) -> InventoryMovement:
    return InventoryMovement(
        movement_id=mvmt_id,
        warehouse_id=whs_id,
        fin_lot_id=lot_id,
        movement_type=m_type,
        quantity=qty,
        reference_id=ref,
        movement_date=TODAY,
        created_at=NOW,
    )


class TestInventoryLedgerNormalFlows:
    """Test standard inventory movements and balances."""

    def test_receipt_then_shipment(self):
        ledger = InventoryLedger()
        whs = "WHS-000001"
        lot = "FINLOT-2026-000001"

        # 1. Receive 100 units
        ledger.apply(_make_mvmt("INV-000001", whs, lot, MovementType.RECEIPT, 100))
        bal = ledger.get_balance(whs, lot)
        assert bal.on_hand_qty == 100
        assert bal.available_qty == 100
        assert bal.quarantined_qty == 0
        assert bal.shipped_qty == 0

        # 2. Ship 40 units
        ledger.apply(_make_mvmt("INV-000002", whs, lot, MovementType.SHIPMENT, 40))
        bal2 = ledger.get_balance(whs, lot)
        assert bal2.on_hand_qty == 60
        assert bal2.available_qty == 60
        assert bal2.quarantined_qty == 0
        assert bal2.shipped_qty == 40

    def test_receipt_quarantine_and_release(self):
        ledger = InventoryLedger()
        whs = "WHS-000001"
        lot = "FINLOT-2026-000001"

        ledger.apply(_make_mvmt("INV-000001", whs, lot, MovementType.RECEIPT, 100))

        # Quarantine 30 units
        ledger.apply(_make_mvmt("INV-000002", whs, lot, MovementType.QUARANTINE, 30))
        bal = ledger.get_balance(whs, lot)
        assert bal.on_hand_qty == 100       # Still physically present in warehouse
        assert bal.available_qty == 70      # Unavailable for sale/shipment
        assert bal.quarantined_qty == 30

        # Release 20 units back to available
        ledger.apply(_make_mvmt("INV-000003", whs, lot, MovementType.RELEASE, 20))
        bal_rel = ledger.get_balance(whs, lot)
        assert bal_rel.on_hand_qty == 100
        assert bal_rel.available_qty == 90
        assert bal_rel.quarantined_qty == 10

    def test_receipt_quarantine_and_disposal_no_double_subtraction(self):
        """
        Verify that quarantine followed by disposal reduces on-hand and quarantined
        quantities without double-subtracting from available inventory.
        """
        ledger = InventoryLedger()
        whs = "WHS-000001"
        lot = "FINLOT-2026-000001"

        # Receive 100 units
        ledger.apply(_make_mvmt("INV-000001", whs, lot, MovementType.RECEIPT, 100))

        # Quarantine 30 units
        ledger.apply(_make_mvmt("INV-000002", whs, lot, MovementType.QUARANTINE, 30))
        bal_q = ledger.get_balance(whs, lot)
        assert bal_q.available_qty == 70
        assert bal_q.quarantined_qty == 30
        assert bal_q.on_hand_qty == 100

        # Dispose (destroy) 30 quarantined units
        ledger.apply(_make_mvmt("INV-000003", whs, lot, MovementType.DISPOSAL, 30))
        bal_d = ledger.get_balance(whs, lot)
        # on_hand must drop to 70 (destroyed units removed physically)
        assert bal_d.on_hand_qty == 70
        # quarantined drops to 0
        assert bal_d.quarantined_qty == 0
        # available remains 70 (NEVER double-subtracted!)
        assert bal_d.available_qty == 70
        assert bal_d.disposed_qty == 30

    def test_inter_warehouse_transfers(self):
        """Test moving inventory from W1 to W2."""
        ledger = InventoryLedger()
        w1 = "WHS-000001"
        w2 = "WHS-000002"
        lot = "FINLOT-2026-000001"

        # Receive 100 units at W1
        ledger.apply(_make_mvmt("INV-000001", w1, lot, MovementType.RECEIPT, 100))

        # Transfer 40 units from W1 to W2
        ledger.apply(_make_mvmt("INV-000002", w1, lot, MovementType.TRANSFER_OUT, 40, ref="TRF-0001"))
        ledger.apply(_make_mvmt("INV-000003", w2, lot, MovementType.TRANSFER_IN, 40, ref="TRF-0001"))

        bal_w1 = ledger.get_balance(w1, lot)
        assert bal_w1.on_hand_qty == 60
        assert bal_w1.available_qty == 60

        bal_w2 = ledger.get_balance(w2, lot)
        assert bal_w2.on_hand_qty == 40
        assert bal_w2.available_qty == 40

        # Total lot balance across all warehouses must equal 100
        lot_bal = ledger.get_lot_balance(lot)
        assert lot_bal.on_hand_qty == 100
        assert lot_bal.available_qty == 100


class TestInventoryLedgerConstraints:
    """Test enforcement of physical stock rules and negative balance detection."""

    def test_shipment_exceeding_available_raises(self):
        ledger = InventoryLedger()
        whs = "WHS-000001"
        lot = "FINLOT-2026-000001"

        ledger.apply(_make_mvmt("INV-000001", whs, lot, MovementType.RECEIPT, 50))
        with pytest.raises(ValueError, match="Insufficient available inventory"):
            ledger.apply(_make_mvmt("INV-000002", whs, lot, MovementType.SHIPMENT, 51))

    def test_multiple_shipments_cannot_oversell(self):
        ledger = InventoryLedger()
        whs = "WHS-000001"
        lot = "FINLOT-2026-000001"

        ledger.apply(_make_mvmt("INV-000001", whs, lot, MovementType.RECEIPT, 100))
        ledger.apply(_make_mvmt("INV-000002", whs, lot, MovementType.SHIPMENT, 60))
        # Second shipment requests 50 (only 40 left)
        with pytest.raises(ValueError, match="Insufficient available inventory"):
            ledger.apply(_make_mvmt("INV-000003", whs, lot, MovementType.SHIPMENT, 50))

    def test_quarantine_exceeding_available_raises(self):
        ledger = InventoryLedger()
        whs = "WHS-000001"
        lot = "FINLOT-2026-000001"

        ledger.apply(_make_mvmt("INV-000001", whs, lot, MovementType.RECEIPT, 50))
        ledger.apply(_make_mvmt("INV-000002", whs, lot, MovementType.SHIPMENT, 30))
        # Available is 20, attempt to quarantine 25
        with pytest.raises(ValueError, match="Cannot quarantine"):
            ledger.apply(_make_mvmt("INV-000003", whs, lot, MovementType.QUARANTINE, 25))

    def test_release_exceeding_quarantined_raises(self):
        ledger = InventoryLedger()
        whs = "WHS-000001"
        lot = "FINLOT-2026-000001"

        ledger.apply(_make_mvmt("INV-000001", whs, lot, MovementType.RECEIPT, 50))
        ledger.apply(_make_mvmt("INV-000002", whs, lot, MovementType.QUARANTINE, 20))
        with pytest.raises(ValueError, match="Cannot release"):
            ledger.apply(_make_mvmt("INV-000003", whs, lot, MovementType.RELEASE, 21))

    def test_disposal_exceeding_quarantined_raises(self):
        ledger = InventoryLedger()
        whs = "WHS-000001"
        lot = "FINLOT-2026-000001"

        ledger.apply(_make_mvmt("INV-000001", whs, lot, MovementType.RECEIPT, 50))
        ledger.apply(_make_mvmt("INV-000002", whs, lot, MovementType.QUARANTINE, 10))
        with pytest.raises(ValueError, match="Cannot dispose"):
            ledger.apply(_make_mvmt("INV-000003", whs, lot, MovementType.DISPOSAL, 15))

    def test_transfer_out_exceeding_available_raises(self):
        ledger = InventoryLedger()
        whs = "WHS-000001"
        lot = "FINLOT-2026-000001"

        ledger.apply(_make_mvmt("INV-000001", whs, lot, MovementType.RECEIPT, 30))
        with pytest.raises(ValueError, match="Insufficient available inventory"):
            ledger.apply(_make_mvmt("INV-000002", whs, lot, MovementType.TRANSFER_OUT, 35))

    def test_ec2_allow_negative_over_shipment(self):
        """Controlled exception EC-2 can record an over-shipment when flag is set."""
        ledger = InventoryLedger()
        whs = "WHS-000001"
        lot = "FINLOT-2026-000001"

        ledger.apply(_make_mvmt("INV-000001", whs, lot, MovementType.RECEIPT, 100))
        # Deliberate EC-2 injection: ship 150 units with allow_negative=True
        ledger.apply(
            _make_mvmt("INV-000002", whs, lot, MovementType.SHIPMENT, 150, ref="EC-2-TEST"),
            allow_negative=True,
        )
        bal = ledger.get_balance(whs, lot)
        assert bal.available_qty == -50
        assert bal.on_hand_qty == -50
        assert bal.shipped_qty == 150
