"""
lifecycle.py — Finite State Machine (FSM) transitions and validation.

Encodes valid status transitions for all lifecycle-tracked entities.
Transitions must be validated explicitly before applying state changes.
"""

from enum import StrEnum

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
)


SUPPLIER_TRANSITIONS: dict[SupplierStatus, set[SupplierStatus]] = {
    SupplierStatus.ACTIVE:    {SupplierStatus.SUSPENDED, SupplierStatus.INACTIVE},
    SupplierStatus.SUSPENDED: {SupplierStatus.ACTIVE,    SupplierStatus.INACTIVE},
    SupplierStatus.INACTIVE:  set(),
}

MATERIAL_LOT_TRANSITIONS: dict[MaterialLotStatus, set[MaterialLotStatus]] = {
    MaterialLotStatus.RECEIVED:    {MaterialLotStatus.APPROVED, MaterialLotStatus.REJECTED},
    MaterialLotStatus.APPROVED:    {MaterialLotStatus.CONSUMED, MaterialLotStatus.QUARANTINED},
    MaterialLotStatus.REJECTED:    {MaterialLotStatus.DISPOSED},
    MaterialLotStatus.CONSUMED:    set(),
    MaterialLotStatus.QUARANTINED: {MaterialLotStatus.DISPOSED, MaterialLotStatus.RELEASED},
    MaterialLotStatus.RELEASED:    {MaterialLotStatus.APPROVED},
    MaterialLotStatus.DISPOSED:    set(),
}

PRODUCT_TRANSITIONS: dict[ProductStatus, set[ProductStatus]] = {
    ProductStatus.ACTIVE:       {ProductStatus.DISCONTINUED},
    ProductStatus.DISCONTINUED: set(),
}

BOM_TRANSITIONS: dict[BOMStatus, set[BOMStatus]] = {
    BOMStatus.DRAFT:      {BOMStatus.APPROVED},
    BOMStatus.APPROVED:   {BOMStatus.SUPERSEDED},
    BOMStatus.SUPERSEDED: set(),
}

PRODUCTION_ORDER_TRANSITIONS: dict[ProductionOrderStatus, set[ProductionOrderStatus]] = {
    ProductionOrderStatus.PLANNED:     {ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.CANCELLED},
    ProductionOrderStatus.IN_PROGRESS: {ProductionOrderStatus.COMPLETED,   ProductionOrderStatus.CANCELLED},
    ProductionOrderStatus.COMPLETED:   set(),
    ProductionOrderStatus.CANCELLED:   set(),
}

FINISHED_LOT_TRANSITIONS: dict[FinishedLotStatus, set[FinishedLotStatus]] = {
    FinishedLotStatus.PRODUCED:    {FinishedLotStatus.AVAILABLE},
    FinishedLotStatus.AVAILABLE:   {FinishedLotStatus.SHIPPED, FinishedLotStatus.QUARANTINED},
    FinishedLotStatus.SHIPPED:     {FinishedLotStatus.QUARANTINED},
    FinishedLotStatus.QUARANTINED: {FinishedLotStatus.DISPOSED, FinishedLotStatus.RELEASED},
    FinishedLotStatus.RELEASED:    {FinishedLotStatus.AVAILABLE},
    FinishedLotStatus.DISPOSED:    set(),
}

WAREHOUSE_TRANSITIONS: dict[WarehouseStatus, set[WarehouseStatus]] = {
    WarehouseStatus.ACTIVE:   {WarehouseStatus.INACTIVE},
    WarehouseStatus.INACTIVE: {WarehouseStatus.ACTIVE},
}

SHIPMENT_TRANSITIONS: dict[ShipmentStatus, set[ShipmentStatus]] = {
    ShipmentStatus.CREATED:   {ShipmentStatus.SHIPPED},
    ShipmentStatus.SHIPPED:   {ShipmentStatus.DELIVERED},
    ShipmentStatus.DELIVERED: {ShipmentStatus.RECALLED},
    ShipmentStatus.RECALLED:  set(),
}

CUSTOMER_TRANSITIONS: dict[CustomerStatus, set[CustomerStatus]] = {
    CustomerStatus.ACTIVE:   {CustomerStatus.INACTIVE},
    CustomerStatus.INACTIVE: {CustomerStatus.ACTIVE},
}

DELIVERY_TRANSITIONS: dict[DeliveryStatus, set[DeliveryStatus]] = {
    DeliveryStatus.PENDING:     {DeliveryStatus.DELIVERED},
    DeliveryStatus.DELIVERED:   {DeliveryStatus.RECALLED, DeliveryStatus.QUARANTINED},
    DeliveryStatus.QUARANTINED: {DeliveryStatus.RECALLED},
    DeliveryStatus.RECALLED:    set(),
}

RECALL_CASE_TRANSITIONS: dict[RecallCaseStatus, set[RecallCaseStatus]] = {
    RecallCaseStatus.OPEN:        {RecallCaseStatus.IN_PROGRESS, RecallCaseStatus.CANCELLED},
    RecallCaseStatus.IN_PROGRESS: {RecallCaseStatus.CLOSED,      RecallCaseStatus.CANCELLED},
    RecallCaseStatus.CLOSED:      set(),
    RecallCaseStatus.CANCELLED:   set(),
}

RECALL_ACTION_TRANSITIONS: dict[RecallActionStatus, set[RecallActionStatus]] = {
    RecallActionStatus.NOTIFIED:             {RecallActionStatus.QUARANTINE_REQUESTED},
    RecallActionStatus.QUARANTINE_REQUESTED: {RecallActionStatus.RECOVERED},
    RecallActionStatus.RECOVERED:            {RecallActionStatus.DISPOSED, RecallActionStatus.RELEASED},
    RecallActionStatus.DISPOSED:             {RecallActionStatus.COMPLETED},
    RecallActionStatus.RELEASED:             {RecallActionStatus.COMPLETED},
    RecallActionStatus.COMPLETED:            set(),
}

_TRANSITION_MAPS: dict[str, dict] = {
    "Supplier":        SUPPLIER_TRANSITIONS,
    "MaterialLot":     MATERIAL_LOT_TRANSITIONS,
    "Product":         PRODUCT_TRANSITIONS,
    "BOM":             BOM_TRANSITIONS,
    "ProductionOrder": PRODUCTION_ORDER_TRANSITIONS,
    "FinishedLot":     FINISHED_LOT_TRANSITIONS,
    "Warehouse":       WAREHOUSE_TRANSITIONS,
    "Shipment":        SHIPMENT_TRANSITIONS,
    "Customer":        CUSTOMER_TRANSITIONS,
    "Delivery":        DELIVERY_TRANSITIONS,
    "RecallCase":      RECALL_CASE_TRANSITIONS,
    "RecallAction":    RECALL_ACTION_TRANSITIONS,
}


def validate_transition(entity_type: str, from_status: StrEnum, to_status: StrEnum) -> None:
    """
    Validate that an entity status transition is permitted by its FSM.

    Raises:
        KeyError: If entity_type is unrecognized.
        ValueError: If the transition is prohibited or the entity is in a terminal state.
    """
    transitions = _TRANSITION_MAPS.get(entity_type)
    if transitions is None:
        raise KeyError(f"Unknown entity type for FSM: {entity_type!r}")
    allowed = transitions.get(from_status, set())
    if to_status not in allowed:
        raise ValueError(
            f"Invalid transition for {entity_type}: "
            f"{from_status!r} → {to_status!r}. "
            f"Allowed: {[str(s) for s in allowed] or 'none (terminal state)'}"
        )
