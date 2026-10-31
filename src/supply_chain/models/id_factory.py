"""
id_factory.py — Deterministic, zero-padded ID generation for all entities.

Rules (FR-02, D.6):
  - All counters are zero-padded to exactly 6 digits.
  - Counter overflows beyond 999999 raise OverflowError.
  - IDs are immutable once assigned.
  - reset() enables clean restarts between independent deterministic runs.
"""

from __future__ import annotations

import re


class _Counter:
    """Thread-unsafe monotonic counter with overflow protection."""

    def __init__(self, start: int = 1) -> None:
        if start < 1 or start > 999999:
            raise ValueError(f"Initial counter must be in [1, 999999], got {start}")
        self._value = start

    def next(self) -> int:
        if self._value > 999999:
            raise OverflowError("Counter exceeded maximum 6-digit capacity (999999)")
        val = self._value
        self._value += 1
        return val

    def reset(self, start: int = 1) -> None:
        if start < 1 or start > 999999:
            raise ValueError(f"Reset start must be in [1, 999999], got {start}")
        self._value = start

    @property
    def current(self) -> int:
        return self._value


# ---------------------------------------------------------------------------
# ID format regex patterns
# ---------------------------------------------------------------------------

SUPPLIER_RE         = re.compile(r"^SUP-\d{6}$")
MATERIAL_LOT_RE     = re.compile(r"^RAWLOT-SUP-\d{6}-2026-\d{6}$")
PRODUCT_RE          = re.compile(r"^PROD-\d{6}$")
BOM_RE              = re.compile(r"^BOM-\d{6}$")
PRODUCTION_ORDER_RE = re.compile(r"^WO-2026-\d{6}$")
FINISHED_LOT_RE     = re.compile(r"^FINLOT-2026-\d{6}$")
WAREHOUSE_RE        = re.compile(r"^WHS-\d{6}$")
INVENTORY_MVT_RE    = re.compile(r"^INV-\d{6}$")
SHIPMENT_RE         = re.compile(r"^SHP-2026-\d{6}$")
CUSTOMER_RE         = re.compile(r"^CUST-\d{6}$")
DELIVERY_RE         = re.compile(r"^DEL-2026-\d{6}$")
RECALL_CASE_RE      = re.compile(r"^REC-2026-\d{6}$")
RECALL_ACTION_RE    = re.compile(r"^RACT-2026-\d{6}$")
EVENT_LOG_RE        = re.compile(r"^EVT-\d{6}$")

ID_PATTERNS: dict[str, re.Pattern] = {
    "Supplier":          SUPPLIER_RE,
    "MaterialLot":       MATERIAL_LOT_RE,
    "Product":           PRODUCT_RE,
    "BOM":               BOM_RE,
    "ProductionOrder":   PRODUCTION_ORDER_RE,
    "FinishedLot":       FINISHED_LOT_RE,
    "Warehouse":         WAREHOUSE_RE,
    "InventoryMovement": INVENTORY_MVT_RE,
    "Shipment":          SHIPMENT_RE,
    "Customer":          CUSTOMER_RE,
    "Delivery":          DELIVERY_RE,
    "RecallCase":        RECALL_CASE_RE,
    "RecallAction":      RECALL_ACTION_RE,
    "EventLog":          EVENT_LOG_RE,
}


def validate_id(entity_type: str, entity_id: str) -> bool:
    """Return True if entity_id matches the expected format for entity_type."""
    pattern = ID_PATTERNS.get(entity_type)
    if pattern is None:
        raise KeyError(f"No ID pattern registered for entity type: {entity_type!r}")
    return bool(pattern.match(entity_id))


class IDFactory:
    """
    Generates unique, zero-padded IDs for a single entity type.
    """

    def __init__(self, prefix: str, start: int = 1) -> None:
        self._prefix = prefix
        self._counter = _Counter(start)

    def next(self, supplier_id: str | None = None) -> str:
        """
        Generate the next ID.
        supplier_id is required for MaterialLot IDs: RAWLOT-<supplier_id>-2026-<6-digit>.
        """
        n = self._counter.next()
        padded = f"{n:06d}"
        if supplier_id is not None:
            return f"RAWLOT-{supplier_id}-2026-{padded}"
        return f"{self._prefix}{padded}"

    def reset(self, start: int = 1) -> None:
        """Reset counter to a specific start value."""
        self._counter.reset(start)

    @property
    def issued_count(self) -> int:
        return self._counter.current - 1

    # Named factory constructors
    @staticmethod
    def for_supplier(start: int = 1) -> IDFactory:
        return IDFactory(prefix="SUP-", start=start)

    @staticmethod
    def for_material_lot(start: int = 1) -> IDFactory:
        return IDFactory(prefix="RAWLOT-", start=start)

    @staticmethod
    def for_product(start: int = 1) -> IDFactory:
        return IDFactory(prefix="PROD-", start=start)

    @staticmethod
    def for_bom(start: int = 1) -> IDFactory:
        return IDFactory(prefix="BOM-", start=start)

    @staticmethod
    def for_production_order(start: int = 1) -> IDFactory:
        return IDFactory(prefix="WO-2026-", start=start)

    @staticmethod
    def for_finished_lot(start: int = 1) -> IDFactory:
        return IDFactory(prefix="FINLOT-2026-", start=start)

    @staticmethod
    def for_warehouse(start: int = 1) -> IDFactory:
        return IDFactory(prefix="WHS-", start=start)

    @staticmethod
    def for_inventory_movement(start: int = 1) -> IDFactory:
        return IDFactory(prefix="INV-", start=start)

    @staticmethod
    def for_shipment(start: int = 1) -> IDFactory:
        return IDFactory(prefix="SHP-2026-", start=start)

    @staticmethod
    def for_customer(start: int = 1) -> IDFactory:
        return IDFactory(prefix="CUST-", start=start)

    @staticmethod
    def for_delivery(start: int = 1) -> IDFactory:
        return IDFactory(prefix="DEL-2026-", start=start)

    @staticmethod
    def for_recall_case(start: int = 1) -> IDFactory:
        return IDFactory(prefix="REC-2026-", start=start)

    @staticmethod
    def for_recall_action(start: int = 1) -> IDFactory:
        return IDFactory(prefix="RACT-2026-", start=start)

    @staticmethod
    def for_event_log(start: int = 1) -> IDFactory:
        return IDFactory(prefix="EVT-", start=start)
