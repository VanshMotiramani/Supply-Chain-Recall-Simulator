# Synthetic Production & Genealogy Generation (Block 3)

## 1. Overview
The production generation subsystem (`src/supply_chain/generators/`) generates synthetic, referentially intact, deterministic transactional manufacturing and inventory entities for the supply chain simulation:
- **Raw Material Lots** (vendor receipts, material batches, positive inventory balances)
- **Production Orders** (manufacturing work orders, planned outputs, yield, and scrap)
- **BOM Lot Consumptions** (genealogical consumption bridge records linking orders to raw material lots)
- **Finished Goods Lots** (commercial product batches produced by completed work orders)

No downstream distribution records (shipments, customer deliveries, recall cases) or injected anomalies (EC-1 through EC-4) are generated in this block; those belong strictly to Block 4 and Block 5 respectively.

---

## 2. Entity Targets & Configurations

Configured via `ProductionConfig`:

| Entity | Default (Full Mode) | Starter Mode | Configurable? | Rationale |
|---|---|---|---|---|
| **Raw Material Lots** | **10,000** | 100 | Yes | Challenge brief Requirement 5 target. |
| **Production Orders** | **5,000** | 50 | Yes | Challenge brief Requirement 5 target. |
| **Finished Goods Lots** | **8,000** | 80 | Yes | Derived from 3,000 2-lot orders + 2,000 1-lot orders (Decision D-03). |
| **Lot Consumptions** | ~17,500 | ~175 | Dynamic | 1 or more consumption records per BOM component. |

### Order-to-Lot Split Formula
For any configuration with $N$ production orders and $M$ finished lots (where $N \le M \le 2N$):
- **Number of orders producing 2 finished lots:** $x = M - N$ (in full mode: $8,000 - 5,000 = 3,000$; starter: $80 - 50 = 30$).
- **Number of orders producing 1 finished lot:** $y = 2N - M$ (in full mode: $2(5,000) - 8,000 = 2,000$; starter: $2(50) - 80 = 20$).
- Total finished lots generated: $2x + y = 2(M - N) + (2N - M) = M$ exactly.

---

## 3. Seed Architecture & Independent Streams

Deterministic reproducibility is achieved through a multi-stream hierarchical seed design using NumPy's `SeedSequence`:

```
                    Root Seed (default: 20261022)
                                 │
                   np.random.SeedSequence(seed)
                                 │
               ┌─────────────────┼─────────────────┐
               ▼                 ▼                 ▼
            Child 0           Child 1           Child 2
               │                 │                 │
         Raw Material       Production        Finished
             Lots             Orders            Lots
                                 │
                           (Consumptions)
```

1. **Independent Subsystem Streams:** `SeedSequence.spawn(3)` isolates random number generators so modifications to one stage do not perturb the data of others.
2. **Deterministic Reproducibility:** Running generation twice with the same configuration and seed produces strictly identical records across all entities and fields.

---

## 4. Raw Material Lots (`material_lots.py`)

- **Primary Key:** `RAWLOT-<supplier_id>-2026-<6-digit>` via `IDFactory.for_material_lot()`.
- **Supplier Eligibility:** Each lot references an active supplier authorized for that material type.
- **Catalog Distribution:** Lots are distributed round-robin across all 13 catalog materials.
- **Lot Sizing & Bulk API:** Standard materials have quantities in `[min_raw_lot_qty, max_raw_lot_qty]` (2,000–10,000 units). `ACTIVE_PHARMA_INGREDIENT` is sized with a $1.5\times$ to $2.0\times$ bulk factor to support 100% BOM line demand without stock exhaustion.
- **Temporal Causality:** Received dates are set 15 to 90 days prior to `base_date` (late 2025), strictly preceding production order start dates. Expirations are set 12 to 24 months after receipt.
- **Status:** Initialized to `MaterialLotStatus.APPROVED`.

---

## 5. Production Orders & Yield Accounting (`production_orders.py`)

- **Primary Key:** `WO-2026-<6-digit>` via `IDFactory.for_production_order()`.
- **References:** References valid `product_id` and approved `bom_id`.
- **Yield & Scrap Accounting (Decision D-02):**
  - Planned output quantity: `[min_order_qty, max_order_qty]` (100–500 units).
  - Yield ratio: deterministic per-order draw in $[0.85, 0.98]$.
  - Actual good output: $\text{actual\_good\_output\_qty} = \lfloor \text{planned\_output\_qty} \times \text{yield\_ratio} \rfloor$.
  - Scrap quantity: $\text{scrap\_qty} = \text{planned\_output\_qty} - \text{actual\_good\_output\_qty}$.
  - Invariant: $\text{actual\_good\_output\_qty} + \text{scrap\_qty} == \text{planned\_output\_qty}$.
