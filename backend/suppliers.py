from __future__ import annotations

import json
from pathlib import Path

from models import Product, SupplierProfile

SUPPLIERS: list[SupplierProfile] = [
    SupplierProfile(
        id=1,
        name="Supplier A",
        quality_rating=4.0,
        cost_tier="cheapest",
        base_lead_time_days=45,
        payment_terms="33/33/33 (order/shipment/delivery)",
        price_multiplier=0.85,
    ),
    SupplierProfile(
        id=2,
        name="Supplier B",
        quality_rating=4.7,
        cost_tier="moderate",
        base_lead_time_days=25,
        payment_terms="30/70 (order/delivery)",
        price_multiplier=1.05,
    ),
    SupplierProfile(
        id=3,
        name="Supplier C",
        quality_rating=4.0,
        cost_tier="expensive",
        base_lead_time_days=15,
        payment_terms="30/70 (order/delivery)",
        price_multiplier=1.20,
    ),
]

_PRODUCTS_PATH = Path(__file__).parent / "products.json"


def load_products() -> list[Product]:
    data = json.loads(_PRODUCTS_PATH.read_text())
    return [Product(**p) for p in data["products"]]


def get_supplier(id: int) -> SupplierProfile:
    for supplier in SUPPLIERS:
        if supplier.id == id:
            return supplier
    raise ValueError(f"No supplier with id={id}")
