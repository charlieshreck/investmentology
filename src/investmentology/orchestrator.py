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
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
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
from investmentology.data.snapshots import fetch_market_snapshot
from investmentology.data.yfinance_client import YFinanceClient
from investmentology.quant_gate.screener import _dict_to_snapshot
from investmentology.compatibility.matrix import CompatibilityEngine, CompatibilityResult
from investmentology.competence.circle import CompetenceFilter, CompetenceResult
from investmentology.competence.moat import MoatAnalyzer, MoatAssessment
from investmentology.learning.kelly_bootstrap import compute_kelly_params
from investmentology.learning.predictions import PredictionManager
from investmentology.learning.registry import DecisionLogger
from investmentology.models.decision import DecisionType
from investmentology.models.lifecycle import WatchlistState
from investmentology.models.signal import AgentSignalSet
from investmentology.registry.queries import Registry
from investmentology.timing.sizing import PositionSizer, SizingResult
from investmentology.verdict import VerdictResult, VotingMethod, synthesize as synthesize_verdict

# Type for optional progress callback: (ticker, stage, step_index, total_steps) -> None
ProgressCallback = Callable[[str, str, int, int], Awaitable[None]]
TOTAL_PIPELINE_STEPS = 9

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
    # Market context at analysis time (Phase 0)
    market_snapshot: dict | None = None


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
        self._yfinance = YFinanceClient(cache_ttl_hours=4)
        self._debate_enabled = enable_debate
        self._prediction_mgr = PredictionManager(registry)
        # Dynamic agent weights from attribution (P0.4)
        self._dynamic_weights = None
        try:
            from investmentology.learning.attribution import AgentAttributionEngine
            attr_engine = AgentAttributionEngine(registry)
            report = attr_engine.compute_attribution()
            if report is not None:
                self._dynamic_weights = {
                    k: Decimal(str(v)) for k, v in report.recommended_weights.items()
                }
                logger.info("Using dynamic agent weights: %s", self._dynamic_weights)
        except Exception:
            logger.debug("Attribution-based weights not available, using defaults")

        # Kelly criterion from closed position history (P0.3)
        kelly = compute_kelly_params(registry)
        if kelly:
            logger.info("Kelly criterion activated: half_kelly=%.3f", kelly.half_kelly())


        # L2 components
        self._competence = CompetenceFilter(gateway)
        self._moat = MoatAnalyzer(gateway)

        # L3 agents — skip any that can't be configured
        self._agents = []
        for agent_cls in [WarrenAgent, SorosAgent, SimonsAgent, AuditorAgent]:
            try:
                agent = agent_cls(gateway)
                self._agents.append(agent)
            except (ValueError, KeyError) as exc:
                logger.warning("Skipping %s: %s", agent_cls.__name__, exc)

        if len(self._agents) < 2:
            raise RuntimeError(
                f"Insufficient agents: {len(self._agents)} available, minimum 2 required. "
                "Check provider API keys."
            )

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
        progress_callback: ProgressCallback | None = None,
    ) -> PipelineResult:
        """Run the full analysis pipeline on a list of candidates.

        Args:
            tickers: List of stock tickers to analyze.
            macro_context: Shared macro data for Soros agent.
            portfolio_context: Current portfolio state for Auditor agent.
            technical_indicators: Per-ticker technical indicators for Simons.
            progress_callback: Optional async callback for real-time stage updates.

        Returns:
            PipelineResult with all analysis details.
        """
        result = PipelineResult(candidates_in=len(tickers), passed_competence=0,
                                analyzed=0, conviction_buys=0, vetoed=0)

        for ticker in tickers:
            analysis = await self._analyze_single(
                ticker, macro_context, portfolio_context,
                (technical_indicators or {}).get(ticker),
                progress_callback=progress_callback,
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
        progress_callback: ProgressCallback | None = None,
    ) -> CandidateAnalysis:
        """Run full pipeline for a single ticker."""
        analysis = CandidateAnalysis(ticker=ticker)

        async def _emit(stage: str, step: int) -> None:
            if progress_callback:
                try:
                    await progress_callback(ticker, stage, step, TOTAL_PIPELINE_STEPS)
                except Exception:
                    pass

        await _emit("Fundamentals", 1)

        # Phase 0: Capture market snapshot at analysis time
        market_snapshot: dict | None = None
        try:
            market_snapshot = fetch_market_snapshot()
            # Store snapshot in DB for historical reference
            self._registry.insert_market_snapshot(market_snapshot)
            analysis.market_snapshot = market_snapshot
            logger.debug("Market snapshot captured: SPY=%s VIX=%s", market_snapshot.get("spy_price"), market_snapshot.get("vix"))
        except Exception:
            logger.warning("Failed to capture market snapshot for %s analysis", ticker)

        # Phase 1: Build thesis context for held positions
        held_position = None
        thesis_context: dict = {}
        if portfolio_context and portfolio_context.get("held_tickers"):
            if ticker in portfolio_context["held_tickers"]:
                for pos in portfolio_context.get("positions", []):
                    if pos.get("ticker") == ticker:
                        held_position = pos
                        thesis_context = {
                            "position_thesis": pos.get("thesis", ""),
                            "position_type": pos.get("position_type", "tactical"),
                            "days_held": pos.get("days_held", 0),
                            "entry_price": pos.get("entry_price"),
                            "pnl_pct": pos.get("pnl_pct", 0),
                        }
                        break

        # Fetch fundamentals — try DB cache first, then on-demand yfinance
        fundamentals = self._registry.get_latest_fundamentals(ticker)
        if fundamentals is None:
            logger.info("No cached fundamentals for %s, trying on-demand yfinance fetch", ticker)
            yf_data = self._yfinance.get_fundamentals(ticker)
            if yf_data:
                fundamentals = _dict_to_snapshot(yf_data)
            if fundamentals is None:
                logger.warning("No fundamentals for %s (yfinance fallback also failed), skipping", ticker)
                return analysis
            logger.info("Got on-demand fundamentals for %s via yfinance", ticker)

        # Get stock info for sector/industry
        stocks = self._registry.get_active_stocks()
        stock_info = next((s for s in stocks if s.ticker == ticker), None)
        sector = stock_info.sector if stock_info else ""
        industry = stock_info.industry if stock_info else ""

        # --- L2: Competence Filter + Moat ---
        await _emit("Competence", 2)
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
            # Phase 0+1: Market context and thesis lifecycle
            market_snapshot=market_snapshot,
            position_thesis=thesis_context.get("position_thesis"),
            position_type=thesis_context.get("position_type"),
            days_held=thesis_context.get("days_held"),
            entry_price=thesis_context.get("entry_price"),
            pnl_pct=thesis_context.get("pnl_pct"),
        )

        # Enrich with external data (FRED macro, Finnhub news/earnings/insider/sentiment)
        if self._enricher:
            try:
                self._enricher.enrich(request)
            except Exception:
                logger.warning("Data enrichment failed for %s, continuing without", ticker)

        # Run all configured agents concurrently
        await _emit("Agents", 3)
        agent_tasks = [self._run_agent(agent, request) for agent in self._agents]
        responses = await asyncio.gather(*agent_tasks, return_exceptions=True)

        # Collect initial responses
        initial_responses: list[AnalysisResponse] = []
        initial_agents: list = []
        for agent, resp in zip(self._agents, responses):
            if isinstance(resp, AnalysisResponse):
                initial_responses.append(resp)
                initial_agents.append(agent)
            elif isinstance(resp, Exception):
                logger.error("Agent %s failed for %s: %s", agent.name, ticker, resp)

        # --- L3.5: Debate Round ---
        await _emit("Debate", 4)
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
        await _emit("Adversarial", 5)
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
        await _emit("Verdict", 6)
        # First pass with weighted vote to determine direction
        initial_verdict = synthesize_verdict(
            agent_signals=analysis.agent_signal_sets,
            compatibility=analysis.compatibility,
            adversarial=analysis.adversarial,
            method=VotingMethod.WEIGHTED_VOTE,
            weights=self._dynamic_weights,
        )

        # Use supermajority for BUY/STRONG_BUY (higher bar for strong actions)
        if initial_verdict.verdict.value in ("STRONG_BUY", "BUY", "ACCUMULATE"):
            analysis.verdict = synthesize_verdict(
                agent_signals=analysis.agent_signal_sets,
                compatibility=analysis.compatibility,
                adversarial=analysis.adversarial,
                method=VotingMethod.SUPERMAJORITY,
                weights=self._dynamic_weights,
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

        # --- Phase 2: Thesis-aware verdict gating ---
        await _emit("Gating", 7)
        gating_result = None
        if held_position and thesis_context.get("position_type"):
            try:
                from investmentology.advisory.thesis_health import apply_verdict_gating, assess_thesis_health
                gating_result = apply_verdict_gating(
                    ticker=ticker,
                    new_verdict=analysis.verdict.verdict.value,
                    new_confidence=analysis.verdict.confidence,
                    position_type=thesis_context["position_type"],
                    registry=self._registry,
                )
                if not gating_result.allowed and gating_result.gated_verdict:
                    from investmentology.verdict import Verdict
                    original_verdict = analysis.verdict.verdict.value
                    analysis.verdict.verdict = Verdict(gating_result.gated_verdict)
                    analysis.verdict.risk_flags.append(
                        f"GATED: {original_verdict}→{gating_result.gated_verdict} ({gating_result.reason})"
                    )
                    logger.info(
                        "Verdict gated for %s: %s → %s (%s)",
                        ticker, original_verdict, gating_result.gated_verdict, gating_result.reason,
                    )

                # Assess and update thesis health on the position
                assessment = assess_thesis_health(ticker, self._registry, thesis_context["position_type"])
                try:
                    self._registry._db.execute(
                        "UPDATE invest.portfolio_positions SET thesis_health = %s "
                        "WHERE ticker = %s AND is_closed = false",
                        (assessment.health.value, ticker),
                    )
                except Exception:
                    logger.debug("Could not update thesis_health for %s (column may not exist yet)", ticker)
            except Exception:
                logger.debug("Verdict gating failed for %s, proceeding without", ticker)

        # Log verdict diff if verdict changed from previous
        self._log_verdict_diff(
            ticker, prev_verdict, analysis,
            was_gated=bool(gating_result and not gating_result.allowed),
            gating_reason=gating_result.reason if gating_result and not gating_result.allowed else None,
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
                price = fundamentals.price
                if price <= 0:
                    logger.warning("No valid price for %s, skipping sizing", ticker)
                    price = None

                if price is not None:
                    # Fetch live pendulum reading for sizing multiplier
                    pendulum_mult = Decimal("1.0")
                    try:
                        from investmentology.data.pendulum_feeds import auto_pendulum_reading
                        reading = auto_pendulum_reading()
                        if reading is not None:
                            pendulum_mult = reading.sizing_multiplier
                            logger.info(
                                "Pendulum reading: score=%d label=%s multiplier=%s",
                                reading.score, reading.label, reading.sizing_multiplier,
                            )
                    except Exception:
                        logger.debug("Pendulum feed unavailable, using neutral multiplier")

                    analysis.sizing = self._sizer.calculate_size(
                        portfolio_value=portfolio_value,
                        price=price,
                        current_position_count=len(positions),
                        pendulum_multiplier=pendulum_mult,
                        ticker=ticker,
                    )
            except Exception:
                logger.exception("L5 sizing failed for %s", ticker)

        # Persist verdict to DB
        await _emit("Persisting", 8)
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

        # Update held positions with fair value + stop loss from analysis
        self._update_held_position(ticker, analysis)

        # Log predictions for the learning feedback loop
        self._log_predictions(ticker, analysis)

        # Phase 4+5: Store in semantic + graph memory (fire-and-forget)
        self._store_memory_async(ticker, analysis, thesis_context)

        await _emit("Complete", 9)
        return analysis


    def _log_predictions(self, ticker: str, analysis: "CandidateAnalysis") -> None:
        """Log predictions from verdict for the learning feedback loop."""
        if not analysis.verdict:
            return

        verdict_val = analysis.verdict.verdict.value
        confidence = analysis.verdict.confidence

        # Map verdict to directional prediction (1=bullish, -1=bearish, 0=neutral)
        bullish_verdicts = {"STRONG_BUY", "BUY", "ACCUMULATE"}
        bearish_verdicts = {"SELL", "AVOID", "DISCARD", "REDUCE"}

        if verdict_val in bullish_verdicts:
            direction = Decimal("1")
            pred_type = "verdict_direction_up"
        elif verdict_val in bearish_verdicts:
            direction = Decimal("-1")
            pred_type = "verdict_direction_down"
        else:
            return  # Skip HOLD/WATCHLIST — ambiguous for predictions

        for horizon in (30, 90):
            try:
                self._prediction_mgr.log_prediction(
                    ticker=ticker,
                    prediction_type=pred_type,
                    predicted_value=direction,
                    confidence=confidence,
                    horizon_days=horizon,
                    source=f"orchestrator:{verdict_val}",
                )
                logger.info("Logged %d-day prediction for %s: %s conf=%s", horizon, ticker, pred_type, confidence)
            except Exception:
                logger.debug("Failed to log %d-day prediction for %s", horizon, ticker)

        # Log target price prediction if any agent provided one
        for resp in analysis.agent_responses:
            if resp.target_price and resp.target_price > 0:
                for horizon in (30, 90):
                    try:
                        self._prediction_mgr.log_prediction(
                            ticker=ticker,
                            prediction_type=f"target_price_{resp.agent_name}",
                            predicted_value=resp.target_price,
                            confidence=resp.signal_set.confidence,
                            horizon_days=horizon,
                            source=f"{resp.agent_name}:{resp.model}",
                        )
                    except Exception:
                        logger.debug("Failed to log %d-day target price prediction for %s/%s", horizon, ticker, resp.agent_name)

        # Phase 0: Backfill market context on predictions just logged
        if analysis.market_snapshot:
            try:
                snap = analysis.market_snapshot
                # Get stock price from fundamentals cache
                fund = self._registry.get_latest_fundamentals(ticker)
                stock_price = float(fund.price) if fund and fund.price else None
                self._registry._db.execute(
                    "UPDATE invest.predictions SET "
                    "price_at_prediction = %s, sp500_at_prediction = %s, vix_at_prediction = %s "
                    "WHERE ticker = %s AND price_at_prediction IS NULL "
                    "AND created_at > NOW() - INTERVAL '5 minutes'",
                    (stock_price, snap.get("spy_price"), snap.get("vix"), ticker),
                )
            except Exception:
                logger.debug("Could not backfill market context on predictions for %s", ticker)

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
            logger.warning("Could not fetch QG data for %s", ticker)
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
            logger.warning("Could not transition %s to %s", ticker, new_state)

    def _update_held_position(self, ticker: str, analysis: CandidateAnalysis) -> None:
        """Update fair_value_estimate and stop_loss on held positions after analysis."""
        if not analysis.agent_responses:
            return

        # Check if we hold this ticker
        positions = self._registry.get_open_positions()
        held = next((p for p in positions if p.ticker == ticker), None)
        if held is None:
            return

        # Compute consensus target price from agents that provided one
        target_prices = [
            r.target_price for r in analysis.agent_responses
            if r.target_price and r.target_price > 0
        ]
        fair_value: Decimal | None = None
        if target_prices:
            fair_value = sum(target_prices, Decimal(0)) / len(target_prices)
            fair_value = fair_value.quantize(Decimal("0.01"))

        # Compute stop loss based on position type
        stop_loss: Decimal | None = None
        if held.entry_price and held.entry_price > 0:
            if held.position_type == "core":
                # Core: 20% trailing stop from current high
                ref_price = max(held.entry_price, held.current_price or held.entry_price)
                stop_loss = (ref_price * Decimal("0.80")).quantize(Decimal("0.01"))
            else:
                # Tactical: 15% hard stop from entry
                stop_loss = (held.entry_price * Decimal("0.85")).quantize(Decimal("0.01"))

        # Phase 1 fix: Only set thesis on FIRST analysis (when entry_thesis is empty).
        # Subsequent analyses update fair_value/stop_loss but NEVER overwrite the thesis.
        thesis: str | None = None
        if analysis.verdict and not held.thesis:
            thesis = f"[{analysis.verdict.verdict.value}] {analysis.verdict.reasoning[:500]}"
            # Also set entry_thesis (immutable) via direct DB call
            try:
                self._registry._db.execute(
                    "UPDATE invest.portfolio_positions SET entry_thesis = %s "
                    "WHERE ticker = %s AND is_closed = false AND entry_thesis IS NULL",
                    (thesis, ticker),
                )
            except Exception:
                logger.debug("Could not set entry_thesis for %s (column may not exist yet)", ticker)

        if fair_value or stop_loss or thesis:
            updated = self._registry.update_position_analysis(
                ticker=ticker,
                fair_value_estimate=fair_value,
                stop_loss=stop_loss,
                thesis=thesis,
            )
            if updated:
                logger.info(
                    "Updated position %s: fair_value=%s stop_loss=%s",
                    ticker, fair_value, stop_loss,
                )

        # Log thesis event for audit trail
        self._log_thesis_event(ticker, held, analysis)

    def _log_thesis_event(
        self, ticker: str, held, analysis: CandidateAnalysis,
    ) -> None:
        """Log a thesis lifecycle event to the audit trail."""
        if not analysis.verdict:
            return

        # Determine event type
        prev = self._registry.get_latest_verdict(ticker)
        # Check if there's already a thesis event for this ticker
        try:
            existing_events = self._registry._db.execute(
                "SELECT event_type FROM invest.thesis_events "
                "WHERE ticker = %s ORDER BY created_at DESC LIMIT 1",
                (ticker,),
            )
        except Exception:
            existing_events = []

        if not existing_events:
            event_type = "ENTRY"
        elif prev and prev.get("verdict") != analysis.verdict.verdict.value:
            # Verdict changed
            bearish = {"SELL", "AVOID", "DISCARD", "REDUCE"}
            if analysis.verdict.verdict.value in bearish:
                event_type = "CHALLENGE"
            else:
                event_type = "REAFFIRM"
        else:
            event_type = "UPDATE"

        # Build agent stances snapshot
        agent_stances = [
            {"name": s.name, "sentiment": s.sentiment, "confidence": float(s.confidence)}
            for s in analysis.verdict.agent_stances
        ] if analysis.verdict.agent_stances else []

        # Build market snapshot for event
        ms = analysis.market_snapshot or {}

        try:
            import json
            self._registry._db.execute(
                "INSERT INTO invest.thesis_events "
                "(ticker, event_type, thesis_text, position_type, verdict_at_time, "
                "confidence_at_time, fair_value_at_time, price_at_time, "
                "market_snapshot, agent_stances) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    ticker,
                    event_type,
                    analysis.verdict.reasoning[:1000] if analysis.verdict.reasoning else None,
                    held.position_type if held else None,
                    analysis.verdict.verdict.value,
                    analysis.verdict.confidence,
                    held.fair_value_estimate if held else None,
                    held.current_price if held else None,
                    json.dumps({k: str(v) for k, v in ms.items() if v is not None}, default=str) if ms else None,
                    json.dumps(agent_stances, default=str) if agent_stances else None,
                ),
            )
            logger.debug("Logged thesis event %s for %s", event_type, ticker)
        except Exception:
            logger.debug("Could not log thesis event for %s (table may not exist yet)", ticker)

    def _log_verdict_diff(
        self, ticker: str, old_verdict: dict | None, analysis: CandidateAnalysis,
        was_gated: bool = False, gating_reason: str | None = None,
    ) -> None:
        """Log a verdict change to the verdict_diffs audit table."""
        if not analysis.verdict or not old_verdict:
            return

        old_v = old_verdict.get("verdict", "UNKNOWN")
        new_v = analysis.verdict.verdict.value
        if old_v == new_v:
            return

        try:
            import json
            self._registry._db.execute(
                "INSERT INTO invest.verdict_diffs "
                "(ticker, old_verdict, new_verdict, old_confidence, new_confidence, "
                "change_drivers, was_gated, gating_reason, position_type) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    ticker, old_v, new_v,
                    old_verdict.get("confidence"),
                    analysis.verdict.confidence,
                    json.dumps({
                        "agent_stances": [
                            {"name": s.name, "sentiment": s.sentiment}
                            for s in analysis.verdict.agent_stances
                        ] if analysis.verdict.agent_stances else [],
                    }),
                    was_gated,
                    gating_reason,
                    None,  # position_type filled by caller
                ),
            )
        except Exception:
            logger.debug("Could not log verdict diff for %s (table may not exist yet)", ticker)

    def _store_memory_async(
        self, ticker: str, analysis: CandidateAnalysis, thesis_context: dict,
    ) -> None:
        """Fire-and-forget storage to Qdrant + Neo4j memory layers."""
        if not analysis.verdict:
            return

        agent_stances = [
            {"name": s.name, "sentiment": s.sentiment, "confidence": float(s.confidence)}
            for s in analysis.verdict.agent_stances
        ] if analysis.verdict.agent_stances else []

        async def _store():
            # Phase 4: Qdrant semantic memory
            try:
                from investmentology.memory.semantic import store_analysis_memory
                await store_analysis_memory(
                    ticker=ticker,
                    verdict=analysis.verdict.verdict.value,
                    confidence=float(analysis.verdict.confidence),
                    reasoning=analysis.verdict.reasoning,
                    position_type=thesis_context.get("position_type"),
                    thesis_health=thesis_context.get("thesis_health"),
                    market_snapshot=analysis.market_snapshot,
                    agent_stances=agent_stances,
                    days_held=thesis_context.get("days_held"),
                    pnl_pct=thesis_context.get("pnl_pct"),
                )
            except Exception:
                logger.debug("Qdrant memory store failed for %s", ticker)

            # Phase 5: Neo4j graph memory
            try:
                from investmentology.memory.graph import record_verdict_node
                await record_verdict_node(
                    ticker=ticker,
                    verdict=analysis.verdict.verdict.value,
                    confidence=float(analysis.verdict.confidence),
                    consensus_score=analysis.verdict.consensus_score,
                    agent_stances=agent_stances,
                    thesis_health=thesis_context.get("thesis_health"),
                )
            except Exception:
                logger.debug("Neo4j memory store failed for %s", ticker)

        try:
            asyncio.ensure_future(_store())
        except RuntimeError:
            # No event loop running — skip memory storage
            logger.debug("No event loop for memory storage, skipping")
