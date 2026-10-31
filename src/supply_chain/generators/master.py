"""
master.py — Master data generation orchestrator.
"""

from __future__ import annotations

import numpy as np
from faker import Faker

from supply_chain.generators.boms import generate_boms
from supply_chain.generators.config import MasterDataConfig, MasterDataset
from supply_chain.generators.customers import generate_customers
from supply_chain.generators.products import generate_products
from supply_chain.generators.suppliers import generate_suppliers
from supply_chain.generators.warehouses import generate_warehouses
from supply_chain.models import IDFactory
from supply_chain.models.enums import SupplierStatus


def generate_master_data(config: MasterDataConfig | None = None) -> MasterDataset:
    """
    Generate the complete synthetic master-data baseline.

    Uses independent deterministic random streams (via SeedSequence) for each
    subsystem so changes in one entity type do not perturb the data of others.

    Order of Generation (Parent before Child):
      1. Suppliers (master)
      2. Products (master)
      3. BOMs and BOMLines (dependent on Products)
      4. Active Supplier Coverage Invariant Check
      5. Warehouses (master)
      6. Customers (master)
    """
    if config is None:
        config = MasterDataConfig()

    # Create root seed sequence and derive 5 independent child streams
    root_ss = np.random.SeedSequence(config.seed)
    child_seeds = root_ss.spawn(5)

    # 1. Suppliers
    rng_sup = np.random.default_rng(child_seeds[0])
    fake_sup = Faker()
    fake_sup.seed_instance(int(rng_sup.integers(0, 10**8)))
    id_sup = IDFactory.for_supplier()
    suppliers = generate_suppliers(config, rng_sup, fake_sup, id_sup)

    # 2. Products
    rng_prod = np.random.default_rng(child_seeds[1])
    fake_prod = Faker()
    fake_prod.seed_instance(int(rng_prod.integers(0, 10**8)))
    id_prod = IDFactory.for_product()
    products = generate_products(config, rng_prod, fake_prod, id_prod)

    # 3. BOMs and BOMLines (depend on Products)
    rng_bom = np.random.default_rng(child_seeds[2])
    id_bom = IDFactory.for_bom()
    boms, bom_lines = generate_boms(products, config, rng_bom, id_bom)

    # 4. Guarantee Active Supplier Coverage Invariant (Review Fix 3)
    active_supplied_materials: set[str] = {
        mat
        for sup in suppliers
        if sup.status == SupplierStatus.ACTIVE
        for mat in sup.material_types
    }
    required_bom_materials: set[str] = {bl.material_type for bl in bom_lines}
    missing_active_materials = required_bom_materials - active_supplied_materials

    if missing_active_materials:
        raise ValueError(
            f"Active supplier coverage invariant violated: no active supplier available "
            f"for required BOM material types: {sorted(missing_active_materials)}. "
            f"Configured supplier_count={config.supplier_count} is insufficient to guarantee "
            f"active supply for all required formulation components."
        )

    # 5. Warehouses
    rng_whs = np.random.default_rng(child_seeds[3])
    fake_whs = Faker()
    fake_whs.seed_instance(int(rng_whs.integers(0, 10**8)))
    id_whs = IDFactory.for_warehouse()
    warehouses = generate_warehouses(config, rng_whs, fake_whs, id_whs)

    # 6. Customers
    rng_cust = np.random.default_rng(child_seeds[4])
    fake_cust = Faker()
    fake_cust.seed_instance(int(rng_cust.integers(0, 10**8)))
    id_cust = IDFactory.for_customer()
    customers = generate_customers(config, rng_cust, fake_cust, id_cust)

    return MasterDataset(
        suppliers=suppliers,
        products=products,
        boms=boms,
        bom_lines=bom_lines,
        warehouses=warehouses,
        customers=customers,
    )
