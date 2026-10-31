# Block 5: Recall Simulation Architecture & Traceability (Stages 1–2)

## 1. Overview & Scope

Block 5 establishes the deterministic recall simulation for the YottaFlex supply-chain challenge.
In Stages 1 and 2, we introduce the simulation foundations without yet injecting anomalies or triggering resolution services:
1. **Simulation Configuration and Data Structures** (`src/supply_chain/simulation/config.py`, `ground_truth.py`, `models.py`).
2. **Defensible Baseline Isolation Strategy** ensuring that baseline data from Blocks 2–4 remains 100% immutable and uncorrupted across all fields.
3. **Pure, Deterministic Traceability Algorithms** (`src/supply_chain/simulation/traceability.py`) enabling bidirectional genealogy traversals across suppliers, production orders, finished lots, deliveries, shipments, and customers.

---

## 2. Package Architecture

```
src/supply_chain/simulation/
├── __init__.py           # Unified exports for simulation package
├── config.py             # RecallSimulationConfig with validation and starter/full/clean presets
├── ground_truth.py       # AnomalyRecord, AnomalyType enum, GroundTruthRegistry
├── models.py             # DiscrepancyCategory, DiscrepancyFinding, DiscrepancyReport,
│                         # RecallMetricsResult, SimulationDataset, create_simulation_dataset
└── traceability.py       # Pure genealogy traversals (forward/backward) with missing-reference handling
```

---

## 3. Data Structures & Decoupled Reporting

### 3.1 Ground Truth vs. Detector Findings Separation & Metadata Immutability
A critical requirement is keeping **ground truth** (what was intentionally injected) strictly separated from **detector findings** (what automated audits and detectors discover):
- `GroundTruthRegistry` stores immutable `AnomalyRecord`s capturing `anomaly_id`, `edge_case_code` (`EC-1`..`EC-4`), `anomaly_type`, `target_entity_type`, `target_entity_id`, and `intended_quantity`.
- **Defensive Immutability of Metadata:** In `AnomalyRecord`, `metadata` is defensively copied on construction (`dict(raw_meta)`) and exposed as an immutable `types.MappingProxyType`. External mutations to the dictionary originally passed into the constructor cannot alter the record, and direct item assignment on `record.metadata` raises a `TypeError`.
- `DiscrepancyReport` aggregates immutable `DiscrepancyFinding`s categorized by `DiscrepancyCategory` (`BROKEN_FOREIGN_KEY`, `NEGATIVE_INVENTORY`, `OVER_SHIPMENT_VARIANCE`, `UNNOTIFIED_CUSTOMER`, `COMMERCIAL_EXPOSURE`, `INVENTORY_CONSERVATION_VARIANCE`).
- Decoupling these representations allows verification metrics (such as precision, recall, and F1 score) to compare findings against ground truth objectively.

### 3.2 Metrics Container
`RecallMetricsResult` encapsulates quantitative recall and audit results:
- `notification_coverage`: $\frac{\text{notified affected customers}}{\text{total affected customers}}$
- `quarantine_coverage`: $\frac{\text{quarantined affected finished stock}}{\text{total affected finished stock}}$
- `recovery_rate`: $\frac{\text{recovered customer units}}{\text{affected shipped units}}$
- `inventory_conservation_variance`: $\text{on\_hand} + \text{net\_shipped} + \text{disposed} - \text{produced}$
- `overshipment_discrepancy`: Excess units dispatched over legitimate availability.

---

## 4. Baseline Isolation Strategy & Proof

### 4.1 Threat Model
In subsequent stages, the recall simulation performs invasive state changes:
- Injecting anomalous consumption records referencing nonexistent raw lots (EC-1).
- Modifying delivery line quantities and forcing over-shipment movements into the inventory ledger (EC-2).
- Applying quarantine, recovery, and disposal inventory movements.
- Generating recall case headers and customer actions.

If these operations directly mutated the baseline `MasterDataset`, `ProductionDataset`, or `DistributionDataset`, the clean baseline would be corrupted, invalidating subsequent runs and comparisons.

### 4.2 Isolation Mechanism (`create_simulation_dataset`)
`create_simulation_dataset(master, production, distribution, config)` establishes clean isolation boundaries:
1. **Master Data (`MasterDataset`)**: Treated as read-only. Retained by reference as static catalog data.
2. **Production Metadata (`ProductionDataset`)**: Retained as reference, but transactional collections subject to mutation are isolated:
   - `lot_consumptions`: Shallow-copied into a fresh `list[LotConsumption | AnomalousLotConsumption]` so EC-1 can append anomalous consumption records without altering `production.lot_consumptions`.
3. **Distribution & Deliveries (`DistributionDataset`)**:
   - `deliveries`: Shallow-copied into a fresh `list[Delivery]` so EC-2 can modify `shipped_qty` or delivery statuses without touching `distribution.deliveries`.
   - `shipments` & `inventory_movements`: Copied into fresh lists.
   - `inventory_ledger`: **Deep-copied (`copy.deepcopy(dist.inventory_ledger)`)**. All ledger slot dictionaries (`_records`) and movement lists (`_movements`) are completely detached. Applying over-shipments with `allow_negative=True` or recall movements alters only the simulation ledger.

