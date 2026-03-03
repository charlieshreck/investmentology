"""Pipeline state API endpoints.

Exposes the agent-first pipeline state machine to the PWA:
- Current cycle status and progress
- Per-ticker step breakdown with gate/screener detail
- Funnel visualization data
- Platform health metrics
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from investmentology.api.deps import get_db
from investmentology.pipeline import state
from investmentology.registry.db import Database

router = APIRouter()


def _get_active_cycle_id(db: Database):
    """Return the active cycle UUID or None."""
    rows = db.execute(
        "SELECT id FROM invest.pipeline_cycles "
        "WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
    )
    return rows[0]["id"] if rows else None


@router.get("/pipeline/status")
def pipeline_status(db: Database = Depends(get_db)) -> dict:
    """Overall pipeline status: active cycle, queue depths, step counts."""
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
    """Per-ticker progress with gate outcome for each ticker."""
    if not cycle_id:
        cid = _get_active_cycle_id(db)
        if not cid:
            return {"tickers": []}
        cycle_id = str(cid)

    tickers = state.get_tickers_summary(db, cycle_id)

    # Enrich each ticker with gate outcome from cache
    enriched = []
    for t in tickers:
        ticker_name = t["ticker"]
        item = dict(t)

        # Pre-filter result
        pf = state.get_data_cache(db, cycle_id, ticker_name, "pre_filter_result")
        if pf:
            item["preFilter"] = {
                "passed": pf.get("passed", True),
                "reason": pf.get("rejection_reason"),
                "rulesFailed": pf.get("rules_failed", []),
            }

        # Gate decision status from step
        gate_row = state.get_step_status(db, cycle_id, ticker_name, "gate_decision")
        if gate_row and gate_row["status"] == "completed":
            # Determine if gate passed by checking if Phase 2 steps exist
            has_analysis = db.execute(
                "SELECT 1 FROM invest.pipeline_state "
                "WHERE cycle_id = %s AND ticker = %s AND step LIKE 'agent:%%' LIMIT 1",
                (cycle_id, ticker_name),
            )
            pre_filtered = pf and not pf.get("passed", True) if pf else False
            item["gateOutcome"] = (
                "pre_filtered" if pre_filtered
                else "passed" if has_analysis
                else "rejected"
            )

        enriched.append(item)

    return {"tickers": enriched}


@router.get("/pipeline/ticker/{ticker}")
def pipeline_ticker_detail(
    ticker: str,
    db: Database = Depends(get_db),
) -> dict:
    """Detailed step breakdown with pre-filter and screener data."""
    cycle_id = _get_active_cycle_id(db)
    if not cycle_id:
        return {"steps": [], "preFilter": None, "screeners": [], "gateOutcome": None}

    ticker = ticker.upper()
    progress = state.get_ticker_progress(db, cycle_id, ticker)

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

    # Pre-filter detail
    pre_filter = None
    pf = state.get_data_cache(db, cycle_id, ticker, "pre_filter_result")
    if pf:
        pre_filter = {
            "passed": pf.get("passed", True),
            "reason": pf.get("rejection_reason"),
            "rulesChecked": pf.get("rules_checked", 0),
            "rulesFailed": pf.get("rules_failed", []),
        }

    # Screener verdicts from agent_signals
    screeners = []
    signal_rows = state.get_agent_signals_for_ticker(db, cycle_id, ticker)
    for row in signal_rows:
        name = row["agent_name"]
        if not name.endswith("_screener"):
            continue
        signals_data = row["signals"]
        if isinstance(signals_data, str):
            signals_data = json.loads(signals_data)

        tags = [s.get("tag", "") for s in signals_data.get("signals", [])]
        has_reject = any(t in ("REJECT", "REJECT_HARD") for t in tags)
        screeners.append({
            "name": name,
            "verdict": "reject" if has_reject else "pass",
            "confidence": float(row["confidence"]) if row["confidence"] else None,
            "tags": tags,
            "latencyMs": row["latency_ms"],
        })

    # Gate outcome
    gate_outcome = None
    has_analysis = db.execute(
        "SELECT 1 FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND ticker = %s AND step LIKE 'agent:%%' LIMIT 1",
        (cycle_id, ticker),
    )
    gate_step = state.get_step_status(db, cycle_id, ticker, "gate_decision")
    if gate_step and gate_step["status"] == "completed":
        pre_filtered = pf and not pf.get("passed", True) if pf else False
        if pre_filtered:
            gate_outcome = "pre_filtered"
        elif has_analysis:
            gate_outcome = "passed"
        else:
            gate_outcome = "rejected"

    # Count screener votes
    pass_count = sum(1 for s in screeners if s["verdict"] == "pass")
    reject_count = sum(1 for s in screeners if s["verdict"] == "reject")

    return {
        "ticker": ticker,
        "steps": steps,
        "preFilter": pre_filter,
        "screeners": screeners,
        "gateOutcome": gate_outcome,
        "screenerVotes": {
            "pass": pass_count,
            "reject": reject_count,
            "total": len(screeners),
            "required": 3,
        } if screeners else None,
    }


@router.get("/pipeline/funnel")
def pipeline_funnel(db: Database = Depends(get_db)) -> dict:
    """Funnel visualization data: how tickers flow through each stage."""
    cycle_id = _get_active_cycle_id(db)
    if not cycle_id:
        return {"hasCycle": False}

    # Total tickers in cycle
    total_rows = db.execute(
        "SELECT COUNT(DISTINCT ticker) as n FROM invest.pipeline_state "
        "WHERE cycle_id = %s",
        (cycle_id,),
    )
    total_tickers = total_rows[0]["n"] if total_rows else 0

    # Data fetch stats
    fetch_rows = db.execute(
        "SELECT status, COUNT(*) as n FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND step = 'data_fetch' GROUP BY status",
        (cycle_id,),
    )
    fetch_stats = {r["status"]: r["n"] for r in fetch_rows}

    # Pre-filter stats from cache
    pf_rows = db.execute(
        "SELECT data_value FROM invest.pipeline_data_cache "
        "WHERE cycle_id = %s AND data_key = 'pre_filter_result'",
        (cycle_id,),
    )
    pf_pass = 0
    pf_reject = 0
    pf_reasons: dict[str, int] = {}
    for r in pf_rows:
        val = r["data_value"]
        if isinstance(val, str):
            val = json.loads(val)
        if val.get("passed"):
            pf_pass += 1
        else:
            pf_reject += 1
            for rule in val.get("rules_failed", []):
                # Extract rule name (before the colon)
                rule_name = rule.split(":")[0].strip() if ":" in rule else rule
                pf_reasons[rule_name] = pf_reasons.get(rule_name, 0) + 1

    # Pre-filter step completion
    pf_step_rows = db.execute(
        "SELECT status, COUNT(*) as n FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND step = 'pre_filter' GROUP BY status",
        (cycle_id,),
    )
    pf_step_stats = {r["status"]: r["n"] for r in pf_step_rows}

    # Screener stats
    screener_rows = db.execute(
        "SELECT step, status, COUNT(*) as n FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND step LIKE 'screener:%%' "
        "GROUP BY step, status ORDER BY step",
        (cycle_id,),
    )
    screener_stats: dict[str, dict[str, int]] = {}
    for r in screener_rows:
        name = r["step"].replace("screener:", "")
        if name not in screener_stats:
            screener_stats[name] = {}
        screener_stats[name][r["status"]] = r["n"]

    # Gate decision stats
    gate_rows = db.execute(
        "SELECT status, COUNT(*) as n FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND step = 'gate_decision' GROUP BY status",
        (cycle_id,),
    )
    gate_stats = {r["status"]: r["n"] for r in gate_rows}

    # Phase 2 tickers (those with agent steps)
    phase2_rows = db.execute(
        "SELECT COUNT(DISTINCT ticker) as n FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND step LIKE 'agent:%%'",
        (cycle_id,),
    )
    phase2_tickers = phase2_rows[0]["n"] if phase2_rows else 0

    # Gate rejected tickers (gate completed but no agent steps)
    gate_rejected = (gate_stats.get("completed", 0) - pf_reject) - phase2_tickers
    if gate_rejected < 0:
        gate_rejected = 0

    # Agent step stats
    agent_rows = db.execute(
        "SELECT status, COUNT(*) as n FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND step LIKE 'agent:%%' GROUP BY status",
        (cycle_id,),
    )
    agent_stats = {r["status"]: r["n"] for r in agent_rows}

    # Cycle timing
    cycle_row = db.execute(
        "SELECT started_at FROM invest.pipeline_cycles WHERE id = %s",
        (cycle_id,),
    )
    started_at = str(cycle_row[0]["started_at"]) if cycle_row else None

    return {
        "hasCycle": True,
        "cycleId": str(cycle_id),
        "startedAt": started_at,
        "totalTickers": total_tickers,
        "stages": {
            "dataFetch": {
                "completed": fetch_stats.get("completed", 0),
                "failed": fetch_stats.get("failed", 0),
                "pending": fetch_stats.get("pending", 0),
                "running": fetch_stats.get("running", 0),
            },
            "preFilter": {
                "completed": pf_step_stats.get("completed", 0),
                "pending": pf_step_stats.get("pending", 0),
                "passed": pf_pass,
                "rejected": pf_reject,
                "reasons": pf_reasons,
            },
            "screeners": {
                "stats": screener_stats,
                "totalScreenerSteps": sum(
                    sum(v.values()) for v in screener_stats.values()
                ),
            },
            "gate": {
                "completed": gate_stats.get("completed", 0),
                "pending": gate_stats.get("pending", 0),
                "passed": phase2_tickers,
                "rejected": gate_rejected,
                "preFiltered": pf_reject,
            },
            "analysis": {
                "tickers": phase2_tickers,
                "completed": agent_stats.get("completed", 0),
                "running": agent_stats.get("running", 0),
                "pending": agent_stats.get("pending", 0),
                "failed": agent_stats.get("failed", 0),
            },
        },
    }


@router.get("/pipeline/health")
def pipeline_health(db: Database = Depends(get_db)) -> dict:
    """Platform-wide pipeline health metrics."""
    cycle_id = _get_active_cycle_id(db)
    if not cycle_id:
        return {"hasCycle": False}

    # Error rate by step type
    error_rows = db.execute(
        "SELECT step, "
        "COUNT(*) FILTER (WHERE status = 'failed') as failed, "
        "COUNT(*) FILTER (WHERE status = 'completed') as completed, "
        "COUNT(*) as total "
        "FROM invest.pipeline_state WHERE cycle_id = %s "
        "GROUP BY step ORDER BY step",
        (cycle_id,),
    )
    step_health = []
    for r in error_rows:
        step_name = r["step"]
        total = r["total"]
        failed = r["failed"]
        completed = r["completed"]
        rate = round(failed / total * 100, 1) if total > 0 else 0
        step_health.append({
            "step": step_name,
            "total": total,
            "completed": completed,
            "failed": failed,
            "errorRate": rate,
        })

    # Average processing time per step type (completed steps only)
    timing_rows = db.execute(
        "SELECT step, "
        "AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_seconds, "
        "MAX(EXTRACT(EPOCH FROM (completed_at - started_at))) as max_seconds, "
        "COUNT(*) as cnt "
        "FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND status = 'completed' "
        "AND started_at IS NOT NULL AND completed_at IS NOT NULL "
        "GROUP BY step ORDER BY step",
        (cycle_id,),
    )
    step_timing = []
    for r in timing_rows:
        avg_s = float(r["avg_seconds"]) if r["avg_seconds"] else 0
        max_s = float(r["max_seconds"]) if r["max_seconds"] else 0
        step_timing.append({
            "step": r["step"],
            "avgSeconds": round(avg_s, 1),
            "maxSeconds": round(max_s, 1),
            "count": r["cnt"],
        })

    # Recent errors (last 10)
    error_detail_rows = db.execute(
        "SELECT ticker, step, error, completed_at, retry_count "
        "FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND status = 'failed' AND error IS NOT NULL "
        "ORDER BY completed_at DESC NULLS LAST LIMIT 10",
        (cycle_id,),
    )
    recent_errors = [
        {
            "ticker": r["ticker"],
            "step": r["step"],
            "error": r["error"][:200] if r["error"] else None,
            "at": str(r["completed_at"]) if r["completed_at"] else None,
            "retries": r["retry_count"],
        }
        for r in error_detail_rows
    ]

    # Reentry blocks
    block_rows = db.execute(
        "SELECT COUNT(*) as total, "
        "COUNT(*) FILTER (WHERE is_cleared = FALSE) as active "
        "FROM invest.reentry_blocks"
    )
    blocks = block_rows[0] if block_rows else {"total": 0, "active": 0}

    return {
        "hasCycle": True,
        "cycleId": str(cycle_id),
        "stepHealth": step_health,
        "stepTiming": step_timing,
        "recentErrors": recent_errors,
        "reentryBlocks": {
            "total": blocks["total"],
            "active": blocks["active"],
        },
    }
