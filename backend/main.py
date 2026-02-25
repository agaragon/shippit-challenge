from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from agents import BrandAgent, SupplierAgent
from models import NegotiationRequest
from suppliers import get_supplier, load_products

NEGOTIATION_ROUNDS = 3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/negotiate")
async def negotiate(ws: WebSocket):
    await ws.accept()

    try:
        # ------------------------------------------------------------------ #
        # 1. Wait for start_negotiation message
        # ------------------------------------------------------------------ #
        raw = await ws.receive_text()
        payload = json.loads(raw)

        if payload.get("type") != "start_negotiation":
            await ws.send_json({"type": "error", "message": "Expected start_negotiation message"})
            return

        req = NegotiationRequest(
            quantities=payload["quantities"],
            note=payload.get("note"),
        )

        # ------------------------------------------------------------------ #
        # 2. Bootstrap agents
        # ------------------------------------------------------------------ #
        products = load_products()
        suppliers = [get_supplier(i) for i in (1, 2, 3)]

        brand_agent = BrandAgent(
            products=products,
            suppliers=suppliers,
            quantities=req.quantities,
            note=req.note,
        )
        supplier_agents: dict[int, SupplierAgent] = {
            s.id: SupplierAgent(supplier=s, products=products) for s in suppliers
        }

        await ws.send_json({"type": "status", "message": "Agents initialised. Starting negotiation…"})

        # ------------------------------------------------------------------ #
        # Helper: stream one message event (brand or supplier turn)
        # ------------------------------------------------------------------ #
        async def send_msg(supplier_id: int, role: str, content: str, round_num: int):
            await ws.send_json({
                "type": "message",
                "supplier_id": supplier_id,
                "role": role,
                "content": content,
                "round": round_num,
            })

        # ------------------------------------------------------------------ #
        # 3. Round 1 — RFQ
        # ------------------------------------------------------------------ #
        await ws.send_json({"type": "status", "message": "Round 1 — sending RFQ to all suppliers…"})

        # Track the most recent supplier reply per supplier_id
        latest_supplier_replies: dict[int, str] = {}

        async def run_round1(supplier_id: int):
            supplier_name = supplier_agents[supplier_id].supplier.name
            rfq = await brand_agent.generate_rfq(supplier_name)
            await send_msg(supplier_id, "brand", rfq, round_num=1)
            reply = await supplier_agents[supplier_id].respond(rfq)
            latest_supplier_replies[supplier_id] = reply
            await send_msg(supplier_id, "supplier", reply, round_num=1)

        await asyncio.gather(*[run_round1(sid) for sid in supplier_agents])

        # ------------------------------------------------------------------ #
        # 4. Rounds 2 … NEGOTIATION_ROUNDS — counter-proposals
        # ------------------------------------------------------------------ #
        for round_num in range(2, NEGOTIATION_ROUNDS + 1):
            await ws.send_json({
                "type": "status",
                "message": f"Round {round_num} — brand generating counter-proposals…",
            })

            async def run_counter_round(supplier_id: int, _rn: int = round_num):
                supplier_reply = latest_supplier_replies.get(supplier_id, "")
                peer_summary = _peer_summary(supplier_id, suppliers, latest_supplier_replies)

                counter = await brand_agent.generate_counter(
                    supplier_id=supplier_id,
                    supplier_response=supplier_reply,
                    all_quotes_summary=peer_summary if _rn > 2 else None,
                )
                await send_msg(supplier_id, "brand", counter, round_num=_rn)

                new_reply = await supplier_agents[supplier_id].respond(counter)
                latest_supplier_replies[supplier_id] = new_reply
                await send_msg(supplier_id, "supplier", new_reply, round_num=_rn)

            await asyncio.gather(*[run_counter_round(sid) for sid in supplier_agents])

        # ------------------------------------------------------------------ #
        # 5. Decision
        # ------------------------------------------------------------------ #
        await ws.send_json({"type": "status", "message": "All rounds complete. Making final decision…"})

        decision = await brand_agent.make_decision(final_offers=latest_supplier_replies)

        await ws.send_json({
            "type": "decision",
            "winner_supplier_id": decision.winner_supplier_id,
            "winner_name": decision.winner_name,
            "reasoning": decision.reasoning,
            "comparison": decision.comparison,
        })

        await ws.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _peer_summary(
    exclude_supplier_id: int,
    suppliers: list,
    replies: dict[int, str],
) -> str:
    """Return a relative description of other suppliers' offers (no exact figures)."""
    peers = [s for s in suppliers if s.id != exclude_supplier_id]
    lines = []
    for s in peers:
        reply = replies.get(s.id, "")
        mention = "has quoted" if "$" in reply else "has responded"
        lines.append(
            f"  - {s.name} (quality {s.quality_rating}/5, lead {s.base_lead_time_days}d) "
            f"{mention} — appears {'competitive' if s.price_multiplier <= 1.0 else 'higher-priced'}."
        )
    return "Other suppliers in this negotiation:\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Serve built frontend (for Docker / single-process deployment)
# ---------------------------------------------------------------------------

STATIC_DIR = Path(__file__).resolve().parent / "static"

if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file = STATIC_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
