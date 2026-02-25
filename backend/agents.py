from __future__ import annotations

import json
import random

from openai import AsyncOpenAI

from config import OPENAI_API_KEY, MODEL_NAME
from models import NegotiationDecision, Product, SupplierProfile

# Lazy client — instantiated on first use so import succeeds without an API key.
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# Supplier Agent
# ---------------------------------------------------------------------------

def _build_supplier_system_prompt(supplier: SupplierProfile, products: list[Product]) -> str:
    catalog_lines = []
    for p in products:
        catalog_lines.append(
            f"  - {p.name} (code: {p.code}): targetFob=${p.targetFob:.2f}"
        )
        for c in p.components:
            line = f"      • [{c.type}] {c.name}"
            if c.composition:
                line += f" — {c.composition}"
            if c.supplier:
                line += f" (from {c.supplier})"
            catalog_lines.append(line)

    catalog_text = "\n".join(catalog_lines)

    return f"""You are {supplier.name}, a footwear supplier with a quality rating of {supplier.quality_rating}/5.

Your base lead time is {supplier.base_lead_time_days} days and your payment terms are {supplier.payment_terms}.

Pricing: you quote per-unit FOB prices by taking each product's targetFob and multiplying by {supplier.price_multiplier}, \
then applying a slight random variation of ±3% per product. This gives your opening quoted price. \
You may offer discounts of up to 8% cumulatively over the course of the negotiation, but do NOT give everything away at once — \
negotiate realistically and push back when the brand's requests are too aggressive.

You may also:
- Suggest swapping specific materials or components for cheaper plausible alternatives (name them concretely based on the component list below).
- Slightly adjust lead time (up to ±5 days) if it helps close a deal.
- Bundle volume incentives if the brand orders multiple products.

Never reveal your internal price multiplier or the targetFob values. Respond in natural, conversational business English. \
Be professional but firm; concede ground gradually, not all at once.

IMPORTANT: Write ready-to-send messages. Never use bracket placeholders like [Your Name], [Supplier A Name], \
[Your Contact Information], or [insert deadline]. Always sign with your actual name: {supplier.name}.

Product catalog you can supply:
{catalog_text}
"""


class SupplierAgent:
    def __init__(self, supplier: SupplierProfile, products: list[Product]) -> None:
        self.supplier = supplier
        self.products = products
        self.conversation_history: list[dict] = [
            {"role": "system", "content": _build_supplier_system_prompt(supplier, products)}
        ]
        # Pre-compute opening prices with ±3% variation so they stay consistent
        self.quoted_prices: dict[str, float] = {
            p.code: round(p.targetFob * supplier.price_multiplier * random.uniform(0.97, 1.03), 2)
            for p in products
        }

    async def respond(self, brand_message: str) -> str:
        self.conversation_history.append({"role": "user", "content": brand_message})
        try:
            completion = await _get_client().chat.completions.create(
                model=MODEL_NAME,
                messages=self.conversation_history,
            )
        except Exception as exc:
            raise RuntimeError(f"{self.supplier.name} LLM call failed: {exc}") from exc

        reply = completion.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": reply})
        return reply


# ---------------------------------------------------------------------------
# Brand Agent
# ---------------------------------------------------------------------------

def _build_brand_system_prompt(
    products: list[Product],
    suppliers: list[SupplierProfile],
    quantities: dict[str, int],
    note: str | None,
) -> str:
    product_lines = []
    for p in products:
        qty = quantities.get(p.code, 0)
        product_lines.append(f"  - {p.name} (code: {p.code}), qty: {qty} units")

    supplier_lines = [
        f"  - {s.name} (id: {s.id}): quality {s.quality_rating}/5, "
        f"lead time {s.base_lead_time_days} days, payment terms: {s.payment_terms}"
        for s in suppliers
    ]

    note_section = (
        f"\nThe brand team has this additional note: {note}" if note else ""
    )

    return (
        "You are Alex Chen, Senior Procurement Manager at UrbanStride Footwear.\n\n"
        "You are sourcing the following products:\n"
        + "\n".join(product_lines)
        + "\n\nYou know these suppliers and their quality ratings:\n"
        + "\n".join(supplier_lines)
        + note_section
        + "\n\nYour goal: negotiate the best overall deal balancing cost, quality, "
        "lead time, and payment terms. Push for lower prices, better terms, and "
        "faster delivery. Be professional but firm. Do not reveal what other "
        "suppliers are quoting in exact figures — only use relative comparisons "
        "(e.g. 'another supplier came in lower on price').\n\n"
        "IMPORTANT: Write ready-to-send messages. NEVER use bracket placeholders "
        "such as [Name], [Company], [Your Contact Information], [insert deadline], "
        "[Supplier Name], or any other [bracketed text]. Use your real identity above, "
        "address suppliers by their known name, and omit any information you don't have "
        "rather than inserting a placeholder."
    )


