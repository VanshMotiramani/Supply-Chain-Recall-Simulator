"""
test_generators.py — Comprehensive tests for synthetic master-data generation.

Coverage:
  - Catalog consistency: all packaging types exist in catalog with valid UOMs.
  - Default supplier count is exactly 500.
  - Configurable counts for products, warehouses, customers.
  - Correct ID formats and global uniqueness per entity type.
  - Foreign-key integrity between Product, BOM, and BOMLine.
  - Meaningful BOM composition: mandatory active ingredient + dosage-compatible packaging.
  - Packaging realism for bottles, ointment tubes, and aerosol canisters.
  - No BOM contains duplicate material types.
  - BOM line counts strictly respect configured [min_lines_per_bom, max_lines_per_bom].
  - Configuration limits validation (min < 2, max < min, max > catalog size).
  - Active supplier coverage guarantee across all required BOM material types.
  - Early failure when custom supplier count cannot satisfy active supply coverage.
  - Deterministic reproducibility across independent runs with identical seed.
  - Different seeds generate distinct descriptive data.
"""

import pytest

from supply_chain.generators import (
    ACTIVE_INGREDIENT_MATERIAL,
    DOSAGE_FORM_PACKAGING,
    MATERIAL_TYPES,
    MATERIAL_UOMS,
    PACKAGING_MATERIAL_TYPES,
    PRODUCT_CATALOG,
    MasterDataConfig,
    generate_master_data,
)
from supply_chain.models import validate_id
from supply_chain.models.enums import (
    BOMStatus,
    CustomerStatus,
    ProductStatus,
    SupplierStatus,
    WarehouseStatus,
)


class TestCatalogConsistency:
    """Verify integrity, completeness, and consistency of the shared material catalog."""

    def test_all_packaging_types_exist_in_material_types(self):
        """Every entry in PACKAGING_MATERIAL_TYPES must exist in MATERIAL_TYPES."""
        for pkg_type in PACKAGING_MATERIAL_TYPES:
            assert pkg_type in MATERIAL_TYPES, f"{pkg_type} missing from MATERIAL_TYPES"

    def test_dosage_form_mapping_integrity(self):
        """Every packaging material in DOSAGE_FORM_PACKAGING must be in the packaging and material catalog."""
        product_types = {p["type"] for p in PRODUCT_CATALOG}
        assert set(DOSAGE_FORM_PACKAGING.keys()) == product_types

        for dosage_form, pkg_options in DOSAGE_FORM_PACKAGING.items():
            assert len(pkg_options) >= 1, f"No packaging options defined for {dosage_form}"
            for pkg in pkg_options:
                assert pkg in PACKAGING_MATERIAL_TYPES, (
                    f"Packaging option {pkg} for {dosage_form} missing from PACKAGING_MATERIAL_TYPES"
                )
                assert pkg in MATERIAL_TYPES, (
                    f"Packaging option {pkg} for {dosage_form} missing from MATERIAL_TYPES"
                )

    def test_all_materials_have_valid_uom(self):
        """Every material type in the catalog must have an associated non-empty unit of measure."""
        for mat_type in MATERIAL_TYPES:
            assert mat_type in MATERIAL_UOMS, f"Missing UOM for {mat_type}"
            uom = MATERIAL_UOMS[mat_type]
            assert isinstance(uom, str) and len(uom.strip()) > 0

    def test_active_ingredient_in_catalog(self):
        """Active ingredient must exist in catalog and not be classified as packaging."""
        assert ACTIVE_INGREDIENT_MATERIAL in MATERIAL_TYPES
        assert ACTIVE_INGREDIENT_MATERIAL not in PACKAGING_MATERIAL_TYPES

    def test_specific_dosage_form_packaging_realism(self):
        """Verify dedicated packaging materials exist for bottles, tubes, canisters, and vials."""
        assert "AMBER_GLASS_BOTTLE" in DOSAGE_FORM_PACKAGING["ORAL_SUSPENSION"]
        assert "ALUMINUM_OINTMENT_TUBE" in DOSAGE_FORM_PACKAGING["TOPICAL_OINTMENT"]
        assert "METERED_AEROSOL_CANISTER" in DOSAGE_FORM_PACKAGING["INHALATION_AEROSOL"]
        assert "PRIMARY_GLASS_VIAL" in DOSAGE_FORM_PACKAGING["INJECTABLE_SOLUTION"]


