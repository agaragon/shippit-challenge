from __future__ import annotations

import json

import pytest
from unittest.mock import MagicMock

from agents import BrandAgent, SupplierAgent
from models import NegotiationDecision


# ---------------------------------------------------------------------------
# Helper — redefine locally to keep this file self-contained
# ---------------------------------------------------------------------------

def _fake_completion(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    return completion


# Valid structured-output JSON that matches _DECISION_SCHEMA
_DECISION_JSON = json.dumps({
    "winner_supplier_id": 2,
    "winner_name": "Supplier B",
    "reasoning": "Best quality-to-cost ratio among the three suppliers.",
    "comparison": [
        {
            "supplier_name": "Supplier A",
            "cost_assessment": "Cheapest option",
            "quality_assessment": "Medium (4.0/5)",
            "lead_time_assessment": "Slowest at 45 days",
            "payment_terms_assessment": "33/33/33 split",
            "overall_score": "7/10",
        },
        {
            "supplier_name": "Supplier B",
            "cost_assessment": "Mid-range pricing",
            "quality_assessment": "High (4.7/5)",
            "lead_time_assessment": "Medium at 25 days",
            "payment_terms_assessment": "30/70 order/delivery",
            "overall_score": "9/10",
        },
        {
            "supplier_name": "Supplier C",
            "cost_assessment": "Most expensive",
            "quality_assessment": "Medium (4.0/5)",
            "lead_time_assessment": "Fastest at 15 days",
            "payment_terms_assessment": "30/70 order/delivery",
            "overall_score": "6/10",
        },
    ],
})


# ---------------------------------------------------------------------------
# SupplierAgent
# ---------------------------------------------------------------------------

class TestSupplierAgent:
    def test_initial_history_contains_system_prompt_only(self, products, suppliers):
        agent = SupplierAgent(supplier=suppliers[0], products=products)
        assert len(agent.conversation_history) == 1
        assert agent.conversation_history[0]["role"] == "system"

    def test_system_prompt_contains_supplier_name(self, products, suppliers):
        agent = SupplierAgent(supplier=suppliers[0], products=products)
        assert suppliers[0].name in agent.conversation_history[0]["content"]

    def test_system_prompt_contains_quality_rating(self, products, suppliers):
        agent = SupplierAgent(supplier=suppliers[1], products=products)
        assert "4.7" in agent.conversation_history[0]["content"]

    @pytest.mark.asyncio
    async def test_respond_returns_llm_reply(self, mock_openai, products, suppliers):
        mock_openai.chat.completions.create.return_value = _fake_completion("Here is my quote.")
        agent = SupplierAgent(supplier=suppliers[0], products=products)
        reply = await agent.respond("Please quote 1 000 units.")
        assert reply == "Here is my quote."

    @pytest.mark.asyncio
    async def test_respond_appends_user_message_to_history(self, mock_openai, products, suppliers):
        mock_openai.chat.completions.create.return_value = _fake_completion("My offer.")
        agent = SupplierAgent(supplier=suppliers[0], products=products)
        await agent.respond("What can you offer?")
        # system + user + assistant = 3
        assert len(agent.conversation_history) == 3
        assert agent.conversation_history[1]["role"] == "user"
        assert agent.conversation_history[1]["content"] == "What can you offer?"

    @pytest.mark.asyncio
    async def test_respond_appends_assistant_reply_to_history(self, mock_openai, products, suppliers):
        mock_openai.chat.completions.create.return_value = _fake_completion("My offer.")
        agent = SupplierAgent(supplier=suppliers[0], products=products)
        await agent.respond("What can you offer?")
        assert agent.conversation_history[2]["role"] == "assistant"
        assert agent.conversation_history[2]["content"] == "My offer."

    @pytest.mark.asyncio
    async def test_respond_accumulates_history_across_multiple_calls(self, mock_openai, products, suppliers):
        mock_openai.chat.completions.create.return_value = _fake_completion("Response.")
        agent = SupplierAgent(supplier=suppliers[1], products=products)
        await agent.respond("Message 1")
        await agent.respond("Message 2")
        # system + 2×(user + assistant) = 5
        assert len(agent.conversation_history) == 5

    @pytest.mark.asyncio
    async def test_respond_raises_runtime_error_on_llm_failure(self, mock_openai, products, suppliers):
        mock_openai.chat.completions.create.side_effect = Exception("connection refused")
        agent = SupplierAgent(supplier=suppliers[0], products=products)
        with pytest.raises(RuntimeError, match="LLM call failed"):
            await agent.respond("Hello")


# ---------------------------------------------------------------------------
# BrandAgent — generate_rfq
# ---------------------------------------------------------------------------

class TestBrandAgentGenerateRfq:
    @pytest.mark.asyncio
    async def test_returns_string_from_llm(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion("RFQ text here.")
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        result = await agent.generate_rfq("Supplier A")
        assert result == "RFQ text here."

    @pytest.mark.asyncio
    async def test_calls_llm_exactly_once(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion("RFQ.")
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        await agent.generate_rfq("Supplier A")
        assert mock_openai.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_generates_rfq_per_supplier_independently(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion("RFQ.")
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        r1 = await agent.generate_rfq("Supplier A")
        r2 = await agent.generate_rfq("Supplier B")
        assert r1 == r2 == "RFQ."  # same mock reply, two independent calls

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_llm_failure(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.side_effect = Exception("timeout")
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        with pytest.raises(RuntimeError, match="RFQ generation failed"):
            await agent.generate_rfq("Supplier A")


# ---------------------------------------------------------------------------
# BrandAgent — generate_counter
# ---------------------------------------------------------------------------

class TestBrandAgentGenerateCounter:
    @pytest.mark.asyncio
    async def test_returns_string(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion("Counter proposal.")
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        result = await agent.generate_counter(
            supplier_id=1,
            supplier_response="We can offer $15/unit.",
        )
        assert result == "Counter proposal."

    @pytest.mark.asyncio
    async def test_appends_to_target_supplier_history(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion("Counter.")
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        len_before = len(agent.conversation_histories[1])
        await agent.generate_counter(supplier_id=1, supplier_response="S1 offer.")
        assert len(agent.conversation_histories[1]) > len_before

    @pytest.mark.asyncio
    async def test_does_not_alter_other_supplier_histories(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion("Counter.")
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        len_s2 = len(agent.conversation_histories[2])
        len_s3 = len(agent.conversation_histories[3])
        await agent.generate_counter(supplier_id=1, supplier_response="S1 offer.")
        assert len(agent.conversation_histories[2]) == len_s2
        assert len(agent.conversation_histories[3]) == len_s3

    @pytest.mark.asyncio
    async def test_independent_histories_per_supplier(self, mock_openai, products, suppliers, quantities):
        """Each supplier has its own separate conversation history from the start."""
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        assert agent.conversation_histories[1] is not agent.conversation_histories[2]
        assert agent.conversation_histories[2] is not agent.conversation_histories[3]

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_llm_failure(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.side_effect = Exception("rate limit")
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        with pytest.raises(RuntimeError, match="counter-proposal generation failed"):
            await agent.generate_counter(supplier_id=1, supplier_response="Some offer.")


# ---------------------------------------------------------------------------
# BrandAgent — make_decision
# ---------------------------------------------------------------------------

class TestBrandAgentMakeDecision:
    @pytest.mark.asyncio
    async def test_returns_negotiation_decision_instance(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion(_DECISION_JSON)
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        decision = await agent.make_decision(final_offers={1: "A offer", 2: "B offer", 3: "C offer"})
        assert isinstance(decision, NegotiationDecision)

    @pytest.mark.asyncio
    async def test_winner_supplier_id_correct(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion(_DECISION_JSON)
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        decision = await agent.make_decision(final_offers={1: "A", 2: "B", 3: "C"})
        assert decision.winner_supplier_id == 2

    @pytest.mark.asyncio
    async def test_winner_name_correct(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion(_DECISION_JSON)
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        decision = await agent.make_decision(final_offers={1: "A", 2: "B", 3: "C"})
        assert decision.winner_name == "Supplier B"

    @pytest.mark.asyncio
    async def test_reasoning_is_non_empty_string(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion(_DECISION_JSON)
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        decision = await agent.make_decision(final_offers={1: "A", 2: "B", 3: "C"})
        assert isinstance(decision.reasoning, str)
        assert len(decision.reasoning) > 0

    @pytest.mark.asyncio
    async def test_comparison_is_dict_keyed_by_supplier_name(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion(_DECISION_JSON)
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        decision = await agent.make_decision(final_offers={1: "A", 2: "B", 3: "C"})
        assert isinstance(decision.comparison, dict)
        assert set(decision.comparison.keys()) == {"Supplier A", "Supplier B", "Supplier C"}

    @pytest.mark.asyncio
    async def test_comparison_entries_have_expected_assessment_keys(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.return_value = _fake_completion(_DECISION_JSON)
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        decision = await agent.make_decision(final_offers={1: "A", 2: "B", 3: "C"})
        for entry in decision.comparison.values():
            assert "cost_assessment" in entry
            assert "quality_assessment" in entry
            assert "lead_time_assessment" in entry
            assert "payment_terms_assessment" in entry
            assert "overall_score" in entry

    @pytest.mark.asyncio
    async def test_supplier_name_key_is_stripped_from_entry(self, mock_openai, products, suppliers, quantities):
        """The supplier_name key should not appear inside the per-supplier dict."""
        mock_openai.chat.completions.create.return_value = _fake_completion(_DECISION_JSON)
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        decision = await agent.make_decision(final_offers={1: "A", 2: "B", 3: "C"})
        for entry in decision.comparison.values():
            assert "supplier_name" not in entry

    @pytest.mark.asyncio
    async def test_raises_runtime_error_on_llm_failure(self, mock_openai, products, suppliers, quantities):
        mock_openai.chat.completions.create.side_effect = Exception("rate limited")
        agent = BrandAgent(products=products, suppliers=suppliers, quantities=quantities)
        with pytest.raises(RuntimeError, match="decision generation failed"):
            await agent.make_decision(final_offers={1: "A", 2: "B", 3: "C"})
