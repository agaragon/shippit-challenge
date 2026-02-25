# Backlog

Items are grouped by theme and ordered roughly by impact within each section.
Items marked **[doc]** are documentation fixes only — no code changes required.

---

## Bugs / Correctness

### 1. Brand conversation history has inverted roles
**File:** `backend/agents.py:221–222`

In `generate_counter`, the supplier's response is appended as `role: "assistant"` and the brand's own counter-proposal as `role: "user"`. From the LLM's perspective the agent's own output should be `"assistant"` and the incoming message from the counterparty should be `"user"`. The inversion works in practice because the system prompt anchors the identity, but it causes the model to re-read its own prior outputs as if they came from the supplier.

**Fix:** swap the roles — append the supplier response as `"user"` and the generated counter as `"assistant"`.

---

### 2. Competitive leverage is withheld from round 2
**File:** `backend/main.py:118`

```python
all_quotes_summary=peer_summary if _rn > 2 else None
```

By round 2 the brand agent already holds all three round-1 quotes, but the peer summary is only injected from round 3 onward. The brand therefore negotiates round 2 without any cross-supplier context, missing an opportunity to apply competitive pressure early.

**Fix:** change the condition to `_rn > 1` so competitive context is available from round 2.

---

### 3. `_peer_summary` leaks internal model data
**File:** `backend/main.py:170`

```python
f"appears {'competitive' if s.price_multiplier <= 1.0 else 'higher-priced'}."
```

`price_multiplier` is an internal simulation parameter that has no equivalent in a real sourcing scenario. Using it to label a supplier "competitive" also ignores the actual negotiated prices — a supplier with `price_multiplier > 1.0` could still be the cheapest after concessions.

**Fix:** remove the heuristic label entirely, or base it on whether a dollar figure appears in the supplier's actual reply.

---

### 4. Decision is made on only the final round's reply
**Files:** `backend/agents.py:253`, `backend/main.py:133`

`make_decision` receives only `latest_supplier_replies` — a single message per supplier. The decision LLM call has no visibility into concessions made in earlier rounds, counter-offers, or the negotiation arc. A supplier who made large concessions across three rounds looks identical to one who opened with the same number.

**Fix:** pass the full per-supplier conversation history (or a structured summary of all rounds) to `make_decision` so the decision reflects the complete negotiation.

---

## Type Safety

### 5. `NegotiationDecision.comparison` is an untyped `dict`
**File:** `backend/models.py:41`

The field is declared as bare `dict`, discarding the detailed structure that the structured-output schema defines. Downstream code (and the frontend rendering) relies on specific keys (`cost_assessment`, `quality_assessment`, etc.) with no Pydantic enforcement.

**Fix:** introduce a `SupplierComparison` Pydantic model with the five assessment fields and change the type to `dict[str, SupplierComparison]`.

---

## Dependencies

### 6. `pydantic` is not listed in `requirements.txt`
**File:** `backend/requirements.txt`

Pydantic is a direct, explicit dependency (imported in `models.py`) but is only available transitively through `fastapi`. Any future change to FastAPI's dependency set could silently break the project.

**Fix:** add `pydantic` as an explicit entry in `requirements.txt`.

---

## Validation

### 7. No input validation on order quantities
**File:** `backend/main.py` (WebSocket handler)

The backend accepts any `dict[str, int]` for quantities — zero, negative values, unknown product codes, and missing codes are all silently passed to the agents. A quantity of 0 or a misspelled product code produces a confusing negotiation rather than a clear error.

**Fix:** add a Pydantic validator on `NegotiationRequest` (or an explicit check in the handler) that rejects non-positive quantities and codes not present in `products.json`.

---

## Resilience & Error Handling

### 8. No retry or backoff on LLM calls
**File:** `backend/agents.py`

With 19 LLM calls per negotiation and three supplier calls running in parallel via `asyncio.gather`, the app is exposed to OpenAI rate-limit errors (HTTP 429). Any single failure aborts the entire negotiation with no recovery.

**Fix:** wrap `_get_client().chat.completions.create(...)` with a retry helper (e.g. `tenacity`) using exponential backoff, retrying on rate-limit and transient network errors.

---

### 9. No WebSocket reconnection or negotiation recovery
**File:** `frontend/src/hooks/useNegotiation.js`