class TestMasterDataCounts:
    """Verify default and configurable entity counts."""

    def test_default_full_counts(self):
        """Default config must produce exactly 500 suppliers."""
        cfg = MasterDataConfig.for_full(seed=20261022)
        dataset = generate_master_data(cfg)

        assert len(dataset.suppliers) == 500
        assert len(dataset.products) == 50
        assert len(dataset.boms) == 50
        assert len(dataset.warehouses) == 10
        assert len(dataset.customers) == 200
        assert len(dataset.bom_lines) >= 50 * 2

    def test_starter_counts(self):
        """Starter config produces scaled-down counts for fast execution."""
        cfg = MasterDataConfig.for_starter(seed=20261022)
        dataset = generate_master_data(cfg)

        assert len(dataset.suppliers) == 50
        assert len(dataset.products) == 10
        assert len(dataset.boms) == 10
        assert len(dataset.warehouses) == 3
        assert len(dataset.customers) == 20

    def test_custom_configurable_counts(self):
        """Custom configuration must be honored precisely."""
        cfg = MasterDataConfig(
            supplier_count=25,
            product_count=8,
            warehouse_count=4,
            customer_count=15,
            min_lines_per_bom=3,
            max_lines_per_bom=3,
        )
        dataset = generate_master_data(cfg)

        assert len(dataset.suppliers) == 25
        assert len(dataset.products) == 8
        assert len(dataset.boms) == 8
        assert len(dataset.bom_lines) == 8 * 3
        assert len(dataset.warehouses) == 4
        assert len(dataset.customers) == 15


class TestIDFormatsAndUniqueness:
    """Verify that all generated IDs follow IDFactory patterns and are globally unique."""

    def test_id_validity_and_uniqueness(self):
        cfg = MasterDataConfig.for_starter(seed=20261022)
        dataset = generate_master_data(cfg)

        # Suppliers
        sup_ids = [s.supplier_id for s in dataset.suppliers]
        assert len(sup_ids) == len(set(sup_ids))
        assert all(validate_id("Supplier", sid) for sid in sup_ids)
        assert sup_ids[0] == "SUP-000001"

        # Products
        prod_ids = [p.product_id for p in dataset.products]
        assert len(prod_ids) == len(set(prod_ids))
        assert all(validate_id("Product", pid) for pid in prod_ids)
        assert prod_ids[0] == "PROD-000001"

        # BOMs
        bom_ids = [b.bom_id for b in dataset.boms]
        assert len(bom_ids) == len(set(bom_ids))
        assert all(validate_id("BOM", bid) for bid in bom_ids)
        assert bom_ids[0] == "BOM-000001"

        # Warehouses
        whs_ids = [w.warehouse_id for w in dataset.warehouses]
        assert len(whs_ids) == len(set(whs_ids))
        assert all(validate_id("Warehouse", wid) for wid in whs_ids)
        assert whs_ids[0] == "WHS-000001"

        # Customers
        cust_ids = [c.customer_id for c in dataset.customers]
        assert len(cust_ids) == len(set(cust_ids))
        assert all(validate_id("Customer", cid) for cid in cust_ids)
        assert cust_ids[0] == "CUST-000001"


