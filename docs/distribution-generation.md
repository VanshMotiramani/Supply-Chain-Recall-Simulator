# Synthetic Downstream Distribution & Inventory Tracking (Block 4)

## 1. Overview
The downstream distribution generation subsystem (`src/supply_chain/generators/distribution.py`) connects manufacturing outputs to warehouses, outbound shipments, customer deliveries, and authoritative inventory ledger movements:
- **Warehouse Receipt Placement:** Initial physical placement of manufactured finished lots into active warehouses via `MovementType.RECEIPT` inventory movements.
- **Outbound Shipments (`Shipment`):** Logistics dispatch records fulfilled from a specific warehouse to an active customer.
- **Customer Deliveries (`Delivery`):** Multi-line delivery line items linking finished goods lots to shipments and customers.
- **Authoritative Inventory Tracking (`InventoryLedger` & `InventoryMovement`):** Real-time physical on-hand, available, and shipped balances reconciled deterministically with zero negative inventory and no overshipments.

No injected anomalies (EC-1 through EC-4) or recall simulation actions are present in this clean baseline dataset; those belong strictly to Block 5.

---

## 2. Entity Targets & Configurations

Configured via `DistributionConfig`:

| Entity | Default (Full Mode) | Starter Mode | Configurable? | Rationale |
|---|---|---|---|---|
| **Deliveries** | **20,000** | 200 | Yes | Challenge brief Requirement 5 target. |
| **Shipments** | ~8,000 | ~80 | Dynamic | Grouped multi-line shipments (1 to 4 delivery lines per shipment). |
| **Inventory Movements** | **28,000** | 280 | Dynamic | Exactly `len(finished_lots)` receipts + `len(deliveries)` shipments. |
| **Inventory Ledger** | 1 (in-memory) | 1 (in-memory) | Yes | Authoritative source of truth for all warehouse inventory balances. |

### Configuration Bounds
```python
DistributionConfig(
    seed=20261022,
    delivery_count=20_000,
    min_delivery_qty=10,
    max_delivery_qty=40,
    min_lines_per_shipment=1,
    max_lines_per_shipment=4,
    base_date=date(2026, 1, 1),
)
```

- **Starter mode:** `DistributionConfig.for_starter()` generates 200 delivery records across ~80 shipments and 280 inventory movements for fast unit testing.
- **Full mode:** `DistributionConfig.for_full()` generates exactly 20,000 deliveries across ~7,978 shipments and 28,000 inventory movements (measured at ~18.1s generator-only runtime on Python 3.15 Windows environment; Section 8 reports automated pytest suite runtimes).

---

## 3. Delivery Quantity Semantics & Accounting Boundaries

### Clean-Baseline Assumption & Schema Limitations
1. **Full Delivery of Shipped Units:** In the clean baseline, every dispatched unit is received in full by the customer. When `Delivery.status == DeliveryStatus.DELIVERED`, the entire `shipped_qty` has been successfully delivered on `delivered_date`.
2. **Schema Design Note:** The domain model intentionally does not define a separate `delivered_qty` field on `Delivery`. The schema cannot represent partial delivery line items.
3. **No Conflation of Distinct Quantity Concepts:**
   - **Shipped Quantity:** Units dispatched from a warehouse under a `Shipment` (`InventoryMovement` of type `SHIPMENT`).
   - **Delivered Quantity:** Units confirmed received at customer facilities (`shipped_qty` under `DELIVERED` status).
   - **Recovered Quantity:** Units returned from customers into quarantine during a recall. Recovery quantities are **strictly tracked via `InventoryMovement` records of type `MovementType.RECOVERY`** applied to `InventoryLedger` and `RecallAction`, **never inferred from `Delivery.status`**. Setting a delivery status to `RECALLED` does not alter ledger balances.
   - **Quarantined Quantity:** Physical stock held under isolation in a warehouse.
   - **Disposed Quantity:** Units condemned and destroyed from quarantine.

---

## 4. Seed Architecture & Independent RNG Streams

Deterministic reproducibility is achieved through NumPy's `SeedSequence`:

```
                 DistributionConfig.seed (default: 20261022)
                                      │
                         np.random.SeedSequence(seed)
                                      │
                     ┌────────────────┴────────────────┐
                     ▼                                 ▼
                  Child 0                           Child 1
                     │                                 │
             Receipt Placement                 Outbound Dispatch
          (Warehouse Allocation)           (Shipments & Deliveries)
```

1. **Independent Subsystem Streams:** `SeedSequence.spawn(2)` isolates random number streams for receipt allocation and dispatch logic. Downstream field additions or dispatch adjustments do not perturb upstream placement.
2. **Deterministic Reproducibility:** Repeated execution with identical configurations and seeds yields strictly identical business keys, timestamps, quantities, and balances across complete canonical records.

---

## 5. Warehouse Inventory & Ledger Accounting

All stock movements and balance evaluations are governed authoritatively by `InventoryLedger` (`src/supply_chain/models/inventory.py`):

### 1. Initial Receipt Placement
- Each finished lot produced in Block 3 is assigned to an active warehouse via an `InventoryMovement` of type `MovementType.RECEIPT`.
- **Reference:** References the source production order `wo_id`.
- **Date:** Set to the lot's production completion date `fin_lot.produced_date`.
- **Quantity:** Matches the total good output quantity `fin_lot.quantity`.

