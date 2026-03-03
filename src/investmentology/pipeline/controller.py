"""Pipeline controller — the main event loop for the agent-first pipeline.

Runs as a K8s Deployment.  Every 60 seconds it:
1. Checks for tickers needing analysis (watchlist + quant gate candidates)
2. Creates pipeline_state rows for each ticker's required steps
3. Dispatches ready steps to CLI queues or direct API calls
4. Checks convergence → triggers debate/synthesis when ready
5. Expires stale rows and retries failed steps

The controller is the orchestrator replacement — it coordinates agents
but doesn't run them in a monolithic per-ticker pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
from decimal import Decimal
from uuid import UUID

from investmentology.agents.base import AnalysisRequest, AnalysisResponse
from investmentology.agents.gateway import LLMGateway
from investmentology.agents.runner import AgentRunner
from investmentology.agents.skills import (
    API_ONLY_AGENTS,
    PRIMARY_SKILLS,
    SCOUT_SKILLS,
    SCREENER_SKILLS,
    SKILLS,
)
from investmentology.pipeline import state
from investmentology.pipeline.convergence import should_debate  # noqa: F401
from investmentology.pipeline.pre_filter import deterministic_pre_filter
from investmentology.pipeline.scheduler import AgentJob, CLIScheduler
from investmentology.registry.db import Database
from investmentology.registry.reentry import create_gate_blocks, get_blocked_tickers

logger = logging.getLogger(__name__)

# How often the main loop runs (seconds)
POLL_INTERVAL = 60

# Agent names by role
PRIMARY_AGENT_NAMES = list(PRIMARY_SKILLS.keys())
SCOUT_AGENT_NAMES = list(SCOUT_SKILLS.keys())
SCREENER_AGENT_NAMES = list(SCREENER_SKILLS.keys())
ALL_AGENT_NAMES = list(SKILLS.keys())
# Analysis agents = all except data_analyst and screeners
ANALYSIS_AGENT_NAMES = [
    n for n in ALL_AGENT_NAMES
    if n != "data_analyst" and n not in SCREENER_AGENT_NAMES
]

# Action tags that indicate a REJECT decision from screeners
_REJECT_TAGS = {"REJECT", "REJECT_HARD"}

# Supermajority: 3 of 4 screeners must pass for a ticker to proceed
SCREENER_PASS_THRESHOLD = 3

# Watchlist states eligible for analysis
_ANALYSABLE_STATES = [
    "CANDIDATE", "ASSESSED", "CONVICTION_BUY",
    "WATCHLIST_EARLY", "WATCHLIST_CATALYST",
    "CONFLICT_REVIEW", "POSITION_HOLD", "POSITION_TRIM",
]


class PipelineController:
    """Main controller for the agent-first pipeline."""

    def __init__(self, db: Database, gateway: LLMGateway) -> None:
        self.db = db
        self.gateway = gateway
        self.scheduler = CLIScheduler()
        self._runners: dict[str, AgentRunner] = {}
        self._running = False
        self._current_cycle_id: UUID | None = None

        # Pre-create runners for all skills
        for name, skill in SKILLS.items():
            self._runners[name] = AgentRunner(skill, gateway)

        # API agent concurrency limits — prevents rate limit bombs
        # Groq: 30 RPM free tier → 2 concurrent
        # DeepSeek: 60 RPM → 15 concurrent (Lynch + Simons + screeners)
        self._api_semaphores: dict[str, asyncio.Semaphore] = {
            "groq": asyncio.Semaphore(2),
            "deepseek": asyncio.Semaphore(15),
        }

        # Track step IDs currently in CLI queues to prevent re-dispatch
        self._cli_queued_steps: set[int] = set()

        # YFinance client — synchronous, used in run_in_executor
        from investmentology.data.yfinance_client import YFinanceClient
        self._yf_client = YFinanceClient(cache_ttl_hours=24)

    async def start(self) -> None:
        """Start the controller and its workers."""
        self._running = True
        await self.gateway.start()
        await self.scheduler.start()
        logger.info("Pipeline controller started")

    async def stop(self) -> None:
        """Stop the controller gracefully."""
        self._running = False
        await self.scheduler.stop()
        await self.gateway.close()
        logger.info("Pipeline controller stopped")

    async def run_loop(self) -> None:
        """Main event loop — polls for work every POLL_INTERVAL seconds."""
        while self._running:
            try:
                await self._tick()
            except Exception:
                logger.exception("Controller tick failed")
            await asyncio.sleep(POLL_INTERVAL)

    # ------------------------------------------------------------------
    # Single tick — one pass through the pipeline state
    # ------------------------------------------------------------------

    async def _tick(self) -> None:
        """Process one iteration of the controller loop."""
        # 1. Expire stale steps, recover stuck running steps, expire old cycles
        state.expire_stale_steps(self.db)
        state.reset_stale_running_steps(self.db)
        state.expire_old_cycles(self.db)

        # 2. Get or create current cycle
        cycle_id = self._get_or_create_cycle()
        if cycle_id is None:
            return
        self._current_cycle_id = cycle_id

        # 3. Populate screening steps for tickers needing analysis
        tickers = self._get_analysis_tickers()
        for ticker in tickers:
            existing = state.get_ticker_progress(self.db, cycle_id, ticker)
            if not existing:
                state.create_screening_steps(
                    self.db, cycle_id, ticker, SCREENER_AGENT_NAMES,
                )

        # 4. Get pending work
        pending = state.get_pending_steps(self.db, cycle_id)
        if not pending:
            # Check if cycle is complete
            self._check_cycle_completion(cycle_id)
            return

        logger.info(
            "Controller tick: %d pending steps in cycle %s",
            len(pending), cycle_id,
        )

        # 5. Process each pending step.
        # CLI agent steps are batched: dispatch at most CLI_DISPATCH_LIMIT
        # jobs per queue per tick to avoid flooding queues. Ticker-first
        # ordering ensures all agents for one ticker complete before the next.
        CLI_DISPATCH_LIMIT = 5  # max CLI jobs per queue per tick
        cli_dispatched: dict[str, int] = {"claude": 0, "gemini": 0}

        # Separate agent steps for ticker-first ordering
        agent_steps: list[dict] = []
        other_steps: list[dict] = []
        for row in pending:
            if row["step"].startswith(state.STEP_AGENT_PREFIX):
                agent_steps.append(row)
            else:
                other_steps.append(row)

        # Process non-agent steps immediately (data_fetch, screener, etc.)
        for row in other_steps:
            step = row["step"]
            ticker = row["ticker"]
            step_id = row["id"]

            if step == state.STEP_DATA_FETCH:
                await self._handle_data_fetch(cycle_id, ticker, step_id)

            elif step == state.STEP_DATA_VALIDATE:
                await self._handle_data_validate(cycle_id, ticker, step_id)

            elif step == state.STEP_PRE_FILTER:
                await self._handle_pre_filter(cycle_id, ticker, step_id)

            elif step.startswith(state.STEP_SCREENER_PREFIX):
                screener_name = step[len(state.STEP_SCREENER_PREFIX):]
                await self._handle_screener(cycle_id, ticker, step_id, screener_name)

            elif step == state.STEP_GATE_DECISION:
                await self._handle_gate_decision(cycle_id, ticker, step_id)

            elif step == state.STEP_DEBATE:
                await self._handle_debate(cycle_id, ticker, step_id)

            elif step == state.STEP_SYNTHESIS:
                await self._handle_synthesis(cycle_id, ticker, step_id)

        # Process agent steps: group by ticker, dispatch ticker-first
        from collections import defaultdict
        ticker_agents: dict[str, list[dict]] = defaultdict(list)
        for row in agent_steps:
            ticker_agents[row["ticker"]].append(row)

        for ticker, rows in ticker_agents.items():
            for row in rows:
                step = row["step"]
                step_id = row["id"]
                agent_name = step[len(state.STEP_AGENT_PREFIX):]

                # Check CLI dispatch limit for CLI agents
                skill = SKILLS.get(agent_name)
                if skill and skill.cli_screen and agent_name not in API_ONLY_AGENTS:
                    screen = skill.cli_screen
                    if cli_dispatched.get(screen, 0) >= CLI_DISPATCH_LIMIT:
                        continue  # Leave as pending for next tick
                    await self._handle_agent(cycle_id, ticker, step_id, agent_name)
                    # Only count if actually dispatched (not already queued)
                    if step_id in self._cli_queued_steps:
                        cli_dispatched[screen] = cli_dispatched.get(screen, 0) + 1
                else:
                    # API agents — no limit
                    await self._handle_agent(cycle_id, ticker, step_id, agent_name)

        # 6. Check if cycle is complete
        self._check_cycle_completion(cycle_id)

    # ------------------------------------------------------------------
    # Step handlers
    # ------------------------------------------------------------------

    async def _handle_data_fetch(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Fetch fresh data for a ticker via yfinance."""
        state.mark_running(self.db, step_id)
        try:
            loop = asyncio.get_event_loop()
            fundamentals = await loop.run_in_executor(
                None, self._yf_client.get_fundamentals, ticker,
            )
            if fundamentals is None:
                state.mark_failed(self.db, step_id, "yfinance returned None")
                return

            if fundamentals.get("_validation_errors"):
                errors = fundamentals["_validation_errors"]
                state.mark_failed(
                    self.db, step_id,
                    f"Data quality: {'; '.join(errors)}",
                )
                return

            # Cache fundamentals in pipeline data cache
            state.store_data_cache(
                self.db, cycle_id, ticker, "fundamentals", fundamentals,
            )

            # Fetch technical indicators if available
            try:
                from investmentology.data.technical_indicators import (
                    compute_technical_indicators,
                )
                tech = await loop.run_in_executor(
                    None, compute_technical_indicators, ticker,
                )
                if tech:
                    state.store_data_cache(
                        self.db, cycle_id, ticker, "technical_indicators", tech,
                    )
            except Exception:
                logger.debug("Technical indicators unavailable for %s", ticker)

            state.mark_completed(self.db, step_id)
            logger.info("Data fetch for %s completed", ticker)
        except Exception as e:
            state.mark_failed(self.db, step_id, str(e))

    async def _handle_data_validate(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Run data validation (deterministic + LLM Data Analyst)."""
        if not state.is_step_completed(
            self.db, cycle_id, ticker, state.STEP_DATA_FETCH,
        ):
            return

        state.mark_running(self.db, step_id)
        try:
            # Load cached fundamentals
            fundamentals = state.get_data_cache(
                self.db, cycle_id, ticker, "fundamentals",
            )
            if not fundamentals:
                state.mark_failed(self.db, step_id, "No cached fundamentals")
                return

            # 1. Deterministic validation
            from investmentology.data.validation import validate_fundamentals
            validation = validate_fundamentals(fundamentals)
            if not validation.is_valid:
                error_msg = "; ".join(validation.errors[:3])
                state.mark_failed(
                    self.db, step_id, f"Validation failed: {error_msg}",
                )
                return

            # Cache validation result
            state.store_data_cache(
                self.db, cycle_id, ticker, "validation", {
                    "is_valid": validation.is_valid,
                    "warnings": validation.warnings,
                    "errors": validation.errors,
                },
            )

            # NOTE: LLM validation via Data Analyst is available but disabled
            # for batch processing (38s per ticker via CLI proxy is too slow
            # for 200+ tickers). Deterministic validation catches the critical
            # cases. Enable for targeted re-analysis via the web UI.

            state.mark_completed(self.db, step_id)
            logger.info("Data validation for %s passed", ticker)
        except Exception as e:
            state.mark_failed(self.db, step_id, str(e))

    async def _handle_pre_filter(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Run deterministic pre-filter before LLM screeners."""
        if not state.is_step_completed(
            self.db, cycle_id, ticker, state.STEP_DATA_VALIDATE,
        ):
            return

        state.mark_running(self.db, step_id)
        try:
            fundamentals = state.get_data_cache(
                self.db, cycle_id, ticker, "fundamentals",
            )
            if not fundamentals:
                state.mark_failed(self.db, step_id, "No cached fundamentals")
                return

            # Load quant gate data
            quant_gate = None
            try:
                qg_rows = self.db.execute(
                    "SELECT combined_rank, piotroski_score, altman_z_score "
                    "FROM invest.quant_gate_results "
                    "WHERE ticker = %s ORDER BY id DESC LIMIT 1",
                    (ticker,),
                )
                if qg_rows:
                    quant_gate = qg_rows[0]
            except Exception:
                pass

            tech = state.get_data_cache(
                self.db, cycle_id, ticker, "technical_indicators",
            )

            result = deterministic_pre_filter(fundamentals, quant_gate, tech)

            state.store_data_cache(
                self.db, cycle_id, ticker, "pre_filter_result", {
                    "passed": result.passed,
                    "rejection_reason": result.rejection_reason,
                    "rules_checked": result.rules_checked,
                    "rules_failed": result.rules_failed,
                },
            )

            if not result.passed:
                # Pre-filter rejection — skip screeners and gate entirely
                for name in SCREENER_AGENT_NAMES:
                    step_key = f"{state.STEP_SCREENER_PREFIX}{name}"
                    s = state.get_step_status(self.db, cycle_id, ticker, step_key)
                    if s and s["status"] == "pending":
                        state.mark_completed(self.db, s["id"])

                gate_step = state.get_step_status(
                    self.db, cycle_id, ticker, state.STEP_GATE_DECISION,
                )
                if gate_step and gate_step["status"] == "pending":
                    state.mark_completed(self.db, gate_step["id"])

                state.mark_completed(self.db, step_id)
                logger.info(
                    "Pre-filter REJECT for %s: %s",
                    ticker, result.rejection_reason,
                )
                return

            state.mark_completed(self.db, step_id)
            logger.info(
                "Pre-filter PASS for %s (%d rules checked)",
                ticker, result.rules_checked,
            )
        except Exception as e:
            # On error, PASS by default (don't penalize for infra issues)
            state.mark_completed(self.db, step_id)
            logger.warning(
                "Pre-filter error for %s, defaulting to PASS: %s", ticker, e,
            )

    async def _handle_screener(
        self, cycle_id: UUID, ticker: str, step_id: int, screener_name: str,
    ) -> None:
        """Dispatch a screener agent (API-only, fast)."""
        if not state.is_step_completed(
            self.db, cycle_id, ticker, state.STEP_PRE_FILTER,
        ):
            return

        # Check pre-filter didn't reject this ticker
        pf_result = state.get_data_cache(
            self.db, cycle_id, ticker, "pre_filter_result",
        )
        if pf_result and not pf_result.get("passed", True):
            return

        skill = SCREENER_SKILLS.get(screener_name)
        if not skill:
            state.mark_failed(self.db, step_id, f"Unknown screener: {screener_name}")
            return

        runner = self._runners.get(screener_name)
        if not runner:
            state.mark_failed(self.db, step_id, f"No runner for: {screener_name}")
            return

        state.mark_running(self.db, step_id)
        asyncio.create_task(
            self._run_api_agent(step_id, runner, ticker),
            name=f"screener-{screener_name}-{ticker}",
        )

    async def _handle_gate_decision(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Deterministic gate decision: supermajority vote (3/4 screeners must pass)."""
        # Check if pre-filter already rejected (gate decision already completed)
        pf_result = state.get_data_cache(
            self.db, cycle_id, ticker, "pre_filter_result",
        )
        if pf_result and not pf_result.get("passed", True):
            return  # Already handled by pre-filter

        # Check all screeners are done (completed or failed)
        all_done = True
        for name in SCREENER_AGENT_NAMES:
            screener_step = f"{state.STEP_SCREENER_PREFIX}{name}"
            step_status = state.get_step_status(
                self.db, cycle_id, ticker, screener_step,
            )
            if step_status is None:
                all_done = False
                break
            if step_status["status"] in ("pending", "running"):
                all_done = False
                break
            # "completed" or "failed" both count as done

        if not all_done:
            return

        state.mark_running(self.db, step_id)
        try:
            # Load screener signal results
            signal_rows = state.get_agent_signals_for_ticker(
                self.db, cycle_id, ticker,
            )
            screener_results = [
                r for r in signal_rows
                if r["agent_name"] in SCREENER_AGENT_NAMES
            ]

            # Count screeners that failed to produce results (API errors)
            failed_screener_count = len(SCREENER_AGENT_NAMES) - len(screener_results)

            if not screener_results and failed_screener_count == len(SCREENER_AGENT_NAMES):
                logger.warning(
                    "All screeners failed for %s, defaulting to PASS", ticker,
                )
                self._gate_pass(cycle_id, ticker, step_id)
                return

            # Check each screener's action tags for REJECT
            reject_count = 0
            screener_tags: list[list[str]] = []
            for row in screener_results:
                signals_data = row["signals"]
                if isinstance(signals_data, str):
                    signals_data = json.loads(signals_data)

                tags = [s.get("tag", "") for s in signals_data.get("signals", [])]
                screener_tags.append(tags)

                # Check if this screener rejected
                action_tags = set(tags) & _REJECT_TAGS
                if action_tags:
                    reject_count += 1

            # Supermajority: 3 of 4 must pass. Failed screeners count as PASS.
            pass_count = (len(screener_results) - reject_count) + failed_screener_count

            if pass_count >= SCREENER_PASS_THRESHOLD:
                self._gate_pass(cycle_id, ticker, step_id)
            else:
                self._gate_fail(cycle_id, ticker, step_id, screener_tags)

        except Exception as e:
            state.mark_failed(self.db, step_id, str(e))
            logger.exception("Gate decision failed for %s", ticker)

    def _gate_pass(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Ticker passed the gate — create Phase 2 analysis steps."""
        state.create_analysis_steps(
            self.db, cycle_id, ticker, ANALYSIS_AGENT_NAMES,
        )
        state.mark_completed(self.db, step_id)
        logger.info("Gate PASS for %s — created analysis steps", ticker)

    def _gate_fail(
        self, cycle_id: UUID, ticker: str, step_id: int,
        screener_tags: list[list[str]],
    ) -> None:
        """Ticker failed the gate — create reentry blocks."""
        # Load fundamentals for baseline snapshot
        fundamentals = None
        if self._current_cycle_id:
            fundamentals = state.get_data_cache(
                self.db, self._current_cycle_id, ticker, "fundamentals",
            )

        blocks = create_gate_blocks(
            self.db, ticker, screener_tags, fundamentals,
        )
        state.mark_completed(self.db, step_id)
        logger.info(
            "Gate FAIL for %s — filtered out (%d reentry blocks created)",
            ticker, blocks,
        )

    async def _handle_agent(
        self, cycle_id: UUID, ticker: str, step_id: int, agent_name: str,
    ) -> None:
        """Dispatch an agent analysis step."""
        if not state.is_step_completed(
            self.db, cycle_id, ticker, state.STEP_GATE_DECISION,
        ):
            return

        skill = SKILLS.get(agent_name)
        if not skill:
            state.mark_failed(self.db, step_id, f"Unknown agent: {agent_name}")
            return

        runner = self._runners.get(agent_name)
        if not runner:
            state.mark_failed(self.db, step_id, f"No runner for: {agent_name}")
            return

        if agent_name in API_ONLY_AGENTS:
            state.mark_running(self.db, step_id)
            asyncio.create_task(
                self._run_api_agent(step_id, runner, ticker),
                name=f"api-{agent_name}-{ticker}",
            )
        else:
            # Guard: don't re-dispatch if already in the CLI queue
            if step_id in self._cli_queued_steps:
                return

            def _on_start(sid=step_id):
                state.mark_running(self.db, sid)

            loop = asyncio.get_event_loop()
            future = loop.create_future()
            job = AgentJob(
                skill=skill,
                runner=runner,
                request=self._build_request(ticker),
                step_id=step_id,
                future=future,
                on_start=_on_start,
            )
            self._cli_queued_steps.add(step_id)
            self.scheduler.submit(job)
            asyncio.create_task(
                self._await_cli_result(step_id, future, agent_name, ticker),
                name=f"cli-{agent_name}-{ticker}",
            )

    async def _handle_debate(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Trigger debate if agents disagree significantly."""
        if not state.are_all_agent_steps_completed(
            self.db, cycle_id, ticker, PRIMARY_AGENT_NAMES,
        ):
            return

        state.mark_running(self.db, step_id)
        try:
            # Load agent signals from DB
            signal_rows = state.get_agent_signals_for_ticker(
                self.db, cycle_id, ticker,
            )
            if not signal_rows:
                logger.warning(
                    "No agent signals for %s, skipping debate", ticker,
                )
                state.mark_completed(self.db, step_id)
                return

            # Reconstruct signal sets for convergence check
            agent_signal_sets = self._reconstruct_signal_sets(signal_rows)
            primary_signals = [
                ss for ss in agent_signal_sets
                if ss.agent_name in PRIMARY_AGENT_NAMES
            ]

            needs_debate = should_debate(primary_signals)
            logger.info(
                "Debate check for %s: needs_debate=%s (%d primary signals)",
                ticker, needs_debate, len(primary_signals),
            )

            if not needs_debate:
                state.mark_completed(self.db, step_id)
                return

            # Run debate via DebateOrchestrator
            from investmentology.agents.debate import DebateOrchestrator

            debate_orch = DebateOrchestrator(self.gateway)
            request = self._build_request(ticker)

            # Build AnalysisResponse list from saved signals
            responses = []
            runners = []
            for ss in primary_signals:
                resp = AnalysisResponse(
                    agent_name=ss.agent_name,
                    model=ss.model,
                    ticker=ticker,
                    signal_set=ss,
                    summary=ss.reasoning,
                    target_price=getattr(ss, "target_price", None),
                )
                responses.append(resp)
                runner = self._runners.get(ss.agent_name)
                if runner:
                    runners.append(runner)

            revised = await debate_orch.debate(runners, responses, request)

            # Save revised signals
            for resp in revised:
                self._save_agent_signals(ticker, resp)

            state.mark_completed(self.db, step_id)
            logger.info("Debate for %s completed with %d revised responses",
                        ticker, len(revised))
        except Exception as e:
            state.mark_failed(self.db, step_id, str(e))
            logger.exception("Debate failed for %s", ticker)

    async def _handle_synthesis(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Run verdict synthesis + advisory board + CIO narrative."""
        if not state.is_step_completed(
            self.db, cycle_id, ticker, state.STEP_DEBATE,
        ):
            return

        state.mark_running(self.db, step_id)
        try:
            # 1. Load all agent signals
            signal_rows = state.get_agent_signals_for_ticker(
                self.db, cycle_id, ticker,
            )
            if not signal_rows:
                state.mark_failed(
                    self.db, step_id, "No agent signals for synthesis",
                )
                return

            agent_signal_sets = self._reconstruct_signal_sets(signal_rows)

            # 2. Build weights from skills
            weights = {
                name: Decimal(str(skill.base_weight))
                for name, skill in SKILLS.items()
                if skill.base_weight > 0
            }

            # 3. Verdict synthesis (deterministic vote aggregation)
            from investmentology.verdict import VotingMethod, synthesize
            verdict_result = synthesize(
                agent_signal_sets,
                method=VotingMethod.WEIGHTED_VOTE,
                weights=weights,
            )
            logger.info(
                "Verdict for %s: %s (conf=%.2f, consensus=%.2f)",
                ticker, verdict_result.verdict.value,
                verdict_result.confidence, verdict_result.consensus_score,
            )

            # 4. Advisory Board (LLM — 4 concurrent calls)
            board_result = None
            try:
                from investmentology.advisory.board import AdvisoryBoard
                board = AdvisoryBoard(self.gateway)
                request = self._build_request(ticker)
                board_result = await board.convene(
                    verdict=verdict_result,
                    stances=verdict_result.agent_stances,
                    adversarial=None,
                    request=request,
                    fundamentals=request.fundamentals,
                )
            except Exception:
                logger.warning(
                    "Advisory board failed for %s, proceeding without",
                    ticker, exc_info=True,
                )

            # 5. CIO Narrative (LLM — 1 call)
            narrative = None
            if board_result:
                try:
                    from investmentology.advisory.cio import CIOSynthesizer
                    cio = CIOSynthesizer(self.gateway)
                    narrative = await cio.synthesize(
                        verdict=verdict_result,
                        board_result=board_result,
                        stances=verdict_result.agent_stances,
                    )
                    board_result.narrative = narrative
                except Exception:
                    logger.warning(
                        "CIO narrative failed for %s, proceeding without",
                        ticker, exc_info=True,
                    )

            # 6. Determine effective verdict
            effective_verdict = verdict_result.verdict.value
            if board_result and board_result.adjusted_verdict:
                effective_verdict = board_result.adjusted_verdict

            # 7. Serialize and save verdict
            from investmentology.registry.queries import Registry
            registry = Registry(self.db)

            advisory_opinions = None
            if board_result:
                advisory_opinions = [
                    {
                        "advisor_name": getattr(op, "advisor_name", ""),
                        "display_name": getattr(op, "display_name", ""),
                        "vote": getattr(op.vote, "value", str(op.vote)),
                        "confidence": float(getattr(op, "confidence", 0)),
                        "assessment": getattr(op, "assessment", ""),
                        "key_concern": getattr(op, "key_concern", ""),
                        "key_endorsement": getattr(op, "key_endorsement", ""),
                        "reasoning": getattr(op, "reasoning", ""),
                    }
                    for op in board_result.opinions
                ]

            board_narrative_dict = None
            if narrative:
                board_narrative_dict = {
                    "headline": getattr(narrative, "headline", ""),
                    "narrative": getattr(narrative, "narrative", ""),
                    "risk_summary": getattr(narrative, "risk_summary", ""),
                    "pre_mortem": getattr(narrative, "pre_mortem", ""),
                    "conflict_resolution": getattr(narrative, "conflict_resolution", ""),
                    "verdict_adjustment": getattr(narrative, "verdict_adjustment", ""),
                    "advisor_consensus": getattr(narrative, "advisor_consensus", ""),
                }

            agent_stances_dicts = [
                {
                    "name": s.name,
                    "sentiment": s.sentiment,
                    "confidence": float(s.confidence),
                    "key_signals": s.key_signals,
                    "summary": s.summary[:500] if s.summary else "",
                }
                for s in verdict_result.agent_stances
            ]

            verdict_id = registry.insert_verdict(
                ticker=ticker,
                verdict=effective_verdict,
                confidence=verdict_result.confidence,
                consensus_score=verdict_result.consensus_score,
                reasoning=verdict_result.reasoning,
                agent_stances=agent_stances_dicts,
                risk_flags=verdict_result.risk_flags,
                auditor_override=verdict_result.auditor_override,
                munger_override=verdict_result.munger_override,
                advisory_opinions=advisory_opinions,
                board_narrative=board_narrative_dict,
                board_adjusted_verdict=(
                    board_result.adjusted_verdict if board_result else None
                ),
            )

            state.mark_completed(self.db, step_id, result_ref=verdict_id)
            logger.info(
                "Synthesis for %s: verdict=%s confidence=%.2f "
                "(board_adjusted=%s, verdict_id=%d)",
                ticker, effective_verdict, verdict_result.confidence,
                board_result.adjusted_verdict if board_result else None,
                verdict_id,
            )

            # 8. Create reentry blocks for negative verdicts
            negative_verdicts = {"AVOID", "DISCARD", "SELL", "REDUCE"}
            if effective_verdict in negative_verdicts:
                try:
                    from investmentology.registry.reentry import (
                        extract_and_save_blocks,
                    )
                    agent_tags = [
                        [s.tag.value for s in ss.signals.signals]
                        for ss in agent_signal_sets
                    ]
                    raw_fund = state.get_data_cache(
                        self.db, cycle_id, ticker, "fundamentals",
                    )
                    extract_and_save_blocks(
                        registry, verdict_id, ticker, agent_tags, raw_fund,
                    )
                except Exception:
                    logger.warning(
                        "Reentry block creation failed for %s", ticker,
                        exc_info=True,
                    )
        except Exception as e:
            state.mark_failed(self.db, step_id, str(e))
            logger.exception("Synthesis failed for %s", ticker)

    # ------------------------------------------------------------------
    # Async result handlers
    # ------------------------------------------------------------------

    # Map remote CLI providers to their underlying rate-limited API provider
    _PROVIDER_RATE_GROUP: dict[str, str] = {
        "remote-simons": "groq",
        "remote-lynch": "deepseek",
        "groq": "groq",
        "deepseek": "deepseek",
    }

    async def _run_api_agent(
        self, step_id: int, runner: AgentRunner, ticker: str,
    ) -> None:
        """Run an API-only agent (Simons, Lynch) with rate limiting."""
        try:
            provider = runner._resolve_provider()
            rate_group = self._PROVIDER_RATE_GROUP.get(provider, provider)
            sem = self._api_semaphores.get(rate_group)

            if sem:
                async with sem:
                    request = self._build_request(ticker)
                    response = await runner.analyze(request)
            else:
                request = self._build_request(ticker)
                response = await runner.analyze(request)

            signal_id = self._save_agent_signals(ticker, response)
            state.mark_completed(self.db, step_id, result_ref=signal_id)
            logger.info(
                "API agent %s/%s completed (conf=%.2f)",
                runner.skill.name, ticker, response.signal_set.confidence,
            )
        except Exception as e:
            state.mark_failed(self.db, step_id, str(e))
            logger.exception("API agent %s/%s failed", runner.skill.name, ticker)

    async def _await_cli_result(
        self, step_id: int, future: asyncio.Future, agent_name: str, ticker: str,
    ) -> None:
        """Wait for a CLI agent result and update pipeline state."""
        try:
            response = await future
            signal_id = self._save_agent_signals(ticker, response)
            state.mark_completed(self.db, step_id, result_ref=signal_id)
        except Exception as e:
            state.mark_failed(self.db, step_id, str(e))
            logger.exception("CLI agent %s/%s failed", agent_name, ticker)
        finally:
            self._cli_queued_steps.discard(step_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_create_cycle(self) -> UUID | None:
        """Get the active cycle or create a new one."""
        rows = self.db.execute(
            "SELECT id FROM invest.pipeline_cycles "
            "WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
        )
        if rows:
            return rows[0]["id"]

        return state.create_cycle(self.db)

    def _check_cycle_completion(self, cycle_id: UUID) -> None:
        """Check if the cycle is complete and mark it if so."""
        summary = state.get_cycle_summary(self.db, cycle_id)
        if summary["pending"] == 0 and summary["running"] == 0:
            if summary["completed"] > 0 or summary["failed"] > 0:
                state.complete_cycle(self.db, cycle_id)
                logger.info(
                    "Pipeline cycle %s completed: %s", cycle_id, summary,
                )

    def _save_agent_signals(
        self, ticker: str, response: AnalysisResponse,
    ) -> int:
        """Save agent signals to DB and return the signal row id."""
        from investmentology.registry.queries import Registry
        registry = Registry(self.db)

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

    def _reconstruct_signal_sets(self, signal_rows: list[dict]) -> list:
        """Reconstruct AgentSignalSet objects from DB rows."""
        from investmentology.models.signal import (
            AgentSignalSet,
            Signal,
            SignalSet,
            SignalTag,
        )

        results = []
        for row in signal_rows:
            signals_data = row["signals"]
            if isinstance(signals_data, str):
                signals_data = json.loads(signals_data)

            signal_list = []
            for s in signals_data.get("signals", []):
                try:
                    tag = SignalTag(s["tag"])
                    signal_list.append(Signal(
                        tag=tag,
                        strength=s.get("strength", "moderate"),
                        detail=s.get("detail", ""),
                    ))
                except (ValueError, KeyError):
                    continue

            target_price = signals_data.get("target_price")
            results.append(AgentSignalSet(
                agent_name=row["agent_name"],
                model=row["model"],
                signals=SignalSet(signals=signal_list),
                confidence=Decimal(str(row["confidence"])),
                reasoning=row["reasoning"] or "",
                target_price=(
                    Decimal(str(target_price)) if target_price else None
                ),
            ))
        return results

    def _build_request(self, ticker: str) -> AnalysisRequest:
        """Build an AnalysisRequest from cached pipeline data or DB fallback."""
        cycle_id = self._current_cycle_id

        # 1. Load fundamentals from pipeline cache
        raw_fundamentals = None
        if cycle_id:
            raw_fundamentals = state.get_data_cache(
                self.db, cycle_id, ticker, "fundamentals",
            )

        # Fallback: load from fundamentals_cache DB table
        if not raw_fundamentals:
            try:
                from investmentology.registry.queries import Registry
                registry = Registry(self.db)
                snap = registry.get_latest_fundamentals(ticker)
                if snap:
                    raw_fundamentals = self._snapshot_to_dict(snap)
            except Exception:
                logger.debug("No DB fundamentals for %s", ticker)

        if not raw_fundamentals:
            logger.warning("No fundamentals for %s, using minimal request", ticker)
            return AnalysisRequest(
                ticker=ticker,
                fundamentals=self._empty_snapshot(ticker),
                sector="Unknown",
                industry="Unknown",
            )

        # 2. Build FundamentalsSnapshot
        fundamentals = self._dict_to_snapshot(ticker, raw_fundamentals)

        # 3. Technical indicators from cache
        tech = None
        if cycle_id:
            tech = state.get_data_cache(
                self.db, cycle_id, ticker, "technical_indicators",
            )

        # 4. Portfolio context
        portfolio_context = self._get_portfolio_context(ticker)

        # 5. Previous verdict
        previous_verdict = None
        try:
            from investmentology.registry.queries import Registry
            registry = Registry(self.db)
            prev = registry.get_latest_verdict(ticker)
            if prev:
                previous_verdict = {
                    "verdict": prev.get("verdict") if isinstance(prev, dict) else getattr(prev, "verdict", None),
                    "confidence": float(prev.get("confidence", 0) if isinstance(prev, dict) else getattr(prev, "confidence", 0)),
                }
        except Exception:
            pass

        # 6. Quant gate context
        qg_rank = None
        piotroski = None
        altman_z = None
        try:
            qg_rows = self.db.execute(
                "SELECT combined_rank, piotroski_score, altman_z_score "
                "FROM invest.quant_gate_results "
                "WHERE ticker = %s ORDER BY id DESC LIMIT 1",
                (ticker,),
            )
            if qg_rows:
                qg_rank = qg_rows[0].get("combined_rank")
                piotroski = qg_rows[0].get("piotroski_score")
                az = qg_rows[0].get("altman_z_score")
                altman_z = Decimal(str(az)) if az is not None else None
        except Exception:
            pass

        return AnalysisRequest(
            ticker=ticker,
            fundamentals=fundamentals,
            sector=raw_fundamentals.get("sector", "Unknown"),
            industry=raw_fundamentals.get("industry", "Unknown"),
            technical_indicators=tech,
            portfolio_context=portfolio_context,
            previous_verdict=previous_verdict,
            quant_gate_rank=qg_rank,
            piotroski_score=piotroski,
            altman_z_score=altman_z,
        )

    def _get_analysis_tickers(self) -> list[str]:
        """Get tickers that need analysis.

        Sources: watchlist, quant gate candidates, held positions.
        Excludes: blocked tickers (reentry gate).
        """
        blocked = get_blocked_tickers(self.db)
        candidates: set[str] = set()

        # 1. Watchlist tickers in analysable states
        try:
            wl_rows = self.db.execute(
                "SELECT ticker FROM invest.watchlist "
                "WHERE state = ANY(%s)",
                (_ANALYSABLE_STATES,),
            )
            for r in wl_rows:
                candidates.add(r["ticker"])
        except Exception:
            logger.debug("Watchlist query failed", exc_info=True)

        # 2. Quant gate candidates (latest run)
        try:
            qg_rows = self.db.execute(
                "SELECT DISTINCT r.ticker FROM invest.quant_gate_results r "
                "WHERE r.run_id = ("
                "  SELECT id FROM invest.quant_gate_runs "
                "  ORDER BY id DESC LIMIT 1"
                ") AND r.combined_rank <= 100",
            )
            for r in qg_rows:
                candidates.add(r["ticker"])
        except Exception:
            logger.debug("Quant gate query failed", exc_info=True)

        # 3. Open positions
        try:
            pos_rows = self.db.execute(
                "SELECT ticker FROM invest.portfolio_positions "
                "WHERE is_closed = FALSE",
            )
            for r in pos_rows:
                candidates.add(r["ticker"])
        except Exception:
            logger.debug("Positions query failed", exc_info=True)

        result = sorted(t for t in candidates if t not in blocked)
        if result:
            logger.info(
                "Analysis tickers: %d candidates (%d blocked)",
                len(result), len(candidates) - len(result),
            )
        return result

    def _get_portfolio_context(self, ticker: str) -> dict | None:
        """Get portfolio context for a ticker if it's a held position."""
        try:
            rows = self.db.execute(
                "SELECT shares, avg_cost, entry_date, entry_thesis, "
                "thesis_type, thesis_health, current_price, "
                "highest_price_since_entry "
                "FROM invest.portfolio_positions "
                "WHERE ticker = %s AND is_closed = FALSE "
                "ORDER BY entry_date DESC LIMIT 1",
                (ticker,),
            )
            if rows:
                r = rows[0]
                return {
                    "shares": float(r["shares"]) if r["shares"] else None,
                    "avg_cost": float(r["avg_cost"]) if r["avg_cost"] else None,
                    "entry_date": str(r["entry_date"]) if r["entry_date"] else None,
                    "entry_thesis": r.get("entry_thesis"),
                    "thesis_type": r.get("thesis_type"),
                    "thesis_health": r.get("thesis_health"),
                    "current_price": float(r["current_price"]) if r.get("current_price") else None,
                    "highest_price": float(r["highest_price_since_entry"]) if r.get("highest_price_since_entry") else None,
                }
        except Exception:
            pass
        return None

    @staticmethod
    def _dict_to_snapshot(ticker: str, raw: dict):
        """Convert a raw yfinance/cache dict to a FundamentalsSnapshot."""
        from datetime import datetime as dt

        from investmentology.models.stock import FundamentalsSnapshot

        def _dec(v) -> Decimal:
            if v is None:
                return Decimal(0)
            return Decimal(str(v))

        fetched = raw.get("fetched_at")
        if isinstance(fetched, str):
            try:
                fetched = dt.fromisoformat(fetched)
            except (ValueError, TypeError):
                fetched = dt.now()
        elif fetched is None:
            fetched = dt.now()

        return FundamentalsSnapshot(
            ticker=ticker,
            fetched_at=fetched,
            operating_income=_dec(raw.get("operating_income")),
            market_cap=_dec(raw.get("market_cap")),
            total_debt=_dec(raw.get("total_debt")),
            cash=_dec(raw.get("cash")),
            current_assets=_dec(raw.get("current_assets")),
            current_liabilities=_dec(raw.get("current_liabilities")),
            net_ppe=_dec(raw.get("net_ppe") or raw.get("net_tangible_assets")),
            revenue=_dec(raw.get("revenue")),
            net_income=_dec(raw.get("net_income")),
            total_assets=_dec(raw.get("total_assets")),
            total_liabilities=_dec(raw.get("total_liabilities")),
            shares_outstanding=int(raw.get("shares_outstanding") or 0),
            price=_dec(raw.get("price")),
        )

    @staticmethod
    def _snapshot_to_dict(snap) -> dict:
        """Convert a FundamentalsSnapshot back to a dict."""
        return {
            "ticker": snap.ticker,
            "fetched_at": str(snap.fetched_at),
            "operating_income": float(snap.operating_income),
            "market_cap": float(snap.market_cap),
            "total_debt": float(snap.total_debt),
            "cash": float(snap.cash),
            "current_assets": float(snap.current_assets),
            "current_liabilities": float(snap.current_liabilities),
            "net_ppe": float(snap.net_ppe),
            "revenue": float(snap.revenue),
            "net_income": float(snap.net_income),
            "total_assets": float(snap.total_assets),
            "total_liabilities": float(snap.total_liabilities),
            "shares_outstanding": snap.shares_outstanding,
            "price": float(snap.price),
        }

    @staticmethod
    def _empty_snapshot(ticker: str):
        """Create a zero-filled FundamentalsSnapshot."""
        from datetime import datetime as dt

        from investmentology.models.stock import FundamentalsSnapshot
        return FundamentalsSnapshot(
            ticker=ticker,
            fetched_at=dt.now(),
            operating_income=Decimal(0),
            market_cap=Decimal(0),
            total_debt=Decimal(0),
            cash=Decimal(0),
            current_assets=Decimal(0),
            current_liabilities=Decimal(0),
            net_ppe=Decimal(0),
            revenue=Decimal(0),
            net_income=Decimal(0),
            total_assets=Decimal(0),
            total_liabilities=Decimal(0),
            shares_outstanding=0,
            price=Decimal(0),
        )