class TestBOMCompositionAndCompatibility:
    """Verify meaningful BOM composition, formulation rules, and supplier coverage."""

    def test_every_bom_has_active_ingredient_and_compatible_packaging(self):
        """Every BOM must have at least one API and one dosage-compatible packaging component."""
        cfg = MasterDataConfig.for_starter(seed=20261022)
        dataset = generate_master_data(cfg)

        prod_by_id = {p.product_id: p for p in dataset.products}

        for bom in dataset.boms:
            prod = prod_by_id[bom.product_id]
            lines = [bl for bl in dataset.bom_lines if bl.bom_id == bom.bom_id]
            materials = {bl.material_type for bl in lines}

            # 1. Mandatory active ingredient check
            assert ACTIVE_INGREDIENT_MATERIAL in materials, (
                f"BOM {bom.bom_id} for product {prod.product_id} lacks mandatory {ACTIVE_INGREDIENT_MATERIAL}"
            )

            # 2. Mandatory packaging check matching product dosage form
            expected_packaging_candidates = set(DOSAGE_FORM_PACKAGING[prod.product_type])
            packaging_present = materials.intersection(expected_packaging_candidates)
            assert len(packaging_present) >= 1, (
                f"BOM {bom.bom_id} for {prod.product_type} has no compatible packaging "
                f"from {expected_packaging_candidates}; materials present: {materials}"
            )

    def test_bom_line_counts_and_uniqueness(self):
        """Verify that line counts fall in range and contain no duplicate material types."""
        cfg = MasterDataConfig(
            supplier_count=50,
            product_count=10,
            min_lines_per_bom=3,
            max_lines_per_bom=5,
        )
        dataset = generate_master_data(cfg)

        for bom in dataset.boms:
            lines = [bl for bl in dataset.bom_lines if bl.bom_id == bom.bom_id]
            assert cfg.min_lines_per_bom <= len(lines) <= cfg.max_lines_per_bom

            # Line numbers are strictly 1..N
            line_numbers = [l.line_no for l in lines]
            assert line_numbers == list(range(1, len(lines) + 1))

            # No duplicate materials within the same BOM
            materials = [l.material_type for l in lines]
            assert len(materials) == len(set(materials))

    def test_active_supplier_coverage_guarantee(self):
        """Every material type required by any BOM must have at least one ACTIVE supplier."""
        # Test full mode
        cfg_full = MasterDataConfig.for_full(seed=20261022)
        d_full = generate_master_data(cfg_full)

        active_materials_full = {
            m for s in d_full.suppliers if s.status == SupplierStatus.ACTIVE for m in s.material_types
        }
        required_materials_full = {bl.material_type for bl in d_full.bom_lines}
        assert required_materials_full.issubset(active_materials_full)

        # Test starter mode
        cfg_starter = MasterDataConfig.for_starter(seed=20261022)
        d_starter = generate_master_data(cfg_starter)

        active_materials_starter = {
            m for s in d_starter.suppliers if s.status == SupplierStatus.ACTIVE for m in s.material_types
        }
        required_materials_starter = {bl.material_type for bl in d_starter.bom_lines}
        assert required_materials_starter.issubset(active_materials_starter)

    def test_insufficient_supplier_count_fails_coverage_invariant(self):
        """A configuration with too few suppliers to cover all BOM requirements fails early."""
        cfg_bad = MasterDataConfig(
            supplier_count=1,  # 1 supplier cannot cover all required BOM components
            product_count=5,
            min_lines_per_bom=4,
            max_lines_per_bom=4,
        )
        with pytest.raises(ValueError, match="Active supplier coverage invariant violated"):
            generate_master_data(cfg_bad)


class TestEntityValidationAndDates:
    """Verify date constraints and lifecycle status enums."""

    def test_statuses_and_dates(self):
        cfg = MasterDataConfig.for_starter(seed=20261022)
        dataset = generate_master_data(cfg)

        # Suppliers
        for s in dataset.suppliers:
            assert isinstance(s.status, SupplierStatus)
            assert s.effective_start <= cfg.base_date
            if s.effective_end is not None:
                assert s.effective_end >= s.effective_start

        # Products
        for p in dataset.products:
            assert isinstance(p.status, ProductStatus)
            assert p.created_at.date() <= cfg.base_date

        # BOMs
        for b in dataset.boms:
            assert b.status == BOMStatus.APPROVED
            assert b.version == 1

        # Warehouses
        for w in dataset.warehouses:
            assert w.status == WarehouseStatus.ACTIVE

        # Customers
        for c in dataset.customers:
            assert isinstance(c.status, CustomerStatus)


