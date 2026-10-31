"""
inventory.py — Inventory movements, balances, and ledger accounting.

INVENTORY ACCOUNTING RULES (B.2, B.3, B.5):
==========================================
For each (warehouse_id, fin_lot_id) pair:

1. Physical On-Hand (on_hand_qty):
   Total physical units located inside the warehouse facility.
   on_hand = (RECEIPT + TRANSFER_IN + RECOVERY) - (SHIPMENT + TRANSFER_OUT + DISPOSAL)

2. Quarantined (quarantined_qty):
   Physical units held under quarantine (cannot be shipped or transferred).
   quarantined = (QUARANTINE + RECOVERY) - (RELEASE + DISPOSAL)
   Constraint: 0 <= quarantined_qty <= on_hand_qty

3. Available (available_qty):
   Physical units unreserved and free for allocation, shipment, or transfer.
   available = on_hand_qty - quarantined_qty
   Expanding the terms:
   available = (RECEIPT + TRANSFER_IN - TRANSFER_OUT - SHIPMENT) - (QUARANTINE - RELEASE)
   Constraint: available_qty >= 0 (strictly enforced; EC-2 is the single labelled exception)

4. Shipped (shipped_qty):
   Units dispatched to customers that have not been recovered.
   shipped = SHIPMENT - RECOVERY

5. Recovered (recovered_qty):
   Units returned from customers into quarantine during a recall.
   recovered = RECOVERY

6. Disposed (disposed_qty):
   Units condemned and physically destroyed from quarantine.
   disposed = DISPOSAL

NO DOUBLE-SUBTRACTION GUARANTEE:
--------------------------------
- When units are quarantined: available decreases, quarantined increases, on_hand is unchanged.
- When quarantined units are disposed: on_hand decreases, quarantined decreases, available is unchanged.
  Quarantine and disposal never double-subtract from available quantity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import ClassVar, Optional

from supply_chain.models.common import (
    EntityBase,
    require_nonempty,
    require_positive,
    utc_now,
)
from supply_chain.models.enums import MovementType


@dataclass
class InventoryMovement(EntityBase):
    """
    Immutable, append-only record of a stock movement event (NFR-07).
    PK: movement_id (INV-<6-digit>)
    FK: warehouse_id -> Warehouse.warehouse_id, fin_lot_id -> FinishedLot.fin_lot_id
    """
    _pk_name: ClassVar[str] = "movement_id"

    movement_id:   str
    warehouse_id:  str
    fin_lot_id:    str
    movement_type: MovementType
    quantity:      int
    reference_id:  str
    movement_date: date
    created_at:    datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        require_nonempty(self.movement_id, "movement_id")
        require_nonempty(self.warehouse_id, "warehouse_id")
        require_nonempty(self.fin_lot_id, "fin_lot_id")
        require_positive(self.quantity, "quantity")
        require_nonempty(self.reference_id, "reference_id")
        self._mark_initialized()


@dataclass(frozen=True)
class InventoryBalance:
    """
    Derived inventory balance snapshot for a warehouse/lot combination.
    """
    warehouse_id:    Optional[str]
    fin_lot_id:      str
    on_hand_qty:     int
    available_qty:   int
    quarantined_qty: int
    shipped_qty:     int
    recovered_qty:   int
    disposed_qty:    int


class InventoryLedger:
    """
    Authoritative in-memory inventory ledger.
    Applies movements deterministically, tracks balances, and enforces non-negative constraints.
    """

    def __init__(self) -> None:
        # Key: (warehouse_id, fin_lot_id) -> breakdown counters
        self._records: dict[tuple[str, str], dict[str, int]] = {}
        self._movements: list[InventoryMovement] = []

    def _ensure_slot(self, warehouse_id: str, fin_lot_id: str) -> dict[str, int]:
        key = (warehouse_id, fin_lot_id)
        if key not in self._records:
            self._records[key] = {
                "receipt": 0,
                "transfer_in": 0,
                "transfer_out": 0,
                "shipment": 0,
                "quarantine": 0,
                "release": 0,
                "disposal": 0,
                "recovery": 0,
            }
        return self._records[key]

    def apply(self, movement: InventoryMovement, allow_negative: bool = False) -> None:
        """
        Record an inventory movement and update running balances.

        Raises:
            ValueError: If the movement violates physical stock constraints (unless allow_negative is True).
        """
        slot = self._ensure_slot(movement.warehouse_id, movement.fin_lot_id)
        qty = movement.quantity

        current = self.get_balance(movement.warehouse_id, movement.fin_lot_id)

        # Enforce prerequisite balance requirements before mutating
        if not allow_negative:
            if movement.movement_type in (MovementType.SHIPMENT, MovementType.TRANSFER_OUT):
                if current.available_qty < qty:
                    raise ValueError(
                        f"Insufficient available inventory at warehouse {movement.warehouse_id} "
                        f"for lot {movement.fin_lot_id}: requested {qty}, available {current.available_qty}"
                    )
            elif movement.movement_type == MovementType.QUARANTINE:
                if current.available_qty < qty:
                    raise ValueError(
                        f"Cannot quarantine {qty} units of lot {movement.fin_lot_id} "
                        f"at warehouse {movement.warehouse_id}: available is only {current.available_qty}"
                    )
            elif movement.movement_type == MovementType.RELEASE:
                if current.quarantined_qty < qty:
                    raise ValueError(
                        f"Cannot release {qty} units from quarantine for lot {movement.fin_lot_id}: "
                        f"quarantined balance is {current.quarantined_qty}"
                    )
            elif movement.movement_type == MovementType.DISPOSAL:
                if current.quarantined_qty < qty:
                    raise ValueError(
                        f"Cannot dispose {qty} units of lot {movement.fin_lot_id}: "
                        f"quarantined balance is only {current.quarantined_qty}"
                    )

        # Apply movement
        m_type = movement.movement_type
        if m_type == MovementType.RECEIPT:
            slot["receipt"] += qty
        elif m_type == MovementType.TRANSFER_IN:
            slot["transfer_in"] += qty
        elif m_type == MovementType.TRANSFER_OUT:
            slot["transfer_out"] += qty
        elif m_type == MovementType.SHIPMENT:
            slot["shipment"] += qty
        elif m_type == MovementType.QUARANTINE:
            slot["quarantine"] += qty
        elif m_type == MovementType.RELEASE:
            slot["release"] += qty
        elif m_type == MovementType.DISPOSAL:
            slot["disposal"] += qty
        elif m_type == MovementType.RECOVERY:
            slot["recovery"] += qty

        self._movements.append(movement)

    def get_balance(self, warehouse_id: str, fin_lot_id: str) -> InventoryBalance:
        """Calculate the precise balance for a specific warehouse and finished lot."""
        key = (warehouse_id, fin_lot_id)
        if key not in self._records:
            return InventoryBalance(
                warehouse_id=warehouse_id,
                fin_lot_id=fin_lot_id,
                on_hand_qty=0,
                available_qty=0,
                quarantined_qty=0,
                shipped_qty=0,
                recovered_qty=0,
                disposed_qty=0,
            )
        s = self._records[key]

        on_hand = (
            s["receipt"] + s["transfer_in"] + s["recovery"]
            - s["transfer_out"] - s["shipment"] - s["disposal"]
        )
        quarantined = s["quarantine"] + s["recovery"] - s["release"] - s["disposal"]
        available = on_hand - quarantined
        shipped = s["shipment"] - s["recovery"]
        recovered = s["recovery"]
        disposed = s["disposal"]

        return InventoryBalance(
            warehouse_id=warehouse_id,
            fin_lot_id=fin_lot_id,
            on_hand_qty=on_hand,
            available_qty=available,
            quarantined_qty=quarantined,
            shipped_qty=shipped,
            recovered_qty=recovered,
            disposed_qty=disposed,
        )

    def get_lot_balance(self, fin_lot_id: str) -> InventoryBalance:
        """Aggregate balance for a finished lot across all warehouses."""
        total_on_hand = 0
        total_available = 0
        total_quarantined = 0
        total_shipped = 0
        total_recovered = 0
        total_disposed = 0

        for (w_id, l_id) in self._records:
            if l_id == fin_lot_id:
                bal = self.get_balance(w_id, l_id)
                total_on_hand += bal.on_hand_qty
                total_available += bal.available_qty
                total_quarantined += bal.quarantined_qty
                total_shipped += bal.shipped_qty
                total_recovered += bal.recovered_qty
                total_disposed += bal.disposed_qty

        return InventoryBalance(
            warehouse_id=None,
            fin_lot_id=fin_lot_id,
            on_hand_qty=total_on_hand,
            available_qty=total_available,
            quarantined_qty=total_quarantined,
            shipped_qty=total_shipped,
            recovered_qty=total_recovered,
            disposed_qty=total_disposed,
        )

    @property
    def all_movements(self) -> list[InventoryMovement]:
        """Read-only view of recorded movements."""
        return list(self._movements)
