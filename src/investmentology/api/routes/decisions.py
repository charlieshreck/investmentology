"""Decisions endpoints."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

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


@router.get("/decisions/export")
def export_decisions(registry: Registry = Depends(get_registry)):
    """Export all decisions as CSV."""
    rows = registry._db.execute(
        "SELECT ticker, decision_type, verdict, confidence, reasoning, "
        "entry_price, target_price, stop_loss, created_at "
        "FROM invest.decisions ORDER BY created_at DESC"
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticker", "Type", "Verdict", "Confidence", "Reasoning",
                      "Entry Price", "Target Price", "Stop Loss", "Date"])
    for r in rows:
        writer.writerow([
            r["ticker"], r["decision_type"], r.get("verdict", ""),
            r.get("confidence", ""), r.get("reasoning", "")[:200],
            r.get("entry_price", ""), r.get("target_price", ""),
            r.get("stop_loss", ""), str(r["created_at"]),
        ])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=decisions.csv"},
    )
