"""Analyse endpoints — trigger on-demand analysis."""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from investmentology.api.deps import get_orchestrator
from investmentology.orchestrator import AnalysisOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


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
) -> dict:
    """Trigger on-demand analysis for a list of tickers."""
    analysis_id = str(uuid.uuid4())
    tickers = [t.upper() for t in body.tickers]

    result = await orchestrator.analyze_candidates(tickers)

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
