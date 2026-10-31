"""
config.py — Configuration and result containers for master-data, production, and distribution generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Sequence

from supply_chain.generators.constants import MATERIAL_TYPES
from supply_chain.models import (
    Supplier,
    Product,
    BOM,
    BOMLine,
    Warehouse,
    Customer,
    MaterialLot,
    ProductionOrder,
    LotConsumption,
    FinishedLot,
    Shipment,
    Delivery,
    InventoryMovement,
    InventoryLedger,
)


@dataclass(frozen=True)
class MasterDataConfig:
    """
    Configuration parameters for synthetic master-data generation.

    Default Counts & Rationale:
      - supplier_count: exactly 500 by default (Mandatory Requirement 5).
      - product_count: 50 (configurable default; provides rich variety across product types).
      - warehouse_count: 10 (configurable default; represents regional distribution network).
      - customer_count: 200 (configurable default; hospitals, distributors, pharmacy chains).
      - min_lines_per_bom: 2 (at least 1 active ingredient + 1 compatible packaging component).
      - max_lines_per_bom: 5 (realistic formulation complexity; upper bounded by catalog size).
      - seed: 20261022 by default (Mandatory Requirement 6).
    """
    seed: int = 20261022
    supplier_count: int = 500
    product_count: int = 50
    warehouse_count: int = 10
    customer_count: int = 200
    min_lines_per_bom: int = 2
    max_lines_per_bom: int = 5
    base_date: date = field(default_factory=lambda: date(2026, 1, 1))

    def __post_init__(self) -> None:
        if self.supplier_count <= 0:
            raise ValueError(f"supplier_count must be > 0, got {self.supplier_count}")
        if self.product_count <= 0:
            raise ValueError(f"product_count must be > 0, got {self.product_count}")
        if self.warehouse_count <= 0:
            raise ValueError(f"warehouse_count must be > 0, got {self.warehouse_count}")
        if self.customer_count <= 0:
            raise ValueError(f"customer_count must be > 0, got {self.customer_count}")

        # BOM line validation constraints
        if self.min_lines_per_bom < 2:
            raise ValueError(
                f"min_lines_per_bom must be at least 2 to accommodate mandatory active ingredient "
                f"and packaging component, got {self.min_lines_per_bom}"
            )
        if self.max_lines_per_bom < self.min_lines_per_bom:
            raise ValueError(
                f"max_lines_per_bom ({self.max_lines_per_bom}) cannot be less than "
                f"min_lines_per_bom ({self.min_lines_per_bom})"
            )
        if self.max_lines_per_bom > len(MATERIAL_TYPES):
            raise ValueError(
                f"max_lines_per_bom ({self.max_lines_per_bom}) cannot exceed total catalog "
                f"material types ({len(MATERIAL_TYPES)})"
            )

    @classmethod
    def for_starter(cls, seed: int = 20261022) -> MasterDataConfig:
        """Starter mode (~10% scale) for fast test execution and CI."""
        return cls(
            seed=seed,
            supplier_count=50,
            product_count=10,
            warehouse_count=3,
            customer_count=20,
            min_lines_per_bom=2,
            max_lines_per_bom=4,
        )

    @classmethod
    def for_full(cls, seed: int = 20261022) -> MasterDataConfig:
        """Full scale targets meeting challenge specifications."""
        return cls(
            seed=seed,
            supplier_count=500,
            product_count=50,
            warehouse_count=10,
            customer_count=200,
            min_lines_per_bom=2,
            max_lines_per_bom=5,
        )


@dataclass
class MasterDataset:
    """
    In-memory container holding generated master-data entities.
    """
    suppliers: Sequence[Supplier]
    products: Sequence[Product]
    boms: Sequence[BOM]
    bom_lines: Sequence[BOMLine]
    warehouses: Sequence[Warehouse]
    customers: Sequence[Customer]

    def summary(self) -> dict[str, int]:
        """Return counts of each generated entity."""
        return {
            "suppliers": len(self.suppliers),
            "products": len(self.products),
            "boms": len(self.boms),
            "bom_lines": len(self.bom_lines),
            "warehouses": len(self.warehouses),
            "customers": len(self.customers),
        }


# ---------------------------------------------------------------------------
# Block 3: Production Configuration and Dataset Container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProductionConfig:
    """
    Configuration parameters for raw materials, production orders, and finished lots.

    Mandatory Full Targets (Challenge Brief Requirement 5 & Decision D-03):
      - raw_lot_count: exactly 10,000 raw material lots.
      - production_order_count: exactly 5,000 production orders.
      - finished_lot_count: exactly 8,000 finished goods lots.
        (Derived as: 3,000 orders producing 2 lots + 2,000 orders producing 1 lot = 8,000).
    """
    seed: int = 20261022
    raw_lot_count: int = 10_000
    production_order_count: int = 5_000
    finished_lot_count: int = 8_000
    base_date: date = field(default_factory=lambda: date(2026, 1, 1))

    # Lot & order sizing bounds
    min_order_qty: int = 100
    max_order_qty: int = 500
    min_raw_lot_qty: int = 2_000
    max_raw_lot_qty: int = 10_000

    def __post_init__(self) -> None:
        if self.raw_lot_count <= 0:
            raise ValueError(f"raw_lot_count must be > 0, got {self.raw_lot_count}")
        if self.production_order_count <= 0:
            raise ValueError(f"production_order_count must be > 0, got {self.production_order_count}")
        if self.finished_lot_count < self.production_order_count:
            raise ValueError(
                f"finished_lot_count ({self.finished_lot_count}) cannot be less than "
                f"production_order_count ({self.production_order_count}) as every order produces >= 1 lot"
            )
        if self.finished_lot_count > 2 * self.production_order_count:
            raise ValueError(
                f"finished_lot_count ({self.finished_lot_count}) cannot exceed "
                f"2 * production_order_count ({2 * self.production_order_count}) as orders produce at most 2 lots"
            )
        if self.min_order_qty <= 0:
            raise ValueError(f"min_order_qty must be > 0, got {self.min_order_qty}")
        if self.max_order_qty < self.min_order_qty:
            raise ValueError(
                f"max_order_qty ({self.max_order_qty}) cannot be less than "
                f"min_order_qty ({self.min_order_qty})"
            )
        if self.min_raw_lot_qty <= 0:
            raise ValueError(f"min_raw_lot_qty must be > 0, got {self.min_raw_lot_qty}")
        if self.max_raw_lot_qty < self.min_raw_lot_qty:
            raise ValueError(
                f"max_raw_lot_qty ({self.max_raw_lot_qty}) cannot be less than "
                f"min_raw_lot_qty ({self.min_raw_lot_qty})"
            )

    @property
    def two_lot_order_count(self) -> int:
        """Number of production orders that must produce exactly 2 finished lots."""
        return self.finished_lot_count - self.production_order_count

    @property
    def one_lot_order_count(self) -> int:
        """Number of production orders that must produce exactly 1 finished lot."""
        return 2 * self.production_order_count - self.finished_lot_count

    @classmethod
    def for_starter(cls, seed: int = 20261022) -> ProductionConfig:
        """
        Scaled-down starter mode (~1% of full mode) for fast unit and integration tests.
        Produces 100 raw lots, 50 production orders, and 80 finished lots (30 * 2 + 20 * 1 = 80).
        """
        return cls(
            seed=seed,
            raw_lot_count=100,
            production_order_count=50,
            finished_lot_count=80,
        )

    @classmethod
    def for_full(cls, seed: int = 20261022) -> ProductionConfig:
        """Full scale targets meeting challenge specifications."""
        return cls(
            seed=seed,
            raw_lot_count=10_000,
            production_order_count=5_000,
            finished_lot_count=8_000,
        )


@dataclass
class ProductionDataset:
    """
    In-memory container holding generated transactional production entities.
    """
    material_lots: Sequence[MaterialLot]
    production_orders: Sequence[ProductionOrder]
    lot_consumptions: Sequence[LotConsumption]
    finished_lots: Sequence[FinishedLot]

    def summary(self) -> dict[str, int]:
        """Return counts of each generated entity."""
        return {
            "material_lots": len(self.material_lots),
            "production_orders": len(self.production_orders),
            "lot_consumptions": len(self.lot_consumptions),
            "finished_lots": len(self.finished_lots),
        }


# ---------------------------------------------------------------------------
# Block 4: Downstream Distribution Configuration and Dataset Container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DistributionConfig:
    """
    Configuration parameters for downstream distribution, shipments, and customer deliveries.

    Mandatory Full Targets (Challenge Brief Requirement 5 & Block 4):
      - delivery_count: exactly 20,000 delivery line items in full mode.
      - seed: 20261022 by default (Mandatory Requirement 6).
      - min_delivery_qty: 10
      - max_delivery_qty: 40
      - min_lines_per_shipment: 1
      - max_lines_per_shipment: 4
    """
    seed: int = 20261022
    delivery_count: int = 20_000
    min_delivery_qty: int = 10
    max_delivery_qty: int = 40
    min_lines_per_shipment: int = 1
    max_lines_per_shipment: int = 4
    base_date: date = field(default_factory=lambda: date(2026, 1, 1))

    def __post_init__(self) -> None:
        if self.delivery_count <= 0:
            raise ValueError(f"delivery_count must be > 0, got {self.delivery_count}")
        if self.min_delivery_qty <= 0:
            raise ValueError(f"min_delivery_qty must be > 0, got {self.min_delivery_qty}")
        if self.max_delivery_qty < self.min_delivery_qty:
            raise ValueError(
                f"max_delivery_qty ({self.max_delivery_qty}) cannot be less than "
                f"min_delivery_qty ({self.min_delivery_qty})"
            )
        if self.min_lines_per_shipment <= 0:
            raise ValueError(f"min_lines_per_shipment must be > 0, got {self.min_lines_per_shipment}")
        if self.max_lines_per_shipment < self.min_lines_per_shipment:
            raise ValueError(
                f"max_lines_per_shipment ({self.max_lines_per_shipment}) cannot be less than "
                f"min_lines_per_shipment ({self.min_lines_per_shipment})"
            )

    @classmethod
    def for_starter(cls, seed: int = 20261022) -> DistributionConfig:
        """
        Scaled-down starter mode (~1% of full mode) for fast unit and integration tests.
        Produces exactly 200 delivery records.
        """
        return cls(
            seed=seed,
            delivery_count=200,
            min_delivery_qty=10,
            max_delivery_qty=40,
            min_lines_per_shipment=1,
            max_lines_per_shipment=4,
        )

    @classmethod
    def for_full(cls, seed: int = 20261022) -> DistributionConfig:
        """Full scale targets meeting challenge specifications (exactly 20,000 deliveries)."""
        return cls(
            seed=seed,
            delivery_count=20_000,
            min_delivery_qty=10,
            max_delivery_qty=40,
            min_lines_per_shipment=1,
            max_lines_per_shipment=4,
        )


@dataclass
class DistributionDataset:
    """
    In-memory container holding generated distribution and inventory entities.
    """
    shipments: Sequence[Shipment]
    deliveries: Sequence[Delivery]
    inventory_movements: Sequence[InventoryMovement]
    inventory_ledger: InventoryLedger

    def summary(self) -> dict[str, int]:
        """Return counts of each generated entity."""
        return {
            "shipments": len(self.shipments),
            "deliveries": len(self.deliveries),
            "inventory_movements": len(self.inventory_movements),
            "ledger_movement_count": len(self.inventory_ledger.all_movements),
        }
