"""Decisions endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from investmentology.api.deps import get_registry
from investmentology.models.decision import DecisionType
from investmentology.registry.queries import Registry

router = APIRouter()


@router.get("/decisions")
def get_decisions(
    ticker: str | None = None,
    type: str | None = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=500),
    registry: Registry = Depends(get_registry),
) -> dict:
    """Paginated decisions with optional ticker and type filters.

    Response shape matches PWA DecisionsResponse:
    {decisions: Decision[], total, page, pageSize}
    """
    decision_type = None
    if type is not None:
        try:
            decision_type = DecisionType(type.upper())
        except ValueError:
            return {"decisions": [], "total": 0, "page": page, "pageSize": pageSize}

    offset = (page - 1) * pageSize

    decisions = registry.get_decisions(
        ticker=ticker.upper() if ticker else None,
        decision_type=decision_type,
        limit=pageSize,
        offset=offset,
    )

    # Get total count for pagination (respecting filters)
    count_sql = "SELECT COUNT(*) as n FROM invest.decisions"
    count_params: list = []
    filters = []
    if ticker:
        filters.append("ticker = %s")
        count_params.append(ticker.upper())
    if decision_type:
        filters.append("decision_type = %s")
        count_params.append(decision_type.value)
    if filters:
        count_sql += " WHERE " + " AND ".join(filters)
    total_row = registry._db.execute(count_sql, tuple(count_params) if count_params else None)
    total = total_row[0]["n"] if total_row else 0

    return {
        "decisions": [
            {
                "id": str(d.id),
                "ticker": d.ticker,
                "decisionType": d.decision_type.value,
                "confidence": float(d.confidence) if d.confidence else 0.0,
                "reasoning": d.reasoning or "",
                "createdAt": str(d.created_at) if d.created_at else "",
                "layer": d.layer_source or "",
                "outcome": None,
                "settledAt": None,
            }
            for d in decisions
        ],
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }
