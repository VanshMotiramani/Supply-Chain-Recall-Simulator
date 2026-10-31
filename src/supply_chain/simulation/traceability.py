"""
traceability.py — Pure, deterministic, read-only supply-chain genealogy traversals.

Stage 2 Requirements:
  - Forward trace from raw material lot -> production orders -> finished lots -> deliveries/shipments -> unique customers.
  - Forward trace from finished lot -> deliveries/shipments -> unique customers.
  - Backward trace from delivery -> finished lot -> production order -> consumed raw lots -> suppliers.
  - Backward trace from finished lot -> production order -> consumed raw lots -> suppliers.
  - Strict determinism: all returned identifier collections are lexicographically sorted tuples.
  - Customer deduplication: each affected customer appears exactly once.
  - Safe missing-reference handling: broken foreign keys (e.g., EC-1 anomalous consumption)
    or missing entity IDs are captured in a typed `missing_references` tuple without throwing exceptions.
  - Pure & read-only: zero mutations to input collections, datasets, or global state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from supply_chain.generators.config import (
    DistributionDataset,
    MasterDataset,
    ProductionDataset,
)
from supply_chain.models import (
    Delivery,
    FinishedLot,
    LotConsumption,
    MaterialLot,
    ProductionOrder,
    Shipment,
    Supplier,
)
from supply_chain.models.production_order import AnomalousLotConsumption
from supply_chain.simulation.models import SimulationDataset


# ---------------------------------------------------------------------------
# Trace Result Containers (Immutable, Deterministically Sorted)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ForwardMaterialLotTrace:
    """
    Downstream genealogy trace starting from a raw material lot.

    Attributes:
        material_lot_id: Target raw material lot identifier.
        production_order_ids: Deterministically sorted production orders that consumed this lot.
        finished_lot_ids: Deterministically sorted finished lots produced by those orders.
        delivery_ids: Deterministically sorted customer delivery lines carrying those finished lots.
        shipment_ids: Deterministically sorted outbound shipments carrying those deliveries.
        affected_customer_ids: Unique, deterministically sorted customer IDs receiving those deliveries.
        missing_references: Sorted diagnostics of any broken foreign keys or missing references.
    """
    material_lot_id: str
    production_order_ids: tuple[str, ...]
    finished_lot_ids: tuple[str, ...]
    delivery_ids: tuple[str, ...]
    shipment_ids: tuple[str, ...]
    affected_customer_ids: tuple[str, ...]
    missing_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class ForwardFinishedLotTrace:
    """
    Downstream trace starting from a finished product lot to shipments and customers.

    Attributes:
        fin_lot_id: Target finished lot identifier.
        delivery_ids: Deterministically sorted delivery lines carrying this lot.
        shipment_ids: Deterministically sorted shipments containing those delivery lines.
        affected_customer_ids: Unique, deterministically sorted customer IDs receiving those shipments.
        missing_references: Sorted diagnostics of any broken foreign keys or missing references.
    """
    fin_lot_id: str
    delivery_ids: tuple[str, ...]
    shipment_ids: tuple[str, ...]
    affected_customer_ids: tuple[str, ...]
    missing_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class BackwardDeliveryTrace:
    """
    Upstream genealogy trace starting from a customer delivery line back to raw materials and suppliers.

    Attributes:
        delivery_id: Target delivery identifier.
        shipment_id: Parent outbound shipment identifier.
        customer_id: Recipient customer identifier.
        fin_lot_id: Delivered finished product lot identifier.
        wo_id: Production work order that produced the finished lot.
        product_id: Product catalog identifier.
        raw_lot_ids: Deterministically sorted raw material lot IDs consumed by the production order.
        supplier_ids: Deterministically sorted supplier IDs who provided those raw materials.
        missing_references: Sorted diagnostics of any broken foreign keys or missing references.
    """
    delivery_id: str
    shipment_id: Optional[str]
    customer_id: Optional[str]
    fin_lot_id: Optional[str]
    wo_id: Optional[str]
    product_id: Optional[str]
    raw_lot_ids: tuple[str, ...]
    supplier_ids: tuple[str, ...]
    missing_references: tuple[str, ...] = ()


@dataclass(frozen=True)
class BackwardFinishedLotTrace:
    """
    Upstream genealogy trace starting from a finished product lot back to raw materials and suppliers.

    Attributes:
        fin_lot_id: Target finished lot identifier.
        wo_id: Production order that produced this finished lot.
        product_id: Product catalog identifier.
        raw_lot_ids: Deterministically sorted raw material lot IDs consumed by the order.
        supplier_ids: Deterministically sorted supplier IDs who provided those raw materials.
        missing_references: Sorted diagnostics of any broken foreign keys or missing references.
    """
    fin_lot_id: str
    wo_id: Optional[str]
    product_id: Optional[str]
    raw_lot_ids: tuple[str, ...]
    supplier_ids: tuple[str, ...]
    missing_references: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Internal Context Extraction Helper
# ---------------------------------------------------------------------------

def _resolve_trace_context(
    production: Optional[ProductionDataset | SimulationDataset] = None,
    distribution: Optional[DistributionDataset | SimulationDataset] = None,
    master: Optional[MasterDataset] = None,
) -> tuple[
    Sequence[MaterialLot],
    Sequence[ProductionOrder],
    Sequence[LotConsumption | AnomalousLotConsumption],
    Sequence[FinishedLot],
    Sequence[Shipment],
    Sequence[Delivery],
    Optional[MasterDataset],
]:
    """
    Extract production and distribution entity collections without invalid type assumptions.

    Supports:
      - Explicit (ProductionDataset, DistributionDataset) pair.
      - Single SimulationDataset passed as production, distribution, or both.
      - Partial context when production or distribution is omitted.
    """
    sim: Optional[SimulationDataset] = None
    if isinstance(production, SimulationDataset):
        sim = production
    elif isinstance(distribution, SimulationDataset):
        sim = distribution

    if sim is not None:
        mat_lots = sim.production.material_lots
        orders = sim.production.production_orders
        consumptions = sim.lot_consumptions
        fin_lots = sim.production.finished_lots
        shipments = sim.shipments
        deliveries = sim.deliveries
        resolved_master = master or sim.master
        return mat_lots, orders, consumptions, fin_lots, shipments, deliveries, resolved_master

    # Regular ProductionDataset (or None)
    if isinstance(production, ProductionDataset):
        mat_lots = production.material_lots
        orders = production.production_orders
        consumptions = production.lot_consumptions
        fin_lots = production.finished_lots
    else:
        mat_lots = ()
        orders = ()
        consumptions = ()
        fin_lots = ()

    # Regular DistributionDataset (or None)
    if isinstance(distribution, DistributionDataset):
        shipments = distribution.shipments
        deliveries = distribution.deliveries
    else:
        shipments = ()
        deliveries = ()

    resolved_master = master
    return mat_lots, orders, consumptions, fin_lots, shipments, deliveries, resolved_master


# ---------------------------------------------------------------------------
# Stage 2 Traversal Functions
# ---------------------------------------------------------------------------

def trace_forward_from_material_lot(
    material_lot_id: str,
    production: ProductionDataset | SimulationDataset,
    distribution: Optional[DistributionDataset | SimulationDataset] = None,
    master: Optional[MasterDataset] = None,
) -> ForwardMaterialLotTrace:
    """
    Pure forward traversal tracing an input raw material lot downstream to affected customers.

    Traversal Chain:
      MaterialLot.lot_id
        -> LotConsumption (wo_id)
        -> ProductionOrder (wo_id)
        -> FinishedLot (fin_lot_id where wo_id matches)
        -> Delivery (delivery_id, shipment_id where fin_lot_id matches)
        -> Shipment (customer_id where shipment_id matches)
        -> Unique Customers

    Args:
        material_lot_id: Raw material lot ID to trace.
        production: Production dataset or simulation dataset.
        distribution: Distribution dataset or simulation dataset (optional if production is SimulationDataset).
        master: Master dataset for reference validation (optional).

    Returns:
        ForwardMaterialLotTrace with deterministically sorted tuples.
    """
    if not isinstance(production, (ProductionDataset, SimulationDataset)):
        raise TypeError(
            f"production must be a ProductionDataset or SimulationDataset, got {type(production).__name__}"
        )
    if distribution is not None and not isinstance(distribution, (DistributionDataset, SimulationDataset)):
        raise TypeError(
            f"distribution must be a DistributionDataset or SimulationDataset, got {type(distribution).__name__}"
        )

    mat_lots, orders, consumptions, fin_lots, shipments, deliveries, resolved_master = _resolve_trace_context(
        production=production,
        distribution=distribution,
        master=master,
    )

    missing_refs: list[str] = []

    # Check distribution context
    if distribution is None and not isinstance(production, SimulationDataset):
        missing_refs.append("Distribution dataset omitted: downstream distribution unresolvable")

    # Fast indexed lookups
    mat_lot_exists = any(m.lot_id == material_lot_id for m in mat_lots)
    if not mat_lot_exists:
        missing_refs.append(f"MaterialLot not found: {material_lot_id}")

    orders_by_id = {o.wo_id: o for o in orders}
    shipments_by_id = {s.shipment_id: s for s in shipments}

    # Step 1: Find all production orders that consumed this raw lot
    affected_wo_ids: set[str] = set()
    for c in consumptions:
        if c.raw_lot_id == material_lot_id:
            affected_wo_ids.add(c.wo_id)
            if c.wo_id not in orders_by_id:
                missing_refs.append(f"ProductionOrder not found for consumption: {c.wo_id}")

    # Step 2: Find all finished lots produced by these production orders
    affected_fin_lot_ids: set[str] = set()
    for f in fin_lots:
        if f.wo_id in affected_wo_ids:
            affected_fin_lot_ids.add(f.fin_lot_id)

    # Step 3: Find all deliveries containing these finished lots
    affected_delivery_ids: set[str] = set()
    affected_shipment_ids: set[str] = set()
    for d in deliveries:
        if d.fin_lot_id in affected_fin_lot_ids:
            affected_delivery_ids.add(d.delivery_id)
            affected_shipment_ids.add(d.shipment_id)
            if d.shipment_id not in shipments_by_id:
                missing_refs.append(f"Shipment not found for delivery {d.delivery_id}: {d.shipment_id}")

    # Step 4: Resolve unique customers through parent shipments
    affected_customer_ids: set[str] = set()
    customer_ids_in_master = (
        {c.customer_id for c in resolved_master.customers} if resolved_master is not None else None
    )

    for s_id in affected_shipment_ids:
        shipment = shipments_by_id.get(s_id)
        if shipment is not None:
            affected_customer_ids.add(shipment.customer_id)
            if customer_ids_in_master is not None and shipment.customer_id not in customer_ids_in_master:
                missing_refs.append(f"Customer not found in master: {shipment.customer_id}")

    return ForwardMaterialLotTrace(
        material_lot_id=material_lot_id,
        production_order_ids=tuple(sorted(affected_wo_ids)),
        finished_lot_ids=tuple(sorted(affected_fin_lot_ids)),
        delivery_ids=tuple(sorted(affected_delivery_ids)),
        shipment_ids=tuple(sorted(affected_shipment_ids)),
        affected_customer_ids=tuple(sorted(affected_customer_ids)),
        missing_references=tuple(sorted(set(missing_refs))),
    )


def trace_forward_from_finished_lot(
    fin_lot_id: str,
    distribution: DistributionDataset | SimulationDataset,
    production: Optional[ProductionDataset | SimulationDataset] = None,
    master: Optional[MasterDataset] = None,
) -> ForwardFinishedLotTrace:
    """
    Pure forward traversal tracing a finished product lot to shipments and unique customers.

    Traversal Chain:
      FinishedLot.fin_lot_id
        -> Delivery (delivery_id, shipment_id where fin_lot_id matches)
        -> Shipment (customer_id where shipment_id matches)
        -> Unique Customers

    Args:
        fin_lot_id: Finished lot ID to trace.
        distribution: Distribution dataset or simulation dataset.
        production: Production dataset (optional, used to verify finished lot existence).
        master: Master dataset (optional, used to verify customer existence).

    Returns:
        ForwardFinishedLotTrace with deterministically sorted tuples.
    """
    if not isinstance(distribution, (DistributionDataset, SimulationDataset)):
        raise TypeError(
            f"distribution must be a DistributionDataset or SimulationDataset, got {type(distribution).__name__}"
        )
    if production is not None and not isinstance(production, (ProductionDataset, SimulationDataset)):
        raise TypeError(
            f"production must be a ProductionDataset or SimulationDataset, got {type(production).__name__}"
        )

    context = _resolve_trace_context(
        production=production,
        distribution=distribution,
        master=master,
    )
    _, _, _, fin_lots, shipments, deliveries, resolved_master = context

    missing_refs: list[str] = []

    if fin_lots and not any(f.fin_lot_id == fin_lot_id for f in fin_lots):
        missing_refs.append(f"FinishedLot not found: {fin_lot_id}")

    shipments_by_id = {s.shipment_id: s for s in shipments}

    affected_delivery_ids: set[str] = set()
    affected_shipment_ids: set[str] = set()
    for d in deliveries:
        if d.fin_lot_id == fin_lot_id:
            affected_delivery_ids.add(d.delivery_id)
            affected_shipment_ids.add(d.shipment_id)
            if d.shipment_id not in shipments_by_id:
                missing_refs.append(f"Shipment not found for delivery {d.delivery_id}: {d.shipment_id}")

    affected_customer_ids: set[str] = set()
    customer_ids_in_master = (
        {c.customer_id for c in resolved_master.customers} if resolved_master is not None else None
    )

    for s_id in affected_shipment_ids:
        shipment = shipments_by_id.get(s_id)
        if shipment is not None:
            affected_customer_ids.add(shipment.customer_id)
            if customer_ids_in_master is not None and shipment.customer_id not in customer_ids_in_master:
                missing_refs.append(f"Customer not found in master: {shipment.customer_id}")

    return ForwardFinishedLotTrace(
        fin_lot_id=fin_lot_id,
        delivery_ids=tuple(sorted(affected_delivery_ids)),
        shipment_ids=tuple(sorted(affected_shipment_ids)),
        affected_customer_ids=tuple(sorted(affected_customer_ids)),
        missing_references=tuple(sorted(set(missing_refs))),
    )


def trace_backward_from_delivery(
    delivery_id: str,
    distribution: DistributionDataset | SimulationDataset,
    production: Optional[ProductionDataset | SimulationDataset] = None,
    master: Optional[MasterDataset] = None,
) -> BackwardDeliveryTrace:
    """
    Pure backward traversal tracing a delivery line back to its finished lot, work order,
    consumed raw material lots, and suppliers.

    Genealogy Resolution Contracts:
      1. Both datasets provided: Full backward trace from delivery -> shipment/customer
         and delivery -> finished lot -> work order -> raw material lots -> suppliers.
      2. SimulationDataset provided: Automatically resolves both distribution and production contexts.
      3. DistributionDataset provided without production dataset (production=None):
         Returns a documented partial trace resolving delivery, shipment, customer, and fin_lot_id,
         while cleanly reporting that production genealogy is unresolvable via `missing_references`.
         Never crashes or silently misinterprets distribution as production.

    Handles EC-1 broken foreign key gracefully without raising unhandled exceptions:
    if a consumed raw material lot does not exist in `material_lots`, its raw_lot_id
    is captured in `raw_lot_ids` and documented in `missing_references`.

    Args:
        delivery_id: Target delivery line identifier.
        distribution: Distribution dataset or simulation dataset.
        production: Production dataset or simulation dataset (optional).
        master: Master dataset (optional, used to verify customer and supplier existence).

    Returns:
        BackwardDeliveryTrace with deterministic fields and sorted tuples.
    """
    if not isinstance(distribution, (DistributionDataset, SimulationDataset)):
        raise TypeError(
            f"distribution must be a DistributionDataset or SimulationDataset, got {type(distribution).__name__}"
        )
    if production is not None and not isinstance(production, (ProductionDataset, SimulationDataset)):
        raise TypeError(
            f"production must be a ProductionDataset or SimulationDataset, got {type(production).__name__}"
        )

    context = _resolve_trace_context(
        production=production,
        distribution=distribution,
        master=master,
    )
    mat_lots, orders, consumptions, fin_lots, shipments, deliveries, resolved_master = context

    missing_refs: list[str] = []

    # Look up delivery
    delivery = next((d for d in deliveries if d.delivery_id == delivery_id), None)
    if delivery is None:
        missing_refs.append(f"Delivery not found: {delivery_id}")
        return BackwardDeliveryTrace(
            delivery_id=delivery_id,
            shipment_id=None,
            customer_id=None,
            fin_lot_id=None,
            wo_id=None,
            product_id=None,
            raw_lot_ids=(),
            supplier_ids=(),
            missing_references=tuple(missing_refs),
        )

    # Resolve shipment & customer
    shipment = next((s for s in shipments if s.shipment_id == delivery.shipment_id), None)
    customer_id: Optional[str] = None
    if shipment is None:
        missing_refs.append(f"Shipment not found for delivery {delivery_id}: {delivery.shipment_id}")
    else:
        customer_id = shipment.customer_id
        if resolved_master is not None:
            if not any(c.customer_id == customer_id for c in resolved_master.customers):
                missing_refs.append(f"Customer not found in master: {customer_id}")

    # Check if production context was omitted (when caller provided only DistributionDataset)
    if production is None and not isinstance(distribution, SimulationDataset):
        missing_refs.append(
            f"Production dataset omitted: cannot resolve upstream genealogy for finished lot {delivery.fin_lot_id}"
        )
        return BackwardDeliveryTrace(
            delivery_id=delivery_id,
            shipment_id=delivery.shipment_id,
            customer_id=customer_id,
            fin_lot_id=delivery.fin_lot_id,
            wo_id=None,
            product_id=None,
            raw_lot_ids=(),
            supplier_ids=(),
            missing_references=tuple(sorted(set(missing_refs))),
        )

    # Resolve finished lot
    fin_lot = next((f for f in fin_lots if f.fin_lot_id == delivery.fin_lot_id), None)
    if fin_lot is None:
        missing_refs.append(f"FinishedLot not found: {delivery.fin_lot_id}")
        return BackwardDeliveryTrace(
            delivery_id=delivery_id,
            shipment_id=delivery.shipment_id,
            customer_id=customer_id,
            fin_lot_id=delivery.fin_lot_id,
            wo_id=None,
            product_id=None,
            raw_lot_ids=(),
            supplier_ids=(),
            missing_references=tuple(sorted(set(missing_refs))),
        )

    # Resolve production order & product
    order = next((o for o in orders if o.wo_id == fin_lot.wo_id), None)
    product_id: Optional[str] = None
    if order is None:
        missing_refs.append(f"ProductionOrder not found for finished lot: {fin_lot.wo_id}")
    else:
        product_id = order.product_id

    # Resolve consumed raw material lots & suppliers
    mat_lots_by_id = {m.lot_id: m for m in mat_lots}
    suppliers_in_master = (
        {s.supplier_id for s in resolved_master.suppliers} if resolved_master is not None else None
    )

    consumed_raw_lots: set[str] = set()
    supplier_ids: set[str] = set()

    for c in consumptions:
        if c.wo_id == fin_lot.wo_id:
            consumed_raw_lots.add(c.raw_lot_id)
            mat_lot = mat_lots_by_id.get(c.raw_lot_id)
            if mat_lot is None:
                # EC-1 anomaly: raw_lot_id does not exist in MaterialLot catalog
                missing_refs.append(f"MaterialLot not found: {c.raw_lot_id}")
            else:
                supplier_ids.add(mat_lot.supplier_id)
                if suppliers_in_master is not None and mat_lot.supplier_id not in suppliers_in_master:
                    missing_refs.append(f"Supplier not found in master: {mat_lot.supplier_id}")

    return BackwardDeliveryTrace(
        delivery_id=delivery_id,
        shipment_id=delivery.shipment_id,
        customer_id=customer_id,
        fin_lot_id=delivery.fin_lot_id,
        wo_id=fin_lot.wo_id,
        product_id=product_id,
        raw_lot_ids=tuple(sorted(consumed_raw_lots)),
        supplier_ids=tuple(sorted(supplier_ids)),
        missing_references=tuple(sorted(set(missing_refs))),
    )


def trace_backward_from_finished_lot(
    fin_lot_id: str,
    production: ProductionDataset | SimulationDataset,
    master: Optional[MasterDataset] = None,
) -> BackwardFinishedLotTrace:
    """
    Pure backward traversal tracing a finished product lot back to its production order,
    consumed raw material lots, and suppliers.

    Args:
        fin_lot_id: Target finished product lot identifier.
        production: Production dataset or simulation dataset.
        master: Master dataset (optional, used to verify supplier existence).

    Returns:
        BackwardFinishedLotTrace with deterministic fields and sorted tuples.
    """
    if not isinstance(production, (ProductionDataset, SimulationDataset)):
        raise TypeError(
            f"production must be a ProductionDataset or SimulationDataset, got {type(production).__name__}"
        )

    context = _resolve_trace_context(production=production, distribution=None, master=master)
    mat_lots, orders, consumptions, fin_lots, _, _, resolved_master = context

    missing_refs: list[str] = []

    fin_lot = next((f for f in fin_lots if f.fin_lot_id == fin_lot_id), None)
    if fin_lot is None:
        missing_refs.append(f"FinishedLot not found: {fin_lot_id}")
        return BackwardFinishedLotTrace(
            fin_lot_id=fin_lot_id,
            wo_id=None,
            product_id=None,
            raw_lot_ids=(),
            supplier_ids=(),
            missing_references=tuple(missing_refs),
        )

    order = next((o for o in orders if o.wo_id == fin_lot.wo_id), None)
    product_id: Optional[str] = None
    if order is None:
        missing_refs.append(f"ProductionOrder not found for finished lot: {fin_lot.wo_id}")
    else:
        product_id = order.product_id

    mat_lots_by_id = {m.lot_id: m for m in mat_lots}
    suppliers_in_master = (
        {s.supplier_id for s in resolved_master.suppliers} if resolved_master is not None else None
    )

    consumed_raw_lots: set[str] = set()
    supplier_ids: set[str] = set()

    for c in consumptions:
        if c.wo_id == fin_lot.wo_id:
            consumed_raw_lots.add(c.raw_lot_id)
            mat_lot = mat_lots_by_id.get(c.raw_lot_id)
            if mat_lot is None:
                missing_refs.append(f"MaterialLot not found: {c.raw_lot_id}")
            else:
                supplier_ids.add(mat_lot.supplier_id)
                if suppliers_in_master is not None and mat_lot.supplier_id not in suppliers_in_master:
                    missing_refs.append(f"Supplier not found in master: {mat_lot.supplier_id}")

    return BackwardFinishedLotTrace(
        fin_lot_id=fin_lot_id,
        wo_id=fin_lot.wo_id,
        product_id=product_id,
        raw_lot_ids=tuple(sorted(consumed_raw_lots)),
        supplier_ids=tuple(sorted(supplier_ids)),
        missing_references=tuple(sorted(set(missing_refs))),
    )
