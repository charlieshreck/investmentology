"""Watchlist endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_registry
from investmentology.registry.queries import Registry

router = APIRouter()


def _format_verdict(row: dict) -> dict | None:
    """Format verdict fields from an enriched row, or return None."""
    if not row.get("verdict"):
        return None
    return {
        "recommendation": row["verdict"],
        "confidence": float(row["verdict_confidence"]) if row.get("verdict_confidence") else None,
        "consensusScore": float(row["consensus_score"]) if row.get("consensus_score") else None,
        "reasoning": row.get("verdict_reasoning"),
        "agentStances": row.get("agent_stances"),
        "riskFlags": row.get("risk_flags"),
        "verdictDate": str(row["verdict_date"]) if row.get("verdict_date") else None,
    }


@router.get("/watchlist")
def get_watchlist(registry: Registry = Depends(get_registry)) -> dict:
    """All watchlist items grouped by state, enriched with prices/scores/verdicts.

    Response shape matches PWA WatchlistResponse:
    {items: WatchlistItem[], groupedByState: Record<string, WatchlistItem[]>}
    """
    rows = registry.get_enriched_watchlist()

    items: list[dict] = []
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        item = {
            "ticker": row["ticker"],
            "name": row.get("name") or row["ticker"],
            "sector": row.get("sector") or "",
            "state": row["state"],
            "addedAt": str(row.get("entered_at", "")) if row.get("entered_at") else "",
            "lastAnalysis": str(row.get("verdict_date", "")) if row.get("verdict_date") else None,
            "priceAtAdd": float(row["price_at_add"]) if row.get("price_at_add") else 0.0,
            "currentPrice": float(row["current_price"]) if row.get("current_price") else 0.0,
            "marketCap": float(row["market_cap"]) if row.get("market_cap") else 0,
            "compositeScore": float(row["composite_score"]) if row.get("composite_score") else None,
            "piotroskiScore": row.get("piotroski_score"),
            "altmanZone": row.get("altman_zone"),
            "combinedRank": row.get("combined_rank"),
            "altmanZScore": float(row["altman_z_score"]) if row.get("altman_z_score") else None,
            "verdict": _format_verdict(row),
            "notes": row.get("notes"),
        }
        items.append(item)
        state = row["state"]
        if state not in grouped:
            grouped[state] = []
        grouped[state].append(item)

    return {
        "items": items,
        "groupedByState": grouped,
    }
