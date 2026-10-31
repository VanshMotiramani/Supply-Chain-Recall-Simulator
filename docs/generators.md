# Synthetic Master Data Generation (Block 2)

## 1. Overview
The master-data generation subsystem (`src/supply_chain/generators/`) produces synthetic, referentially intact, deterministic master entities for the supply chain simulation:
- **Suppliers** (vendor profiles, material capabilities)
- **Products** (finished goods catalog, dosage forms, UOMs)
- **BOMs & BOM Lines** (formulation recipes and component quantities)
- **Warehouses** (regional storage and logistics hubs)
- **Customers** (hospitals, health systems, distributors)

No transactional records (raw lots, production orders, shipments, deliveries, recall cases) or injected anomalies (EC-1 through EC-4) are generated in this block.

---

## 2. Dependencies

| Library | Version | Purpose |
|---|---|---|
| `numpy` | `>=1.26.0` | Seeded random number generators via modern `default_rng` and `SeedSequence.spawn()`. |
| `faker` | `>=26.0.0` | Realistic descriptive entity names, locations, and simulated contact emails. |
| `python` standard library | `>=3.11` | Dataclasses, enums, dates, typing, and deterministic orchestration. |

> **ID Generation Rule:** Faker is never used to create business identifiers. All entity IDs are generated exclusively using `supply_chain.models.IDFactory`.

---

## 3. Seed Architecture & Determinism

Deterministic reproducibility is achieved through a multi-stream hierarchical seed design:

```
                      Root Seed (default: 20261022)
                                   │
                     np.random.SeedSequence(seed)
                                   │
              ┌─────────┬──────────┼──────────┬─────────┐
              ▼         ▼          ▼          ▼         ▼
           Child 0   Child 1    Child 2    Child 3   Child 4
              │         │          │          │         │
          Suppliers  Products     BOMs    Warehouses Customers
```

1. **Independent Subsystem Streams:** `SeedSequence.spawn(5)` generates five independent, statistically uncorrelated child seeds.
2. **Subsystem Isolation:** Adjusting parameters or counts for Warehouses will not perturb the generated data for Suppliers or Products.
3. **Explicit Faker Seeding:** Each Faker instance is seeded via `seed_instance()` using an integer drawn from that subsystem's dedicated generator stream.
4. **Byte-for-Byte Reproducibility:** Running generation twice with the same configuration and seed produces identical records.

---

## 4. Entity Counts & Configurations

Configured via `MasterDataConfig`:

| Entity | Default (Full Mode) | Starter Mode | Configurable? | Rationale |
|---|---|---|---|---|
| **Suppliers** | **500** | 50 | Yes | Fixed target from challenge brief (Requirement 5). |
| **Products** | 50 | 10 | Yes | Diverse coverage across 5 therapeutic dosage forms. |
| **BOMs** | 50 | 10 | Yes | 1:1 active approved BOM per product. |
| **BOM Lines** | ~175 (2–5 per BOM) | ~30 (2–4 per BOM) | Yes | Meaningful formulation complexity. |
| **Warehouses** | 10 | 3 | Yes | Multi-facility regional network to test transfers and inventory. |
| **Customers** | 200 | 20 | Yes | Recipient base for 20,000 downstream deliveries. |

---

## 5. Domain Rules & Realistic Packaging

### 5.1 Comprehensive Material Catalog
The catalog encompasses 13 standard material types with unambiguous units of measure:
- **Active & Chemical Raw Materials:** `ACTIVE_PHARMA_INGREDIENT` (KG), `STABILIZING_AGENT` (KG), `EXCIPIENT_BASE` (KG), `PURIFIED_SOLVENT` (LITER), `PRESERVATIVE_COMPOUND` (LITER).
- **Primary Containers & Closures:** `PRIMARY_GLASS_VIAL` (UNIT), `AMBER_GLASS_BOTTLE` (UNIT), `ALUMINUM_OINTMENT_TUBE` (UNIT), `METERED_AEROSOL_CANISTER` (UNIT), `STERILE_STOPPER` (UNIT), `ALUMINUM_SEAL` (UNIT).
- **Secondary & Tertiary Packaging:** `SECONDARY_CARTON` (UNIT), `LABEL_STOCK` (UNIT).

### 5.2 Dosage-Form Packaging Compatibility Mapping
Each product dosage form is mapped to realistic primary and closure packaging options:
- **Injectable Solution** (`VIAL`) $\rightarrow$ `PRIMARY_GLASS_VIAL`, `STERILE_STOPPER`, `ALUMINUM_SEAL`
- **Oral Suspension** (`BOTTLE`) $\rightarrow$ `AMBER_GLASS_BOTTLE`, `LABEL_STOCK`, `SECONDARY_CARTON`
- **Topical Ointment** (`TUBE`) $\rightarrow$ `ALUMINUM_OINTMENT_TUBE`, `LABEL_STOCK`, `SECONDARY_CARTON`
- **Ophthalmic Drops** (`BOTTLE`) $\rightarrow$ `AMBER_GLASS_BOTTLE`, `PRIMARY_GLASS_VIAL`, `LABEL_STOCK`
- **Inhalation Aerosol** (`CANISTER`) $\rightarrow$ `METERED_AEROSOL_CANISTER`, `ALUMINUM_SEAL`, `SECONDARY_CARTON`

### 5.3 Formulation Rules
1. **Mandatory Active Ingredient:** Every BOM includes `ACTIVE_PHARMA_INGREDIENT` at Line 1.
2. **Mandatory Dosage-Compatible Packaging:** Every BOM includes a compatible packaging component from the dosage form mapping at Line 2.
3. **Sampling Without Replacement:** Additional formulation components up to `num_lines` are sampled without replacement from remaining catalog materials.
4. **Configuration Bounds:** `min_lines_per_bom >= 2` (to fit API + packaging) and `max_lines_per_bom <= len(MATERIAL_TYPES)` (13) are validated at construction.

### 5.4 Active Supplier Coverage Guarantee
- The initial supplier cohort covering all catalog materials (`i < len(MATERIAL_TYPES)`) is guaranteed `SupplierStatus.ACTIVE` round-robin.
- In both starter (`50 >= 13`) and full (`500 >= 13`) modes, 100% of catalog materials are actively supplied.
- `generate_master_data` cross-checks required BOM materials against active suppliers, immediately raising a `ValueError` if a custom configuration cannot guarantee active supply.
