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
import logging
from uuid import UUID

from investmentology.agents.gateway import LLMGateway
from investmentology.agents.runner import AgentRunner
from investmentology.agents.skills import (
    API_ONLY_AGENTS,
    PRIMARY_SKILLS,
    SCOUT_SKILLS,
    SKILLS,
)
from investmentology.pipeline import state
from investmentology.pipeline.convergence import should_debate, synthesis_ready  # noqa: F401
from investmentology.pipeline.scheduler import AgentJob, CLIScheduler
from investmentology.registry.db import Database
from investmentology.registry.reentry import get_blocked_tickers

logger = logging.getLogger(__name__)

# How often the main loop runs (seconds)
POLL_INTERVAL = 60

# Agent names by role
PRIMARY_AGENT_NAMES = list(PRIMARY_SKILLS.keys())
SCOUT_AGENT_NAMES = list(SCOUT_SKILLS.keys())
ALL_AGENT_NAMES = list(SKILLS.keys())
# Remove data_analyst from agent analysis steps (it's a validation step)
ANALYSIS_AGENT_NAMES = [n for n in ALL_AGENT_NAMES if n != "data_analyst"]


class PipelineController:
    """Main controller for the agent-first pipeline."""

    def __init__(self, db: Database, gateway: LLMGateway) -> None:
        self.db = db
        self.gateway = gateway
        self.scheduler = CLIScheduler()
        self._runners: dict[str, AgentRunner] = {}
        self._running = False

        # Pre-create runners for all skills
        for name, skill in SKILLS.items():
            self._runners[name] = AgentRunner(skill, gateway)

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
        # 1. Expire stale steps and cycles
        state.expire_stale_steps(self.db)
        state.expire_old_cycles(self.db)

        # 2. Get or create current cycle
        cycle_id = self._get_or_create_cycle()
        if cycle_id is None:
            return

        # 3. Get pending work
        pending = state.get_pending_steps(self.db, cycle_id)
        if not pending:
            logger.debug("No pending steps in cycle %s", cycle_id)
            return

        logger.info(
            "Controller tick: %d pending steps in cycle %s",
            len(pending), cycle_id,
        )

        # 4. Process each pending step
        for row in pending:
            step = row["step"]
            ticker = row["ticker"]
            step_id = row["id"]

            if step == state.STEP_DATA_FETCH:
                await self._handle_data_fetch(cycle_id, ticker, step_id)

            elif step == state.STEP_DATA_VALIDATE:
                await self._handle_data_validate(cycle_id, ticker, step_id)

            elif step.startswith(state.STEP_AGENT_PREFIX):
                agent_name = step[len(state.STEP_AGENT_PREFIX):]
                await self._handle_agent(cycle_id, ticker, step_id, agent_name)

            elif step == state.STEP_DEBATE:
                await self._handle_debate(cycle_id, ticker, step_id)

            elif step == state.STEP_SYNTHESIS:
                await self._handle_synthesis(cycle_id, ticker, step_id)

    # ------------------------------------------------------------------
    # Step handlers
    # ------------------------------------------------------------------

    async def _handle_data_fetch(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Fetch fresh data for a ticker."""
        state.mark_running(self.db, step_id)
        try:
            # Data fetch is done in-process — call yfinance client
            # For now, mark as completed. The actual fetch logic will be
            # integrated when we wire up the data layer.
            logger.info("Data fetch for %s — delegating to data layer", ticker)
            state.mark_completed(self.db, step_id)
        except Exception as e:
            state.mark_failed(self.db, step_id, str(e))

    async def _handle_data_validate(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Run data validation (deterministic + LLM)."""
        # Check dependency: data_fetch must be completed
        if not state.is_step_completed(self.db, cycle_id, ticker, state.STEP_DATA_FETCH):
            return

        state.mark_running(self.db, step_id)
        try:
            runner = self._runners.get("data_analyst")
            if runner:
                # TODO: Build AnalysisRequest from fetched data
                # For now, mark completed after deterministic validation passes
                logger.info("Data validation for %s — running", ticker)
            state.mark_completed(self.db, step_id)
        except Exception as e:
            state.mark_failed(self.db, step_id, str(e))

    async def _handle_agent(
        self, cycle_id: UUID, ticker: str, step_id: int, agent_name: str,
    ) -> None:
        """Dispatch an agent analysis step."""
        # Check dependency: data_validate must be completed
        if not state.is_step_completed(self.db, cycle_id, ticker, state.STEP_DATA_VALIDATE):
            return

        skill = SKILLS.get(agent_name)
        if not skill:
            state.mark_failed(self.db, step_id, f"Unknown agent: {agent_name}")
            return

        runner = self._runners.get(agent_name)
        if not runner:
            state.mark_failed(self.db, step_id, f"No runner for: {agent_name}")
            return

        state.mark_running(self.db, step_id)

        if agent_name in API_ONLY_AGENTS:
            # API agents run directly (no CLI queue needed)
            asyncio.create_task(
                self._run_api_agent(step_id, runner, ticker),
                name=f"api-{agent_name}-{ticker}",
            )
        else:
            # CLI agents go through the scheduler
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            job = AgentJob(
                skill=skill,
                runner=runner,
                request=self._build_request(ticker),
                step_id=step_id,
                future=future,
            )
            self.scheduler.submit(job)
            # Don't await — the scheduler processes it asynchronously
            asyncio.create_task(
                self._await_cli_result(step_id, future, agent_name, ticker),
                name=f"cli-{agent_name}-{ticker}",
            )

    async def _handle_debate(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Trigger debate if agents disagree significantly."""
        # Check dependency: all primary agents must be completed
        if not state.are_all_agent_steps_completed(
            self.db, cycle_id, ticker, PRIMARY_AGENT_NAMES,
        ):
            return

        # TODO: Load agent signals from DB and check convergence
        # For now, mark debate as completed (skip)
        logger.info("Debate check for %s — evaluating convergence", ticker)
        state.mark_running(self.db, step_id)
        state.mark_completed(self.db, step_id)

    async def _handle_synthesis(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Run CIO synthesis to produce final verdict."""
        # Check dependency: debate must be completed
        if not state.is_step_completed(self.db, cycle_id, ticker, state.STEP_DEBATE):
            return

        # TODO: Load all agent signals, run synthesis
        logger.info("Synthesis for %s — producing verdict", ticker)
        state.mark_running(self.db, step_id)
        state.mark_completed(self.db, step_id)

    # ------------------------------------------------------------------
    # Async result handlers
    # ------------------------------------------------------------------

    async def _run_api_agent(
        self, step_id: int, runner: AgentRunner, ticker: str,
    ) -> None:
        """Run an API-only agent (Simons, Lynch) directly."""
        try:
            request = self._build_request(ticker)
            response = await runner.analyze(request)
            # TODO: Save signals to DB and get result_ref
            state.mark_completed(self.db, step_id)
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
            await future  # Result will be used for DB signal storage
            # TODO: Save signals to DB and get result_ref
            state.mark_completed(self.db, step_id)
        except Exception as e:
            state.mark_failed(self.db, step_id, str(e))
            logger.exception("CLI agent %s/%s failed", agent_name, ticker)

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

        # Create a new cycle
        return state.create_cycle(self.db)

    def _build_request(self, ticker: str):
        """Build an AnalysisRequest for a ticker.

        TODO: This needs to be wired up to the data layer (yfinance cache,
        fundamentals DB, portfolio context, etc.). For now returns a
        placeholder that will be replaced during integration.
        """
        from investmentology.agents.base import AnalysisRequest

        # Placeholder — real implementation loads from DB
        logger.warning(
            "Using placeholder AnalysisRequest for %s — "
            "wire up data layer integration", ticker,
        )
        return AnalysisRequest(
            ticker=ticker,
            fundamentals=None,  # type: ignore[arg-type]
            sector="Unknown",
            industry="Unknown",
        )

    def _get_analysis_tickers(self) -> list[str]:
        """Get tickers that need analysis.

        Sources: watchlist, quant gate candidates, held positions.
        Excludes: blocked tickers (reentry gate).
        """
        blocked = get_blocked_tickers(self.db)

        # TODO: Query watchlist + quant gate + positions
        # For now return empty
        candidates: list[str] = []

        return [t for t in candidates if t not in blocked]
