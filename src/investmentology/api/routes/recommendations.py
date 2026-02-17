"""Recommendations endpoints — actionable verdicts grouped by strength."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_registry
from investmentology.registry.queries import Registry

router = APIRouter()

VERDICT_ORDER = [
    "STRONG_BUY", "BUY", "ACCUMULATE", "HOLD",
    "WATCHLIST", "REDUCE", "SELL", "AVOID",
]


def _format_recommendation(row: dict) -> dict:
    return {
        "ticker": row["ticker"],
        "name": row.get("name") or row["ticker"],
        "sector": row.get("sector") or "",
        "industry": row.get("industry") or "",
        "currentPrice": float(row["current_price"]) if row.get("current_price") else 0.0,
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
    }


@router.get("/recommendations")
def get_recommendations(registry: Registry = Depends(get_registry)) -> dict:
    """All stocks with actionable verdicts, grouped by recommendation."""
    rows = registry.get_all_actionable_verdicts()
    items = [_format_recommendation(r) for r in rows]

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
