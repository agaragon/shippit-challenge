from __future__ import annotations

import pytest
from unittest.mock import patch
from starlette.testclient import TestClient

from main import app, _peer_summary
from models import NegotiationDecision
from suppliers import SUPPLIERS


# ---------------------------------------------------------------------------
# Mock agent classes — no LLM calls, return predictable values immediately
# ---------------------------------------------------------------------------

class _MockSupplierAgent:
    def __init__(self, supplier, products):
        self.supplier = supplier

    async def respond(self, message: str) -> str:
        return f"Supplier {self.supplier.id}: competitive offer received."


class _MockBrandAgent:
    def __init__(self, products, suppliers, quantities, note=None):
        self.suppliers = suppliers

    async def generate_rfq(self, supplier_name: str) -> str:
        return f"RFQ addressed to {supplier_name}."

    async def generate_counter(
        self,
        supplier_id: int,
        supplier_response: str,
        all_quotes_summary: str | None = None,
    ) -> str:
        return f"Counter-proposal to supplier {supplier_id}."

    async def make_decision(self, final_offers: dict) -> NegotiationDecision:
        return NegotiationDecision(
            winner_supplier_id=1,
            winner_name="Supplier A",
            reasoning="Best overall value considering all factors.",
            comparison={
                "Supplier A": {
                    "cost_assessment": "Cheapest",
                    "quality_assessment": "Medium",
                    "lead_time_assessment": "Slow",
                    "payment_terms_assessment": "Flexible 33/33/33",
                    "overall_score": "8/10",
                },
                "Supplier B": {
                    "cost_assessment": "Mid-range",
                    "quality_assessment": "High",
                    "lead_time_assessment": "Medium",
                    "payment_terms_assessment": "30/70",
                    "overall_score": "7/10",
                },
                "Supplier C": {
                    "cost_assessment": "Expensive",
                    "quality_assessment": "Medium",
                    "lead_time_assessment": "Fastest",
                    "payment_terms_assessment": "30/70",
                    "overall_score": "6/10",
                },
            },
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_QUANTITIES = {
    "FSH013": 10000,
    "FSH014": 5000,
    "FSH016": 5000,
    "FSH019": 5000,
    "FSH021": 5000,
}

_AGENT_PATCHES = {
    "main.BrandAgent": _MockBrandAgent,
    "main.SupplierAgent": _MockSupplierAgent,
}


def _run_negotiation(extra_payload: dict | None = None) -> list[dict]:
    """Open a WebSocket, run a full negotiation, and return all received messages."""
    payload = {"type": "start_negotiation", "quantities": _QUANTITIES}
    if extra_payload:
        payload.update(extra_payload)

    with patch("main.BrandAgent", _MockBrandAgent), patch("main.SupplierAgent", _MockSupplierAgent):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/negotiate") as ws:
                ws.send_json(payload)
                messages = []
                while True:
                    data = ws.receive_json()
                    messages.append(data)
                    if data["type"] in ("done", "error"):
                        break
    return messages


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health_returns_200():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_ok_json():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# _peer_summary helper
# ---------------------------------------------------------------------------

class TestPeerSummary:
    def test_excludes_given_supplier_id(self):
        suppliers = list(SUPPLIERS)
        result = _peer_summary(exclude_supplier_id=1, suppliers=suppliers, replies={1: "", 2: "", 3: ""})
        assert "Supplier A" not in result
        assert "Supplier B" in result
        assert "Supplier C" in result

    def test_includes_all_other_suppliers(self):
        suppliers = list(SUPPLIERS)
        for exclude_id in (1, 2, 3):
            result = _peer_summary(exclude_id, suppliers, replies={1: "", 2: "", 3: ""})
            excluded_name = next(s.name for s in suppliers if s.id == exclude_id)
            assert excluded_name not in result
            for s in suppliers:
                if s.id != exclude_id:
                    assert s.name in result

    def test_result_starts_with_header(self):
        result = _peer_summary(1, list(SUPPLIERS), replies={})
        assert result.startswith("Other suppliers")

    def test_dollar_sign_in_reply_triggers_has_quoted(self):
        replies = {2: "We can offer $14.00 per unit.", 3: ""}
        result = _peer_summary(1, list(SUPPLIERS), replies=replies)
        assert "has quoted" in result

    def test_no_dollar_sign_triggers_has_responded(self):
        replies = {2: "We can work with you on this.", 3: ""}
        result = _peer_summary(1, list(SUPPLIERS), replies=replies)
        assert "has responded" in result

    def test_missing_reply_treated_as_empty(self):
        # Supplier 2 has no entry in replies — should not raise
        result = _peer_summary(1, list(SUPPLIERS), replies={3: "offer"})
        assert "Supplier B" in result
        assert "Supplier C" in result


# ---------------------------------------------------------------------------
# WebSocket — happy path
# ---------------------------------------------------------------------------

def test_negotiation_ends_with_done():
    messages = _run_negotiation()
    types = [m["type"] for m in messages]
    assert types[-1] == "done"


def test_negotiation_contains_decision():
    messages = _run_negotiation()
    types = [m["type"] for m in messages]
    assert "decision" in types


def test_negotiation_contains_message_events():
    messages = _run_negotiation()
    types = [m["type"] for m in messages]
    assert "message" in types


def test_negotiation_contains_status_events():
    messages = _run_negotiation()
    types = [m["type"] for m in messages]
    assert "status" in types


def test_negotiation_decision_comes_before_done():
    messages = _run_negotiation()
    types = [m["type"] for m in messages]
    assert types.index("decision") < types.index("done")


def test_negotiation_decision_has_required_fields():
    messages = _run_negotiation()
    decision = next(m for m in messages if m["type"] == "decision")
    assert "winner_supplier_id" in decision
    assert "winner_name" in decision
    assert "reasoning" in decision
    assert "comparison" in decision


def test_negotiation_all_three_suppliers_receive_messages():
    messages = _run_negotiation()
    chat = [m for m in messages if m["type"] == "message"]
    assert {m["supplier_id"] for m in chat} == {1, 2, 3}


def test_negotiation_message_events_have_required_fields():
    messages = _run_negotiation()
    for msg in (m for m in messages if m["type"] == "message"):
        assert "supplier_id" in msg
        assert "role" in msg
        assert msg["role"] in ("brand", "supplier")
        assert "content" in msg
        assert "round" in msg


def test_negotiation_round_numbers_are_positive():
    messages = _run_negotiation()
    for msg in (m for m in messages if m["type"] == "message"):
        assert msg["round"] >= 1


def test_negotiation_both_roles_appear_per_supplier():
    """Each supplier column should have both brand and supplier messages."""
    messages = _run_negotiation()
    for supplier_id in (1, 2, 3):
        supplier_msgs = [m for m in messages if m["type"] == "message" and m["supplier_id"] == supplier_id]
        roles = {m["role"] for m in supplier_msgs}
        assert "brand" in roles
        assert "supplier" in roles


def test_negotiation_accepts_optional_note():
    messages = _run_negotiation(extra_payload={"note": "Prioritise lead time over cost."})
    types = [m["type"] for m in messages]
    assert "done" in types


def test_negotiation_works_without_note():
    messages = _run_negotiation()
    types = [m["type"] for m in messages]
    assert "done" in types


# ---------------------------------------------------------------------------
# WebSocket — error paths
# ---------------------------------------------------------------------------

def test_wrong_message_type_returns_error():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/negotiate") as ws:
            ws.send_json({"type": "unknown_event"})
            response = ws.receive_json()
    assert response["type"] == "error"


def test_invalid_json_returns_error():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/negotiate") as ws:
            ws.send_text("this is not valid json {{{{")
            response = ws.receive_json()
    assert response["type"] == "error"
