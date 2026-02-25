from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class ProductComponent(BaseModel):
    type: str
    name: str
    composition: Optional[str] = None
    supplier: Optional[str] = None


class Product(BaseModel):
    code: str
    name: str
    description: str
    targetFob: float
    categoryPath: str
    components: list[ProductComponent]


class SupplierProfile(BaseModel):
    id: int
    name: str
    quality_rating: float
    base_lead_time_days: int
    payment_terms: str
    price_multiplier: float


class NegotiationRequest(BaseModel):
    quantities: dict[str, int]
    note: Optional[str] = None


class NegotiationDecision(BaseModel):
    winner_supplier_id: int
    winner_name: str
    reasoning: str
    comparison: dict
