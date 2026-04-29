"""Tool functions for the Product Advisor agent."""

import json
from pathlib import Path

# Load product catalog
_CATALOG_PATH = Path(__file__).parent.parent / "data" / "products.json"
_catalog: dict = {}


def _load_catalog() -> dict:
    """Load and index the product catalog by ID."""
    global _catalog
    if not _catalog:
        with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
            products = json.load(f)
        _catalog = {p["id"]: p for p in products}
    return _catalog


def age_check(product_id: str, child_age_months: int) -> dict:
    """Check if a product is age-appropriate for a child of a given age.

    Args:
        product_id: The product ID to check.
        child_age_months: The child's age in months.

    Returns:
        Dict with suitability result and age range details.
    """
    catalog = _load_catalog()
    product = catalog.get(product_id)

    if not product:
        return {
            "status": "error",
            "message": f"Product '{product_id}' not found in catalog.",
        }

    min_age = product.get("min_age_months")
    max_age = product.get("max_age_months")

    # Products without age ranges (e.g., breast pumps) — not child-use items
    if min_age is None and max_age is None:
        return {
            "status": "ok",
            "is_age_appropriate": True,
            "note": "This product is not directly used by children (e.g., parent product).",
            "min_age_months": None,
            "max_age_months": None,
            "child_age_months": child_age_months,
        }

    min_age = min_age or 0
    max_age = max_age or 216  # Default to 18 years

    is_suitable = min_age <= child_age_months <= max_age

    # Additional choking hazard check for children under 36 months
    has_choking_hazard = product.get("choking_hazard", False) and child_age_months < 36

    result = {
        "status": "ok",
        "is_age_appropriate": is_suitable and not has_choking_hazard,
        "min_age_months": min_age,
        "max_age_months": max_age,
        "child_age_months": child_age_months,
        "choking_hazard_risk": has_choking_hazard,
    }

    if not is_suitable:
        if child_age_months < min_age:
            result["reason"] = f"Child is too young. Minimum age is {min_age} months."
        else:
            result["reason"] = f"Child is too old. Maximum age is {max_age} months."

    if has_choking_hazard:
        result["reason"] = (
            result.get("reason", "")
            + " Product contains small parts — choking hazard for children under 36 months."
        ).strip()

    return result


def product_lookup(product_id: str) -> dict:
    """Retrieve full product details by product ID.

    Args:
        product_id: The product ID to look up.

    Returns:
        Dict with full product details or error.
    """
    catalog = _load_catalog()
    product = catalog.get(product_id)

    if not product:
        return {
            "status": "error",
            "message": f"Product '{product_id}' not found in catalog.",
        }

    return {"status": "ok", "product": product}


def weight_check(product_id: str, child_weight_kg: float) -> dict:
    """Check if a child's weight is within the product's weight limit.

    Args:
        product_id: The product ID to check.
        child_weight_kg: The child's weight in kilograms.

    Returns:
        Dict with weight suitability result.
    """
    catalog = _load_catalog()
    product = catalog.get(product_id)

    if not product:
        return {
            "status": "error",
            "message": f"Product '{product_id}' not found in catalog.",
        }

    max_weight = product.get("max_weight_kg")

    if max_weight is None:
        return {
            "status": "ok",
            "is_weight_appropriate": True,
            "note": "No weight limit specified for this product.",
            "max_weight_kg": None,
            "child_weight_kg": child_weight_kg,
        }

    is_suitable = child_weight_kg <= max_weight
    result = {
        "status": "ok",
        "is_weight_appropriate": is_suitable,
        "max_weight_kg": max_weight,
        "child_weight_kg": child_weight_kg,
    }

    if not is_suitable:
        result["reason"] = (
            f"Child weighs {child_weight_kg}kg but product maximum is {max_weight}kg."
        )

    return result


def get_all_products_summary() -> list[dict]:
    """Get a summary of all products in the catalog for browsing."""
    catalog = _load_catalog()
    return [
        {
            "id": p["id"],
            "name_en": p["name_en"],
            "name_ar": p["name_ar"],
            "category": p["category"],
            "price_aed": p["price_aed"],
            "age_range": f"{p.get('min_age_months', '?')}-{p.get('max_age_months', '?')} months",
        }
        for p in catalog.values()
    ]
