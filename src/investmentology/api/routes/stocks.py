"""Stock endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_registry
from investmentology.data.profile import fetch_news_from_yfinance, get_or_fetch_profile
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

router = APIRouter()


def _format_profile(p: dict) -> dict:
    """Format a stock_profiles row for JSON response."""
    return {
        "sector": p.get("sector"),
        "industry": p.get("industry"),
        "businessSummary": p.get("business_summary"),
        "website": p.get("website"),
        "employees": p.get("employees"),
        "city": p.get("city"),
        "country": p.get("country"),
        "beta": float(p["beta"]) if p.get("beta") else None,
        "dividendYield": float(p["dividend_yield"]) if p.get("dividend_yield") else None,
        "trailingPE": float(p["trailing_pe"]) if p.get("trailing_pe") else None,
        "forwardPE": float(p["forward_pe"]) if p.get("forward_pe") else None,
        "priceToBook": float(p["price_to_book"]) if p.get("price_to_book") else None,
        "priceToSales": float(p["price_to_sales"]) if p.get("price_to_sales") else None,
        "fiftyTwoWeekHigh": float(p["fifty_two_week_high"]) if p.get("fifty_two_week_high") else None,
        "fiftyTwoWeekLow": float(p["fifty_two_week_low"]) if p.get("fifty_two_week_low") else None,
        "averageVolume": p.get("average_volume"),
        "analystTarget": float(p["analyst_target"]) if p.get("analyst_target") else None,
        "analystRecommendation": p.get("analyst_recommendation"),
        "analystCount": p.get("analyst_count"),
    }


@router.get("/stock/{ticker}")
def get_stock(ticker: str, registry: Registry = Depends(get_registry)) -> dict:
    """Full deep dive: profile, fundamentals, signals, decisions, watchlist state."""
    ticker = ticker.upper()

    # Business profile (cached, fetched from yfinance on-demand)
    profile_data = None
    try:
        profile_row = get_or_fetch_profile(registry._db, ticker)
        if profile_row:
            profile_data = _format_profile(profile_row)
    except Exception:
        logger.debug("Could not fetch profile for %s", ticker)

    # Fundamentals
    fundamentals = registry.get_latest_fundamentals(ticker)
    fund_data = None
    if fundamentals:
        fund_data = {
            "ticker": fundamentals.ticker,
            "fetched_at": str(fundamentals.fetched_at),
            "market_cap": float(fundamentals.market_cap),
            "operating_income": float(fundamentals.operating_income),
            "revenue": float(fundamentals.revenue),
            "net_income": float(fundamentals.net_income),
            "total_debt": float(fundamentals.total_debt),
            "cash": float(fundamentals.cash),
            "shares_outstanding": fundamentals.shares_outstanding,
            "price": float(fundamentals.price),
            "earnings_yield": float(fundamentals.earnings_yield) if fundamentals.earnings_yield else None,
            "roic": float(fundamentals.roic) if fundamentals.roic else None,
            "enterprise_value": float(fundamentals.enterprise_value),
        }

    # Signals
    signal_rows = registry._db.execute(
        "SELECT agent_name, model, signals, confidence, reasoning, created_at "
        "FROM invest.agent_signals WHERE ticker = %s ORDER BY created_at DESC LIMIT 20",
        (ticker,),
    )

    # Decisions
    decisions = registry.get_decisions(ticker=ticker, limit=20)
    decision_data = [
        {
            "id": str(d.id),
            "decisionType": d.decision_type.value,
            "layer": d.layer_source,
            "confidence": float(d.confidence) if d.confidence else None,
            "reasoning": d.reasoning,
            "createdAt": str(d.created_at) if d.created_at else None,
        }
        for d in decisions
    ]

    # Watchlist state
    watchlist_rows = registry._db.execute(
        "SELECT state, notes, updated_at FROM invest.watchlist "
        "WHERE ticker = %s ORDER BY updated_at DESC LIMIT 1",
        (ticker,),
    )
    watchlist = None
    if watchlist_rows:
        w = watchlist_rows[0]
        watchlist = {
            "state": w["state"],
            "notes": w["notes"],
            "updated_at": str(w["updated_at"]) if w["updated_at"] else None,
        }

    # Quant gate scoring (latest run)
    qg_rows = registry._db.execute(
        "SELECT r.combined_rank, r.ey_rank, r.roic_rank, r.piotroski_score, "
        "r.altman_z_score, r.altman_zone, r.composite_score, "
        "s.name, s.sector, s.market_cap "
        "FROM invest.quant_gate_results r "
        "LEFT JOIN invest.stocks s ON s.ticker = r.ticker "
        "WHERE r.ticker = %s ORDER BY r.run_id DESC LIMIT 1",
        (ticker,),
    )
    quant_gate = None
    if qg_rows:
        q = qg_rows[0]
        quant_gate = {
            "combinedRank": q["combined_rank"],
            "eyRank": q["ey_rank"],
            "roicRank": q["roic_rank"],
            "piotroskiScore": q["piotroski_score"],
            "altmanZScore": float(q["altman_z_score"]) if q["altman_z_score"] else None,
            "altmanZone": q["altman_zone"],
            "compositeScore": float(q["composite_score"]) if q["composite_score"] else None,
        }

    # Verdict history (latest + previous)
    verdict_history_rows = registry.get_verdict_history(ticker, limit=20)
    verdict_data = None
    verdict_history: list[dict] = []
    for vr in verdict_history_rows:
        entry = {
            "recommendation": vr["verdict"],
            "confidence": float(vr["confidence"]) if vr["confidence"] else None,
            "consensusScore": float(vr["consensus_score"]) if vr["consensus_score"] else None,
            "reasoning": vr["reasoning"],
            "agentStances": vr["agent_stances"],
            "riskFlags": vr["risk_flags"],
            "auditorOverride": vr["auditor_override"],
            "mungerOverride": vr["munger_override"],
            "createdAt": str(vr["created_at"]) if vr["created_at"] else None,
        }
        verdict_history.append(entry)
    if verdict_history:
        verdict_data = verdict_history[0]

    # Competence & moat from latest L2 decision
    competence_data = None
    for d in decisions:
        if d.decision_type.value in ("COMPETENCE_PASS", "COMPETENCE_FAIL"):
            competence_data = {
                "passed": d.decision_type.value == "COMPETENCE_PASS",
                "confidence": float(d.confidence) if d.confidence else None,
                "reasoning": d.reasoning,
            }
            if d.signals:
                competence_data["in_circle"] = d.signals.get("in_circle")
                competence_data["sector_familiarity"] = d.signals.get("sector_familiarity")
                competence_data["moat"] = d.signals.get("moat")
            break

    # Stock name — prefer profile data, fall back to stocks table
    stock_name = ticker
    stock_sector = ""
    stock_industry = ""
    if profile_data:
        stock_sector = profile_data.get("sector") or ""
        stock_industry = profile_data.get("industry") or ""
    stock_rows = registry._db.execute(
        "SELECT name, sector, industry FROM invest.stocks WHERE ticker = %s",
        (ticker,),
    )
    if stock_rows:
        stock_name = stock_rows[0]["name"] or ticker
        if not stock_sector:
            stock_sector = stock_rows[0].get("sector") or ""
        if not stock_industry:
            stock_industry = stock_rows[0].get("industry") or ""

    return {
        "ticker": ticker,
        "name": stock_name,
        "sector": stock_sector,
        "industry": stock_industry,
        "profile": profile_data,
        "fundamentals": fund_data,
        "quantGate": quant_gate,
        "competence": competence_data,
        "verdict": verdict_data,
        "verdictHistory": verdict_history,
        "signals": [
            {
                "agentName": r["agent_name"],
                "model": r["model"],
                "signals": r["signals"],
                "confidence": float(r["confidence"]) if r["confidence"] else None,
                "reasoning": r["reasoning"],
                "createdAt": str(r["created_at"]) if r["created_at"] else None,
            }
            for r in signal_rows
        ],
        "decisions": decision_data,
        "watchlist": watchlist,
    }


@router.get("/stock/{ticker}/news")
def get_stock_news(ticker: str) -> dict:
    """Fetch recent news articles for a ticker."""
    ticker = ticker.upper()
    articles = fetch_news_from_yfinance(ticker, limit=12)
    return {"ticker": ticker, "articles": articles}


@router.get("/stock/{ticker}/signals")
def get_stock_signals(ticker: str, registry: Registry = Depends(get_registry)) -> dict:
    """Agent signal sets for a ticker."""
    ticker = ticker.upper()
    rows = registry._db.execute(
        "SELECT id, agent_name, model, signals, confidence, reasoning, "
        "token_usage, latency_ms, created_at "
        "FROM invest.agent_signals WHERE ticker = %s ORDER BY created_at DESC",
        (ticker,),
    )
    return {
        "ticker": ticker,
        "signals": [
            {
                "id": r["id"],
                "agent_name": r["agent_name"],
                "model": r["model"],
                "signals": r["signals"],
                "confidence": float(r["confidence"]) if r["confidence"] else None,
                "reasoning": r["reasoning"],
                "token_usage": r["token_usage"],
                "latency_ms": r["latency_ms"],
                "created_at": str(r["created_at"]) if r["created_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/stock/{ticker}/decisions")
def get_stock_decisions(ticker: str, registry: Registry = Depends(get_registry)) -> dict:
    """Decision history for a ticker."""
    ticker = ticker.upper()
    decisions = registry.get_decisions(ticker=ticker, limit=100)
    return {
        "ticker": ticker,
        "decisions": [
            {
                "id": d.id,
                "decision_type": d.decision_type.value,
                "layer_source": d.layer_source,
                "confidence": float(d.confidence) if d.confidence else None,
                "reasoning": d.reasoning,
                "signals": d.signals,
                "metadata": d.metadata,
                "created_at": str(d.created_at) if d.created_at else None,
            }
            for d in decisions
        ],
    }
