from __future__ import annotations

import pytest
from pydantic import ValidationError

from models import (
    ProductComponent,
    Product,
    SupplierProfile,
    NegotiationRequest,
    NegotiationDecision,
)


# ---------------------------------------------------------------------------
# ProductComponent
# ---------------------------------------------------------------------------

class TestProductComponent:
    def test_valid_full(self):
        c = ProductComponent(
            type="material",
            name="Premium Leather",
            composition="100% Cowhide",
            supplier="ACME Textiles",
        )
        assert c.type == "material"
        assert c.name == "Premium Leather"
        assert c.composition == "100% Cowhide"
        assert c.supplier == "ACME Textiles"

    def test_optional_fields_default_to_none(self):
        c = ProductComponent(type="trim", name="Eyelet")
        assert c.composition is None
        assert c.supplier is None

    def test_missing_type_raises(self):
        with pytest.raises(ValidationError):
            ProductComponent(name="Eyelet")

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            ProductComponent(type="trim")

    def test_extra_fields_ignored(self):
        # products.json has fields like color, size, position — model ignores them
        c = ProductComponent(type="trim", name="Eyelet", color="Gunmetal", size="5mm")
        assert c.type == "trim"


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class TestProduct:
    _COMPONENT = {"type": "material", "name": "Leather"}

    def _make(self, **overrides):
        base = dict(
            code="FSH013",
            name="Pulse Pro High-Top",
            description="Premium shoe.",
            targetFob=14.49,
            categoryPath="Footwear > Sneakers > High-top Sneakers",
            components=[self._COMPONENT],
        )
        base.update(overrides)
        return Product(**base)

    def test_valid_construction(self):
        p = self._make()
        assert p.code == "FSH013"
        assert p.targetFob == 14.49
        assert len(p.components) == 1

    def test_empty_components_allowed(self):
        p = self._make(components=[])
        assert p.components == []

    def test_missing_code_raises(self):
        with pytest.raises(ValidationError):
            Product(
                name="Test",
                description="desc",
                targetFob=10.0,
                categoryPath="A > B",
                components=[],
            )

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            Product(
                code="X001",
                description="desc",
                targetFob=10.0,
                categoryPath="A > B",
                components=[],
            )

    def test_target_fob_as_string_raises(self):
        with pytest.raises(ValidationError):
            self._make(targetFob="not-a-number")

    def test_missing_target_fob_raises(self):
        with pytest.raises(ValidationError):
            Product(
                code="X001",
                name="Test",
                description="desc",
                categoryPath="A > B",
                components=[],
            )

    def test_components_are_product_component_instances(self):
        p = self._make()
        assert all(isinstance(c, ProductComponent) for c in p.components)

    def test_extra_top_level_fields_ignored(self):
        # products.json has createdAt, updatedAt, htsCode — model must ignore them
        p = self._make(createdAt="2025-01-01T00:00:00Z", htsCode="6404114900")
        assert p.code == "FSH013"


# ---------------------------------------------------------------------------
# SupplierProfile
# ---------------------------------------------------------------------------

class TestSupplierProfile:
    def _make(self, **overrides):
        base = dict(
            id=1,
            name="Supplier A",
            quality_rating=4.0,
            base_lead_time_days=45,
            payment_terms="33/33/33 (order/shipment/delivery)",
            price_multiplier=0.85,
        )
        base.update(overrides)
        return SupplierProfile(**base)

    def test_valid_construction(self):
        s = self._make()
        assert s.id == 1
        assert s.quality_rating == 4.0
        assert s.price_multiplier == 0.85

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            SupplierProfile(
                name="Supplier A",
                quality_rating=4.0,
                base_lead_time_days=45,
                payment_terms="33/33/33",
                price_multiplier=0.85,
            )

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            self._make(name=None)

    def test_quality_rating_as_float(self):
        s = self._make(quality_rating=4.7)
        assert s.quality_rating == 4.7


# ---------------------------------------------------------------------------
# NegotiationRequest
# ---------------------------------------------------------------------------

class TestNegotiationRequest:
    def test_valid_with_note(self):
        r = NegotiationRequest(quantities={"FSH013": 10000}, note="Prioritise speed.")
        assert r.note == "Prioritise speed."

    def test_note_defaults_to_none(self):
        r = NegotiationRequest(quantities={"FSH013": 10000})
        assert r.note is None

    def test_missing_quantities_raises(self):
        with pytest.raises(ValidationError):
            NegotiationRequest()

    def test_quantities_type_coercion(self):
        # Pydantic coerces numeric strings to int for dict[str, int]
        r = NegotiationRequest(quantities={"FSH013": 1000})
        assert r.quantities["FSH013"] == 1000


# ---------------------------------------------------------------------------
# NegotiationDecision
# ---------------------------------------------------------------------------

class TestNegotiationDecision:
    def test_valid_construction(self):
        d = NegotiationDecision(
            winner_supplier_id=2,
            winner_name="Supplier B",
            reasoning="Best quality-to-cost ratio.",
            comparison={"Supplier B": {"cost_assessment": "mid-range"}},
        )
        assert d.winner_supplier_id == 2
        assert d.winner_name == "Supplier B"
        assert isinstance(d.comparison, dict)

    def test_missing_winner_id_raises(self):
        with pytest.raises(ValidationError):
            NegotiationDecision(
                winner_name="Supplier B",
                reasoning="Best.",
                comparison={},
            )

    def test_missing_reasoning_raises(self):
        with pytest.raises(ValidationError):
            NegotiationDecision(
                winner_supplier_id=1,
                winner_name="Supplier A",
                comparison={},
            )

    def test_comparison_accepts_arbitrary_dict(self):
        d = NegotiationDecision(
            winner_supplier_id=1,
            winner_name="Supplier A",
            reasoning="Cheapest.",
            comparison={
                "Supplier A": {
                    "cost_assessment": "Low",
                    "quality_assessment": "Medium",
                    "lead_time_assessment": "Slow",
                    "payment_terms_assessment": "Flexible",
                    "overall_score": "7/10",
                }
            },
        )
        assert "Supplier A" in d.comparison
