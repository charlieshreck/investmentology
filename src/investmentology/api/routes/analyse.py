"""Analyse endpoints — trigger on-demand analysis."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from investmentology.api.deps import get_orchestrator, get_registry
from investmentology.orchestrator import AnalysisOrchestrator
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_portfolio_context(registry: Registry) -> dict:
    """Build portfolio context dict from current open positions."""
    from datetime import date

    positions = registry.get_open_positions()
    if not positions:
        return {}

    total_value = float(sum(p.current_price * p.shares for p in positions))

    # Compute sector exposure from positions + stocks table
    sector_exposure: dict[str, float] = {}
    stocks = registry.get_active_stocks()
    stock_map = {s.ticker: s for s in stocks}
    for p in positions:
        stock = stock_map.get(p.ticker)
        sector = stock.sector if stock else "Unknown"
        mv = float(p.current_price * p.shares)
        pct = (mv / total_value * 100) if total_value > 0 else 0
        sector_exposure[sector] = sector_exposure.get(sector, 0) + pct

    pos_list = []
    for p in positions:
        pnl = float(p.pnl_pct * 100) if p.entry_price else 0
        weight = (float(p.current_price * p.shares) / total_value * 100) if total_value > 0 else 0
        days = (date.today() - p.entry_date).days if p.entry_date else 0
        pos_list.append({
            "ticker": p.ticker,
            "shares": float(p.shares),
            "entry_price": float(p.entry_price),
            "current_price": float(p.current_price),
            "weight": float(p.weight) if p.weight else 0,
            "weight_pct": round(weight, 1),
            "pnl_pct": round(pnl, 1),
            "position_type": p.position_type,
            "entry_date": str(p.entry_date) if p.entry_date else None,
            "days_held": days,
            "thesis": p.thesis or "",
            "fair_value_estimate": float(p.fair_value_estimate) if p.fair_value_estimate else None,
            "stop_loss": float(p.stop_loss) if p.stop_loss else None,
        })

    return {
        "held_tickers": [p.ticker for p in positions],
        "position_count": len(positions),
        "total_value": total_value,
        "sector_exposure": sector_exposure,
        "positions": pos_list,
    }


class AnalyseRequest(BaseModel):
    tickers: list[str]


class AnalyseResponse(BaseModel):
    analysis_id: str
    candidates_in: int
    passed_competence: int
    analyzed: int
    conviction_buys: int
    vetoed: int
    results: list[dict]


@router.post("/analyse")
async def trigger_analysis(
    body: AnalyseRequest,
    orchestrator: AnalysisOrchestrator = Depends(get_orchestrator),
    registry: Registry = Depends(get_registry),
) -> dict:
    """Trigger on-demand analysis for a list of tickers."""
    analysis_id = str(uuid.uuid4())
    tickers = [t.upper() for t in body.tickers]

    # Build real portfolio context from current holdings
    portfolio_context = _build_portfolio_context(registry)

    result = await orchestrator.analyze_candidates(
        tickers,
        portfolio_context=portfolio_context,
    )

    return _format_pipeline_result(analysis_id, result)


def _format_pipeline_result(analysis_id: str, result) -> dict:
    """Format PipelineResult into API response dict."""
    return {
        "analysis_id": analysis_id,
        "candidates_in": result.candidates_in,
        "passed_competence": result.passed_competence,
        "analyzed": result.analyzed,
        "conviction_buys": result.conviction_buys,
        "vetoed": result.vetoed,
        "results": [
            {
                "ticker": r.ticker,
                "passed_competence": r.passed_competence,
                "final_action": r.final_action,
                "final_confidence": float(r.final_confidence),
                "data_quality_error": r.data_quality_error,
                "competence": {
                    "in_circle": r.competence.in_circle,
                    "confidence": float(r.competence.confidence),
                    "reasoning": r.competence.reasoning,
                    "sector_familiarity": r.competence.sector_familiarity,
                } if r.competence else None,
                "moat": {
                    "type": r.moat.moat_type,
                    "sources": r.moat.sources,
                    "trajectory": r.moat.trajectory,
                    "durability_years": r.moat.durability_years,
                    "confidence": float(r.moat.confidence),
                    "reasoning": r.moat.reasoning,
                } if r.moat else None,
                "verdict": {
                    "recommendation": r.verdict.verdict.value,
                    "confidence": float(r.verdict.confidence),
                    "consensus_score": r.verdict.consensus_score,
                    "reasoning": r.verdict.reasoning,
                    "auditor_override": r.verdict.auditor_override,
                    "munger_override": r.verdict.munger_override,
                    "risk_flags": r.verdict.risk_flags,
                    "agent_stances": [
                        {
                            "name": s.name,
                            "sentiment": s.sentiment,
                            "confidence": float(s.confidence),
                            "key_signals": s.key_signals,
                            "summary": s.summary,
                        }
                        for s in r.verdict.agent_stances
                    ],
                } if r.verdict else None,
            }
            for r in result.results
        ],
    }


@router.post("/analyse/stream")
async def trigger_analysis_stream(
    body: AnalyseRequest,
    request: Request,
    orchestrator: AnalysisOrchestrator = Depends(get_orchestrator),
    registry: Registry = Depends(get_registry),
):
    """Trigger analysis with real-time SSE progress streaming.

    Returns a text/event-stream with progress events followed by the final result.
    """
    analysis_id = str(uuid.uuid4())
    tickers = [t.upper() for t in body.tickers]
    ticker_total = len(tickers)
    portfolio_context = _build_portfolio_context(registry)

    queue: asyncio.Queue = asyncio.Queue()
    ticker_index = 0

    async def progress_callback(ticker: str, stage: str, step: int, total: int) -> None:
        nonlocal ticker_index
        # Track which ticker we're on
        if stage == "Fundamentals":
            ticker_index += 1
        await queue.put({
            "type": "progress",
            "ticker": ticker,
            "stage": stage,
            "step": step,
            "totalSteps": total,
            "tickerIndex": ticker_index,
            "tickerTotal": ticker_total,
        })

    async def run_analysis() -> None:
        try:
            result = await orchestrator.analyze_candidates(
                tickers,
                portfolio_context=portfolio_context,
                progress_callback=progress_callback,
            )
            await queue.put({
                "type": "result",
                **_format_pipeline_result(analysis_id, result),
            })
        except Exception as exc:
            logger.exception("Streaming analysis failed")
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            await queue.put(None)  # Sentinel to close stream

    async def event_generator():
        task = asyncio.create_task(run_analysis())
        try:
            while True:
                if await request.is_disconnected():
                    task.cancel()
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
