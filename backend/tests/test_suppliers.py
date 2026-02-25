from __future__ import annotations

import pytest

from suppliers import load_products, get_supplier, SUPPLIERS
from models import Product, SupplierProfile


# ---------------------------------------------------------------------------
# load_products
# ---------------------------------------------------------------------------

class TestLoadProducts:
    def test_returns_exactly_five_products(self, products):
        assert len(products) == 5

    def test_all_items_are_product_instances(self, products):
        assert all(isinstance(p, Product) for p in products)

    def test_all_codes_are_non_empty(self, products):
        assert all(p.code for p in products)

    def test_all_names_are_non_empty(self, products):
        assert all(p.name for p in products)

    def test_all_target_fobs_are_positive(self, products):
        assert all(p.targetFob > 0 for p in products)

    def test_all_products_have_at_least_one_component(self, products):
        assert all(len(p.components) > 0 for p in products)

    def test_expected_product_codes_present(self, products):
        codes = {p.code for p in products}
        assert codes == {"FSH013", "FSH014", "FSH016", "FSH019", "FSH021"}

    def test_pulse_pro_high_top_present(self, products):
        names = [p.name for p in products]
        assert "Pulse Pro High-Top" in names

    def test_products_are_reloaded_each_call(self):
        """load_products() should be a pure function — two calls return equal data."""
        a = load_products()
        b = load_products()
        assert [p.code for p in a] == [p.code for p in b]


# ---------------------------------------------------------------------------
# get_supplier
# ---------------------------------------------------------------------------

class TestGetSupplier:
    @pytest.mark.parametrize("supplier_id,expected_name", [
        (1, "Supplier A"),
        (2, "Supplier B"),
        (3, "Supplier C"),
    ])
    def test_returns_correct_supplier(self, supplier_id, expected_name):
        s = get_supplier(supplier_id)
        assert isinstance(s, SupplierProfile)
        assert s.id == supplier_id
        assert s.name == expected_name

    def test_raises_value_error_for_unknown_id(self):
        with pytest.raises(ValueError):
            get_supplier(999)

    def test_raises_value_error_for_zero(self):
        with pytest.raises(ValueError):
            get_supplier(0)

    def test_raises_value_error_for_negative_id(self):
        with pytest.raises(ValueError):
            get_supplier(-1)


# ---------------------------------------------------------------------------
# SUPPLIERS list integrity
# ---------------------------------------------------------------------------

class TestSuppliersList:
    def test_exactly_three_suppliers(self):
        assert len(SUPPLIERS) == 3

    def test_supplier_names_in_order(self):
        assert [s.name for s in SUPPLIERS] == ["Supplier A", "Supplier B", "Supplier C"]

    def test_supplier_ids_are_1_2_3(self):
        assert {s.id for s in SUPPLIERS} == {1, 2, 3}

    def test_supplier_quality_ratings(self):
        ratings = {s.id: s.quality_rating for s in SUPPLIERS}
        assert ratings[1] == 4.0   # medium quality
        assert ratings[2] == 4.7   # high quality
        assert ratings[3] == 4.0   # medium quality

    def test_supplier_payment_terms(self):
        terms = {s.id: s.payment_terms for s in SUPPLIERS}
        assert "33/33/33" in terms[1]
        assert "30/70" in terms[2]
        assert "30/70" in terms[3]

    def test_price_multiplier_ordering(self):
        """Supplier 1 cheapest, Supplier 3 most expensive."""
        m = {s.id: s.price_multiplier for s in SUPPLIERS}
        assert m[1] < m[2] < m[3]

    def test_lead_time_ordering(self):
        """Supplier 3 fastest, Supplier 1 slowest."""
        lt = {s.id: s.base_lead_time_days for s in SUPPLIERS}
        assert lt[3] < lt[2] < lt[1]

    def test_all_suppliers_have_positive_lead_time(self):
        assert all(s.base_lead_time_days > 0 for s in SUPPLIERS)
