"""Recommendations endpoints — stocks that have met all criteria, ready for portfolio action."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_registry
from investmentology.advisory.portfolio_fit import PortfolioFitScorer
from investmentology.api.routes.shared import (
    get_dividend_data,
    success_probability as _success_probability,
)
from investmentology.registry.queries import Registry

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
        "consensusScore": float(row["consensus_score"]) if row.get("consensus_score") else None,
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

    # Compute portfolio fit for each recommendation
    try:
        scorer = PortfolioFitScorer(registry)
        for row in positive_rows:
            ticker = row.get("ticker", "")
            sector = row.get("sector")
            row["_portfolio_fit"] = scorer.score(ticker, sector)
    except Exception:
        pass  # Fit scoring is optional — don't break recommendations

    # Fetch dividend data (cached, parallel)
    try:
        rec_tickers = [r.get("ticker", "") for r in positive_rows if r.get("ticker")]
        div_data = get_dividend_data(rec_tickers)
        for row in positive_rows:
            ticker = row.get("ticker", "")
            dd = div_data.get(ticker)
            if dd and dd.get("annual_div", 0) > 0:
                price = float(row.get("current_price") or 0)
                div_yield = (dd["annual_div"] / price * 100) if price > 0 else 0.0
                row["_dividend_data"] = {
                    "yield": round(div_yield, 2),
                    "annual": round(dd["annual_div"], 2),
                    "frequency": dd.get("frequency", "none"),
                }
    except Exception:
        pass  # Dividend enrichment is optional

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
