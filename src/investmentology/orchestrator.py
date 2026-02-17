"""Stage 6: Analysis Orchestrator — ties the full L2→L3→L4 pipeline together.

For a given set of candidates (from L1 Quant Gate), runs:
  L2: Competence Filter + Moat Analysis
  L3: Multi-Agent Analysis (Warren, Soros, Simons, Auditor)
  L4: Compatibility Matrix + Adversarial Review (Munger)
  L5: Position Sizing

Logs every decision and prediction to the Decision Registry.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from investmentology.adversarial.munger import AdversarialResult, MungerOrchestrator, MungerVerdict
from investmentology.agents.auditor import AuditorAgent
from investmentology.agents.base import AnalysisRequest, AnalysisResponse
from investmentology.agents.debate import DebateOrchestrator
from investmentology.agents.gateway import LLMGateway
from investmentology.agents.simons import SimonsAgent
from investmentology.agents.soros import SorosAgent
from investmentology.agents.warren import WarrenAgent
from investmentology.data.enricher import DataEnricher
from investmentology.compatibility.matrix import CompatibilityEngine, CompatibilityResult
from investmentology.competence.circle import CompetenceFilter, CompetenceResult
from investmentology.competence.moat import MoatAnalyzer, MoatAssessment
from investmentology.learning.registry import DecisionLogger
from investmentology.models.decision import DecisionType
from investmentology.models.lifecycle import WatchlistState
from investmentology.models.signal import AgentSignalSet
from investmentology.models.stock import FundamentalsSnapshot
from investmentology.registry.queries import Registry
from investmentology.timing.sizing import PositionSizer, SizingResult
from investmentology.verdict import VerdictResult, VotingMethod, synthesize as synthesize_verdict

logger = logging.getLogger(__name__)


@dataclass
class CandidateAnalysis:
    """Full analysis result for a single candidate stock."""

    ticker: str
    # L2
    competence: CompetenceResult | None = None
    moat: MoatAssessment | None = None
    passed_competence: bool = False
    # L3
    agent_responses: list[AnalysisResponse] = field(default_factory=list)
    agent_signal_sets: list[AgentSignalSet] = field(default_factory=list)
    # L4
    compatibility: CompatibilityResult | None = None
    adversarial: AdversarialResult | None = None
    # L5
    sizing: SizingResult | None = None
    # Verdict
    verdict: VerdictResult | None = None
    # Overall
    final_action: str = "NO_ACTION"
    final_confidence: Decimal = Decimal("0")


@dataclass
class PipelineResult:
    """Result of running the full pipeline on a batch of candidates."""

    candidates_in: int
    passed_competence: int
    analyzed: int
    conviction_buys: int
    vetoed: int
    results: list[CandidateAnalysis] = field(default_factory=list)


class AnalysisOrchestrator:
    """Orchestrates the full L2→L5 analysis pipeline."""

    def __init__(
        self,
        registry: Registry,
        gateway: LLMGateway,
        decision_logger: DecisionLogger,
        position_sizer: PositionSizer | None = None,
        enricher: DataEnricher | None = None,
        enable_debate: bool = True,
    ) -> None:
        self._registry = registry
        self._gateway = gateway
        self._decision_logger = decision_logger
        self._sizer = position_sizer
        self._enricher = enricher
        self._debate_enabled = enable_debate

        # L2 components
        self._competence = CompetenceFilter(gateway)
        self._moat = MoatAnalyzer(gateway)

        # L3 agents
        self._warren = WarrenAgent(gateway)
        self._soros = SorosAgent(gateway)
        self._simons = SimonsAgent(gateway)
        self._auditor = AuditorAgent(gateway)
        self._agents = [self._warren, self._soros, self._simons, self._auditor]

        # L3.5 debate
        self._debate = DebateOrchestrator(gateway) if enable_debate else None

        # L4 components
        self._compat_engine = CompatibilityEngine()
        self._munger = MungerOrchestrator(gateway, registry=registry)

    async def analyze_candidates(
        self,
        tickers: list[str],
        macro_context: dict | None = None,
        portfolio_context: dict | None = None,
        technical_indicators: dict[str, dict] | None = None,
    ) -> PipelineResult:
        """Run the full analysis pipeline on a list of candidates.

        Args:
            tickers: List of stock tickers to analyze.
            macro_context: Shared macro data for Soros agent.
            portfolio_context: Current portfolio state for Auditor agent.
            technical_indicators: Per-ticker technical indicators for Simons.

        Returns:
            PipelineResult with all analysis details.
        """
        result = PipelineResult(candidates_in=len(tickers), passed_competence=0,
                                analyzed=0, conviction_buys=0, vetoed=0)

        for ticker in tickers:
            analysis = await self._analyze_single(
                ticker, macro_context, portfolio_context,
                (technical_indicators or {}).get(ticker),
            )
            result.results.append(analysis)

            if analysis.passed_competence:
                result.passed_competence += 1
            if analysis.agent_responses:
                result.analyzed += 1
            if analysis.final_action == "CONVICTION_BUY":
                result.conviction_buys += 1
            if analysis.adversarial and analysis.adversarial.verdict == MungerVerdict.VETO:
                result.vetoed += 1

        return result

    async def _analyze_single(
        self,
        ticker: str,
        macro_context: dict | None,
        portfolio_context: dict | None,
        technical_indicators: dict | None,
    ) -> CandidateAnalysis:
        """Run full pipeline for a single ticker."""
        analysis = CandidateAnalysis(ticker=ticker)

        # Fetch fundamentals
        fundamentals = self._registry.get_latest_fundamentals(ticker)
        if fundamentals is None:
            logger.warning("No fundamentals for %s, skipping", ticker)
            return analysis

        # Get stock info for sector/industry
        stocks = self._registry.get_active_stocks()
        stock_info = next((s for s in stocks if s.ticker == ticker), None)
        sector = stock_info.sector if stock_info else ""
        industry = stock_info.industry if stock_info else ""

        # --- L2: Competence Filter + Moat ---
        try:
            analysis.competence = await self._competence.assess(
                ticker, sector, industry,
                f"{sector} / {industry} company with ${fundamentals.market_cap:,.0f} market cap",
            )
            analysis.moat = await self._moat.analyze(ticker, sector, fundamentals)
        except Exception:
            logger.exception("L2 failed for %s, treating as out-of-circle", ticker)
            analysis.competence = CompetenceResult(
                in_circle=False, confidence=Decimal("0.3"),
                reasoning="L2 assessment failed", sector_familiarity="low",
            )

        analysis.passed_competence = bool(
            analysis.competence and analysis.competence.in_circle
        )

        # Build competence + moat detail for decision log
        competence_signals: dict = {}
        if analysis.competence:
            competence_signals["in_circle"] = analysis.competence.in_circle
            competence_signals["confidence"] = float(analysis.competence.confidence)
            competence_signals["sector_familiarity"] = analysis.competence.sector_familiarity
        if analysis.moat:
            competence_signals["moat"] = {
                "type": analysis.moat.moat_type,
                "sources": analysis.moat.sources,
                "trajectory": analysis.moat.trajectory,
                "durability_years": analysis.moat.durability_years,
                "confidence": float(analysis.moat.confidence),
                "reasoning": analysis.moat.reasoning,
            }

        # Log competence decision (pass or fail) with full details
        self._decision_logger.log_competence_decision(
            ticker=ticker,
            passed=analysis.passed_competence,
            reasoning=analysis.competence.reasoning if analysis.competence else "No assessment",
            confidence=analysis.competence.confidence if analysis.competence else Decimal("0"),
            signals=competence_signals,
        )

        # Competence is advisory, not a gate — always continue to L3

        # --- L3: Multi-Agent Analysis ---
        # Get quant gate data for enrichment
        qg_data = self._get_quant_gate_data(ticker)

        # Fetch previous analysis context for history-aware re-analysis
        prev_verdict = self._registry.get_latest_verdict(ticker)
        prev_signals: list[dict] = []
        if prev_verdict:
            signal_rows = self._registry._db.execute(
                "SELECT agent_name, signals, confidence, reasoning, created_at "
                "FROM invest.agent_signals WHERE ticker = %s "
                "ORDER BY created_at DESC LIMIT 4",
                (ticker,),
            )
            prev_signals = [
                {
                    "agent_name": r["agent_name"],
                    "signals": r["signals"],
                    "confidence": float(r["confidence"]) if r["confidence"] else None,
                    "reasoning": r["reasoning"],
                    "date": str(r["created_at"]) if r["created_at"] else None,
                }
                for r in signal_rows
            ]

        request = AnalysisRequest(
            ticker=ticker,
            fundamentals=fundamentals,
            sector=sector,
            industry=industry,
            quant_gate_rank=qg_data.get("combined_rank"),
            piotroski_score=qg_data.get("piotroski_score"),
            altman_z_score=qg_data.get("altman_z_score"),
            macro_context=macro_context,
            portfolio_context=portfolio_context,
            technical_indicators=technical_indicators,
            previous_verdict={
                "verdict": prev_verdict["verdict"],
                "confidence": float(prev_verdict["confidence"]) if prev_verdict["confidence"] else None,
                "consensus_score": float(prev_verdict["consensus_score"]) if prev_verdict["consensus_score"] else None,
                "reasoning": prev_verdict["reasoning"],
                "date": str(prev_verdict["created_at"]) if prev_verdict["created_at"] else None,
            } if prev_verdict else None,
            previous_signals=prev_signals or None,
        )

        # Enrich with external data (FRED macro, Finnhub news/earnings/insider/sentiment)
        if self._enricher:
            try:
                self._enricher.enrich(request)
            except Exception:
                logger.debug("Data enrichment failed for %s, continuing without", ticker)

        # Run all 4 agents concurrently
        agent_tasks = [
            self._run_agent(self._warren, request),
            self._run_agent(self._soros, request),
            self._run_agent(self._simons, request),
            self._run_agent(self._auditor, request),
        ]
        responses = await asyncio.gather(*agent_tasks, return_exceptions=True)

        # Collect initial responses
        initial_responses: list[AnalysisResponse] = []
        initial_agents: list = []
        for i, resp in enumerate(responses):
            if isinstance(resp, AnalysisResponse):
                initial_responses.append(resp)
                initial_agents.append(self._agents[i])
            elif isinstance(resp, Exception):
                logger.error("Agent failed for %s: %s", ticker, resp)

        # --- L3.5: Debate Round ---
        if self._debate and len(initial_responses) >= 2:
            try:
                revised = await self._debate.debate(
                    initial_agents, initial_responses, request,
                )
                final_responses = revised
            except Exception:
                logger.exception("Debate round failed for %s, using initial responses", ticker)
                final_responses = initial_responses
        else:
            final_responses = initial_responses

        for resp in final_responses:
            analysis.agent_responses.append(resp)
            analysis.agent_signal_sets.append(resp.signal_set)
            # Log agent signals to DB
            self._registry.insert_agent_signals(
                ticker=ticker,
                agent_name=resp.agent_name,
                model=resp.model,
                signals={"tags": [str(s.tag) for s in resp.signal_set.signals.signals]},
                confidence=resp.signal_set.confidence,
                reasoning=resp.summary,
                token_usage=resp.token_usage,
                latency_ms=resp.latency_ms,
            )

        if not analysis.agent_signal_sets:
            logger.warning("No agent signals for %s, skipping L4", ticker)
            return analysis

        # --- L4: Compatibility Matrix + Adversarial ---
        analysis.compatibility = self._compat_engine.evaluate(
            ticker, analysis.agent_signal_sets,
        )

        # Log L3 pattern decision
        pattern_name = (
            analysis.compatibility.matched_pattern.name
            if analysis.compatibility.matched_pattern
            else "NONE"
        )
        self._decision_logger.log_analysis_decision(
            ticker=ticker,
            decision_type=DecisionType.AGENT_ANALYSIS,
            layer_source="L3_COMPATIBILITY",
            confidence=analysis.compatibility.avg_confidence,
            reasoning=f"Pattern: {pattern_name}, score: {analysis.compatibility.pattern_score:.2f}",
            signals={
                "pattern": pattern_name,
                "score": float(analysis.compatibility.pattern_score),
                "dangerous_disagreements": analysis.compatibility.dangerous_disagreement_count,
            },
        )

        # Run Munger adversarial if needed
        if analysis.compatibility.requires_munger:
            thesis = "; ".join(r.summary for r in analysis.agent_responses)
            fundamentals_summary = (
                f"EY: {fundamentals.earnings_yield}, ROIC: {fundamentals.roic}, "
                f"Market Cap: ${fundamentals.market_cap:,.0f}"
            )
            try:
                analysis.adversarial = await self._munger.review(
                    ticker=ticker,
                    fundamentals_summary=fundamentals_summary,
                    thesis=thesis,
                    agent_signals=analysis.agent_signal_sets,
                    sector=sector,
                )
            except Exception:
                logger.exception("Munger review failed for %s", ticker)

        # --- Synthesize verdict ---
        # First pass with weighted vote to determine direction
        initial_verdict = synthesize_verdict(
            agent_signals=analysis.agent_signal_sets,
            compatibility=analysis.compatibility,
            adversarial=analysis.adversarial,
            method=VotingMethod.WEIGHTED_VOTE,
        )

        # Use supermajority for BUY/STRONG_BUY (higher bar for strong actions)
        if initial_verdict.verdict.value in ("STRONG_BUY", "BUY", "ACCUMULATE"):
            analysis.verdict = synthesize_verdict(
                agent_signals=analysis.agent_signal_sets,
                compatibility=analysis.compatibility,
                adversarial=analysis.adversarial,
                method=VotingMethod.SUPERMAJORITY,
            )
        else:
            analysis.verdict = initial_verdict

        # Add competence warning as risk flag if outside circle
        if not analysis.passed_competence and analysis.competence:
            familiarity = analysis.competence.sector_familiarity
            conf = analysis.competence.confidence * 100
            analysis.verdict.risk_flags.append(
                f"Outside Circle of Competence ({familiarity} familiarity, {conf:.0f}% confidence)"
            )

        # Map verdict to legacy action code for backward compat
        analysis.final_action = self._verdict_to_action(analysis.verdict)
        analysis.final_confidence = analysis.verdict.confidence

        # --- L5: Position Sizing ---
        if self._sizer and analysis.final_action in ("CONVICTION_BUY", "BUY"):
            try:
                positions = self._registry.get_open_positions()
                portfolio_value = sum(
                    p.current_price * p.shares for p in positions
                ) or Decimal("100000")
                price = fundamentals.price if fundamentals.price > 0 else Decimal("100")
                analysis.sizing = self._sizer.calculate_size(
                    portfolio_value=portfolio_value,
                    price=price,
                    current_position_count=len(positions),
                    ticker=ticker,
                )
            except Exception:
                logger.exception("L5 sizing failed for %s", ticker)

        # Persist verdict to DB
        self._save_verdict(ticker, analysis.verdict)

        # Build consensus breakdown for logging
        breakdown_data = {}
        if analysis.verdict.consensus_breakdown:
            cb = analysis.verdict.consensus_breakdown
            breakdown_data = {
                "voting_method": cb.method,
                "votes": cb.votes,
                "bullish": cb.bullish_count,
                "bearish": cb.bearish_count,
                "supermajority_met": cb.supermajority_met,
            }

        # Log final decision
        self._decision_logger.log_analysis_decision(
            ticker=ticker,
            decision_type=self._action_to_decision_type(analysis.final_action),
            layer_source="L4_VERDICT",
            confidence=analysis.final_confidence,
            reasoning=analysis.verdict.reasoning,
            signals={
                "verdict": analysis.verdict.verdict.value,
                "consensus_score": analysis.verdict.consensus_score,
                "action": analysis.final_action,
                "auditor_override": analysis.verdict.auditor_override,
                "munger_override": analysis.verdict.munger_override,
                "munger_verdict": (
                    analysis.adversarial.verdict.value
                    if analysis.adversarial
                    else "NOT_REVIEWED"
                ),
                "consensus_breakdown": breakdown_data,
                "sizing": {
                    "method": analysis.sizing.sizing_method,
                    "shares": analysis.sizing.shares,
                    "dollar_amount": float(analysis.sizing.dollar_amount),
                } if analysis.sizing else None,
            },
        )

        # Update watchlist state
        self._update_watchlist(ticker, analysis)

        return analysis

    async def _run_agent(
        self, agent: WarrenAgent | SorosAgent | SimonsAgent | AuditorAgent,
        request: AnalysisRequest,
    ) -> AnalysisResponse:
        """Run a single agent with error wrapping."""
        return await agent.analyze(request)

    def _get_quant_gate_data(self, ticker: str) -> dict:
        """Get the latest quant gate results for a ticker."""
        try:
            rows = self._registry._db.execute(
                "SELECT combined_rank, piotroski_score, altman_z_score "
                "FROM invest.quant_gate_results "
                "WHERE ticker = %s "
                "ORDER BY run_id DESC LIMIT 1",
                (ticker,),
            )
            if rows:
                r = rows[0]
                return {
                    "combined_rank": r.get("combined_rank"),
                    "piotroski_score": r.get("piotroski_score"),
                    "altman_z_score": (
                        Decimal(str(r["altman_z_score"]))
                        if r.get("altman_z_score") is not None
                        else None
                    ),
                }
        except Exception:
            logger.debug("Could not fetch QG data for %s", ticker)
        return {}

    def _save_verdict(self, ticker: str, verdict: VerdictResult) -> bool:
        """Persist a verdict to the database. Returns True on success."""
        try:
            self._registry.insert_verdict(
                ticker=ticker,
                verdict=verdict.verdict.value,
                confidence=verdict.confidence,
                consensus_score=verdict.consensus_score,
                reasoning=verdict.reasoning,
                agent_stances=[
                    {
                        "name": s.name,
                        "sentiment": s.sentiment,
                        "confidence": float(s.confidence),
                        "key_signals": s.key_signals,
                        "summary": s.summary,
                    }
                    for s in verdict.agent_stances
                ],
                risk_flags=verdict.risk_flags,
                auditor_override=verdict.auditor_override,
                munger_override=verdict.munger_override,
            )
            return True
        except Exception:
            logger.exception("Failed to save verdict for %s", ticker)
            return False

    # Verdict → legacy action mapping for watchlist state transitions
    _VERDICT_ACTION_MAP: dict[str, str] = {
        "STRONG_BUY": "CONVICTION_BUY",
        "BUY": "CONVICTION_BUY",
        "ACCUMULATE": "WATCHLIST_EARLY",
        "HOLD": "HOLD",
        "WATCHLIST": "WATCHLIST_CATALYST",
        "REDUCE": "SELL",
        "SELL": "SELL",
        "AVOID": "REJECTED",
        "DISCARD": "HARD_REJECT",
    }

    @classmethod
    def _verdict_to_action(cls, verdict: VerdictResult) -> str:
        """Map VerdictResult to a legacy action code."""
        return cls._VERDICT_ACTION_MAP.get(verdict.verdict.value, "MANUAL_REVIEW")

    @staticmethod
    def _action_to_decision_type(action: str) -> DecisionType:
        """Map final action string to DecisionType."""
        mapping = {
            "CONVICTION_BUY": DecisionType.BUY,
            "BUY": DecisionType.BUY,
            "WATCHLIST_EARLY": DecisionType.WATCHLIST,
            "WATCHLIST_CATALYST": DecisionType.WATCHLIST,
            "HOLD": DecisionType.HOLD,
            "SELL": DecisionType.SELL,
            "REJECTED": DecisionType.REJECT,
            "MANUAL_REVIEW": DecisionType.AGENT_ANALYSIS,
            "NO_ACTION": DecisionType.HOLD,
            "HARD_REJECT": DecisionType.REJECT,
        }
        return mapping.get(action, DecisionType.AGENT_ANALYSIS)

    def _update_watchlist(self, ticker: str, analysis: CandidateAnalysis) -> None:
        """Update watchlist state based on final action."""
        state_map = {
            "CONVICTION_BUY": WatchlistState.CONVICTION_BUY,
            "WATCHLIST_EARLY": WatchlistState.WATCHLIST_EARLY,
            "WATCHLIST_CATALYST": WatchlistState.WATCHLIST_CATALYST,
            "SELL": WatchlistState.POSITION_SELL,
            "REJECTED": WatchlistState.REJECTED,
            "HARD_REJECT": WatchlistState.REJECTED,
        }
        new_state = state_map.get(analysis.final_action)
        if new_state is None:
            return

        try:
            self._registry.update_watchlist_state(ticker, new_state)
        except ValueError:
            logger.debug("Could not transition %s to %s", ticker, new_state)
