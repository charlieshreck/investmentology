"""Thesis lifecycle API endpoints.

Phase 6: Thesis health, investment story, verdict journey, portfolio risk.
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from investmentology.api.deps import get_registry
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

router = APIRouter()


class ThesisHealthResponse(BaseModel):
    ticker: str
    thesis_health: str
    conviction_trend: float
    bearish_ratio: float
    consecutive_bearish: int
    reasoning: str


class ThesisEventResponse(BaseModel):
    id: int
    ticker: str
    event_type: str
    thesis_text: str | None
    position_type: str | None
    verdict_at_time: str | None
    confidence_at_time: float | None
    price_at_time: float | None
    created_at: str


class InvestmentStoryResponse(BaseModel):
    ticker: str
    entry_thesis: str | None
    thesis_health: str
    position_type: str
    entry_date: str | None
    entry_price: float | None
    current_price: float | None
    pnl_pct: float
    days_held: int
    conviction_trend: float
    thesis_events: list[dict]
    verdict_journey: list[dict]


class VerdictDiffResponse(BaseModel):
    ticker: str
    old_verdict: str
    new_verdict: str
    was_gated: bool
    gating_reason: str | None
    created_at: str


class PortfolioThesisSummaryItem(BaseModel):
    ticker: str
    position_type: str
    thesis_health: str
    entry_thesis: str | None
    pnl_pct: float
    days_held: int
    conviction_trend: float


class PortfolioRiskResponse(BaseModel):
    total_value: float
    position_count: int
    sector_concentration: dict
    top_position_weight: float
    avg_thesis_health_score: float
    positions: list[PortfolioThesisSummaryItem]


@router.get("/portfolio/thesis/{ticker}")
async def get_thesis_detail(
    ticker: str,
    registry: Registry = Depends(get_registry),
) -> dict:
    """Get full thesis lifecycle detail for a ticker.

    Returns: entry_thesis, thesis_health, thesis_events, verdict_chain,
    conviction_trend, investment story.
    """
    ticker = ticker.upper()

    # Get position info
    positions = registry.get_open_positions()
    pos = next((p for p in positions if p.ticker == ticker), None)

    if not pos:
        return {"error": f"No open position found for {ticker}"}

    # Thesis health assessment
    from investmentology.advisory.thesis_health import assess_thesis_health
    assessment = assess_thesis_health(ticker, registry, pos.position_type)

    # Thesis events
    try:
        events = registry._db.execute(
            "SELECT id, ticker, event_type, thesis_text, position_type, "
            "verdict_at_time, confidence_at_time, price_at_time, created_at "
            "FROM invest.thesis_events WHERE ticker = %s "
            "ORDER BY created_at DESC LIMIT 20",
            (ticker,),
        )
    except Exception:
        events = []

    # Verdict journey
    verdicts = registry.get_verdict_history(ticker, limit=20)
    verdict_journey = []
    for v in reversed(verdicts):
        verdict_journey.append({
            "verdict": v.get("verdict"),
            "confidence": float(v["confidence"]) if v.get("confidence") else None,
            "consensus_score": float(v["consensus_score"]) if v.get("consensus_score") else None,
            "date": str(v["created_at"]) if v.get("created_at") else None,
            "reasoning": (v.get("reasoning") or "")[:200],
        })

    # Verdict diffs (gating events)
    try:
        diffs = registry._db.execute(
            "SELECT * FROM invest.verdict_diffs WHERE ticker = %s "
            "ORDER BY created_at DESC LIMIT 10",
            (ticker,),
        )
    except Exception:
        diffs = []

    days_held = (date.today() - pos.entry_date).days if pos.entry_date else 0
    pnl_pct = float(pos.pnl_pct * 100) if pos.entry_price else 0

    # Get entry_thesis from position
    entry_thesis = pos.thesis
    try:
        et_rows = registry._db.execute(
            "SELECT entry_thesis FROM invest.portfolio_positions "
            "WHERE ticker = %s AND is_closed = false LIMIT 1",
            (ticker,),
        )
        if et_rows and et_rows[0].get("entry_thesis"):
            entry_thesis = et_rows[0]["entry_thesis"]
    except Exception:
        pass

    return {
        "ticker": ticker,
        "position_type": pos.position_type,
        "entry_date": str(pos.entry_date) if pos.entry_date else None,
        "entry_price": float(pos.entry_price),
        "current_price": float(pos.current_price),
        "pnl_pct": pnl_pct,
        "days_held": days_held,
        "entry_thesis": entry_thesis,
        "thesis_health": assessment.health.value,
        "conviction_trend": assessment.conviction_trend,
        "bearish_ratio": assessment.bearish_ratio,
        "consecutive_bearish": assessment.consecutive_bearish,
        "health_reasoning": assessment.reasoning,
        "thesis_events": [
            {
                "id": e["id"],
                "event_type": e["event_type"],
                "thesis_text": e.get("thesis_text"),
                "verdict_at_time": e.get("verdict_at_time"),
                "confidence_at_time": float(e["confidence_at_time"]) if e.get("confidence_at_time") else None,
                "price_at_time": float(e["price_at_time"]) if e.get("price_at_time") else None,
                "date": str(e["created_at"]),
            }
            for e in (events or [])
        ],
        "verdict_journey": verdict_journey,
        "verdict_diffs": [
            {
                "old_verdict": d.get("old_verdict"),
                "new_verdict": d.get("new_verdict"),
                "was_gated": d.get("was_gated", False),
                "gating_reason": d.get("gating_reason"),
                "date": str(d["created_at"]) if d.get("created_at") else None,
            }
            for d in (diffs or [])
        ],
    }


@router.get("/portfolio/thesis-summary")
async def get_thesis_summary(
    registry: Registry = Depends(get_registry),
) -> dict:
    """Get thesis health summary for all open positions.

    Lightweight endpoint for the Portfolio view — returns per-position
    thesis health and one-liner, without full event history.
    """
    from investmentology.advisory.thesis_health import assess_thesis_health

    positions = registry.get_open_positions()
    if not positions:
        return {"positions": []}

    summaries = []
    for pos in positions:
        assessment = assess_thesis_health(pos.ticker, registry, pos.position_type)
        days_held = (date.today() - pos.entry_date).days if pos.entry_date else 0
        pnl_pct = float(pos.pnl_pct * 100) if pos.entry_price else 0

        # Get entry_thesis
        entry_thesis = pos.thesis
        try:
            et_rows = registry._db.execute(
                "SELECT entry_thesis FROM invest.portfolio_positions "
                "WHERE ticker = %s AND is_closed = false LIMIT 1",
                (pos.ticker,),
            )
            if et_rows and et_rows[0].get("entry_thesis"):
                entry_thesis = et_rows[0]["entry_thesis"]
        except Exception:
            pass

        summaries.append({
            "ticker": pos.ticker,
            "position_type": pos.position_type,
            "thesis_health": assessment.health.value,
            "entry_thesis": entry_thesis,
            "pnl_pct": pnl_pct,
            "days_held": days_held,
            "conviction_trend": assessment.conviction_trend,
            "reasoning": assessment.reasoning,
        })

    return {"positions": summaries}


@router.get("/portfolio/risk-snapshot")
async def get_portfolio_risk(
    registry: Registry = Depends(get_registry),
) -> dict:
    """Get current portfolio-level risk snapshot.

    Returns sector concentration, position weights, thesis health overview,
    and overall risk level.
    """
    from investmentology.advisory.thesis_health import assess_thesis_health

    positions = registry.get_open_positions()
    if not positions:
        return {
            "total_value": 0,
            "position_count": 0,
            "sector_concentration": {},
            "top_position_weight": 0,
            "avg_thesis_health_score": 0,
            "risk_level": "NORMAL",
            "positions": [],
        }

    total_value = float(sum(p.current_price * p.shares for p in positions))

    # Sector concentration
    stocks = registry.get_active_stocks()
    stock_map = {s.ticker: s for s in stocks}
    sector_values: dict[str, float] = {}
    for p in positions:
        stock = stock_map.get(p.ticker)
        sector = stock.sector if stock else "Unknown"
        mv = float(p.current_price * p.shares)
        sector_values[sector] = sector_values.get(sector, 0) + mv

    sector_pcts = {s: v / total_value * 100 for s, v in sector_values.items()} if total_value > 0 else {}

    # Position weights
    pos_weights = []
    for p in positions:
        w = float(p.current_price * p.shares) / total_value * 100 if total_value > 0 else 0
        pos_weights.append(w)

    top_weight = max(pos_weights) if pos_weights else 0

    # Thesis health scores (INTACT=1.0, UNDER_REVIEW=0.7, CHALLENGED=0.4, BROKEN=0.1)
    health_scores = {"INTACT": 1.0, "UNDER_REVIEW": 0.7, "CHALLENGED": 0.4, "BROKEN": 0.1}
    scores = []
    pos_details = []
    for p in positions:
        assessment = assess_thesis_health(p.ticker, registry, p.position_type)
        scores.append(health_scores.get(assessment.health.value, 0.5))
        days_held = (date.today() - p.entry_date).days if p.entry_date else 0
        pnl_pct = float(p.pnl_pct * 100) if p.entry_price else 0
        pos_details.append({
            "ticker": p.ticker,
            "position_type": p.position_type,
            "thesis_health": assessment.health.value,
            "weight_pct": float(p.current_price * p.shares) / total_value * 100 if total_value > 0 else 0,
            "pnl_pct": pnl_pct,
            "days_held": days_held,
        })

    avg_health = sum(scores) / len(scores) if scores else 0

    # Determine risk level
    risk_level = "NORMAL"
    if avg_health < 0.4:
        risk_level = "CRITICAL"
    elif avg_health < 0.6:
        risk_level = "HIGH"
    elif avg_health < 0.8 or top_weight > 25:
        risk_level = "ELEVATED"

    return {
        "total_value": total_value,
        "position_count": len(positions),
        "sector_concentration": sector_pcts,
        "top_position_weight": top_weight,
        "avg_thesis_health_score": avg_health,
        "risk_level": risk_level,
        "positions": pos_details,
    }