### 2. Outbound Dispatch
- For each delivery line item dispatched to a customer, an `InventoryMovement` of type `MovementType.SHIPMENT` is recorded.
- **Reference:** References the outbound shipment `shipment_id`.
- **Date:** Matches the shipment dispatch date `shipment.ship_date`.
- **Quantity:** Matches the delivery line item quantity `delivery.shipped_qty`.
- **1-to-1 Movement Integrity:** Every `MovementType.SHIPMENT` inventory movement matches exactly one delivery line's lot (`fin_lot_id`), quantity (`shipped_qty`), warehouse (`shipment.warehouse_id`), and shipment reference (`shipment_id`).

### 3. Inventory Formulas and Conservation Invariants
For every `(warehouse_id, fin_lot_id)` pair:
- **Physical On-Hand:**
  $$\text{on\_hand\_qty} = \text{RECEIPT} - \text{SHIPMENT}$$
- **Available Quantity:**
  $$\text{available\_qty} = \text{on\_hand\_qty} - \text{quarantined\_qty}$$
  *(In clean baseline, $\text{quarantined\_qty} = 0$, so $\text{available\_qty} == \text{on\_hand\_qty}$.)*
- **Shipped Quantity:**
  $$\text{shipped\_qty} = \text{SHIPMENT}$$
- **Conservation Invariant:**
  $$\text{on\_hand\_qty} + \text{shipped\_qty} == \text{fin\_lot.quantity}$$
  $$\text{available\_qty} \ge 0$$

All ledger mutations are applied with `allow_negative=False`. Any attempt to over-allocate or over-ship immediately raises a descriptive `ValueError`.

---

## 6. Shipments, Deliveries, and Line-Count Rules

- **Multi-Line Shipments:** Shipments consolidate 1 to 4 delivery line items (`min_lines_per_shipment=1`, `max_lines_per_shipment=4`). All lines within a shipment originate from the same fulfilling warehouse and serve the same customer.
- **Line Count Rule:**
  - Every non-final shipment has line count within `[min_lines_per_shipment, max_lines_per_shipment]`.
  - **Final Shipment Exception:** When the remaining delivery count is strictly less than `min_lines_per_shipment`, the final shipment is sized to exactly `remaining` lines to hit the target delivery count without overshooting.
- **Customer & Warehouse Eligibility:** Shipments only originate from warehouses with `status == WarehouseStatus.ACTIVE` and dispatch only to customers with `status == CustomerStatus.ACTIVE`.
- **Primary Key Patterns:**
  - `Shipment`: `SHP-2026-<6-digit>` via `IDFactory.for_shipment()`.
  - `Delivery`: `DEL-2026-<6-digit>` via `IDFactory.for_delivery()`.
  - `InventoryMovement`: `INV-<6-digit>` via `IDFactory.for_inventory_movement()`.
- **Chronological Causality:**
  - $\text{fin\_lot.produced\_date} == \text{warehouse\_receipt\_date}$
  - $\text{shipment.ship\_date} = \max(\text{line\_ready\_dates}) > \text{fin\_lot.produced\_date}$ (1 to 7 days dispatch delay)
  - $\text{delivery.delivered\_date} = \text{shipment.ship\_date} + \text{transit\_days}$ (1 to 3 days transit time)
  - Guaranteed invariant: $\text{fin\_lot.produced\_date} < \text{shipment.ship\_date} \le \text{delivery.delivered\_date}$.
- **Status Consistency:**
  - `Shipment`: `ShipmentStatus.DELIVERED`
  - `Delivery`: `DeliveryStatus.DELIVERED` with verified non-null `delivered_date`.

---

## 7. Bidirectional Traceability / Genealogy

Block 4 closes the complete end-to-end supply chain graph:

### Backward Trace (Customer Delivery $\to$ Upstream Supplier)
1. **Delivery:** `DEL-2026-XXXXXX` references `fin_lot_id`.
2. **FinishedLot:** `FINLOT-2026-XXXXXX` references `wo_id`.
3. **ProductionOrder:** `WO-2026-XXXXXX` references consumed raw material lots via `LotConsumption` records.
4. **LotConsumption:** References `raw_lot_id`.
5. **MaterialLot:** `RAWLOT-SUP-XXXXXX-2026-XXXXXX` references `supplier_id`.
6. **Supplier:** `SUP-XXXXXX` active master vendor record.

### Forward Trace (Finished Lot $\to$ Customer)
1. **FinishedLot:** `FINLOT-2026-XXXXXX`.
2. **Delivery:** All deliveries where `fin_lot_id == lot.fin_lot_id`.
3. **Shipment:** Deliveries reference `shipment_id`.
4. **Customer:** Shipments reference `customer_id`.

---

## 8. Verification & Test Execution

Run the complete test suite including Block 1, Block 2, Block 3, and Block 4:

```powershell
& .venv\Scripts\pytest.exe -v
```

### Verified Test Results
- **Total Tests Passing:** **233 passed** (197 upstream + 36 Block 4 tests)
- **Block 4 Distribution Tests:** **36 passed**
- **Full Suite Execution Time:** ~18.42 seconds
- **Block 4 Standalone Execution Time:** ~16.20 seconds
- **Failures / Warnings:** **0 failures, 0 warnings**