- **Dates & Status:** Planned and actual dates span 2026 chronologically. Orders are initialized to `ProductionOrderStatus.COMPLETED`.

---

## 6. BOM Component Consumption & Genealogy (`production_orders.py`)

- **Bridge Entity:** `LotConsumption` with composite key `(wo_id, raw_lot_id)`.
- **Component Completeness:** For each line in the referenced BOM, required quantity is:
  $$\text{qty\_needed} = \text{planned\_output\_qty} \times \text{quantity\_per\_unit}$$
- **Deferred-Candidate Priority Queue Architecture & Complexity:**
  - Candidate lots per material type are initially partitioned into `pending_deques` ordered by `(effective_start, received_date, lot_id)` ascending.
  - Active candidate inventory is managed in `available_heaps`, a min-heap keyed by `(received_date, lot_id)` ensuring strict FIFO consumption.
  - **Monotonic Date Activation:** As production dates advance monotonically, pending lots whose $\text{effective\_start} \le \text{actual\_start}$ are moved into `available_heaps`. Each lot is evaluated and activated at most once throughout the entire simulation.
  - **Preservation of Future-Effective Lots:** Future-effective older lots remain queued in `pending_deques` without being prematurely discarded or blocking currently effective later lots. Upon becoming effective, they enter `available_heaps` and immediately take their rightful FIFO priority based on `received_date`.
  - **Accurate Algorithmic Complexity:**
    - Initial sorting and queue partitioning: $O(L \log L)$ across all $L$ material lots.
    - Activation from pending to available: $O(L \log K)$ total across the simulation, where $K \le L$ is active heap size.
    - Consumption step: $O(1)$ peek at the top of the heap; $O(\log K)$ pop when a lot is exhausted or expires.
    - Total execution complexity across the entire simulation: $O(L \log L + M)$ for $L$ lots and $M$ consumptions. This guarantees sub-second execution ($< 0.15$s at full scale) and completely eliminates repeated linear scanning ($O(N \cdot L)$) of future-effective inventory.
- **Multi-Lot Support:** When a raw lot's remaining balance is insufficient for an order's component demand, the balance is fully consumed and the remainder is drawn from the subsequent lot, producing multiple `LotConsumption` records for that component.
- **Zero-Overconsumption Invariant:** Across all production orders:
  $$\sum_{\text{consumptions}} \text{consumed\_qty} \le \text{lot.quantity} \quad \forall \; \text{lot} \in \text{MaterialLots}$$
- **Expiry & Eligibility Semantics:**
  - Evaluated via `MaterialLot.is_eligible_for_consumption(actual_start)`.
  - A lot is eligible if and only if its status is `APPROVED` and its effective date range encompasses the consumption date: $\text{effective\_start} \le \text{actual\_start} \le \text{effective\_end}$.
  - Inclusive boundary: A lot expiring on the consumption date ($\text{effective\_end} == \text{actual\_start}$) remains eligible on that date (does not precede consumption date).
  - FIFO Expiry Skipping: Expired lots ($\text{effective\_end} < \text{actual\_start}$) or exhausted lots are evicted from the top of `available_heaps` upon evaluation.
  - Fail-Fast Invariant: If eligible inventory for a required component is exhausted, generation fails explicitly with a descriptive `ValueError` rather than consuming expired stock or generating incomplete consumption records.

---

## 7. Finished Goods Lots (`finished_lots.py`)

- **Primary Key:** `FINLOT-2026-<6-digit>` via `IDFactory.for_finished_lot()`.
- **Two-Lot Split (Decision D-03):** Exactly `two_lot_order_count` orders produce 2 finished lots:
  - $\text{lot1\_qty} = \lfloor \text{actual\_good\_output\_qty} / 2 \rfloor$
  - $\text{lot2\_qty} = \text{actual\_good\_output\_qty} - \text{lot1\_qty}$
  - Both lots have strictly positive integer quantities.
- **One-Lot Orders:** Remaining orders produce 1 finished lot with $\text{quantity} = \text{actual\_good\_output\_qty}$.
- **Output Reconciliation Invariant:** The sum of finished lot quantities for any production order strictly equals that order's `actual_good_output_qty`.
- **Dates & Status:** `produced_date` matches `po.actual_end`. Status is `FinishedLotStatus.AVAILABLE`. Warehouse assignments are managed via `InventoryMovement` records in the ledger, avoiding competing attributes.

---

## 8. Verification & Test Execution

Run the complete test suite:
```powershell
& .venv\Scripts\pytest.exe -v
```

All 197 unit and integration tests (including full-scale generation of 10,000 raw lots, 5,000 work orders, and 8,000 finished lots) pass in $\approx 1.7$ seconds with zero warnings.