If the WebSocket connection drops mid-negotiation, the frontend shows an error and all progress is lost. There is no automatic reconnection and no way for the user to resume.

**Fix (short term):** detect `onerror`/`onclose` events mid-negotiation and show a "Reconnect" button that replays the start payload.
**Fix (long term):** assign each negotiation a server-side session ID and persist intermediate state so a reconnecting client can resume from the last completed round.

---

### 10. No session management for concurrent negotiations
**File:** `backend/main.py`

Multiple browser tabs each run a fully independent negotiation sharing the same OpenAI rate-limit budget. There is no queuing, concurrency cap, or mutual exclusion.

**Fix:** add a semaphore or queue in the WebSocket handler to limit the number of simultaneous in-flight negotiations, returning an informative message to clients that are made to wait.

---

## Architecture & Code Quality

### 11. Global mutable `_client` singleton
**File:** `backend/agents.py:11–17`

`_client` is a module-level mutable global. This makes the client hard to replace in tests (requiring `patch`) and prevents any future per-request configuration (e.g. different API keys or timeouts per negotiation).

**Fix:** accept an `AsyncOpenAI` instance as a constructor argument on both agent classes, defaulting to a lazily-created module-level instance for production use.

---

### 12. `main.py` is too large — orchestrator logic is mixed with routing
**File:** `backend/main.py`

The WebSocket handler contains the full negotiation loop, round logic, peer-summary helper, and static-file serving — roughly 190 lines in a single file alongside the FastAPI app definition.

**Fix:** extract the negotiation orchestrator into a dedicated `orchestrator.py` module. Keep `main.py` as the FastAPI application definition (middleware, routes, static-file mount).

---

### 13. Supplier profiles are hardcoded in Python
**File:** `backend/suppliers.py`

The three supplier profiles are embedded as Python literals rather than data. Changing a quality rating or lead time requires editing source code.

**Fix:** move supplier profiles to a `suppliers.json` file alongside `products.json` and load them with the same pattern as `load_products()`.

---

### 14. All LLM calls use the same model
**Files:** `backend/config.py`, `backend/agents.py`

Both the brand agent's decision call (which benefits from a capable model) and the supplier simulation calls (commodity role-play) use the same `MODEL_NAME`. Using a cheaper model for supplier responses would significantly reduce cost and latency.

**Fix:** introduce a second config variable (e.g. `SUPPLIER_MODEL_NAME`, defaulting to `gpt-4o-mini`) and pass different models to brand and supplier agents.

---

## Security

### 15. CORS wildcard is not suitable for production
**File:** `backend/main.py:20–26`

`allow_origins=["*"]` is set unconditionally. This must be tightened before any public deployment.

**Fix:** restrict `allow_origins` to the actual frontend origin, driven by an environment variable (e.g. `ALLOWED_ORIGIN`).

---

### 16. API key stored in a local `.env` file
**File:** `backend/.env` (git-ignored)

Acceptable for local development, but the key has no rotation mechanism and is one accidental `git add` away from exposure.

**Fix:** for any non-local deployment, inject `OPENAI_API_KEY` from a secrets manager (AWS Secrets Manager, Doppler, etc.) rather than a file on disk.

---

## Documentation Fixes

### 17. **[doc]** ARCHITECTURE.md caveat #8 is stale
**File:** `ARCHITECTURE.md`

Caveat #8 states *"The frontend connects to `ws://localhost:8000/ws/negotiate`. This won't work in production."* The actual code in `useNegotiation.js` already constructs the URL dynamically from `window.location.protocol` and `window.location.host`, making it production-safe. The caveat should be removed.

---

### 18. **[doc]** ARCHITECTURE.md caveat #15 is stale
**File:** `ARCHITECTURE.md`

Caveat #15 states *"No Dockerfile, docker-compose, or CI/CD configuration."* Both `Dockerfile` (multi-stage build) and `docker-compose.yml` already exist in the repository. The caveat should be removed.

---

### 19. **[doc]** LLM call count in ARCHITECTURE.md is incorrect
**File:** `ARCHITECTURE.md`

The data-flow section states the total is **17 LLM calls**. The actual count is **19**: `generate_rfq` is called once per supplier (3 calls, not 1), because each RFQ is personalised with the supplier's name inside `asyncio.gather`. The description and the count should be corrected.
