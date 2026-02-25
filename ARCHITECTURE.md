# Architecture

## Overview

A full-stack application that simulates a brand sourcing footwear products from three competing suppliers using AI-driven negotiation agents. A human user configures the order (product quantities and an optional note), then watches as a Brand Agent and three Supplier Agents negotiate in parallel over multiple rounds via an LLM. At the end, the Brand Agent picks a winner and explains its reasoning.

```
┌──────────────────────────────────────────────────┐
│                   Browser                        │
│  React + Vite + TailwindCSS v4                   │
│                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │ Supplier A │  │ Supplier B │  │ Supplier C │  │
│  │   chat     │  │   chat     │  │   chat     │  │
│  └────────────┘  └────────────┘  └────────────┘  │
│                                                  │
│  ┌──────────────────────────────────────────────┐│
│  │         Decision panel (when done)           ││
│  └──────────────────────────────────────────────┘│
└────────────────────┬─────────────────────────────┘
                     │ WebSocket (ws://localhost:8000/ws/negotiate)
                     ▼
┌──────────────────────────────────────────────────┐
│               FastAPI backend                    │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │         Negotiation Orchestrator            │  │
│  │         (main.py — WS endpoint)             │  │
│  │                                             │  │
│  │  ┌─────────────┐   ┌──────────────────┐    │  │
│  │  │ Brand Agent │──▶│  Supplier Agents  │    │  │
│  │  │   (1 inst)  │   │  (3 instances)    │    │  │
│  │  └─────────────┘   └──────────────────┘    │  │
│  └────────────────────────────────────────────┘  │
│                      │                           │
│                      ▼                           │
│              OpenAI API (gpt-4o)                 │
└──────────────────────────────────────────────────┘
```

## Backend (`backend/`)

### Files

| File | Purpose |
|---|---|
| `config.py` | Loads `OPENAI_API_KEY` and `MODEL_NAME` from a `.env` file via `python-dotenv`. `MODEL_NAME` defaults to `gpt-4o`. |
| `models.py` | Pydantic models: `ProductComponent`, `Product`, `SupplierProfile`, `NegotiationRequest`, `NegotiationMessage`, `SupplierQuote`, `NegotiationDecision`. |
| `suppliers.py` | Hardcoded list of 3 `SupplierProfile` objects. Exposes `load_products()` (reads `products.json`) and `get_supplier(id)`. |
| `products.json` | Catalog of 5 high-top sneaker SKUs with materials, trims, and components. |
| `agents.py` | `SupplierAgent` and `BrandAgent` classes — system prompts, conversation history management, LLM calls. |
| `main.py` | FastAPI app with CORS middleware, `GET /health`, and `WebSocket /ws/negotiate` endpoint containing the negotiation orchestrator. |
| `requirements.txt` | `fastapi`, `uvicorn[standard]`, `openai`, `python-dotenv`. |

### Agent design

**SupplierAgent** — one instance per supplier (3 total per negotiation).

- Receives a `SupplierProfile` and the product list.
- Builds a system prompt that embeds the supplier's identity, pricing rules (targetFob × price_multiplier ± 3%), lead time, payment terms, and the full product catalog with components.
- Pre-computes quoted prices in `__init__` with random ±3% variation (stored in `self.quoted_prices`, though these are guidance for the LLM — the actual quoting happens in natural language via the LLM).
- `respond(brand_message)` appends the brand's message to conversation history, calls the LLM, appends the reply, and returns it.

**BrandAgent** — one instance per negotiation.

- Receives products, suppliers, quantities, and an optional user note.
- Maintains separate `conversation_histories` per supplier (keyed by `supplier_id`).
- `generate_rfq()` creates the initial Request For Quote message via a fresh LLM call (not tied to any per-supplier history).
- `generate_counter(supplier_id, supplier_response, all_quotes_summary)` adds the supplier's response to that supplier's history, optionally injects a competitive-leverage hint about other suppliers (without exact figures), and generates a counter-proposal.
- `make_decision(final_offers)` takes the last response from each supplier, asks the LLM to compare and pick a winner. Uses OpenAI's structured output (`response_format: json_schema` with `strict: true`) to return reliable JSON matching a schema with `winner_supplier_id`, `winner_name`, `reasoning`, and a `comparison` array. The comparison array is then converted to a dict keyed by supplier name before returning a `NegotiationDecision`.

