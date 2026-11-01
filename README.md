# Supply-Chain Traceability & Recall Simulation

A deterministic, high-integrity supply-chain simulation engine modeling multi-echelon pharmaceutical manufacturing, batch genealogy, warehouse inventory movements, and downstream customer distribution.

---

## 1. Project Purpose

The Supply-Chain Recall Simulator provides an authoritative, referenceable domain model and data pipeline designed to simulate end-to-end pharmaceutical traceability:
- **Upstream Provenance:** Active suppliers and raw material lots (`RAWLOT-...`) with expiration boundaries and catalog compatibility.
- **Manufacturing Execution:** Work orders (`WO-2026-...`) with deterministic yield and scrap accounting, bill of materials (BOM) lot consumption records, and finished goods lots (`FINLOT-2026-...`).
- **Downstream Logistics:** Outbound multi-line shipments (`SHP-2026-...`), customer delivery records (`DEL-2026-...`), and active customer facilities (`CUST-...`).
- **Double-Entry Inventory Ledger:** Authoritative stock tracking (`InventoryLedger` and `InventoryMovement`) enforcing physical on-hand, quarantined, available, and shipped balances across warehouse facilities (`WHS-...`).
- **Simulation & Pure Traceability:** Isolated runtime simulation datasets (`SimulationDataset`), deeply immutable ground truth registry (`GroundTruthRegistry`), and pure, read-only bidirectional genealogy traversals across suppliers, production orders, finished lots, shipments, and customers.

> **Note on Data and Notifications:** All entities, batches, and transactions are purely synthetic, generated deterministically from seeded pseudo-random streams. Notification channels (`EMAIL`, `SMS`, `EDI`, `PORTAL`) and actions in the domain model represent simulated state tracking only; no real external networks or messaging providers are contacted.

---

## 2. Implementation Status

| Milestone | Scope / Module | Status | Verified Test Count |
|---|---|---|---|
| **Block 1** | Domain Models, Enums, ID Factory, Lifecycle FSM, Inventory Ledger | **Complete** | 152 passed |
| **Block 2** | Master Data Generators (Suppliers, Products, BOMs, Warehouses, Customers) | **Complete** | 23 passed |
| **Block 3** | Production Orders, Yield Accounting, Raw Lots, Finished Lots, Expiry Queues | **Complete** | 22 passed |
| **Block 4** | Downstream Distribution, Multi-Line Shipments, Deliveries, Inventory Tracking | **Complete** | 36 passed |
| **Block 5 (Stages 1–2)** | Simulation Config, Ground Truth Registry, Baseline Isolation, Pure Traceability | **Complete** | 23 passed (focused local run) |
| **Block 5 (Stages 3–6)** | Anomaly Injection (EC-1 to EC-4), Discrepancy Detectors, Recall Resolution, Metrics | **Pending** | *Scheduled next* |

> **Current Boundary:** Block 5 Stages 1 and 2 are complete (providing configuration, deeply immutable ground truth registry, baseline isolation containers, and pure bidirectional traceability functions). Recall anomaly injection (EC-1 through EC-4), automated discrepancy detection, quarantine remediation, and recall KPI metrics are not yet implemented and will be delivered in Stages 3–6.

---

## 3. Scale Targets and Seed Configuration

All generators use deterministic pseudo-random number streams governed by root seed `20261022` (NumPy `SeedSequence`).

| Entity / Dimension | Starter Mode (`--mode starter`) | Full Mode (`--mode full`) | Configuration Source |
|---|---|---|---|
| **Root Seed** | `20261022` | `20261022` | `MasterDataConfig.seed` |
| **Suppliers** | 50 | 500 | `MasterDataConfig.supplier_count` |
| **Products (Dosage Forms)** | 10 | 50 | `MasterDataConfig.product_count` |
| **Warehouses** | 3 | 10 | `MasterDataConfig.warehouse_count` |
| **Customers** | 20 | 200 | `MasterDataConfig.customer_count` |
| **Raw Material Lots** | 100 | 10,000 | `ProductionConfig.raw_lot_count` |
| **Production Orders** | 50 | 5,000 | `ProductionConfig.production_order_count` |
| **Finished Goods Lots** | 80 | 8,000 | `ProductionConfig.finished_lot_count` |
| **Customer Deliveries** | 200 | 20,000 | `DistributionConfig.delivery_count` |
| **Inventory Movements** | 280 | 28,000 | Receipts (8k) + Shipments (20k) |

