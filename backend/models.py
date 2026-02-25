from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel


class ProductComponent(BaseModel):
    type: str
    name: str
    composition: Optional[str] = None
    supplier: Optional[str] = None
    position: Optional[str] = None
    color: Optional[str] = None
    code: Optional[str] = None
    size: Optional[str] = None
    material: Optional[str] = None
    weight: Optional[str] = None
    function: Optional[str] = None


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
    cost_tier: str
    base_lead_time_days: int
    payment_terms: str
    price_multiplier: float


class NegotiationRequest(BaseModel):
    quantities: dict[str, int]
    note: Optional[str] = None


class NegotiationMessage(BaseModel):
    supplier_id: int
    role: Literal["brand", "supplier"]
    content: str
    round: int


class SupplierQuote(BaseModel):
    supplier_id: int
    per_product_prices: dict[str, float]
    total_price: float
    lead_time_days: int
    payment_terms: str


class NegotiationDecision(BaseModel):
    winner_supplier_id: int
    winner_name: str
    reasoning: str
    comparison: dict