**OpenAI client** — a lazy-initialized global `AsyncOpenAI` singleton. Instantiated on first use so the module can be imported without an API key set.

### Negotiation orchestrator (`main.py`)

The WebSocket endpoint drives the negotiation in a synchronous round-based loop:

1. **Accept connection**, wait for a `start_negotiation` JSON message with `quantities` and optional `note`.
2. **Bootstrap**: load products and suppliers, create 1 `BrandAgent` + 3 `SupplierAgent` instances.
3. **Round 1 — RFQ**: Brand generates a single RFQ. That same message is sent to all 3 suppliers in parallel via `asyncio.gather`. Each supplier responds independently. All messages are streamed to the frontend as they arrive.
4. **Rounds 2–N** (default N=3): Brand generates a counter-proposal per supplier (can see a summary of other suppliers' positions from round 3 onward). Counter-proposals are sent to suppliers in parallel. Each round waits for all suppliers to finish before starting the next.
5. **Decision**: After all rounds, the brand agent evaluates all final offers and picks a winner. The decision (with per-supplier comparison) is sent to the frontend.
6. **Done**: A `{"type": "done"}` event signals completion.

Error handling: all exceptions are caught and forwarded to the frontend as `{"type": "error", "message": "..."}`.

### WebSocket protocol

Frontend → Backend:
```json
{
  "type": "start_negotiation",
  "quantities": {"FSH013": 10000, "FSH014": 5000, ...},
  "note": "optional string"
}
```

Backend → Frontend:
```json
{"type": "status",   "message": "Round 1 — sending RFQ…"}
{"type": "message",  "supplier_id": 1, "role": "brand"|"supplier", "content": "…", "round": 1}
{"type": "decision", "winner_supplier_id": 2, "winner_name": "…", "reasoning": "…", "comparison": {…}}
{"type": "error",    "message": "…"}
{"type": "done"}
```

## Frontend (`frontend/`)

### Files

| File | Purpose |
|---|---|
| `src/hooks/useNegotiation.js` | Custom React hook managing WebSocket lifecycle and state (`messages`, `status`, `statusText`, `error`, `decision`). |
| `src/App.jsx` | Single-page UI with three sections: order configuration form, 3-column live chat panels, and a decision panel. |
| `src/index.css` | TailwindCSS v4 import + minimal base resets. |
| `src/main.jsx` | React entry point. |
| `vite.config.js` | Vite config with `@vitejs/plugin-react` and `@tailwindcss/vite`. |

### UI structure

1. **Order Configuration** (top): quantity inputs for each of the 5 products (pre-filled with 10000/5000/5000/5000/5000), a textarea for an optional note to the brand negotiator, and a Start Negotiation button (disabled while negotiating, shows a spinner).
2. **Conversations** (middle, visible once negotiation starts): three side-by-side columns, one per supplier. Each column shows a filtered view of all messages for that supplier. Brand messages appear as left-aligned blue bubbles, supplier messages as right-aligned gray bubbles. Round dividers separate negotiation rounds. Auto-scrolls on new messages.
3. **Decision** (bottom, visible when status is `done`): shows the winning supplier highlighted, a comparison table (cost, quality, lead time, payment terms, overall score per supplier), and the AI's reasoning text.

### State management

All state lives in the `useNegotiation` hook via `useState`. No external state library. The WebSocket connection is opened on demand when the user clicks "Start Negotiation" and closed when a `done` or `error` event arrives.

## Data flow

```
User clicks "Start Negotiation"
  │
  ├─► useNegotiation opens WebSocket
  │     └─► sends { type: "start_negotiation", quantities, note }
  │
  ├─► Backend creates agents
  │     ├─► Brand Agent generates RFQ (1 LLM call)
  │     │     └─► streams "message" events to frontend
  │     ├─► 3× Supplier Agents respond in parallel (3 LLM calls)
  │     │     └─► streams "message" events to frontend
  │     ├─► Repeat for rounds 2–3:
  │     │     ├─► Brand generates counter per supplier (3 LLM calls)
  │     │     └─► Suppliers respond in parallel (3 LLM calls)
  │     ├─► Brand makes decision (1 LLM call, structured output)
  │     │     └─► streams "decision" event
  │     └─► sends "done"
  │
  └─► Frontend renders messages in real-time, then shows decision
```

Total LLM calls per negotiation: 1 (RFQ) + 3 (round 1 supplier replies) + 3×2 (rounds 2–3: brand counter + supplier reply) × 2 rounds + 1 (decision) = **17 calls** with the default 3 rounds.

## Caveats and limitations

### Functional

1. **No persistence.** All state is in-memory for the duration of a single WebSocket connection. Refreshing the page or disconnecting loses the entire negotiation. There is no database.

2. **Single concurrent negotiation.** The backend has no session management. Multiple browser tabs opening WebSocket connections simultaneously will each run independent negotiations, all competing for LLM API rate limits. There is no queuing or mutual exclusion.

3. **`quoted_prices` are computed but not enforced.** `SupplierAgent.__init__` pre-computes opening prices in `self.quoted_prices`, but this dict is never injected into the system prompt or referenced by the LLM. The LLM is told the pricing formula in the system prompt and generates its own numbers. The pre-computed prices and the LLM-generated prices may not match.

4. **Brand Agent conversation history has a role inversion.** In `generate_counter`, the supplier's response is appended as `role: "assistant"` and the brand's own counter-proposal is appended as `role: "user"`. This means the brand agent's conversation history has the brand's own messages as "user" turns and supplier messages as "assistant" turns — effectively the brand agent is roleplaying in a conversation where it treats the supplier's words as its own outputs. This works in practice because the system prompt establishes the brand identity, but it's semantically inverted.

5. **Competitive leverage is only injected from round 3 onward.** In `main.py`, `all_quotes_summary` is only passed when `round_num > 2`. The brand agent has no cross-supplier context during its round-2 counter-proposals, even though it already has all three round-1 quotes.

6. **`_peer_summary` leaks internal data.** The peer summary helper uses `s.price_multiplier` to determine if a supplier "appears competitive" — this is internal data that shouldn't be in a prompt. The heuristic (`price_multiplier <= 1.0` → "competitive") is also overly simplistic and doesn't reflect actual quoted prices.

7. **Decision is made on only the last reply.** `make_decision(final_offers=latest_supplier_replies)` passes only each supplier's most recent message, not the full conversation. The decision LLM call doesn't see earlier rounds, counter-offers, or concessions — only the final response from each supplier.

8. **`NegotiationDecision.comparison` is typed as `dict` (untyped).** The Pydantic model uses a bare `dict` for the comparison field, losing all type safety. The structured output schema defines a detailed per-supplier object, but after JSON parsing and conversion, it's stored as an untyped dict.

### Technical

9. **Hardcoded WebSocket URL.** The frontend connects to `ws://localhost:8000/ws/negotiate`. This won't work in production or if the backend runs on a different host/port. No environment variable or proxy configuration is set up.

10. **No reconnection or retry logic.** If the WebSocket connection drops mid-negotiation, the frontend simply shows an error. There is no automatic reconnection, and the negotiation cannot be resumed.

11. **No input validation on quantities.** The backend trusts whatever quantities are sent. Zero or negative quantities, missing product codes, or non-existent codes are not validated beyond Pydantic's `dict[str, int]` type check.

12. **All LLM calls use the same model.** Both the brand and supplier agents use the same `MODEL_NAME` (default `gpt-4o`). There's no option to use a cheaper model for supplier simulation and a more capable one for the brand decision.

13. **No rate-limit handling.** With 17 LLM calls per negotiation and parallel `asyncio.gather` calls, the app can hit OpenAI rate limits. There are no retries, exponential backoff, or rate-limit awareness.

14. **`pydantic` is not in `requirements.txt`.** It's pulled in transitively by `fastapi`, so it works, but it's an implicit dependency.

### Deployment

15. **Dev-only CORS configuration.** `allow_origins=["*"]` is set for development convenience. This must be tightened for any production deployment.

16. **No containerization or deployment config.** No Dockerfile, docker-compose, or CI/CD configuration. The `Makefile` provides local dev convenience only.

17. **API key in `.env` file.** The OpenAI API key is loaded from a local `.env` file. For production, a secrets manager or environment variable injection from the deployment platform would be needed.
