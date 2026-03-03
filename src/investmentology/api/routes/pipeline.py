"""Pipeline state API endpoints.

Exposes the agent-first pipeline state machine to the PWA:
- Current cycle status and progress
- Per-ticker step breakdown
- Queue sizes for CLI workers
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from investmentology.api.deps import get_db
from investmentology.pipeline import state
from investmentology.registry.db import Database

router = APIRouter()


@router.get("/pipeline/status")
def pipeline_status(db: Database = Depends(get_db)) -> dict:
    """Overall pipeline status: active cycle, queue depths, step counts."""
    # Active cycle
    rows = db.execute(
        "SELECT id, started_at, ticker_count, status FROM invest.pipeline_cycles "
        "WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
    )
    cycle = None
    cycle_id = None
    if rows:
        r = rows[0]
        cycle_id = r["id"]
        cycle = {
            "id": str(r["id"]),
            "startedAt": str(r["started_at"]),
            "tickerCount": r["ticker_count"],
            "status": r["status"],
        }

    # Step counts by status
    step_counts: dict[str, int] = {}
    if cycle_id:
        count_rows = db.execute(
            "SELECT status, COUNT(*) as n FROM invest.pipeline_state "
            "WHERE cycle_id = %s GROUP BY status",
            (cycle_id,),
        )
        step_counts = {r["status"]: r["n"] for r in count_rows}

    return {
        "cycle": cycle,
        "steps": step_counts,
    }


@router.get("/pipeline/tickers")
def pipeline_tickers(
    db: Database = Depends(get_db),
    cycle_id: str | None = Query(None, description="Cycle ID (default: active cycle)"),
) -> dict:
    """Per-ticker progress for the current or specified cycle."""
    if not cycle_id:
        rows = db.execute(
            "SELECT id FROM invest.pipeline_cycles "
            "WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
        )
        if not rows:
            return {"tickers": []}
        cycle_id = str(rows[0]["id"])

    tickers = state.get_tickers_summary(db, cycle_id)
    return {"tickers": tickers}


@router.get("/pipeline/ticker/{ticker}")
def pipeline_ticker_detail(
    ticker: str,
    db: Database = Depends(get_db),
) -> dict:
    """Detailed step breakdown for a specific ticker in the active cycle."""
    rows = db.execute(
        "SELECT id FROM invest.pipeline_cycles "
        "WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
    )
    if not rows:
        return {"steps": []}

    cycle_id = rows[0]["id"]
    progress = state.get_ticker_progress(db, cycle_id, ticker.upper())

    steps = []
    for row in progress:
        steps.append({
            "step": row["step"],
            "status": row["status"],
            "startedAt": str(row["started_at"]) if row["started_at"] else None,
            "completedAt": str(row["completed_at"]) if row["completed_at"] else None,
            "error": row["error"],
            "retryCount": row["retry_count"],
        })

    return {"ticker": ticker.upper(), "steps": steps}