### 4.3 Automated Verification
In `tests/test_simulation_stage1_2.py::TestBaselineIsolation`, automated tests:
1. Snapshot **every single field** across all baseline entities:
   - All fields of all deliveries (`delivery_id`, `shipment_id`, `fin_lot_id`, `shipped_qty`, `status`, `delivered_date`, `created_at`, `updated_at`).
   - All fields of all shipments (`shipment_id`, `customer_id`, `warehouse_id`, `status`, `ship_date`, `created_at`, `updated_at`).
   - All fields of all consumptions (`wo_id`, `raw_lot_id`, `consumed_qty`, `created_at`).
   - All fields of all movements (`movement_id`, `warehouse_id`, `fin_lot_id`, `movement_type`, `quantity`, `reference_id`, `movement_date`, `created_at`).
   - Every warehouse/lot balance in `dist.inventory_ledger` across all 6 quantity components (`on_hand`, `available`, `quarantined`, `shipped`, `recovered`, `disposed`).
   - All recorded movements in the baseline ledger.
2. Create a `SimulationDataset`.
3. Apply aggressive mutations: mutate `delivery.shipped_qty += 50`, `delivery.status`, `delivery.delivered_date = None`, `shipment.status`, append `AnomalousLotConsumption`, mutate movement quantities, and apply a 99,999-unit over-shipment movement driving warehouse availability negative.
4. Verify with element-by-element equality that **100% of baseline entity fields, balances, and lists remain completely identical** to the pre-mutation snapshot.
5. In `test_traceability_calls_do_not_mutate_baseline_datasets`, verify that executing forward and backward traversals does not alter source dataset collections or records.

---

## 5. Pure Traceability Algorithms

All genealogy traversal functions in `src/supply_chain/simulation/traceability.py` are pure, read-only, deterministic functions returning frozen dataclasses with lexicographically sorted tuples.

### 5.1 Traversal Paths
1. **Forward from Raw Material Lot (`trace_forward_from_material_lot`)**:
   $$\text{MaterialLot} \xrightarrow{\text{LotConsumption}} \text{ProductionOrder} \xrightarrow{\text{FinishedLot.wo\_id}} \text{FinishedLot} \xrightarrow{\text{Delivery.fin\_lot\_id}} \text{Delivery} \xrightarrow{\text{Shipment.shipment\_id}} \text{Shipment} \to \text{Unique Customers}$$
2. **Forward from Finished Product Lot (`trace_forward_from_finished_lot`)**:
   $$\text{FinishedLot} \xrightarrow{\text{Delivery.fin\_lot\_id}} \text{Delivery} \xrightarrow{\text{Shipment.shipment\_id}} \text{Shipment} \to \text{Unique Customers}$$
3. **Backward from Delivery Line Item (`trace_backward_from_delivery`)**:
   $$\text{Delivery} \to \{\text{Shipment} \to \text{Customer}\} \ \& \ \{\text{FinishedLot} \to \text{ProductionOrder} \xrightarrow{\text{LotConsumption}} \text{MaterialLot} \to \text{Supplier}\}$$
4. **Backward from Finished Product Lot (`trace_backward_from_finished_lot`)**:
   $$\text{FinishedLot} \to \text{ProductionOrder} \xrightarrow{\text{LotConsumption}} \text{MaterialLot} \to \text{Supplier}$$

### 5.2 Determinism & Customer Deduplication
- Because multiple delivery lines on different shipments can go to the same customer, `affected_customer_ids` is deduplicated and sorted: `tuple(sorted(set(customer_ids)))`.
- All output collections (`production_order_ids`, `finished_lot_ids`, `delivery_ids`, `shipment_ids`, `raw_lot_ids`, `supplier_ids`) are guaranteed to be sorted tuples.

### 5.3 Context Resolution & Missing-Reference Policy
- **Context Extraction (`_resolve_trace_context`):**
  - Explicitly handles `ProductionDataset`, `DistributionDataset`, and `SimulationDataset`.
  - Passing a `SimulationDataset` automatically populates both production and distribution contexts.
  - Never silently passes a `DistributionDataset` into production slots or assumes matching attributes.
- **Backward Delivery Trace Contract (`trace_backward_from_delivery`):**
  - When provided with both `distribution` and `production` (or a `SimulationDataset`), resolves full bidirectional genealogy.
  - When called with a `DistributionDataset` and `production=None`, returns a documented partial trace: `delivery_id`, `shipment_id`, `customer_id`, and `fin_lot_id` are fully resolved from distribution data, while `wo_id`, `product_id`, `raw_lot_ids`, and `supplier_ids` are `None`/`()`, with `"Production dataset omitted: cannot resolve upstream genealogy for finished lot <id>"` captured in `missing_references`. Never raises `AttributeError`.
- **Dangling Foreign Keys (EC-1):**
  - If a consumption record references a nonexistent raw lot, the anomalous ID is still included in `raw_lot_ids` and reported in `missing_references` (`f"MaterialLot not found: {raw_lot_id}"`) without raising an unhandled exception.

---

## 6. Implementation Status & Next Stages

| Stage | Description | Status |
|---|---|---|
| **Stage 1** | Configuration, Ground Truth Registry, Discrepancy Models, Simulation Dataset | **COMPLETE** |
| **Stage 2** | Pure Traceability Functions (Forward & Backward Traversals, Deduplication) | **COMPLETE** |
| **Stage 3** | Anomaly Injectors (EC-1, EC-2, EC-3, EC-4) | *Pending (Stage 3)* |
| **Stage 4** | Anomaly & Discrepancy Detectors, Inventory Reconciliation Engine | *Pending (Stage 4)* |
| **Stage 5** | Recall Execution & Resolution Services (Quarantine, Recovery, Notifications) | *Pending (Stage 5)* |
| **Stage 6** | End-to-End Orchestrator, CLI Runner, & Verification Report | *Pending (Stage 6)* |