# Strict-mode-compatible schema: comparison is an array of per-supplier objects.
# OpenAI strict mode requires additionalProperties:false on every object and all
# properties listed in required — dynamic-key dicts are not permitted.
_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "winner_supplier_id": {"type": "integer"},
        "winner_name": {"type": "string"},
        "reasoning": {"type": "string"},
        "comparison": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "supplier_name": {"type": "string"},
                    "cost_assessment": {"type": "string"},
                    "quality_assessment": {"type": "string"},
                    "lead_time_assessment": {"type": "string"},
                    "payment_terms_assessment": {"type": "string"},
                    "overall_score": {"type": "string"},
                },
                "required": [
                    "supplier_name",
                    "cost_assessment",
                    "quality_assessment",
                    "lead_time_assessment",
                    "payment_terms_assessment",
                    "overall_score",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["winner_supplier_id", "winner_name", "reasoning", "comparison"],
    "additionalProperties": False,
}


class BrandAgent:
    def __init__(
        self,
        products: list[Product],
        suppliers: list[SupplierProfile],
        quantities: dict[str, int],
        note: str | None = None,
    ) -> None:
        self.products = products
        self.suppliers = suppliers
        self.quantities = quantities
        self._system_prompt = _build_brand_system_prompt(products, suppliers, quantities, note)
        # One conversation history per supplier_id
        self.conversation_histories: dict[int, list[dict]] = {
            s.id: [{"role": "system", "content": self._system_prompt}]
            for s in suppliers
        }

    async def generate_rfq(self, supplier_name: str) -> str:
        messages = [
            {"role": "system", "content": self._system_prompt},
            {
                "role": "user",
                "content": (
                    f"Generate an RFQ message addressed to {supplier_name}, listing the "
                    "products and quantities you need quoted. Keep it concise and professional. "
                    "Sign off with your name and title only — no placeholder contact information."
                ),
            },
        ]
        try:
            completion = await _get_client().chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
            )
        except Exception as exc:
            raise RuntimeError(f"Brand RFQ generation failed: {exc}") from exc

        return completion.choices[0].message.content

    async def generate_counter(
        self,
        supplier_id: int,
        supplier_response: str,
        all_quotes_summary: str | None = None,
    ) -> str:
        history = self.conversation_histories[supplier_id]

        # Add supplier response as assistant turn in that supplier's thread
        history.append({"role": "assistant", "content": supplier_response})

        competitive_hint = ""
        if all_quotes_summary:
            competitive_hint = (
                f"\n\n[Internal context — do NOT quote exact numbers to the supplier: "
                f"{all_quotes_summary}]"
            )

        supplier_name = next(s.name for s in self.suppliers if s.id == supplier_id)
        user_content = (
            f"You are negotiating with {supplier_name}. Based on their response above, "
            "write a professional counter-proposal or follow-up addressed to them by name. "
            "Push for better pricing, terms, or lead time. If you have context "
            "about competing offers, use it as leverage without revealing exact figures."
            + competitive_hint
        )
        history.append({"role": "user", "content": user_content})

        try:
            completion = await _get_client().chat.completions.create(
                model=MODEL_NAME,
                messages=history,
            )
        except Exception as exc:
            raise RuntimeError(f"Brand counter-proposal generation failed: {exc}") from exc

        reply = completion.choices[0].message.content
        # Replace the raw instruction with the actual reply so history reads naturally
        history[-1] = {"role": "user", "content": reply}
        return reply

    async def make_decision(self, final_offers: dict[int, str]) -> NegotiationDecision:
        supplier_summaries = "\n\n".join(
            f"--- {next(s.name for s in self.suppliers if s.id == sid)} (id: {sid}) ---\n{offer}"
            for sid, offer in final_offers.items()
        )

        supplier_meta = "\n".join(
            f"  - {s.name} (id: {s.id}): quality {s.quality_rating}/5, "
            f"lead time {s.base_lead_time_days} days, payment: {s.payment_terms}"
            for s in self.suppliers
        )

        decision_prompt = (
            "You have completed negotiations with all suppliers. "
            "Here is a summary of their final offers:\n\n"
            + supplier_summaries
            + "\n\nSupplier profiles for reference:\n"
            + supplier_meta
            + "\n\nSelect the best supplier considering cost, quality rating, lead time, "
            "and payment terms. Provide a detailed comparison and clear reasoning. "
            "The comparison field must contain one entry per supplier."
        )

        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": decision_prompt},
        ]

        try:
            completion = await _get_client().chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "NegotiationDecision",
                        "strict": True,
                        "schema": _DECISION_SCHEMA,
                    },
                },
            )
        except Exception as exc:
            raise RuntimeError(f"Brand decision generation failed: {exc}") from exc

        data = json.loads(completion.choices[0].message.content)

        # Convert comparison array → dict keyed by supplier_name for NegotiationDecision
        comparison_list: list[dict] = data.pop("comparison", [])
        data["comparison"] = {
            item["supplier_name"]: {k: v for k, v in item.items() if k != "supplier_name"}
            for item in comparison_list
        }

        return NegotiationDecision(**data)
