"""Pipeline state API endpoints.

Exposes the agent-first pipeline state machine to the PWA:
- Current cycle status and progress
- Per-ticker step breakdown with gate/screener detail
- Funnel visualization data
- Platform health metrics
- Manual trigger endpoints for agent/board/verdict re-runs
- Data availability report per ticker
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from investmentology.api.deps import get_db, get_gateway
from investmentology.agents.gateway import LLMGateway
from investmentology.pipeline import state
from investmentology.registry.db import Database

logger = logging.getLogger(__name__)

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


# ═══════════════════════════════════════════════════════════════════════════
# TRIGGER ENDPOINTS — manual re-runs for agents, board, and full pipeline
# ═══════════════════════════════════════════════════════════════════════════


class TriggerAgentRequest(BaseModel):
    ticker: str
    agent: str


class TriggerAgentsRequest(BaseModel):
    ticker: str
    agents: list[str] | None = None  # None = all agents


class TriggerBoardRequest(BaseModel):
    ticker: str
    verdict_id: int | None = None  # None = latest


class TriggerHypotheticalRequest(BaseModel):
    ticker: str
    verdict_id: int | None = None
    stance_overrides: dict[str, str] = {}  # agent -> bearish/bullish/neutral
    confidence_overrides: dict[str, float] = {}


class TriggerVerdictRequest(BaseModel):
    ticker: str
    signal_source: str = "latest"  # "latest" or "cycle"


class TriggerDataRequest(BaseModel):
    ticker: str
    data_keys: list[str]  # e.g. ["analyst_ratings", "short_interest"]


class TriggerFullRequest(BaseModel):
    tickers: list[str]
    force_data_refresh: bool = False


def _ensure_active_cycle(db: Database):
    """Return active cycle id or raise 422."""
    cycle_id = _get_active_cycle_id(db)
    if not cycle_id:
        raise HTTPException(422, "No active pipeline cycle")
    return cycle_id


def _save_agent_signal(db: Database, ticker: str, response) -> int:
    """Save agent signal to DB and return signal row id."""
    from investmentology.registry.queries import Registry
    registry = Registry(db)
    signals_dict = {
        "signals": [
            {
                "tag": s.tag.value,
                "strength": s.strength,
                "detail": s.detail,
            }
            for s in response.signal_set.signals.signals
        ],
        "target_price": (
            float(response.target_price) if response.target_price else None
        ),
    }
    return registry.insert_agent_signals(
        ticker=ticker,
        agent_name=response.agent_name,
        model=response.model,
        signals=signals_dict,
        confidence=response.signal_set.confidence,
        reasoning=response.summary or response.signal_set.reasoning,
        token_usage=response.token_usage,
        latency_ms=response.latency_ms,
    )


@router.post("/pipeline/trigger/agent")
async def trigger_agent(
    body: TriggerAgentRequest,
    db: Database = Depends(get_db),
    gateway: LLMGateway = Depends(get_gateway),
) -> dict:
    """Re-run a single agent for a single ticker.

    API-only agents (simons, lynch, income_analyst, sector_specialist) run
    in-process and return completed results. CLI agents are queued for
    the controller to pick up.
    """
    from investmentology.agents.runner import AgentRunner
    from investmentology.agents.skills import API_ONLY_AGENTS, SKILLS
    from investmentology.pipeline.builder import build_analysis_request

    ticker = body.ticker.upper()
    agent = body.agent.lower()

    if agent not in SKILLS:
        raise HTTPException(400, f"Unknown agent: {agent}. Valid: {sorted(SKILLS.keys())}")

    cycle_id = _ensure_active_cycle(db)

    if agent in API_ONLY_AGENTS:
        # Run in-process
        skill = SKILLS[agent]
        runner = AgentRunner(skill=skill, gateway=gateway)
        request = build_analysis_request(db, ticker, str(cycle_id))
        response = await runner.analyze(request)
        signal_id = _save_agent_signal(db, ticker, response)

        # Update pipeline state if step exists
        step_id, action = state.reset_or_create_step(
            db, cycle_id, ticker, f"agent:{agent}",
        )
        state.mark_running(db, step_id)
        state.mark_completed(db, step_id, result_ref=signal_id)

        return {
            "status": "completed",
            "agent": agent,
            "ticker": ticker,
            "confidence": float(response.signal_set.confidence),
            "signalId": signal_id,
        }

    # CLI agent — queue for controller
    step_id, action = state.reset_or_create_step(
        db, cycle_id, ticker, f"agent:{agent}",
    )
    return {
        "status": "queued" if action != "running" else "already_running",
        "agent": agent,
        "ticker": ticker,
        "stepId": step_id,
        "action": action,
        "estimatedWaitSeconds": 60,
    }


@router.post("/pipeline/trigger/agents")
async def trigger_agents(
    body: TriggerAgentsRequest,
    db: Database = Depends(get_db),
    gateway: LLMGateway = Depends(get_gateway),
) -> dict:
    """Re-run multiple agents for a ticker. None = all agents."""
    from investmentology.agents.runner import AgentRunner
    from investmentology.agents.skills import API_ONLY_AGENTS, SKILLS
    from investmentology.pipeline.builder import build_analysis_request

    ticker = body.ticker.upper()
    agent_names = [a.lower() for a in body.agents] if body.agents else list(SKILLS.keys())

    invalid = [a for a in agent_names if a not in SKILLS]
    if invalid:
        raise HTTPException(400, f"Unknown agents: {invalid}")

    cycle_id = _ensure_active_cycle(db)
    request = build_analysis_request(db, ticker, str(cycle_id))
    results = []

    for agent in agent_names:
        if agent in API_ONLY_AGENTS:
            try:
                skill = SKILLS[agent]
                runner = AgentRunner(skill=skill, gateway=gateway)
                response = await runner.analyze(request)
                signal_id = _save_agent_signal(db, ticker, response)

                step_id, action = state.reset_or_create_step(
                    db, cycle_id, ticker, f"agent:{agent}",
                )
                state.mark_running(db, step_id)
                state.mark_completed(db, step_id, result_ref=signal_id)

                results.append({
                    "agent": agent,
                    "status": "completed",
                    "confidence": float(response.signal_set.confidence),
                    "signalId": signal_id,
                })
            except Exception as e:
                results.append({
                    "agent": agent,
                    "status": "error",
                    "error": str(e),
                })
        else:
            step_id, action = state.reset_or_create_step(
                db, cycle_id, ticker, f"agent:{agent}",
            )
            results.append({
                "agent": agent,
                "status": "queued" if action != "running" else "already_running",
                "stepId": step_id,
                "action": action,
            })

    return {"ticker": ticker, "results": results}


@router.post("/pipeline/trigger/board")
async def trigger_board(
    body: TriggerBoardRequest,
    db: Database = Depends(get_db),
    gateway: LLMGateway = Depends(get_gateway),
) -> dict:
    """Re-evaluate advisory board with existing agent stances."""
    from investmentology.advisory.board import AdvisoryBoard
    from investmentology.advisory.cio import CIOSynthesizer
    from investmentology.pipeline.builder import (
        build_analysis_request,
        reconstruct_signal_sets,
    )
    from investmentology.verdict import AgentStance, synthesize

    ticker = body.ticker.upper()

    # Load verdict
    if body.verdict_id:
        rows = db.execute(
            "SELECT * FROM invest.verdicts WHERE id = %s",
            (body.verdict_id,),
        )
    else:
        rows = db.execute(
            "SELECT * FROM invest.verdicts WHERE ticker = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (ticker,),
        )

    if not rows:
        raise HTTPException(404, f"No verdict found for {ticker}")

    verdict_row = rows[0]

    # Reconstruct stances
    stances_data = verdict_row.get("agent_stances") or []
    if isinstance(stances_data, str):
        stances_data = json.loads(stances_data)
    stances = [
        AgentStance(
            name=s["name"],
            sentiment=s["sentiment"],
            confidence=s["confidence"],
            key_signals=s.get("key_signals", []),
            summary=s.get("summary", ""),
        )
        for s in stances_data
    ]

    # Load latest agent signals and re-synthesize verdict
    signal_rows = state.get_latest_agent_signals(db, ticker)
    signal_sets = reconstruct_signal_sets(signal_rows)

    verdict_result = synthesize(signal_sets)

    # Build request for board context
    cycle_id = _get_active_cycle_id(db)
    request = build_analysis_request(db, ticker, str(cycle_id) if cycle_id else None)

    # Run board
    board = AdvisoryBoard(gateway)
    board_result = await board.convene(verdict_result, stances, None, request)

    # Run CIO synthesis
    cio = CIOSynthesizer(gateway)
    cio_result = await cio.synthesize(verdict_result, board_result, stances)

    # Persist board results to verdict row
    def _jsonable(v):
        """Coerce Decimal/non-serializable values to float/str."""
        from decimal import Decimal as _D
        if isinstance(v, _D):
            return float(v)
        return v

    opinions_json = [
        {
            "advisor_name": op.advisor_name,
            "display_name": op.display_name,
            "vote": op.vote,
            "confidence": _jsonable(op.confidence),
            "assessment": op.assessment,
            "key_concern": op.key_concern,
            "key_endorsement": op.key_endorsement,
            "reasoning": op.reasoning,
        }
        for op in board_result.opinions
    ]
    narrative_json = {
        "headline": cio_result.headline,
        "narrative": cio_result.narrative,
        "risk_summary": cio_result.risk_summary,
        "pre_mortem": cio_result.pre_mortem,
        "conflict_resolution": cio_result.conflict_resolution,
        "advisor_consensus": cio_result.advisor_consensus,
    }

    def _default_ser(o):
        from decimal import Decimal as _D
        return float(o) if isinstance(o, _D) else str(o)

    db.execute(
        "UPDATE invest.verdicts SET "
        "advisory_opinions = %s::jsonb, "
        "board_narrative = %s::jsonb, "
        "board_adjusted_verdict = %s "
        "WHERE id = %s",
        (
            json.dumps(opinions_json, default=_default_ser),
            json.dumps(narrative_json, default=_default_ser),
            board_result.adjusted_verdict,
            verdict_row["id"],
        ),
    )

    return {
        "status": "completed",
        "ticker": ticker,
        "verdictId": verdict_row["id"],
        "adjustedVerdict": board_result.adjusted_verdict,
        "opinions": opinions_json,
        "narrative": narrative_json,
    }


@router.post("/pipeline/trigger/board/hypothetical")
async def trigger_board_hypothetical(
    body: TriggerHypotheticalRequest,
    db: Database = Depends(get_db),
    gateway: LLMGateway = Depends(get_gateway),
) -> dict:
    """What-if board simulation with overridden agent stances. Never persisted."""
    from decimal import Decimal

    from investmentology.advisory.board import AdvisoryBoard
    from investmentology.advisory.cio import CIOSynthesizer
    from investmentology.pipeline.builder import (
        build_analysis_request,
        reconstruct_signal_sets,
    )
    from investmentology.verdict import AgentStance, synthesize

    ticker = body.ticker.upper()

    # Load verdict
    if body.verdict_id:
        rows = db.execute(
            "SELECT * FROM invest.verdicts WHERE id = %s",
            (body.verdict_id,),
        )
    else:
        rows = db.execute(
            "SELECT * FROM invest.verdicts WHERE ticker = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (ticker,),
        )

    if not rows:
        raise HTTPException(404, f"No verdict found for {ticker}")

    verdict_row = rows[0]

    # Reconstruct stances
    stances_data = verdict_row.get("agent_stances") or []
    if isinstance(stances_data, str):
        stances_data = json.loads(stances_data)

    STANCE_MAP = {"bearish": -0.7, "bullish": 0.7, "neutral": 0.0}
    stances = []
    for s in stances_data:
        name = s["name"]
        sentiment = s["sentiment"]
        confidence = s["confidence"]

        if name in body.stance_overrides:
            label = body.stance_overrides[name].lower()
            sentiment = STANCE_MAP.get(label, sentiment)
        if name in body.confidence_overrides:
            confidence = body.confidence_overrides[name]

        stances.append(AgentStance(
            name=name,
            sentiment=sentiment,
            confidence=confidence,
            key_signals=s.get("key_signals", []),
            summary=s.get("summary", ""),
        ))

    # Re-synthesize with modified signals
    signal_rows = state.get_latest_agent_signals(db, ticker)
    signal_sets = reconstruct_signal_sets(signal_rows)

    # Apply overrides to signal sets too (adjust confidence)
    for ss in signal_sets:
        if ss.agent_name in body.confidence_overrides:
            ss.confidence = Decimal(str(body.confidence_overrides[ss.agent_name]))

    verdict_result = synthesize(signal_sets)

    # Build request for board context
    cycle_id = _get_active_cycle_id(db)
    request = build_analysis_request(db, ticker, str(cycle_id) if cycle_id else None)

    # Run board + CIO (not persisted)
    board = AdvisoryBoard(gateway)
    board_result = await board.convene(verdict_result, stances, None, request)

    cio = CIOSynthesizer(gateway)
    cio_result = await cio.synthesize(verdict_result, board_result, stances)

    return {
        "hypothetical": True,
        "ticker": ticker,
        "verdict": verdict_result.verdict.value,
        "confidence": float(verdict_result.confidence),
        "consensusScore": verdict_result.consensus_score,
        "adjustedVerdict": board_result.adjusted_verdict,
        "stanceOverrides": body.stance_overrides,
        "confidenceOverrides": body.confidence_overrides,
        "opinions": [
            {
                "advisor_name": op.advisor_name,
                "display_name": op.display_name,
                "vote": op.vote,
                "confidence": float(op.confidence) if isinstance(op.confidence, Decimal) else op.confidence,
                "assessment": op.assessment,
            }
            for op in board_result.opinions
        ],
        "narrative": {
            "headline": cio_result.headline,
            "narrative": cio_result.narrative,
        },
    }


@router.post("/pipeline/trigger/verdict")
async def trigger_verdict(
    body: TriggerVerdictRequest,
    db: Database = Depends(get_db),
) -> dict:
    """Re-synthesize verdict from stored agent signals (pure Python, no LLM)."""
    from investmentology.pipeline.builder import reconstruct_signal_sets
    from investmentology.verdict import synthesize

    ticker = body.ticker.upper()
    cycle_id = _get_active_cycle_id(db)

    if body.signal_source == "cycle":
        if not cycle_id:
            raise HTTPException(422, "No active cycle for cycle-scoped signals")
        signal_rows = state.get_agent_signals_for_ticker(db, cycle_id, ticker)
    else:
        signal_rows = state.get_latest_agent_signals(db, ticker)

    if not signal_rows:
        raise HTTPException(404, f"No agent signals found for {ticker}")

    signal_sets = reconstruct_signal_sets(signal_rows)
    result = synthesize(signal_sets)

    # Persist new verdict
    from investmentology.registry.queries import Registry
    registry = Registry(db)
    stances_json = [
        {
            "name": s.name,
            "sentiment": s.sentiment,
            "confidence": s.confidence,
            "key_signals": s.key_signals,
            "summary": s.summary,
        }
        for s in result.agent_stances
    ]

    verdict_id = registry.insert_verdict(
        ticker=ticker,
        verdict=result.verdict.value,
        confidence=result.confidence,
        reasoning=result.reasoning,
        consensus_score=result.consensus_score,
        risk_flags=result.risk_flags,
        agent_stances=stances_json,
        auditor_override=result.auditor_override,
        munger_override=result.munger_override,
    )

    return {
        "status": "completed",
        "ticker": ticker,
        "verdictId": verdict_id,
        "verdict": result.verdict.value,
        "confidence": float(result.confidence),
        "consensusScore": result.consensus_score,
        "agentCount": len(signal_sets),
        "signalSource": body.signal_source,
    }


@router.post("/pipeline/trigger/data")
async def trigger_data_refresh(
    body: TriggerDataRequest,
    db: Database = Depends(get_db),
) -> dict:
    """Refresh individual data sources for a ticker without re-running the full pipeline.

    Fetches the requested data keys in-process and caches them. Useful for
    filling gaps (e.g. just refresh analyst_ratings) without triggering
    a full data_fetch + all agents.
    """
    import asyncio
    from datetime import datetime, timezone

    from investmentology.config import load_config
    from investmentology.data.enricher import build_enricher
    from investmentology.data.web_search_provider import FallbackProvider

    ticker = body.ticker.upper()
    cycle_id = _ensure_active_cycle(db)

    valid_keys = {
        "fundamentals", "technical_indicators", "macro_context",
        "news_context", "earnings_context", "insider_context",
        "filing_context", "institutional_context", "analyst_ratings",
        "short_interest", "social_sentiment", "research_briefing",
    }
    bad_keys = [k for k in body.data_keys if k not in valid_keys]
    if bad_keys:
        raise HTTPException(400, f"Invalid data keys: {bad_keys}")

    config = load_config()
    enricher = build_enricher(config)
    fallback = FallbackProvider()

    results = []
    loop = asyncio.get_event_loop()

    for key in body.data_keys:
        result_data = None
        source = "unknown"

        try:
            # Try primary provider first
            if key == "macro_context" and enricher and enricher._fred:
                result_data = await loop.run_in_executor(
                    None, enricher._fred.get_macro_context,
                )
                source = "fred"
            elif key == "news_context" and enricher and enricher._finnhub:
                result_data = await loop.run_in_executor(
                    None, enricher._finnhub.get_news, ticker,
                )
                source = "finnhub"
            elif key == "earnings_context" and enricher and enricher._finnhub:
                result_data = await loop.run_in_executor(
                    None, enricher._finnhub.get_earnings, ticker,
                )
                source = "finnhub"
            elif key == "insider_context" and enricher and enricher._finnhub:
                result_data = await loop.run_in_executor(
                    None, enricher._finnhub.get_insider_transactions, ticker,
                )
                source = "finnhub"
            elif key == "social_sentiment" and enricher and enricher._finnhub:
                result_data = await loop.run_in_executor(
                    None, enricher._finnhub.get_social_sentiment, ticker,
                )
                source = "finnhub"
            elif key == "analyst_ratings" and enricher and enricher._finnhub:
                result_data = await loop.run_in_executor(
                    None, enricher._finnhub.get_analyst_ratings, ticker,
                )
                source = "finnhub"
            elif key == "short_interest" and enricher and enricher._finnhub:
                result_data = await loop.run_in_executor(
                    None, enricher._finnhub.get_short_interest, ticker,
                )
                source = "finnhub"
            elif key == "filing_context" and enricher and enricher._edgar:
                result_data = await loop.run_in_executor(
                    None, enricher._edgar.get_filing_text, ticker,
                )
                source = "edgar"
            elif key == "institutional_context" and enricher and enricher._edgar:
                raw = await loop.run_in_executor(
                    None, enricher._edgar.get_institutional_holders, ticker,
                )
                result_data = raw.get("holders", []) if isinstance(raw, dict) else raw
                source = "edgar"

            # Fallback to yfinance/SearXNG if primary returned None
            if result_data is None:
                fb_method = {
                    "analyst_ratings": fallback.get_analyst_ratings,
                    "short_interest": fallback.get_short_interest,
                    "insider_context": fallback.get_insider_transactions,
                    "earnings_context": fallback.get_earnings,
                    "news_context": fallback.get_news,
                    "social_sentiment": fallback.get_social_sentiment,
                    "filing_context": fallback.get_filing_context,
                }.get(key)
                if fb_method:
                    result_data = await loop.run_in_executor(
                        None, fb_method, ticker,
                    )
                    source = "fallback"

            if result_data is not None:
                # Stamp and cache
                now = datetime.now(timezone.utc).isoformat()
                if isinstance(result_data, dict) and "fetched_at" not in result_data:
                    result_data["fetched_at"] = now
                elif isinstance(result_data, list):
                    result_data = {
                        "items": result_data,
                        "count": len(result_data),
                        "fetched_at": now,
                    }
                state.store_data_cache(db, cycle_id, ticker, key, result_data)
                results.append({
                    "key": key, "status": "ok", "source": source,
                })
            else:
                results.append({
                    "key": key, "status": "empty", "source": source,
                })

        except Exception as exc:
            logger.warning("Data refresh %s failed for %s: %s", key, ticker, exc)
            results.append({
                "key": key, "status": "error", "error": str(exc)[:100],
            })

    ok_count = sum(1 for r in results if r["status"] == "ok")
    return {
        "ticker": ticker,
        "results": results,
        "refreshed": ok_count,
        "total": len(body.data_keys),
    }


@router.post("/pipeline/trigger/full")
async def trigger_full(
    body: TriggerFullRequest,
    db: Database = Depends(get_db),
) -> dict:
    """Full re-analysis for one or more tickers via the pipeline."""
    cycle_id = _ensure_active_cycle(db)

    results = []
    for raw_ticker in body.tickers:
        ticker = raw_ticker.upper()

        if body.force_data_refresh:
            # Reset from data_fetch onwards
            for step_name in [
                state.STEP_DATA_FETCH, state.STEP_DATA_VALIDATE,
                state.STEP_PRE_FILTER,
            ]:
                state.reset_or_create_step(db, cycle_id, ticker, step_name)

            # Also create screening + gate steps
            from investmentology.agents.skills import SCREENER_SKILLS
            for sname in SCREENER_SKILLS:
                state.reset_or_create_step(
                    db, cycle_id, ticker, f"{state.STEP_SCREENER_PREFIX}{sname}",
                )
            state.reset_or_create_step(db, cycle_id, ticker, state.STEP_GATE_DECISION)
            state.reset_or_create_step(db, cycle_id, ticker, state.STEP_RESEARCH)

        # Create Phase 2 steps (agents + debate + synthesis)
        from investmentology.agents.skills import SKILLS
        for agent_name in SKILLS:
            state.reset_or_create_step(
                db, cycle_id, ticker, f"agent:{agent_name}",
            )
        state.reset_or_create_step(db, cycle_id, ticker, state.STEP_DEBATE)
        state.reset_or_create_step(db, cycle_id, ticker, state.STEP_ADVERSARIAL)
        state.reset_or_create_step(db, cycle_id, ticker, state.STEP_SYNTHESIS)

        results.append({
            "ticker": ticker,
            "status": "queued",
            "forceDataRefresh": body.force_data_refresh,
        })

    return {"results": results}


# ═══════════════════════════════════════════════════════════════════════════
# DATA REPORT — data availability and agent impact per ticker
# ═══════════════════════════════════════════════════════════════════════════


# The enrichment data keys stored in pipeline_data_cache
_DATA_KEYS = [
    "fundamentals", "technical_indicators", "macro_context",
    "news_context", "earnings_context", "insider_context",
    "filing_context", "institutional_context", "analyst_ratings",
    "short_interest", "social_sentiment", "research_briefing",
]

# Data gate rules: agent -> (required_key, cap_value)
_DATA_GATE_CAPS: dict[str, tuple[str, float]] = {
    "simons": ("technical_indicators", 0.15),
    "soros": ("macro_context", 0.20),
    "druckenmiller": ("macro_context", 0.20),
    "dalio": ("macro_context", 0.20),
}


def _build_ticker_data_report(db: Database, cycle_id, ticker: str) -> dict:
    """Build data availability and agent impact report for a single ticker."""
    from investmentology.agents.skills import SKILLS

    # Load most recent cached data across all cycles (not just the active one)
    # This ensures data populated in a previous cycle still shows as available
    cached = state.get_latest_data_cache(db, ticker)

    # Data availability
    available = {}
    data_age = {}
    for key in _DATA_KEYS:
        if key in cached:
            available[key] = True
            # Try to extract timestamp from cached data
            val = cached[key]
            if isinstance(val, dict) and "fetched_at" in val:
                data_age[key] = val["fetched_at"]
        else:
            available[key] = False

    # Agent impact analysis
    agent_impact = []
    latest_signals = state.get_latest_agent_signals(db, ticker)
    signal_map = {r["agent_name"]: r for r in latest_signals}

    for agent_name, skill in SKILLS.items():
        info: dict = {"agent": agent_name, "status": "ok", "missingOptional": []}

        # Check data gates
        if agent_name in _DATA_GATE_CAPS:
            required_key, cap = _DATA_GATE_CAPS[agent_name]
            if not available.get(required_key):
                info["status"] = "capped"
                info["cap"] = cap
                info["reason"] = f"No {required_key.replace('_', ' ')}"

        # Check optional data
        for opt_key in skill.optional_data:
            # Map AnalysisRequest field names to cache keys
            cache_key = opt_key
            if not available.get(cache_key, False):
                info["missingOptional"].append(opt_key)

        # Last signal info
        sig = signal_map.get(agent_name)
        if sig:
            info["lastSignalAt"] = str(sig.get("created_at", ""))
            info["lastConfidence"] = float(sig["confidence"]) if sig.get("confidence") else None

        agent_impact.append(info)

    capped_count = sum(1 for a in agent_impact if a["status"] == "capped")

    return {
        "ticker": ticker,
        "dataAge": data_age,
        "available": available,
        "agentImpact": agent_impact,
        "cappedAgentCount": capped_count,
        "totalAgentCount": len(SKILLS),
    }


@router.get("/pipeline/data-report/{ticker}")
def data_report_ticker(
    ticker: str,
    db: Database = Depends(get_db),
) -> dict:
    """Data availability and agent impact for a single ticker."""
    ticker = ticker.upper()
    cycle_id = _get_active_cycle_id(db)
    return _build_ticker_data_report(db, cycle_id, ticker)


@router.get("/pipeline/data-report")
def data_report_portfolio(
    db: Database = Depends(get_db),
    scope: str = Query("portfolio", description="portfolio or all"),
) -> dict:
    """Portfolio-wide data availability summary."""
    cycle_id = _get_active_cycle_id(db)

    # Get tickers based on scope
    if scope == "portfolio":
        rows = db.execute(
            "SELECT DISTINCT ticker FROM ("
            "  SELECT ticker FROM invest.portfolio_positions WHERE is_closed = FALSE "
            "  UNION "
            "  SELECT ticker FROM invest.watchlist WHERE state = ANY(%s)"
            ") t",
            (["CANDIDATE", "CONVICTION_BUY", "WATCHLIST_EARLY", "WATCHLIST_CATALYST"],),
        )
    else:
        # All tickers in current cycle
        if not cycle_id:
            return {"scope": scope, "totalTickers": 0, "tickers": []}
        rows = db.execute(
            "SELECT DISTINCT ticker FROM invest.pipeline_state "
            "WHERE cycle_id = %s",
            (cycle_id,),
        )

    tickers = [r["ticker"] for r in rows]
    ticker_reports = [_build_ticker_data_report(db, cycle_id, t) for t in tickers]

    # Aggregate stats
    fully_enriched = sum(
        1 for r in ticker_reports
        if all(r["available"].get(k) for k in _DATA_KEYS[:3])  # fundamentals + tech + macro
    )
    missing_fundamentals = sum(
        1 for r in ticker_reports
        if not r["available"].get("fundamentals")
    )

    # Count data-gated agents across all tickers
    gated_agents: dict[str, int] = {}
    missing_by_key: dict[str, int] = {}
    for report in ticker_reports:
        for ai in report["agentImpact"]:
            if ai["status"] == "capped":
                gated_agents[ai["agent"]] = gated_agents.get(ai["agent"], 0) + 1
        for key in _DATA_KEYS:
            if not report["available"].get(key):
                missing_by_key[key] = missing_by_key.get(key, 0) + 1

    return {
        "scope": scope,
        "totalTickers": len(tickers),
        "fullyEnriched": fully_enriched,
        "partiallyEnriched": len(tickers) - fully_enriched - missing_fundamentals,
        "missingFundamentals": missing_fundamentals,
        "dataGatedAgents": gated_agents,
        "missingByDataKey": missing_by_key,
        "tickers": ticker_reports,
    }


# ---------------------------------------------------------------------------
# Analysis overview (multi-ticker command center)
# ---------------------------------------------------------------------------


@router.get("/pipeline/analysis-overview")
def analysis_overview(
    db: Database = Depends(get_db),
    scope: str = Query("portfolio", description="portfolio | watchlist | recommendations | custom"),
    tickers: str | None = Query(None, description="Comma-separated tickers for scope=custom"),
) -> dict:
    """Per-ticker analysis status for the Analysis dashboard.

    Combines data-report availability with latest verdict and agent signal
    timestamps into a single batch response.
    """
    from datetime import datetime, timezone, timedelta

    cycle_id = _get_active_cycle_id(db)

    # ── Resolve ticker list ──────────────────────────────────────────────
    if scope == "custom":
        if not tickers:
            return {"scope": scope, "tickers": []}
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        category_map = {t: "other" for t in ticker_list}

    elif scope == "portfolio":
        rows = db.execute(
            "SELECT ticker FROM invest.portfolio_positions "
            "WHERE is_closed = FALSE AND shares > 0"
        )
        ticker_list = [r["ticker"] for r in rows]
        category_map = {t: "portfolio" for t in ticker_list}

    elif scope == "watchlist":
        rows = db.execute(
            "SELECT DISTINCT ticker FROM invest.watchlist "
            "WHERE state NOT IN ('GRADUATED', 'REJECTED')"
        )
        ticker_list = [r["ticker"] for r in rows]
        category_map = {t: "watchlist" for t in ticker_list}

    elif scope == "recommendations":
        rows = db.execute(
            "SELECT DISTINCT ON (ticker) ticker "
            "FROM invest.verdicts "
            "WHERE verdict IN ('STRONG_BUY', 'BUY', 'ACCUMULATE') "
            "ORDER BY ticker, created_at DESC"
        )
        ticker_list = [r["ticker"] for r in rows]
        category_map = {t: "recommendation" for t in ticker_list}

    else:
        return {"scope": scope, "tickers": []}

    if not ticker_list:
        return {"scope": scope, "tickers": []}

    # ── Latest verdict per ticker (single batch query) ───────────────────
    placeholders = ",".join(["%s"] * len(ticker_list))
    verdict_rows = db.execute(
        f"SELECT DISTINCT ON (ticker) ticker, verdict, confidence, "
        f"created_at, board_adjusted_verdict "
        f"FROM invest.verdicts WHERE ticker IN ({placeholders}) "
        f"ORDER BY ticker, created_at DESC",
        tuple(ticker_list),
    )
    verdict_map = {r["ticker"]: r for r in verdict_rows}

    # ── Build per-ticker overview ────────────────────────────────────────
    now = datetime.now(timezone.utc)
    FRESH_THRESHOLD = timedelta(hours=6)
    STALE_THRESHOLD = timedelta(hours=24)

    result = []
    for ticker in ticker_list:
        report = _build_ticker_data_report(db, cycle_id, ticker)
        verdict_row = verdict_map.get(ticker)

        # Data staleness classification
        data_count = sum(1 for v in report["available"].values() if v)
        data_total = len(report["available"])

        staleness = "missing"
        if data_count > 0:
            ages = []
            for _key, ts in report["dataAge"].items():
                if ts:
                    try:
                        dt = datetime.fromisoformat(
                            str(ts).replace("Z", "+00:00")
                        )
                        ages.append(now - dt)
                    except (ValueError, TypeError):
                        pass
            if ages:
                oldest = max(ages)
                if oldest < FRESH_THRESHOLD and data_count == data_total:
                    staleness = "fresh"
                elif oldest < STALE_THRESHOLD:
                    staleness = "partial"
                else:
                    staleness = "stale"
            else:
                staleness = "partial"

        # Agent signals summary
        agents = []
        last_agent_run = None
        agent_count = 0
        for ai in report["agentImpact"]:
            ran_at = ai.get("lastSignalAt")
            if ran_at:
                agents.append({
                    "name": ai["agent"],
                    "confidence": ai.get("lastConfidence"),
                    "ranAt": ran_at,
                    "status": ai["status"],
                })
                agent_count += 1
                if last_agent_run is None or ran_at > last_agent_run:
                    last_agent_run = ran_at

        result.append({
            "ticker": ticker,
            "category": category_map.get(ticker, "other"),
            "verdict": verdict_row["verdict"] if verdict_row else None,
            "verdictConfidence": (
                float(verdict_row["confidence"])
                if verdict_row and verdict_row.get("confidence") is not None
                else None
            ),
            "verdictAt": (
                str(verdict_row["created_at"])
                if verdict_row and verdict_row.get("created_at")
                else None
            ),
            "boardAdjustedVerdict": (
                verdict_row.get("board_adjusted_verdict")
                if verdict_row
                else None
            ),
            "dataSourceCount": data_count,
            "dataSourceTotal": data_total,
            "dataStaleness": staleness,
            "lastAgentRun": last_agent_run,
            "agentCount": agent_count,
            "agentTotal": report["totalAgentCount"],
            "agents": sorted(
                agents, key=lambda a: a["ranAt"] or "", reverse=True
            ),
            "available": report["available"],
            "dataAge": report["dataAge"],
            "cappedAgentCount": report["cappedAgentCount"],
        })

    return {"scope": scope, "tickers": result}