---

## 4. Environment Setup

### Prerequisites
- Python `>= 3.11` (tested on Python 3.15.2)
- Git

### Installation
Clone or navigate to the repository directory and set up a virtual environment:

```powershell
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate virtual environment (Linux/macOS)
# source .venv/bin/activate

# Install package in editable mode with development dependencies
pip install -e ".[dev]"
```

Alternatively, on environments with GNU `make`:
```bash
make install
```

---

## 5. Running the Test Suite

The test suite validates data models, lifecycle transitions, ID formatting, FIFO allocation, inventory reconciliation, deterministic reproducibility, deep baseline isolation, and pure genealogy traversals:

```powershell
# Run the complete test suite (last completed full-suite run: 255 passed; full suite has not been rerun for the 256th test)
pytest

# Run with verbose output
pytest -v

# Run targeted test modules:
pytest tests/test_simulation_stage1_2.py -v       # Block 5 Stage 1–2 simulation & traceability tests (23 passed in focused local run)
pytest tests/test_distribution_generation.py -v   # Block 4 distribution tests (36 tests)
pytest tests/test_production_generation.py -v     # Block 3 production tests (22 tests)
pytest tests/test_generators.py -v                # Block 2 master data tests (23 tests)
pytest tests/test_inventory.py -v                 # Block 1 ledger accounting tests (11 tests)
pytest tests/test_entities.py -v                  # Block 1 entity validation tests (78 tests)
pytest tests/test_enums.py -v                     # Block 1 enum and lifecycle tests (45 tests)
pytest tests/test_id_factory.py -v                # Block 1 ID factory tests (18 tests)
```

---

## 6. Architecture & Documentation Links

The system is structured as modular, cohesive layers:

```
src/supply_chain/
├── models/             # Domain entities, enums, ledger, lifecycle rules, ID factory
│   ├── enums/          # Status enums (material lot, production, shipment, recall, audit)
│   ├── inventory.py    # Authoritative InventoryLedger and InventoryMovement models
│   └── id_factory.py   # Zero-padded deterministic business ID generator
├── generators/         # Deterministic synthetic data generation pipeline
│   ├── master.py       # Master data orchestrator (suppliers, products, BOMs, warehouses, customers)
│   ├── production_pipeline.py # Manufacturing orders, raw lots, yield accounting, finished lots
│   ├── distribution.py # Warehouse placement, shipments, customer deliveries, ledger movements
│   └── config.py       # Configuration containers and dataset dataclasses
└── simulation/         # Recall simulation runtime, ground truth, baseline isolation, and pure traceability (Block 5 Stages 1–2)
    ├── config.py       # RecallSimulationConfig
    ├── ground_truth.py # AnomalyRecord (deeply immutable metadata) and GroundTruthRegistry
    ├── models.py       # SimulationDataset, create_simulation_dataset, DiscrepancyReport
    └── traceability.py # Pure, read-only forward and backward genealogy traversals
```

For detailed specifications and architectural documentation, see:
- [`Requirement Analysis.pdf`](Requirement%20Analysis.pdf): Formal 26-page system requirement analysis and business rules.
- [`docs/recall-simulation.md`](docs/recall-simulation.md): Recall simulation architecture, deeply immutable ground truth registry, baseline isolation proof, and pure genealogy algorithms.
- [`docs/generators.md`](docs/generators.md): Master data catalog, supplier assignment, and dosage-form BOM composition.
- [`docs/production-generation.md`](docs/production-generation.md): Production orders, yield/scrap formulas, and FIFO raw material expiry allocation.
- [`docs/distribution-generation.md`](docs/distribution-generation.md): Downstream distribution, delivery line items, and authoritative inventory accounting.
- [`docs/ai-assistance-log.md`](docs/ai-assistance-log.md): Disclosure of AI-assisted engineering, prompt records, human reviews, and testing outcomes.
