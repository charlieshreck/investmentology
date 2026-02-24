"""Watchlist endpoints — stocks being watched but not yet meeting all criteria."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_registry
from investmentology.registry.queries import Registry

router = APIRouter()

# States that represent "watching" — promoted from screen, not yet ready
WATCH_STATES = {
    "CANDIDATE", "ASSESSED", "WATCHLIST_EARLY",
    "WATCHLIST_CATALYST", "CONFLICT_REVIEW",
}

# State maturity weight (how far along the pipeline)
_STATE_MATURITY: dict[str, float] = {
    "CANDIDATE": 0.2,
    "ASSESSED": 0.4,
    "WATCHLIST_EARLY": 0.5,
    "WATCHLIST_CATALYST": 0.6,
    "CONFLICT_REVIEW": 0.3,
}


def _success_probability(row: dict) -> float | None:
    """Blended success probability (0.0-1.0) from quantitative + qualitative signals.

    Components (weights renormalized when data is missing):
        30% composite score (Greenblatt + Piotroski + Altman blend)
        25% verdict confidence (if analyzed)
        15% consensus score (agent alignment, normalized -1..+1 to 0..1)
        15% pipeline maturity (state position)
        10% Piotroski F-Score (/9)
         5% Altman Z-Score zone
    """
    components: list[tuple[float, float]] = []

    cs = row.get("composite_score")
    if cs is not None:
        components.append((float(cs), 0.30))

    vc = row.get("verdict_confidence")
    if vc is not None:
        components.append((float(vc), 0.25))

    cons = row.get("consensus_score")
    if cons is not None:
        components.append(((float(cons) + 1) / 2, 0.15))

    state = row.get("state", "")
    maturity = _STATE_MATURITY.get(state)
    if maturity is not None:
        components.append((maturity, 0.15))

    ps = row.get("piotroski_score")
    if ps is not None:
        components.append((min(int(ps) / 9, 1.0), 0.10))

    az = row.get("altman_zone")
    if az is not None:
        zone_map = {"safe": 1.0, "grey": 0.5, "distress": 0.0}
        components.append((zone_map.get(az, 0.3), 0.05))

    if not components:
        return None

    total_weight = sum(w for _, w in components)
    return round(sum(v * w for v, w in components) / total_weight, 4)


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
    """Watchlist items being watched — promoted from screen but not yet meeting all criteria.

    Filtered to CANDIDATE, ASSESSED, WATCHLIST_EARLY, WATCHLIST_CATALYST,
    CONFLICT_REVIEW states. Each item includes a blended success probability.
    """
    rows = registry.get_enriched_watchlist()

    items: list[dict] = []
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        state = row["state"]
        if state not in WATCH_STATES:
            continue

        item = {
            "ticker": row["ticker"],
            "name": row.get("name") or row["ticker"],
            "sector": row.get("sector") or "",
            "state": state,
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
            "successProbability": _success_probability(row),
        }
        items.append(item)
        if state not in grouped:
            grouped[state] = []
        grouped[state].append(item)

    return {
        "items": items,
        "groupedByState": grouped,
    }
