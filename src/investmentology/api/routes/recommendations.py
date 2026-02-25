"""Recommendations endpoints — stocks that have met all criteria, ready for portfolio action."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_registry
from investmentology.advisory.portfolio_fit import PortfolioFitScorer
from investmentology.registry.queries import Registry

router = APIRouter()

# Positive verdicts indicating the stock passed all criteria
POSITIVE_VERDICTS = {"STRONG_BUY", "BUY", "ACCUMULATE"}
VERDICT_ORDER = ["STRONG_BUY", "BUY", "ACCUMULATE"]


def _success_probability(row: dict) -> float | None:
    """Blended success probability (0.0-1.0) from agent analysis signals.

    Components (weights renormalized when data is missing):
        35% verdict confidence
        25% consensus score (normalized -1..+1 to 0..1)
        20% agent alignment (fraction of agents with positive sentiment)
        20% risk-adjusted (penalized by risk flag count)
    """
    components: list[tuple[float, float]] = []

    vc = row.get("confidence")
    if vc is not None:
        components.append((float(vc), 0.35))

    cons = row.get("consensus_score")
    if cons is not None:
        components.append(((float(cons) + 1) / 2, 0.25))

    stances = row.get("agent_stances")
    if stances and isinstance(stances, list) and len(stances) > 0:
        pos_count = sum(
            1 for s in stances
            if isinstance(s, dict) and s.get("sentiment", 0) > 0
        )
        alignment = pos_count / len(stances)
        components.append((alignment, 0.20))

    # Risk-adjusted component: start at 1.0, deduct per risk flag
    risk_flags = row.get("risk_flags")
    risk_score = 1.0
    if risk_flags and isinstance(risk_flags, list):
        risk_score = max(0.0, 1.0 - len(risk_flags) * 0.15)
    components.append((risk_score, 0.20))

    if not components:
        return None

    total_weight = sum(w for _, w in components)
    return round(sum(v * w for v, w in components) / total_weight, 4)



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
