"""
constants.py — Shared domain constants and categories for synthetic generation.
"""

# Standard material types used across suppliers, raw materials, and BOM components
MATERIAL_TYPES: tuple[str, ...] = (
    # Active ingredients & chemical raw materials
    "ACTIVE_PHARMA_INGREDIENT",
    "STABILIZING_AGENT",
    "EXCIPIENT_BASE",
    "PURIFIED_SOLVENT",
    "PRESERVATIVE_COMPOUND",
    # Primary containers and closures
    "PRIMARY_GLASS_VIAL",
    "AMBER_GLASS_BOTTLE",
    "ALUMINUM_OINTMENT_TUBE",
    "METERED_AEROSOL_CANISTER",
    "STERILE_STOPPER",
    "ALUMINUM_SEAL",
    # Secondary and tertiary packaging
    "SECONDARY_CARTON",
    "LABEL_STOCK",
)

# Mandatory active ingredient identifier
ACTIVE_INGREDIENT_MATERIAL: str = "ACTIVE_PHARMA_INGREDIENT"

# Packaging components catalog
PACKAGING_MATERIAL_TYPES: tuple[str, ...] = (
    "PRIMARY_GLASS_VIAL",
    "AMBER_GLASS_BOTTLE",
    "ALUMINUM_OINTMENT_TUBE",
    "METERED_AEROSOL_CANISTER",
    "STERILE_STOPPER",
    "ALUMINUM_SEAL",
    "SECONDARY_CARTON",
    "LABEL_STOCK",
)

# Compatible packaging components by product dosage form
DOSAGE_FORM_PACKAGING: dict[str, tuple[str, ...]] = {
    "INJECTABLE_SOLUTION": ("PRIMARY_GLASS_VIAL", "STERILE_STOPPER", "ALUMINUM_SEAL"),
    "ORAL_SUSPENSION":    ("AMBER_GLASS_BOTTLE", "LABEL_STOCK", "SECONDARY_CARTON"),
    "TOPICAL_OINTMENT":   ("ALUMINUM_OINTMENT_TUBE", "LABEL_STOCK", "SECONDARY_CARTON"),
    "OPHTHALMIC_DROPS":   ("AMBER_GLASS_BOTTLE", "PRIMARY_GLASS_VIAL", "LABEL_STOCK"),
    "INHALATION_AEROSOL": ("METERED_AEROSOL_CANISTER", "ALUMINUM_SEAL", "SECONDARY_CARTON"),
}

# Product types and default units of measure
PRODUCT_CATALOG: tuple[dict[str, str], ...] = (
    {"type": "INJECTABLE_SOLUTION", "uom": "VIAL", "prefix": "Injectable Solution"},
    {"type": "ORAL_SUSPENSION",    "uom": "BOTTLE", "prefix": "Oral Suspension"},
    {"type": "TOPICAL_OINTMENT",   "uom": "TUBE", "prefix": "Topical Ointment"},
    {"type": "OPHTHALMIC_DROPS",   "uom": "BOTTLE", "prefix": "Ophthalmic Drops"},
    {"type": "INHALATION_AEROSOL", "uom": "CANISTER", "prefix": "Inhalation Aerosol"},
)

# Units of measure for raw materials
MATERIAL_UOMS: dict[str, str] = {
    "ACTIVE_PHARMA_INGREDIENT": "KG",
    "STABILIZING_AGENT":        "KG",
    "EXCIPIENT_BASE":           "KG",
    "PURIFIED_SOLVENT":         "LITER",
    "PRESERVATIVE_COMPOUND":    "LITER",
    "PRIMARY_GLASS_VIAL":       "UNIT",
    "AMBER_GLASS_BOTTLE":       "UNIT",
    "ALUMINUM_OINTMENT_TUBE":   "UNIT",
    "METERED_AEROSOL_CANISTER": "UNIT",
    "STERILE_STOPPER":          "UNIT",
    "ALUMINUM_SEAL":            "UNIT",
    "SECONDARY_CARTON":         "UNIT",
    "LABEL_STOCK":              "UNIT",
}
