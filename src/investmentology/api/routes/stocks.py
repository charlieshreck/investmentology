"""Stock endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query

from investmentology.api.deps import get_registry
from investmentology.api.routes.shared import consensus_tier, verdict_stability
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


def _build_briefing(
    ticker: str,
    name: str,
    verdict: dict | None,
    position: dict | None,
    all_positions: list,
    fundamentals: dict | None,
    profile: dict | None,
    competence: dict | None,
    quant_gate: dict | None,
) -> dict | None:
    """Build a plain-English briefing synthesizing all data into actionable guidance."""
    if not verdict:
        return None

    rec = verdict.get("recommendation", "")
    conf = verdict.get("confidence")
    conf_pct = f"{conf * 100:.0f}%" if conf else "unknown"
    stances = verdict.get("agentStances") or []
    risk_flags = verdict.get("riskFlags") or []
    price = fundamentals.get("price") if fundamentals else None

    # Count bulls vs bears
    bulls = [s for s in stances if s.get("sentiment", 0) > 0.1]
    bears = [s for s in stances if s.get("sentiment", 0) < -0.1]
    bull_names = [s["name"].capitalize() for s in bulls]
    bear_names = [s["name"].capitalize() for s in bears]

    # Short company descriptor
    short_name = name.split(",")[0].split(" Inc")[0].split(" Corp")[0].strip()

    # --- Build the narrative pieces ---
    headline = ""
    situation = ""
    action = ""
    rationale_parts: list[str] = []

    # Position-aware context
    if position:
        pnl = position.get("pnl", 0)
        pnl_pct = position.get("pnlPct", 0)
        shares = position.get("shares", 0)
        entry = position.get("entryPrice", 0)
        pos_type = position.get("positionType", "tactical")
        pnl_dir = "up" if pnl >= 0 else "down"
        pnl_str = f"${abs(pnl):,.0f} ({abs(pnl_pct):.1f}%)"

        situation = (
            f"You hold {int(shares)} shares of {short_name} at ${entry:.2f}. "
            f"You're currently {pnl_dir} {pnl_str}. "
            f"This is a {pos_type} position."
        )

        fair_value = position.get("fairValue")
        stop_loss = position.get("stopLoss")
        if fair_value and price:
            upside = ((fair_value - price) / price) * 100
            if upside > 0:
                rationale_parts.append(
                    f"Our agents estimate fair value at ${fair_value:.2f}, "
                    f"suggesting {upside:.0f}% upside from here."
                )
            else:
                rationale_parts.append(
                    f"Our agents estimate fair value at ${fair_value:.2f}, "
                    f"which is {abs(upside):.0f}% below the current price."
                )
        if stop_loss:
            rationale_parts.append(f"Stop loss is set at ${stop_loss:.2f}.")

        # Action based on verdict + position
        if rec in ("STRONG_BUY", "BUY"):
            headline = f"Keep holding — the thesis is intact"
            action = f"The system rates {ticker} a {rec} with {conf_pct} confidence. Consider adding to this position if you have available capital."
        elif rec == "ACCUMULATE":
            headline = f"Gradually add on dips"
            action = f"The fundamentals support building this position over time. Look for pullbacks to add shares at better prices."
        elif rec in ("REDUCE", "SELL"):
            headline = f"Consider reducing your exposure"
            action = f"The system flags {ticker} as {rec}. Review whether your original thesis still holds and consider trimming."
        elif rec == "WATCHLIST":
            headline = f"Hold but watch closely"
            action = f"Mixed signals — the position is worth keeping but not adding to right now. Monitor for the risk flags to resolve."
        elif rec == "HOLD":
            headline = f"No action needed right now"
            action = f"The position is stable. Hold and review at the next analysis cycle."
        elif rec == "AVOID":
            headline = f"This position may need exiting"
            action = f"The system rates {ticker} as AVOID. Review urgently — this may warrant selling."
        else:
            headline = f"Review this position"
            action = f"Verdict: {rec} at {conf_pct} confidence."
    else:
        # Not held — should you buy?
        situation = f"{short_name} is not currently in your portfolio."

        if rec in ("STRONG_BUY", "BUY"):
            headline = f"Strong candidate for purchase"
            action = f"The system rates {ticker} a {rec} with {conf_pct} confidence. This could be worth initiating a position."
        elif rec == "ACCUMULATE":
            headline = f"Worth starting a small position"
            action = f"Start accumulating gradually. Don't go all-in — build the position over time."
        elif rec == "WATCHLIST":
            headline = f"Interesting but not ready yet"
            action = f"Add to your watch list and wait for a better entry point or for risk flags to clear."
        elif rec in ("HOLD", "REDUCE", "SELL"):
            headline = f"Not recommended for purchase"
            action = f"The system does not recommend initiating a new position in {ticker} right now."
        elif rec == "AVOID":
            headline = f"Stay away"
            action = f"Multiple agents flag significant concerns. There are better opportunities elsewhere."
        else:
            headline = f"{rec} — needs more analysis"
            action = f"Run the full analysis pipeline for a clearer picture."

    # Agent consensus narrative
    if bulls and bears:
        rationale_parts.append(
            f"{', '.join(bull_names)} {'are' if len(bulls) > 1 else 'is'} bullish, "
            f"while {', '.join(bear_names)} {'raise' if len(bears) > 1 else 'raises'} concerns."
        )
    elif bulls:
        rationale_parts.append(f"All active agents ({', '.join(bull_names)}) are bullish.")
    elif bears:
        rationale_parts.append(f"All active agents ({', '.join(bear_names)}) are cautious or bearish.")

    # Risk flag narrative
    if risk_flags:
        flag_labels = []
        for f in risk_flags:
            label = f.split(":")[0].strip().replace("_", " ").lower()
            flag_labels.append(label)
        rationale_parts.append(f"Key risks: {', '.join(flag_labels)}.")

    # Portfolio context
    total_value = sum(
        float(p.current_price) * float(p.shares) for p in all_positions
    ) if all_positions else 0
    if total_value > 0 and position:
        weight = (position.get("currentPrice", 0) * position.get("shares", 0)) / total_value * 100
        rationale_parts.append(f"This position is {weight:.1f}% of your portfolio.")

    # Sector context
    if all_positions and fundamentals:
        from collections import Counter
        # Get sector of this stock
        this_sector = profile.get("sector") if profile else None
        if this_sector:
            sector_count = sum(1 for p in all_positions if hasattr(p, 'ticker'))
            # Simple check — we don't have sector per position easily, skip if complex
            pass

    # Quant gate summary
    if quant_gate:
        comp = quant_gate.get("compositeScore")
        piotroski = quant_gate.get("piotroskiScore")
        altman = quant_gate.get("altmanZone")
        qg_parts = []
        if comp is not None:
            qg_parts.append(f"composite score {comp:.2f}")
        if piotroski is not None:
            qg_parts.append(f"Piotroski {piotroski}/9")
        if altman:
            qg_parts.append(f"Altman {altman}")
        if qg_parts:
            rationale_parts.append(f"Quantitative health: {', '.join(qg_parts)}.")

    # Analyst target
    if profile and profile.get("analystTarget") and price:
        target = profile["analystTarget"]
        diff_pct = ((target - price) / price) * 100
        if abs(diff_pct) > 2:
            direction = "above" if diff_pct > 0 else "below"
            rationale_parts.append(
                f"Wall Street target is ${target:.0f} ({abs(diff_pct):.0f}% {direction} current price)."
            )

    return {
        "headline": headline,
        "situation": situation,
        "action": action,
        "rationale": " ".join(rationale_parts),
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

    # Position data (if held)
    position_data = None
    positions = registry.get_open_positions()
    held = next((p for p in positions if p.ticker == ticker), None)
    if held:
        current = float(fund_data["price"]) if fund_data and fund_data.get("price") else float(held.current_price)
        entry = float(held.entry_price)
        pnl = (current - entry) * float(held.shares)
        pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
        position_data = {
            "id": held.id,
            "shares": float(held.shares),
            "entryPrice": entry,
            "currentPrice": current,
            "positionType": held.position_type,
            "weight": float(held.weight) if held.weight else None,
            "stopLoss": float(held.stop_loss) if held.stop_loss else None,
            "fairValue": float(held.fair_value_estimate) if held.fair_value_estimate else None,
            "pnl": round(pnl, 2),
            "pnlPct": round(pnl_pct, 2),
            "entryDate": str(held.entry_date) if held.entry_date else None,
            "thesis": held.thesis or None,
        }

    # Signal enrichment: buzz, earnings momentum, stability, consensus tier
    buzz_data = None
    try:
        buzz_rows = registry._db.execute(
            "SELECT buzz_score, buzz_label, headline_sentiment, "
            "news_count_7d, news_count_30d, contrarian_flag "
            "FROM invest.buzz_scores WHERE ticker = %s ORDER BY scored_at DESC LIMIT 1",
            (ticker,),
        )
        if buzz_rows:
            b = buzz_rows[0]
            buzz_data = {
                "buzzScore": b["buzz_score"],
                "buzzLabel": b["buzz_label"],
                "headlineSentiment": float(b["headline_sentiment"]) if b["headline_sentiment"] else None,
                "articleCount": (b["news_count_7d"] or 0) + (b["news_count_30d"] or 0),
                "contrarianFlag": b.get("contrarian_flag", False),
            }
    except Exception:
        logger.debug("Could not fetch buzz for %s", ticker)

    earnings_data = None
    try:
        em_rows = registry._db.execute(
            "SELECT momentum_score, momentum_label, upward_revisions, downward_revisions, beat_streak "
            "FROM invest.earnings_momentum WHERE ticker = %s ORDER BY computed_at DESC LIMIT 1",
            (ticker,),
        )
        if em_rows:
            em = em_rows[0]
            earnings_data = {
                "score": float(em["momentum_score"]) if em["momentum_score"] else 0,
                "label": em["momentum_label"],
                "upwardRevisions": em["upward_revisions"] or 0,
                "downwardRevisions": em["downward_revisions"] or 0,
                "beatStreak": em["beat_streak"] or 0,
            }
    except Exception:
        logger.debug("Could not fetch earnings momentum for %s", ticker)

    stab_score, stab_label = verdict_stability(ticker, registry)
    cons_tier = consensus_tier(
        float(verdict_data["consensusScore"]) if verdict_data and verdict_data.get("consensusScore") else None
    )

    # Synthesized briefing — plain English, position-aware
    briefing = _build_briefing(
        ticker, stock_name, verdict_data, position_data, positions,
        fund_data, profile_data, competence_data, quant_gate,
    )

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
        "position": position_data,
        "briefing": briefing,
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
        "buzz": buzz_data,
        "earningsMomentum": earnings_data,
        "stabilityScore": stab_score,
        "stabilityLabel": stab_label,
        "consensusTier": cons_tier,
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


# Period map: query param -> yfinance period/interval
_CHART_PERIODS = {
    "1w": ("5d", "15m"),
    "1mo": ("1mo", "1d"),
    "3mo": ("3mo", "1d"),
    "6mo": ("6mo", "1d"),
    "1y": ("1y", "1wk"),
    "ytd": ("ytd", "1d"),
}


@router.get("/stock/{ticker}/chart")
def get_stock_chart(
    ticker: str,
    period: str = Query("1mo", regex="^(1w|1mo|3mo|6mo|1y|ytd)$"),
) -> dict:
    """Price chart data from yfinance. Returns OHLCV time series."""
    import yfinance as yf

    ticker = ticker.upper()
    yf_period, yf_interval = _CHART_PERIODS.get(period, ("1mo", "1d"))

    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=yf_period, interval=yf_interval)
        if hist.empty:
            return {"ticker": ticker, "period": period, "data": []}

        data = []
        for dt, row in hist.iterrows():
            ts = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
            data.append({
                "date": ts,
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        return {"ticker": ticker, "period": period, "data": data}
    except Exception as exc:
        logger.warning("Chart fetch failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "period": period, "data": [], "error": str(exc)}
