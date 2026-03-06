"""Watchlist endpoints — stocks agents tagged as WATCHLIST (stepping stone to Recommend)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_registry
from investmentology.api.routes.shared import success_probability as _success_probability
from investmentology.registry.queries import Registry

router = APIRouter()


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

    # Days on watchlist
    added_at_str = str(row.get("watchlist_entered") or row.get("created_at") or "")
    days_on_watchlist = None
    if added_at_str:
        try:
            from datetime import datetime, date
            added_date = datetime.fromisoformat(added_at_str[:10]).date()
            days_on_watchlist = (date.today() - added_date).days
        except (ValueError, TypeError):
            pass

    # Conviction trend from verdict history
    conviction_trend = row.get("_conviction_trend")

    # Target entry price and distance
    target_entry = row.get("target_entry_price")
    distance_to_entry = None
    if target_entry and current_price > 0:
        distance_to_entry = round(
            (current_price - float(target_entry)) / current_price * 100, 2,
        )

    result = {
        "ticker": row["ticker"],
        "name": row.get("name") or row["ticker"],
        "sector": row.get("sector") or "",
        "state": row.get("watchlist_state") or "WATCHLIST",
        "addedAt": added_at_str,
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
        # Batch 8 enrichment
        "daysOnWatchlist": days_on_watchlist,
        "convictionTrend": conviction_trend,
        "targetEntryPrice": float(target_entry) if target_entry else None,
        "distanceToEntry": distance_to_entry,
    }

    # Watchlist structured metadata (blocking factors, graduation criteria)
    blocking_factors = row.get("watchlist_blocking_factors") or []
    graduation_criteria = row.get("watchlist_graduation_criteria") or []
    watchlist_reason = row.get("watchlist_reason")

    result["watchlistMeta"] = {
        "reason": watchlist_reason or _derive_reason_from_verdict(row),
        "blockingFactors": blocking_factors if isinstance(blocking_factors, list) else [],
        "graduationCriteria": graduation_criteria if isinstance(graduation_criteria, list) else [],
        "graduationTrigger": _summarize_graduation(graduation_criteria),
    }

    # QG rank
    qg_rank = row.get("_qg_rank")
    if qg_rank is not None:
        result["qgRank"] = qg_rank

    # Next catalyst date
    catalyst_date = row.get("_next_catalyst_date")
    if catalyst_date:
        result["nextCatalystDate"] = str(catalyst_date)

    return result


def _derive_reason_from_verdict(row: dict) -> str | None:
    """Derive a reason string from the verdict reasoning when no explicit reason is stored."""
    reasoning = row.get("reasoning")
    if reasoning:
        return reasoning[:200]
    return None


def _summarize_graduation(criteria: list | None) -> str | None:
    """Summarize graduation criteria into a single trigger sentence."""
    if not criteria or not isinstance(criteria, list):
        return None
    labels = [c.get("label", "") for c in criteria[:3] if isinstance(c, dict) and c.get("label")]
    if not labels:
        return None
    return "; ".join(labels)


def _compute_conviction_trend(ticker: str, registry: Registry) -> str | None:
    """Compute conviction trend from last 3-5 verdicts: declining/stable/improving."""
    try:
        rows = registry._db.execute(
            """SELECT confidence FROM invest.verdicts
               WHERE ticker = %s ORDER BY created_at DESC LIMIT 5""",
            (ticker,),
        )
        if not rows or len(rows) < 2:
            return None
        confs = [float(r["confidence"]) for r in rows if r.get("confidence")]
        if len(confs) < 2:
            return None
        # Compare average of recent half vs older half
        mid = len(confs) // 2
        recent_avg = sum(confs[:mid]) / mid
        older_avg = sum(confs[mid:]) / (len(confs) - mid)
        diff = recent_avg - older_avg
        if diff > 0.05:
            return "improving"
        if diff < -0.05:
            return "declining"
        return "stable"
    except Exception:
        return None


@router.get("/watchlist")
def get_watchlist(registry: Registry = Depends(get_registry)) -> dict:
    """Stocks tagged WATCHLIST by agents — close but not yet meeting buy criteria.

    Each item includes entry price, current price, change %, and price history
    for a sparkline chart.
    """
    rows = registry.get_watch_verdicts_enriched()

    # Enrich with conviction trend
    for row in rows:
        ticker = row.get("ticker")
        if ticker:
            row["_conviction_trend"] = _compute_conviction_trend(ticker, registry)

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
