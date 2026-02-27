"""Recommendations endpoints — stocks that have met all criteria, ready for portfolio action."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_registry
from investmentology.advisory.portfolio_fit import PortfolioFitScorer
from investmentology.api.routes.shared import (
    consensus_tier as _consensus_tier,
    get_dividend_data,
    success_probability as _success_probability,
    verdict_stability as _verdict_stability,
)
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

router = APIRouter()

# Positive verdicts indicating the stock passed all criteria
POSITIVE_VERDICTS = {"STRONG_BUY", "BUY", "ACCUMULATE"}
VERDICT_ORDER = ["STRONG_BUY", "BUY", "ACCUMULATE"]


def _build_price_history(row: dict, registry: Registry) -> list[dict]:
    """Build price history for a recommendation from verdict history."""
    ticker = row.get("ticker")
    if not ticker or not registry:
        return []

    try:
        rows = registry._db.execute(
            """SELECT v.verdict, v.confidence, v.created_at
               FROM invest.verdicts v
               WHERE v.ticker = %s
               ORDER BY v.created_at DESC
               LIMIT 10""",
            (ticker,),
        )
        if not rows:
            return []

        return [
            {
                "date": str(r["created_at"])[:10] if r.get("created_at") else None,
                "verdict": r.get("verdict"),
                "confidence": float(r["confidence"]) if r.get("confidence") else None,
            }
            for r in rows
        ]
    except Exception:
        return []

def _format_recommendation(row: dict, registry: Registry | None = None) -> dict:
    entry_price = float(row["entry_price"]) if row.get("entry_price") else 0.0
    current_price = float(row["current_price"]) if row.get("current_price") else 0.0
    change_pct = (
        ((current_price - entry_price) / entry_price * 100)
        if entry_price > 0 else 0.0
    )

    # Compute verdict stability and consensus tier
    cons_score = float(row["consensus_score"]) if row.get("consensus_score") else None
    stability = row.get("_stability")  # Pre-computed if registry available
    cons_tier = _consensus_tier(cons_score)

    result = {
        "ticker": row["ticker"],
        "name": row.get("name") or row["ticker"],
        "sector": row.get("sector") or "",
        "industry": row.get("industry") or "",
        "currentPrice": current_price,
        "marketCap": float(row["market_cap"]) if row.get("market_cap") else 0,
        "watchlistState": row.get("watchlist_state"),
        "verdict": row["verdict"],
        "confidence": float(row["confidence"]) if row.get("confidence") else None,
        "consensusScore": cons_score,
        "consensusTier": cons_tier,
        "reasoning": row.get("reasoning"),
        "agentStances": row.get("agent_stances"),
        "riskFlags": row.get("risk_flags"),
        "auditorOverride": row.get("auditor_override", False),
        "mungerOverride": row.get("munger_override", False),
        "analysisDate": str(row["created_at"]) if row.get("created_at") else None,
        "successProbability": _success_probability(row),
        "changePct": round(change_pct, 2),
        "priceHistory": _build_price_history(row, registry) if registry else row.get("price_history") or [],
    }

    if stability:
        result["stabilityScore"] = stability[0]
        result["stabilityLabel"] = stability[1]

    # Add portfolio fit if scorer is available
    fit = row.get("_portfolio_fit")
    if fit:
        result["portfolioFit"] = {
            "score": fit.score,
            "reasoning": fit.reasoning,
            "diversificationScore": fit.diversification_score,
            "balanceScore": fit.balance_score,
            "capacityScore": fit.capacity_score,
            "alreadyHeld": fit.already_held,
        }

    # Add dividend data if available
    div_data = row.get("_dividend_data")
    if div_data:
        result["dividendYield"] = div_data["yield"]
        result["annualDividend"] = div_data["annual"]
        result["dividendFrequency"] = div_data["frequency"]

    # Add buzz score
    buzz = row.get("_buzz")
    if buzz:
        result["buzzScore"] = buzz["buzz_score"]
        result["buzzLabel"] = buzz["buzz_label"]
        result["headlineSentiment"] = buzz["headline_sentiment"]
        result["contrarianFlag"] = buzz.get("contrarian_flag", False)

    # Add earnings momentum
    earnings_m = row.get("_earnings_momentum")
    if earnings_m:
        result["earningsMomentum"] = {
            "score": earnings_m["momentum_score"],
            "label": earnings_m["momentum_label"],
            "upwardRevisions": earnings_m["upward_revisions"],
            "downwardRevisions": earnings_m["downward_revisions"],
            "beatStreak": earnings_m["beat_streak"],
        }

    # Suggest position type: core (long-term hold) vs tactical (shorter-term)
    core_signals = 0
    tactical_signals = 0
    verdict = row.get("verdict", "")
    if verdict == "STRONG_BUY":
        core_signals += 2
    elif verdict == "ACCUMULATE":
        core_signals += 1
    conf = float(row["confidence"]) if row.get("confidence") else 0
    if conf >= 0.75:
        core_signals += 1
    elif conf < 0.55:
        tactical_signals += 1
    if stability and stability[1] == "STABLE":
        core_signals += 1
    elif stability and stability[1] == "UNSTABLE":
        tactical_signals += 1
    if cons_tier == "HIGH_CONVICTION":
        core_signals += 1
    elif cons_tier == "CONTRARIAN":
        tactical_signals += 1
    div_yield = result.get("dividendYield", 0) or 0
    if div_yield >= 1.5:
        core_signals += 1
    buzz_label = result.get("buzzLabel")
    if buzz_label == "HIGH":
        tactical_signals += 1
    result["suggestedType"] = "core" if core_signals > tactical_signals else "tactical"

    return result


@router.get("/recommendations")
def get_recommendations(registry: Registry = Depends(get_registry)) -> dict:
    """Stocks that have met all criteria — ready for portfolio action.

    Filtered to STRONG_BUY, BUY, ACCUMULATE verdicts only.
    Each item includes a blended success probability and portfolio-fit score.
    """
    rows = registry.get_all_actionable_verdicts()

    # Filter to positive verdicts only
    positive_rows = [r for r in rows if r.get("verdict") in POSITIVE_VERDICTS]

    # Fast enrichment (DB only — sub-millisecond per ticker)
    for row in positive_rows:
        ticker = row.get("ticker", "")
        if ticker:
            try:
                row["_stability"] = _verdict_stability(ticker, registry)
            except Exception:
                pass

    try:
        scorer = PortfolioFitScorer(registry)
        for row in positive_rows:
            row["_portfolio_fit"] = scorer.score(row.get("ticker", ""), row.get("sector"))
    except Exception:
        pass

    # Enrichment from DB (populated by daily monitor cronjob — no external API calls)
    rec_tickers = [r.get("ticker", "") for r in positive_rows if r.get("ticker")]

    # Batch-fetch buzz scores from DB
    buzz_results: dict = {}
    if rec_tickers:
        try:
            placeholders = ",".join(["%s"] * len(rec_tickers))
            buzz_rows = registry._db.execute(
                f"SELECT DISTINCT ON (ticker) ticker, buzz_score, buzz_label, "
                f"headline_sentiment, news_count_7d, news_count_30d, contrarian_flag "
                f"FROM invest.buzz_scores WHERE ticker IN ({placeholders}) "
                f"ORDER BY ticker, scored_at DESC",
                tuple(rec_tickers),
            )
            for b in (buzz_rows or []):
                buzz_results[b["ticker"]] = b
        except Exception:
            logger.debug("Could not fetch buzz scores from DB")

    # Batch-fetch earnings momentum from DB
    earnings_results: dict = {}
    if rec_tickers:
        try:
            placeholders = ",".join(["%s"] * len(rec_tickers))
            em_rows = registry._db.execute(
                f"SELECT DISTINCT ON (ticker) ticker, momentum_score, momentum_label, "
                f"upward_revisions, downward_revisions, beat_streak "
                f"FROM invest.earnings_momentum WHERE ticker IN ({placeholders}) "
                f"ORDER BY ticker, computed_at DESC",
                tuple(rec_tickers),
            )
            for em in (em_rows or []):
                earnings_results[em["ticker"]] = em
        except Exception:
            logger.debug("Could not fetch earnings momentum from DB")

    # Dividends: yfinance with in-memory cache (fast after first load)
    div_data: dict = {}
    try:
        div_data = get_dividend_data(rec_tickers)
    except Exception:
        logger.debug("Dividend enrichment failed")

    # Apply enrichment results
    for row in positive_rows:
        ticker = row.get("ticker", "")
        # Buzz
        buzz = buzz_results.get(ticker)
        if buzz:
            row["_buzz"] = buzz
        # Dividends
        dd = div_data.get(ticker)
        if dd and dd.get("annual_div", 0) > 0:
            price = float(row.get("current_price") or 0)
            div_yield = (dd["annual_div"] / price * 100) if price > 0 else 0.0
            row["_dividend_data"] = {
                "yield": round(div_yield, 2),
                "annual": round(dd["annual_div"], 2),
                "frequency": dd.get("frequency", "none"),
            }
        # Earnings
        em = earnings_results.get(ticker)
        if em:
            row["_earnings_momentum"] = em

    items = [_format_recommendation(r, registry) for r in positive_rows]

    grouped: dict[str, list[dict]] = {}
    for item in items:
        verdict = item["verdict"]
        if verdict not in grouped:
            grouped[verdict] = []
        grouped[verdict].append(item)

    # Sort groups by verdict strength
    ordered_grouped: dict[str, list[dict]] = {}
    for v in VERDICT_ORDER:
        if v in grouped:
            ordered_grouped[v] = grouped[v]

    return {
        "items": items,
        "groupedByVerdict": ordered_grouped,
        "totalCount": len(items),
    }
