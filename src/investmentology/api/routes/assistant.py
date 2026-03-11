"""Portfolio assistant — lightweight conversational AI over existing analysis data.

Uses a fast cheap model (DeepSeek-chat) to answer questions about portfolio state,
verdicts, recommendations, thesis data, and regime guidance. Does NOT run the full
9-agent pipeline — reads existing DB data and synthesises quick answers.
"""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from investmentology.api.deps import get_gateway, get_registry
from investmentology.agents.gateway import LLMGateway
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

router = APIRouter()

# Chat history limit to keep context window reasonable
_MAX_HISTORY = 10


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str
    context_keys: list[str]  # which data sources were included
    latency_ms: int


def _build_context_packet(registry: Registry) -> tuple[str, list[str]]:
    """Build a compact context packet from current portfolio state.

    Returns (context_text, list_of_keys_included).
    """
    db = registry._db
    parts: list[str] = []
    keys: list[str] = []

    # 1. Portfolio positions
    try:
        positions = db.execute(
            "SELECT ticker, shares, entry_price, current_price, "
            "position_type, thesis_summary, thesis_health "
            "FROM invest.portfolio_positions WHERE status = 'open' "
            "ORDER BY (shares * current_price) DESC"
        )
        if positions:
            parts.append("PORTFOLIO POSITIONS:")
            total_value = 0.0
            for p in positions:
                val = float(p["shares"] * p["current_price"])
                pnl_pct = ((float(p["current_price"]) / float(p["entry_price"])) - 1) * 100 if p["entry_price"] else 0
                total_value += val
                health = p.get("thesis_health") or "N/A"
                ptype = p.get("position_type") or "core"
                parts.append(
                    f"  {p['ticker']}: {p['shares']} shares @ ${float(p['current_price']):.2f} "
                    f"(entry ${float(p['entry_price']):.2f}, P&L {pnl_pct:+.1f}%, "
                    f"type={ptype}, thesis={health})"
                )
            parts.append(f"  Total portfolio value: ${total_value:,.0f}")
            keys.append("positions")
    except Exception:
        pass

    # 2. Portfolio budget / cash
    try:
        budget = db.execute(
            "SELECT total_budget, cash_available FROM invest.portfolio_budget "
            "ORDER BY updated_at DESC LIMIT 1"
        )
        if budget:
            b = budget[0]
            parts.append(f"\nCASH: ${float(b['cash_available']):,.0f} available "
                         f"of ${float(b['total_budget']):,.0f} total budget")
            keys.append("budget")
    except Exception:
        pass

    # 3. Active alerts
    try:
        alerts = db.execute(
            "SELECT ticker, alert_type, message, severity "
            "FROM invest.portfolio_alerts WHERE resolved_at IS NULL "
            "ORDER BY created_at DESC LIMIT 10"
        )
        if alerts:
            parts.append("\nACTIVE ALERTS:")
            for a in alerts:
                parts.append(f"  [{a['severity']}] {a['ticker']}: {a['alert_type']} — {a['message']}")
            keys.append("alerts")
    except Exception:
        pass

    # 4. Latest verdicts (most recent per ticker)
    try:
        verdicts = db.execute(
            "SELECT DISTINCT ON (ticker) ticker, decision_type, confidence, "
            "reasoning, created_at "
            "FROM invest.decisions "
            "WHERE decision_type IN ('BUY', 'SELL', 'HOLD') "
            "ORDER BY ticker, created_at DESC"
        )
        if verdicts:
            parts.append("\nLATEST VERDICTS:")
            for v in verdicts:
                conf = f"{float(v['confidence']):.0%}" if v.get("confidence") else "N/A"
                reasoning = (v.get("reasoning") or "")[:120]
                parts.append(f"  {v['ticker']}: {v['decision_type']} (conf={conf}) — {reasoning}")
            keys.append("verdicts")
    except Exception:
        pass

    # 5. Top recommendations
    try:
        recs = db.execute(
            "SELECT DISTINCT ON (ticker) ticker, decision_type, confidence, "
            "reasoning, created_at "
            "FROM invest.decisions "
            "WHERE decision_type = 'BUY' "
            "AND created_at > NOW() - INTERVAL '30 days' "
            "ORDER BY ticker, created_at DESC "
            "LIMIT 10"
        )
        if recs:
            parts.append("\nRECENT BUY RECOMMENDATIONS (last 30d):")
            for r in recs:
                conf = f"{float(r['confidence']):.0%}" if r.get("confidence") else "N/A"
                parts.append(f"  {r['ticker']}: conf={conf}")
            keys.append("recommendations")
    except Exception:
        pass

    # 6. Thesis invalidation triggers
    try:
        triggers = db.execute(
            "SELECT tc.criteria_type, tc.threshold_value, tc.qualitative_text, "
            "tc.last_status, pp.ticker "
            "FROM invest.thesis_criteria tc "
            "JOIN invest.portfolio_positions pp ON tc.position_id = pp.id "
            "WHERE pp.status = 'open' AND tc.monitoring_active = true "
            "ORDER BY tc.last_status DESC, pp.ticker"
        )
        if triggers:
            parts.append("\nTHESIS INVALIDATION TRIGGERS:")
            for t in triggers:
                status = t.get("last_status") or "OK"
                flag = " **BREACHED**" if status == "BREACHED" else " *WARNING*" if status == "WARNING" else ""
                desc = t.get("threshold_value") or t.get("qualitative_text") or ""
                parts.append(f"  {t['ticker']}: {t['criteria_type']} — {desc}{flag}")
            keys.append("triggers")
    except Exception:
        pass

    # 7. Macro regime
    try:
        regime = db.execute(
            "SELECT data_value FROM invest.pipeline_data_cache "
            "WHERE data_key = 'macro_regime' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        if regime:
            val = regime[0]["data_value"]
            rd = val if isinstance(val, dict) else json.loads(val)
            parts.append(f"\nMACRO REGIME: {rd.get('regime', 'unknown')} "
                         f"(stance: {rd.get('stance', 'N/A')})")
            keys.append("regime")
    except Exception:
        pass

    # 8. Watchlist
    try:
        watch = db.execute(
            "SELECT ticker, notes FROM invest.watchlist "
            "WHERE status = 'active' ORDER BY created_at DESC LIMIT 10"
        )
        if watch:
            parts.append("\nWATCHLIST:")
            for w in watch:
                notes = (w.get("notes") or "")[:80]
                parts.append(f"  {w['ticker']}: {notes}")
            keys.append("watchlist")
    except Exception:
        pass

    return "\n".join(parts), keys


_SYSTEM_PROMPT = """\
You are the Investmentology Portfolio Assistant — a concise, data-grounded \
investment advisor. You have access to the user's live portfolio data, latest \
analysis verdicts, recommendations, thesis health, alerts, and macro regime.

Rules:
- Answer from the DATA PROVIDED below. Never fabricate positions, prices, or verdicts.
- If the data doesn't contain the answer, say so honestly.
- Be concise. 2-4 sentences for simple questions, up to a short paragraph for complex ones.
- Use specific numbers (prices, P&L %, confidence scores) when available.
- For "should I sell?" questions, reference thesis health and invalidation triggers.
- For "what should I buy?" questions, reference recent recommendations and portfolio gaps.
- Never give definitive trading advice — frame as "the data suggests" or "based on the analysis."
- If asked about a ticker not in the portfolio or recommendations, say you don't have data on it.
"""


@router.post("/assistant/chat", response_model=ChatResponse)
async def assistant_chat(
    req: ChatRequest,
    registry: Registry = Depends(get_registry),
    gateway: LLMGateway = Depends(get_gateway),
) -> dict:
    """Conversational portfolio assistant using fast LLM over existing data."""
    start = time.time()

    # Build context from current DB state
    context_text, context_keys = _build_context_packet(registry)

    # Build messages for LLM
    system = _SYSTEM_PROMPT + "\n\n--- CURRENT PORTFOLIO DATA ---\n" + context_text

    user_prompt = req.message

    # Include conversation history (truncated)
    history = req.history[-_MAX_HISTORY:]
    if history:
        conversation = "\n".join(
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}"
            for m in history
        )
        user_prompt = f"Previous conversation:\n{conversation}\n\nUser: {req.message}"

    # Call fast LLM (DeepSeek-chat preferred, fallback to groq)
    provider = "deepseek"
    model = "deepseek-chat"
    if "deepseek" not in gateway._providers:
        provider = "groq"
        model = "llama-3.3-70b-versatile"

    try:
        response = await gateway.call(
            provider=provider,
            system_prompt=system,
            user_prompt=user_prompt,
            model=model,
            max_tokens=1024,
            temperature=0.3,
        )
        reply = response.content
    except Exception as e:
        logger.exception("Assistant LLM call failed")
        reply = f"Sorry, I couldn't process that right now. Error: {str(e)[:100]}"

    latency = int((time.time() - start) * 1000)
    return {"reply": reply, "context_keys": context_keys, "latency_ms": latency}
