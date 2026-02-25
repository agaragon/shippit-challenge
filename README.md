# Supplier Negotiation Agent

AI-powered multi-supplier negotiation app. A brand agent negotiates simultaneously with three supplier agents over WebSocket, comparing offers across cost, quality, lead time, and payment terms, then picks a winner with structured reasoning.

Built as a response to a coding challenge simulating brand–supplier procurement for footwear products.

## Architecture

```
React (Vite + TailwindCSS)  ──WebSocket──►  FastAPI
                                              │
                                  ┌───────────┼───────────┐
                              Brand Agent   Supplier 1   Supplier 2   Supplier 3
                              (orchestrator)  Agent        Agent        Agent
```

- **Brand Agent** — generates RFQs, counter-proposals using competitive leverage, and a final structured decision.
- **Supplier Agents** — each has a distinct profile (quality, cost tier, lead time, payment terms) and negotiates independently via LLM calls.
- **WebSocket** — streams every message in real time to the frontend as the negotiation unfolds.

## Prerequisites

- Python 3.11+
- Node.js 18+
- An OpenAI API key (GPT-4o by default)

## Setup & Run

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, configure quantities, and click **Start Negotiation**.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | Required. Set in `backend/.env` |
| `MODEL_NAME` | `gpt-4o` | LLM model used for all agents |
| `NEGOTIATION_ROUNDS` | `3` | Number of negotiation rounds (set in `backend/main.py`) |

## Project Structure

```
backend/
  main.py          # FastAPI app, WebSocket negotiation orchestrator
  agents.py        # BrandAgent and SupplierAgent classes
  models.py        # Pydantic models
  suppliers.py     # Supplier profiles and product loader
  products.json    # Product catalog (5 SKUs)
  config.py        # Env config
frontend/
  src/
    App.jsx                    # Main UI (controls, chat columns, decision panel)
    hooks/useNegotiation.js    # WebSocket state management hook
```
