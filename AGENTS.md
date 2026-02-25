# Test Agent

You are a test-writing agent for a supplier negotiation app. Follow these instructions when asked to create, update, or fix tests.

## Project Layout

```
backend/                    # Python — FastAPI + OpenAI
  main.py                   # FastAPI app, WebSocket negotiation orchestrator, _peer_summary helper
  agents.py                 # BrandAgent, SupplierAgent classes (async LLM calls via AsyncOpenAI)
  models.py                 # Pydantic models: ProductComponent, Product, SupplierProfile, NegotiationRequest, NegotiationDecision
  suppliers.py              # Hardcoded SUPPLIERS list, load_products() (reads products.json), get_supplier()
  config.py                 # Loads OPENAI_API_KEY and MODEL_NAME from .env
  products.json             # Product catalog (5 SKUs)
  requirements.txt          # fastapi, uvicorn, openai, python-dotenv

frontend/                   # React — Vite + TailwindCSS v4
  src/App.jsx               # Full UI: order form, 3 chat columns, decision panel
  src/hooks/useNegotiation.js  # WebSocket lifecycle hook (messages, status, decision state)
  src/main.jsx              # React entry
  src/index.css             # TailwindCSS imports

scenarios.json              # 7 pre-built negotiation scenarios with quantities and notes
```

## Backend Tests

### Stack

- **pytest** + **pytest-asyncio** for async tests
- **httpx** for FastAPI HTTP endpoint testing (`/health`)
- **unittest.mock** (`AsyncMock`, `patch`) to mock the OpenAI client — never make real API calls
- Place tests in `backend/tests/`. Use `conftest.py` for shared fixtures.

### What to Test

#### `models.py`
- Valid construction of each Pydantic model with correct fields.
- Validation failures: missing required fields, wrong types (e.g. `targetFob` as string).
- Optional fields default to `None`.

#### `suppliers.py`
- `load_products()` returns a list of `Product` with length 5.
- Each product has a non-empty `code`, `name`, positive `targetFob`, and at least one component.
- `get_supplier(id)` returns the correct `SupplierProfile` for ids 1, 2, 3.
- `get_supplier(999)` raises `ValueError`.
- `SUPPLIERS` list has exactly 3 entries with expected names.

#### `agents.py`
Always mock `AsyncOpenAI.chat.completions.create`. Return a fake `completion` object with `choices[0].message.content` set to a canned string (or valid JSON for `make_decision`).

- **`SupplierAgent`**: calling `respond(msg)` appends user + assistant messages to `conversation_history` and returns the LLM reply.
- **`BrandAgent.generate_rfq`**: returns a string from the mocked LLM.
- **`BrandAgent.generate_counter`**: appends to the correct per-supplier history, returns a counter-proposal.
- **`BrandAgent.make_decision`**: mock the LLM to return valid JSON matching `_DECISION_SCHEMA`. Verify it returns a `NegotiationDecision` with correct `winner_supplier_id`, `winner_name`, `reasoning`, and `comparison` dict keyed by supplier name.
- Verify `RuntimeError` is raised when the LLM call throws.

#### `main.py`
- `GET /health` returns `{"status": "ok"}` with 200.
- `_peer_summary` returns a string containing peer supplier names, excluding the given ID.
- WebSocket `/ws/negotiate`: use `TestClient` or `httpx.ASGITransport` to open a WebSocket, send a `start_negotiation` payload, and assert the sequence of received message types (`status`, `message`, `decision`, `done`). Mock all agent classes so no LLM calls happen.
- WebSocket error path: send a malformed first message and assert an `error` event is returned.

### Mocking Pattern

```python
from unittest.mock import AsyncMock, patch, MagicMock

def fake_completion(content: str):
    choice = MagicMock()
    choice.message.content = content
    completion = MagicMock()
    completion.choices = [choice]
    return completion

@patch("agents._get_client")
async def test_supplier_respond(mock_get_client):
    client = AsyncMock()
    client.chat.completions.create.return_value = fake_completion("Sure, here's my quote…")
    mock_get_client.return_value = client
    # ... create SupplierAgent, call respond(), assert result
```

### Fixtures (`conftest.py`)

Provide reusable fixtures for:
- `products`: call `load_products()` once.
- `suppliers`: the 3 `SupplierProfile` objects from `suppliers.py`.
- `quantities`: a default `dict[str, int]` like `{"FSH013": 1000, "FSH014": 500, ...}`.
- `mock_openai`: auto-used fixture that patches `agents._get_client` with a configurable `AsyncMock`.

### Running

```bash
cd backend
source venv/bin/activate
pip install pytest pytest-asyncio httpx
pytest tests/ -v
```

## Frontend Tests

### Stack

- **vitest** as the test runner (already Vite-based project).
- **@testing-library/react** + **jsdom** for component rendering.
- **Mock WebSocket** via a simple class or `vi.fn()` — never open real connections.
- Place tests in `frontend/src/__tests__/` or colocated as `*.test.jsx`.

### What to Test

#### `useNegotiation` hook
- Initial state: `status === 'idle'`, empty `messages`, `decision === null`.
- After calling `startNegotiation`: status transitions to `'negotiating'`.
- Receiving a `message` event appends to the `messages` array.
- Receiving a `decision` event populates the `decision` object.
- Receiving a `done` event sets status to `'done'`.
- Receiving an `error` event sets `error` and resets status to `'idle'`.
- `clearError` clears the error state.

#### `App` component
- Renders 5 product quantity inputs with default values.
- Start button is enabled when idle, disabled when negotiating.
- Chat columns appear after negotiation starts.
- Decision panel renders when status is `'done'` and decision is set.

### WebSocket Mock Pattern

```javascript
class MockWebSocket {
  constructor() { this.sent = []; setTimeout(() => this.onopen?.(), 0); }
  send(data) { this.sent.push(JSON.parse(data)); }
  close() { this.onclose?.(); }
}
vi.stubGlobal('WebSocket', MockWebSocket);
```

### Running

```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
npx vitest run
```

## Rules

1. **Never call the real OpenAI API or open real WebSockets in tests.**
2. Keep each test focused on one behaviour. Name tests descriptively: `test_get_supplier_raises_for_unknown_id`.
3. Use `pytest.mark.asyncio` for all async backend tests.
4. Prefer fixtures over repeated setup code.
5. When testing WebSocket flows, mock the agent classes at the module level (`patch("main.BrandAgent")`) so the orchestrator logic is tested without LLM calls.
6. Load `scenarios.json` in parametrised tests when you need varied input data.
7. Don't create snapshot tests for LLM output — it's non-deterministic. Assert structure and types instead.
