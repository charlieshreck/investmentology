"""Watchlist endpoints — stocks agents tagged as WATCHLIST (stepping stone to Recommend)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_registry
from investmentology.registry.queries import Registry

router = APIRouter()


def _success_probability(row: dict) -> float | None:
    """Blended success probability (0.0-1.0) — how close to graduating to Recommend."""
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

    risk_flags = row.get("risk_flags")
    risk_score = 1.0
    if risk_flags and isinstance(risk_flags, list):
        risk_score = max(0.0, 1.0 - len(risk_flags) * 0.15)
    components.append((risk_score, 0.20))

    if not components:
        return None

    total_weight = sum(w for _, w in components)
    return round(sum(v * w for v, w in components) / total_weight, 4)


def _format_watch_item(row: dict) -> dict:
    """Format an enriched WATCHLIST verdict row."""
    entry_price = float(row["entry_price"]) if row.get("entry_price") else 0.0
    current_price = float(row["current_price"]) if row.get("current_price") else 0.0
    change_pct = (
        ((current_price - entry_price) / entry_price * 100)
        if entry_price > 0 else 0.0
    )

    # Price history for sparkline: [{date, price}, ...]
    history = row.get("price_history") or []

    return {
        "ticker": row["ticker"],
        "name": row.get("name") or row["ticker"],
        "sector": row.get("sector") or "",
        "state": row.get("watchlist_state") or "WATCHLIST",
        "addedAt": str(row.get("watchlist_entered") or row["created_at"]),
        "lastAnalysis": str(row["created_at"]) if row.get("created_at") else None,
        "priceAtAdd": entry_price,
        "currentPrice": current_price,
        "changePct": round(change_pct, 2),
        "marketCap": float(row["market_cap"]) if row.get("market_cap") else 0,
        "compositeScore": None,
        "piotroskiScore": None,
        "altmanZone": None,
        "combinedRank": None,
        "altmanZScore": None,
        "verdict": {
            "recommendation": row["verdict"],
            "confidence": float(row["confidence"]) if row.get("confidence") else None,
            "consensusScore": float(row["consensus_score"]) if row.get("consensus_score") else None,
            "reasoning": row.get("reasoning"),
            "agentStances": row.get("agent_stances"),
            "riskFlags": row.get("risk_flags"),
            "verdictDate": str(row["created_at"]) if row.get("created_at") else None,
        },
        "notes": None,
        "successProbability": _success_probability(row),
        "priceHistory": history,
    }


@router.get("/watchlist")
def get_watchlist(registry: Registry = Depends(get_registry)) -> dict:
    """Stocks tagged WATCHLIST by agents — close but not yet meeting buy criteria.

    Each item includes entry price, current price, change %, and price history
    for a sparkline chart.
    """
    rows = registry.get_watch_verdicts_enriched()
    items = [_format_watch_item(r) for r in rows]

    # Sort by success probability descending
    items.sort(key=lambda x: x.get("successProbability") or 0, reverse=True)

    # Group by sector
    grouped: dict[str, list[dict]] = {}
    for item in items:
        key = item["sector"] or "Other"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(item)

    return {
        "items": items,
        "groupedByState": grouped,
    }