class TestReproducibility:
    """Verify deterministic generation and seed sensitivity."""

    def test_two_identical_runs_produce_identical_records(self):
        cfg1 = MasterDataConfig.for_starter(seed=20261022)
        cfg2 = MasterDataConfig.for_starter(seed=20261022)

        d1 = generate_master_data(cfg1)
        d2 = generate_master_data(cfg2)

        # Suppliers
        assert len(d1.suppliers) == len(d2.suppliers)
        for s1, s2 in zip(d1.suppliers, d2.suppliers):
            assert s1.supplier_id == s2.supplier_id
            assert s1.supplier_name == s2.supplier_name
            assert s1.material_types == s2.material_types
            assert s1.status == s2.status
            assert s1.effective_start == s2.effective_start

        # Products
        assert len(d1.products) == len(d2.products)
        for p1, p2 in zip(d1.products, d2.products):
            assert p1.product_id == p2.product_id
            assert p1.product_name == p2.product_name
            assert p1.unit_of_measure == p2.unit_of_measure

        # BOMs and BOMLines
        assert len(d1.boms) == len(d2.boms)
        for b1, b2 in zip(d1.boms, d2.boms):
            assert b1.bom_id == b2.bom_id
            assert b1.product_id == b2.product_id

        assert len(d1.bom_lines) == len(d2.bom_lines)
        for l1, l2 in zip(d1.bom_lines, d2.bom_lines):
            assert l1.bom_id == l2.bom_id
            assert l1.line_no == l2.line_no
            assert l1.material_type == l2.material_type
            assert l1.quantity_per_unit == l2.quantity_per_unit

        # Warehouses
        assert len(d1.warehouses) == len(d2.warehouses)
        for w1, w2 in zip(d1.warehouses, d2.warehouses):
            assert w1.warehouse_id == w2.warehouse_id
            assert w1.name == w2.name
            assert w1.location == w2.location

        # Customers
        assert len(d1.customers) == len(d2.customers)
        for c1, c2 in zip(d1.customers, d2.customers):
            assert c1.customer_id == c2.customer_id
            assert c1.customer_name == c2.customer_name
            assert c1.contact_email == c2.contact_email

    def test_different_seeds_produce_different_data(self):
        cfg1 = MasterDataConfig.for_starter(seed=20261022)
        cfg2 = MasterDataConfig.for_starter(seed=99999999)

        d1 = generate_master_data(cfg1)
        d2 = generate_master_data(cfg2)

        names1 = [s.supplier_name for s in d1.suppliers]
        names2 = [s.supplier_name for s in d2.suppliers]
        assert names1 != names2

        cust1 = [c.customer_name for c in d1.customers]
        cust2 = [c.customer_name for c in d2.customers]
        assert cust1 != cust2


class TestInvalidConfiguration:
    """Verify rejection of invalid parameters."""

    def test_non_positive_counts_raise(self):
        with pytest.raises(ValueError, match="supplier_count must be > 0"):
            MasterDataConfig(supplier_count=0)

        with pytest.raises(ValueError, match="product_count must be > 0"):
            MasterDataConfig(product_count=-5)

        with pytest.raises(ValueError, match="warehouse_count must be > 0"):
            MasterDataConfig(warehouse_count=0)

        with pytest.raises(ValueError, match="customer_count must be > 0"):
            MasterDataConfig(customer_count=0)

    def test_invalid_bom_lines_limits_raise(self):
        """BOM lines must be at least 2, max >= min, and max <= catalog size."""
        # min_lines < 2 raises
        with pytest.raises(ValueError, match="min_lines_per_bom must be at least 2"):
            MasterDataConfig(min_lines_per_bom=1)

        # max_lines < min_lines raises
        with pytest.raises(ValueError, match="max_lines_per_bom .* cannot be less than"):
            MasterDataConfig(min_lines_per_bom=5, max_lines_per_bom=4)

        # max_lines > len(MATERIAL_TYPES) raises
        with pytest.raises(ValueError, match="cannot exceed total catalog material types"):
            MasterDataConfig(min_lines_per_bom=2, max_lines_per_bom=len(MATERIAL_TYPES) + 1)
