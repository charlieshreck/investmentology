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
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import time as _time

from investmentology.agents.base import AnalysisRequest, AnalysisResponse
from investmentology.agents.gateway import LLMGateway
from investmentology.agents.runner import AgentRunner
from investmentology.agents.skills import (
    API_ONLY_AGENTS,
    PRIMARY_SKILLS,
    SCOUT_SKILLS,
    SCREENER_SKILLS,
    SKILLS,
    build_sector_specialist,
)
from investmentology.pipeline import state
from investmentology.pipeline.convergence import should_debate, synthesis_ready
from investmentology.pipeline.pre_filter import deterministic_pre_filter
from investmentology.pipeline.scheduler import AgentJob, CLIScheduler
from investmentology.pipeline import freshness
from investmentology.pipeline.selection import select_tickers, get_portfolio_tickers
from investmentology.pipeline.task_registry import TaskRegistry
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
# Analysis agents = all except data_analyst, screeners, and conditional agents
_CONDITIONAL_AGENTS = {"income_analyst"}
ANALYSIS_AGENT_NAMES = [
    n for n in ALL_AGENT_NAMES
    if n != "data_analyst" and n not in SCREENER_AGENT_NAMES
    and n not in _CONDITIONAL_AGENTS
]

# Sectors that get a specialist agent
_SECTOR_SPECIALIST_SECTORS = {
    "Healthcare", "Financial Services", "Energy", "Real Estate", "Technology",
}

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
        self._tick_count = 0
        self._portfolio_tickers: set[str] = set()

        # YFinance client — synchronous, used in run_in_executor
        from investmentology.data.yfinance_client import YFinanceClient
        self._yf_client = YFinanceClient(cache_ttl_hours=24)

        # Data enricher — FRED, Finnhub, EDGAR providers
        from investmentology.data.enricher import build_enricher
        from investmentology.config import load_config
        self._enricher = build_enricher(load_config())

        # ReAct tool catalog for tool-use-capable agents
        tool_catalog = self._create_tool_catalog()

        # Pre-create runners for all skills
        for name, skill in SKILLS.items():
            if skill.react_capable and tool_catalog is not None:
                from investmentology.agents.react.runner import ReActRunner
                self._runners[name] = ReActRunner(skill, gateway, tool_catalog)
                logger.info("ReAct runner created for %s", name)
            else:
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

        # Non-blocking dispatch: track in-flight debate/adversarial/synthesis
        self._task_registry = TaskRegistry(max_tasks=50)
        self._inflight_steps: set[int] = set()
        self._llm_task_sem = asyncio.Semaphore(3)  # max 3 concurrent LLM tasks

        # Cache AgentCalibrator per cycle (fit once, reuse for all tickers)
        self._calibrator_cycle_id: UUID | None = None
        self._cached_calibrator = None

    def _create_tool_catalog(self):
        """Create the ReAct tool catalog with available data sources."""
        try:
            from investmentology.agents.react.tools import ToolCatalog

            # Optional: Finnhub provider (needs API key)
            finnhub = None
            try:
                import os
                finnhub_key = os.environ.get("FINNHUB_API_KEY")
                if finnhub_key:
                    from investmentology.data.finnhub_provider import FinnhubProvider
                    finnhub = FinnhubProvider(finnhub_key)
            except Exception:
                logger.debug("Finnhub provider not available for ReAct tools")

            # Optional: FRED provider (needs API key)
            fred = None
            try:
                import os
                fred_key = os.environ.get("FRED_API_KEY")
                if fred_key:
                    from investmentology.data.fred_provider import FredProvider
                    fred = FredProvider(fred_key)
            except Exception:
                logger.debug("FRED provider not available for ReAct tools")

            catalog = ToolCatalog(
                yf_client=self._yf_client,
                finnhub=finnhub,
                fred=fred,
            )
            logger.info(
                "ReAct tool catalog created with %d tools",
                len(catalog.openai_schema()),
            )
            return catalog
        except Exception:
            logger.warning("Failed to create ReAct tool catalog", exc_info=True)
            return None

    def _get_agents_for_ticker(
        self, ticker: str, cycle_id: UUID | None = None,
    ) -> list[str]:
        """Compute agent list for a ticker, adding conditional agents as needed.

        Always includes ANALYSIS_AGENT_NAMES. Conditionally adds:
        - income_analyst: for dividend-paying stocks or PERMANENT positions
        - sector_specialist: for stocks in specialist-covered sectors

        Uses cached fundamentals from the pipeline data cache (already fetched
        during data_fetch step) to avoid blocking the event loop with sync
        yfinance calls.
        """
        agents = list(ANALYSIS_AGENT_NAMES)

        # Check if income_analyst should be activated
        try:
            # Prefer cached fundamentals (non-blocking) over sync yfinance
            fundamentals = None
            if cycle_id:
                fundamentals = state.get_data_cache(
                    self.db, cycle_id, ticker, "fundamentals",
                )
            if fundamentals is None:
                fundamentals = self._yf_client.get_fundamentals(ticker)
            dividend_yield = fundamentals.get("dividend_yield", 0) if isinstance(fundamentals, dict) else (getattr(fundamentals, "dividend_yield", 0) or 0)
            dividend_yield = dividend_yield or 0

            # Check position type from DB
            position_type = None
            try:
                rows = self.db.execute(
                    "SELECT position_type FROM invest.portfolio_positions "
                    "WHERE ticker = %s AND is_closed = false LIMIT 1",
                    (ticker,),
                )
                if rows:
                    position_type = rows[0].get("position_type")
            except Exception:
                pass

            if dividend_yield > 1.5 or position_type == "permanent":
                agents.append("income_analyst")

            # Check if sector specialist should be activated
            sector = fundamentals.get("sector", "") if isinstance(fundamentals, dict) else (getattr(fundamentals, "sector", "") or "")
            if sector in _SECTOR_SPECIALIST_SECTORS:
                spec_name = f"sector_specialist_{sector.lower().replace(' ', '_')}"
                if spec_name not in self._runners:
                    specialist_skill = build_sector_specialist(sector)
                    if specialist_skill:
                        self._runners[spec_name] = AgentRunner(
                            specialist_skill, self.gateway,
                        )
                        logger.info("Created sector specialist runner for %s", sector)
                if spec_name in self._runners:
                    agents.append(spec_name)

        except Exception:
            logger.debug("Could not evaluate conditional agents for %s", ticker)

        return agents

    async def start(self) -> None:
        """Start the controller and its workers."""
        self._running = True

        # Startup recovery: reset steps stuck in 'running' from a prior crash
        recovered = state.reset_stale_running_steps(self.db, cutoff_minutes=2)
        if recovered:
            logger.info("Startup recovery: reset %d orphaned running steps", recovered)

        await self.gateway.start()
        # Start parallel queue workers for each CLI agent.
        # 2 workers per agent = 2 concurrent tickers per agent.
        cli_agent_names = [
            name for name, skill in SKILLS.items()
            if skill.cli_screen and name not in API_ONLY_AGENTS
        ]
        await self.scheduler.start(cli_agent_names, workers_per_agent=2)
        logger.info("Pipeline controller started")

    async def stop(self) -> None:
        """Stop the controller gracefully."""
        self._running = False
        cancelled = self._task_registry.cancel_all()
        if cancelled:
            logger.info("Cancelled %d in-flight tasks during shutdown", cancelled)
        self._inflight_steps.clear()
        await self.scheduler.stop()
        await self.gateway.close()
        logger.info("Pipeline controller stopped")

    @property
    def _is_overnight(self) -> bool:
        """True during overnight processing window (00:00-06:00 UTC)."""
        return datetime.now(timezone.utc).hour < 6

    async def run_loop(self) -> None:
        """Main event loop — polls for work every POLL_INTERVAL seconds.

        Launches the reaper coroutine alongside the tick loop so orphan
        detection and timeout enforcement run independently.
        """
        from investmentology.api.metrics import pipeline_cycle_duration, pipeline_cycles_total

        # Launch reaper as a sibling coroutine
        reaper_task = asyncio.create_task(
            self._reaper_loop(), name="pipeline-reaper",
        )

        try:
            while self._running:
                start = _time.monotonic()
                status = "success"
                try:
                    await self._tick()
                except Exception:
                    status = "error"
                    logger.exception("Controller tick failed")
                finally:
                    pipeline_cycle_duration.labels(status=status).observe(
                        _time.monotonic() - start,
                    )
                    pipeline_cycles_total.labels(status=status).inc()
                await asyncio.sleep(POLL_INTERVAL)
        finally:
            reaper_task.cancel()
            try:
                await reaper_task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------
    # Single tick — one pass through the pipeline state
    # ------------------------------------------------------------------

    async def _tick(self) -> None:
        """Process one iteration of the controller loop."""
        # 1. Expire stale steps, recover stuck running steps, expire old cycles
        state.expire_stale_steps(self.db)
        state.reset_stale_running_steps(self.db)
        state.expire_old_cycles(self.db)

        # 1b. Cascade-fail zombie pending steps for tickers with upstream failures
        if self._current_cycle_id:
            state.cascade_fail_blocked_tickers(self.db, self._current_cycle_id)

        # 2. Get or create current cycle
        cycle_id = self._get_or_create_cycle()
        if cycle_id is None:
            return
        self._current_cycle_id = cycle_id

        # 3. Refresh portfolio ticker set
        self._portfolio_tickers = set(get_portfolio_tickers(self.db))

        # 3b. Macro regime pre-classification (once per cycle)
        await self._ensure_macro_regime(cycle_id)

        # 3c. Backtest calibration (once per cycle — loads latest IC data)
        self._ensure_backtest_calibration(cycle_id)

        # 3d. Clear expired reentry blocks (every ~60 min)
        if self._tick_count % 60 == 0:
            try:
                from investmentology.registry.reentry import check_and_clear_blocks
                fund_map = self._get_cached_fundamentals_map()
                if fund_map:
                    cleared = check_and_clear_blocks(self.db, fund_map)
                    if cleared:
                        logger.info("Cleared %d reentry blocks", cleared)
            except Exception:
                logger.debug("Reentry block clearing failed", exc_info=True)

        # 4. Populate screening steps for tickers needing analysis
        tickers = self._get_analysis_tickers()
        for ticker in tickers:
            existing = state.get_ticker_progress(self.db, cycle_id, ticker)
            if not existing:
                state.create_screening_steps(
                    self.db, cycle_id, ticker, SCREENER_AGENT_NAMES,
                )

        # 5. Get pending work
        pending = state.get_pending_steps(self.db, cycle_id)
        if not pending:
            # Check if cycle is complete
            self._check_cycle_completion(cycle_id)
            # Staleness sweep even when no pending work
            self._tick_count += 1
            if self._tick_count % 10 == 0:
                await self._staleness_sweep(cycle_id)
            return

        # Sort pending: portfolio tickers first, then watchlist
        pending.sort(key=lambda r: (0 if r["ticker"] in self._portfolio_tickers else 1, r["ticker"], r["step"]))

        logger.info(
            "Controller tick: %d pending steps in cycle %s",
            len(pending), cycle_id,
        )

        # 5b. Bulk-process data_fetch steps in parallel
        pending = await self._bulk_data_fetch(cycle_id, pending)
        if not pending:
            self._check_cycle_completion(cycle_id)
            return

        # 6. Process each pending step.
        # Each CLI agent has its own queue worker, so all agents run in
        # parallel. No dispatch limit needed — workers self-serialize.
        for row in pending:
            step = row["step"]
            ticker = row["ticker"]
            step_id = row["id"]

            if step == state.STEP_DATA_FETCH:
                # Leftovers from non-bulk path (should be rare)
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

            elif step == state.STEP_RESEARCH:
                await self._handle_research(cycle_id, ticker, step_id)

            elif step.startswith(state.STEP_AGENT_PREFIX):
                agent_name = step[len(state.STEP_AGENT_PREFIX):]
                await self._handle_agent(cycle_id, ticker, step_id, agent_name)

            elif step == state.STEP_DEBATE:
                if step_id not in self._inflight_steps:
                    self._inflight_steps.add(step_id)
                    task = asyncio.create_task(
                        self._run_step_async(
                            self._handle_debate, cycle_id, ticker, step_id,
                            timeout=600,
                        ),
                        name=f"debate-{ticker}",
                    )
                    self._task_registry.track(
                        step_id, task, ticker, "debate", timeout=600,
                    )

            elif step == state.STEP_ADVERSARIAL:
                if step_id not in self._inflight_steps:
                    self._inflight_steps.add(step_id)
                    task = asyncio.create_task(
                        self._run_step_async(
                            self._handle_adversarial, cycle_id, ticker, step_id,
                            timeout=300,
                        ),
                        name=f"adversarial-{ticker}",
                    )
                    self._task_registry.track(
                        step_id, task, ticker, "adversarial", timeout=300,
                    )

            elif step == state.STEP_SYNTHESIS:
                if step_id not in self._inflight_steps:
                    self._inflight_steps.add(step_id)
                    task = asyncio.create_task(
                        self._run_step_async(
                            self._handle_synthesis, cycle_id, ticker, step_id,
                            timeout=660,
                        ),
                        name=f"synthesis-{ticker}",
                    )
                    self._task_registry.track(
                        step_id, task, ticker, "synthesis", timeout=660,
                    )

        # 7. Check if cycle is complete
        self._check_cycle_completion(cycle_id)

        # 8. Staleness sweep every 10th tick (~10 minutes)
        self._tick_count += 1
        if self._tick_count % 10 == 0:
            await self._staleness_sweep(cycle_id)

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    async def _bulk_data_fetch(
        self, cycle_id: UUID, pending: list[dict],
    ) -> list[dict]:
        """Process all pending data_fetch steps in parallel.

        Returns the remaining pending steps (non-data_fetch) for normal processing.
        """
        fetch_steps = [r for r in pending if r["step"] == state.STEP_DATA_FETCH]
        other_steps = [r for r in pending if r["step"] != state.STEP_DATA_FETCH]

        if not fetch_steps:
            return pending

        logger.info(
            "Bulk data fetch: starting %d tickers in parallel",
            len(fetch_steps),
        )

        # Mark all as running
        for row in fetch_steps:
            state.mark_running(self.db, row["id"])

        loop = asyncio.get_event_loop()

        async def _fetch_one(ticker: str, step_id: int) -> None:
            """Fetch data for a single ticker (runs in executor)."""
            try:
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

                # Cache fundamentals
                state.store_data_cache(
                    self.db, cycle_id, ticker, "fundamentals", fundamentals,
                )

                # Technical indicators
                try:
                    from investmentology.data.technical_indicators import (
                        compute_technical_indicators,
                    )
                    tech = await loop.run_in_executor(
                        None, compute_technical_indicators, ticker,
                    )
                    if tech:
                        state.store_data_cache(
                            self.db, cycle_id, ticker,
                            "technical_indicators", tech,
                        )
                except Exception:
                    logger.debug(
                        "Technical indicators unavailable for %s", ticker,
                    )

                # Enrichment
                if self._enricher:
                    await loop.run_in_executor(
                        None, self._run_enrichment, cycle_id, ticker,
                    )

                state.mark_completed(self.db, step_id)
            except Exception as e:
                state.mark_failed(self.db, step_id, str(e))

        # Limit concurrency to avoid yfinance rate limits
        sem = asyncio.Semaphore(5)

        async def _throttled_fetch(ticker: str, step_id: int) -> None:
            async with sem:
                await _fetch_one(ticker, step_id)

        tasks = [
            _throttled_fetch(row["ticker"], row["id"])
            for row in fetch_steps
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Bulk data fetch: %d tickers processed", len(fetch_steps))
        return other_steps

    def _get_cached_fundamentals_map(self) -> dict[str, dict]:
        """Get cached fundamentals for all tickers with active reentry blocks."""
        try:
            rows = self.db.execute(
                "SELECT DISTINCT ON (rb.ticker) rb.ticker, pdc.data "
                "FROM invest.reentry_blocks rb "
                "LEFT JOIN invest.pipeline_data_cache pdc "
                "  ON pdc.ticker = rb.ticker AND pdc.data_key = 'fundamentals' "
                "WHERE rb.is_cleared = FALSE AND pdc.data IS NOT NULL "
                "ORDER BY rb.ticker, pdc.created_at DESC",
            )
            return {r["ticker"]: r["data"] for r in rows}
        except Exception:
            logger.debug("Failed to build fundamentals map for reentry blocks")
            return {}

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

            # ── Enrichment: FRED, Finnhub, EDGAR ──────────────────────
            # Each provider is called individually so partial failures
            # don't block the rest. Results cached per data key.
            enrichment_ok = 0
            enrichment_fail = 0

            if self._enricher:
                enrichment_ok, enrichment_fail = await loop.run_in_executor(
                    None, self._run_enrichment, cycle_id, ticker,
                )

            state.mark_completed(self.db, step_id)
            logger.info(
                "Data fetch for %s completed (enrichment: %d ok, %d failed)",
                ticker, enrichment_ok, enrichment_fail,
            )
        except Exception as e:
            state.mark_failed(self.db, step_id, str(e))

    def _run_enrichment(self, cycle_id: UUID, ticker: str) -> tuple[int, int]:
        """Run all enrichment providers for a ticker, caching results individually.

        Uses a two-tier approach: primary providers (Finnhub/FRED/EDGAR) first,
        then SearXNG web search fallback for any keys that returned None.

        Returns (success_count, failure_count). Each provider failure is logged
        with the specific data key so silent data gaps become visible.
        """
        ok = 0
        fail = 0
        enricher = self._enricher
        if not enricher:
            return ok, fail

        # Provider → cache_key mapping
        # Each is called independently so one failure doesn't block others
        providers: list[tuple[str, callable]] = []

        if enricher._fred:
            providers.append(("macro_context", lambda: enricher._fred.get_macro_context()))

        if enricher._finnhub:
            providers.extend([
                ("news_context", lambda t=ticker: enricher._finnhub.get_news(t)),
                ("earnings_context", lambda t=ticker: enricher._finnhub.get_earnings(t)),
                ("insider_context", lambda t=ticker: enricher._finnhub.get_insider_transactions(t)),
                ("social_sentiment", lambda t=ticker: enricher._finnhub.get_social_sentiment(t)),
                ("analyst_ratings", lambda t=ticker: enricher._finnhub.get_analyst_ratings(t)),
                ("short_interest", lambda t=ticker: enricher._finnhub.get_short_interest(t)),
            ])

        if enricher._edgar:
            providers.extend([
                ("filing_context", lambda t=ticker: enricher._edgar.get_filing_text(t)),
                ("institutional_context", lambda t=ticker: self._fetch_institutional(t)),
            ])

        # Track which keys got no data from primary providers
        missing_keys: list[str] = []

        for cache_key, fetcher in providers:
            try:
                result = fetcher()
                if result is not None:
                    result = self._stamp_result(result)
                    state.store_data_cache(
                        self.db, cycle_id, ticker, cache_key, result,
                    )
                    ok += 1
                else:
                    missing_keys.append(cache_key)
            except Exception as exc:
                missing_keys.append(cache_key)
                logger.warning(
                    "Primary enrichment %s failed for %s: %s",
                    cache_key, ticker, str(exc)[:200],
                )

        # ── Web search fallbacks for missing keys ───────────────────
        if missing_keys:
            web_ok, web_fail = self._run_web_fallbacks(
                cycle_id, ticker, missing_keys,
            )
            ok += web_ok
            fail += web_fail

        return ok, fail

    def _run_web_fallbacks(
        self, cycle_id: UUID, ticker: str, missing_keys: list[str],
    ) -> tuple[int, int]:
        """Try SearXNG web search for enrichment keys that primary providers missed.

        Returns (success_count, failure_count).
        """
        from investmentology.data.web_search_provider import FallbackProvider

        ok = 0
        fail = 0

        try:
            fb = FallbackProvider()
        except Exception:
            logger.warning("FallbackProvider init failed, skipping fallbacks")
            return 0, len(missing_keys)

        # Map cache_key → fallback method (yfinance first, SearXNG for news/social)
        fallbacks: dict[str, callable] = {
            "news_context": lambda: fb.get_news(ticker),
            "earnings_context": lambda: fb.get_earnings(ticker),
            "insider_context": lambda: fb.get_insider_transactions(ticker),
            "social_sentiment": lambda: fb.get_social_sentiment(ticker),
            "analyst_ratings": lambda: fb.get_analyst_ratings(ticker),
            "short_interest": lambda: fb.get_short_interest(ticker),
            "filing_context": lambda: fb.get_filing_context(ticker),
        }

        for cache_key in missing_keys:
            fetcher = fallbacks.get(cache_key)
            if fetcher is None:
                # No web fallback for this key (e.g. macro_context, institutional_context)
                fail += 1
                logger.warning(
                    "Enrichment %s returned None for %s (no web fallback)",
                    cache_key, ticker,
                )
                continue

            try:
                result = fetcher()
                if result is not None:
                    result = self._stamp_result(result)
                    state.store_data_cache(
                        self.db, cycle_id, ticker, cache_key, result,
                    )
                    ok += 1
                    logger.info(
                        "Web search fallback filled %s for %s", cache_key, ticker,
                    )
                else:
                    fail += 1
                    logger.warning(
                        "Enrichment %s returned None for %s (web fallback also empty)",
                        cache_key, ticker,
                    )
            except Exception as exc:
                fail += 1
                logger.warning(
                    "Web fallback %s failed for %s: %s",
                    cache_key, ticker, str(exc)[:200],
                )

        return ok, fail

    @staticmethod
    def _stamp_result(result: object) -> object:
        """Add fetched_at timestamp and wrap lists in metadata dict."""
        from datetime import datetime, timezone

        if isinstance(result, dict) and "fetched_at" not in result:
            result["fetched_at"] = datetime.now(timezone.utc).isoformat()
        elif isinstance(result, list):
            result = {
                "items": result,
                "count": len(result),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        return result

    def _fetch_institutional(self, ticker: str):
        """Fetch institutional holders with dict unwrapping."""
        result = self._enricher._edgar.get_institutional_holders(ticker)
        if isinstance(result, dict):
            return result.get("holders", [])
        return result or []

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

            # Phase 2: LLM Data Analyst (ALL tickers, hard gate)
            runner = self._runners.get("data_analyst")
            if not runner:
                # Data Analyst not configured — deterministic-only is sufficient
                state.mark_completed(self.db, step_id)
                logger.info("Data validation for %s passed (deterministic only)", ticker)
                return

            try:
                request = self._build_request(ticker)
                response = await runner.analyze(request)
            except Exception:
                # First attempt failed — retry once
                try:
                    response = await runner.analyze(request)
                except Exception:
                    state.mark_failed(
                        self.db, step_id,
                        "Data Analyst unavailable after 2 attempts",
                    )
                    return

            if response and hasattr(response, "signal_set"):
                reasoning = response.signal_set.reasoning or ""
                conf = float(response.signal_set.confidence)

                if "[DATA_REJECTED]" in reasoning:
                    state.mark_failed(
                        self.db, step_id,
                        f"Data Analyst REJECTED: {reasoning[:200]}",
                    )
                    return

                if "[DATA_SUSPICIOUS]" in reasoning and conf < 0.4:
                    state.mark_failed(
                        self.db, step_id,
                        f"Data Analyst SUSPICIOUS (conf={conf:.2f}): {reasoning[:200]}",
                    )
                    return

                # VALIDATED or SUSPICIOUS with decent confidence — proceed
                status_tag = "VALIDATED" if "[DATA_VALIDATED]" in reasoning else "SUSPICIOUS"
                state.store_data_cache(
                    self.db, cycle_id, ticker, "data_analyst_review", {
                        "status": status_tag,
                        "confidence": conf,
                        "summary": reasoning[:500],
                    },
                )
                if status_tag == "SUSPICIOUS":
                    logger.warning(
                        "Data Analyst flagged %s as SUSPICIOUS (conf=%.2f): %s",
                        ticker, conf, reasoning[:200],
                    )

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
        """Ticker passed the gate — enforce data freshness, then create Phase 2 steps.

        If critical data is stale or missing, reset back to data_fetch so
        agents never run against outdated information.
        """
        report = freshness.check_freshness(self.db, str(cycle_id), ticker)
        if not report.is_fresh:
            stale_names = report.stale_key_names
            is_critical = report.has_critical_staleness

            if is_critical:
                # Critical data stale — reset to data_fetch, do NOT proceed
                logger.warning(
                    "Gate PASS for %s BLOCKED — critical data stale: %s. "
                    "Resetting to data_fetch.",
                    ticker, ", ".join(stale_names[:5]),
                )
                state.reset_or_create_step(
                    self.db, cycle_id, ticker, state.STEP_DATA_FETCH,
                )
                # Don't mark gate completed — it will re-run after fresh data
                return

            # Non-critical staleness — attempt synchronous gap-fill before proceeding
            logger.info(
                "Gate PASS for %s with non-critical gaps: %s — attempting gap-fill",
                ticker, ", ".join(stale_names[:5]),
            )
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    self._attempt_gap_fill(cycle_id, ticker, stale_names),
                    name=f"gap-fill-{ticker}",
                )

        agent_names = self._get_agents_for_ticker(ticker, cycle_id)
        state.create_analysis_steps(
            self.db, cycle_id, ticker, agent_names,
        )
        state.mark_completed(self.db, step_id)
        logger.info(
            "Gate PASS for %s — created %d analysis steps (conditional: %s)",
            ticker, len(agent_names),
            [a for a in agent_names if a not in ANALYSIS_AGENT_NAMES] or "none",
        )

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

        # Wait for research step if it exists (may not for legacy cycles)
        research_status = state.get_step_status(
            self.db, cycle_id, ticker, state.STEP_RESEARCH,
        )
        if research_status and research_status["status"] not in ("completed", "failed", "expired"):
            return

        skill = SKILLS.get(agent_name)
        runner = self._runners.get(agent_name)

        # Sector specialists and other dynamic agents may not be in SKILLS
        if not skill and runner:
            skill = runner.skill
        if not skill:
            state.mark_failed(self.db, step_id, f"Unknown agent: {agent_name}")
            return
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

    async def _handle_research(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Gather raw research data and send to Gemini for synthesis."""
        if not state.is_step_completed(
            self.db, cycle_id, ticker, state.STEP_GATE_DECISION,
        ):
            return

        state.mark_running(self.db, step_id)
        try:
            # 1. Gather raw research material
            from investmentology.data.research_gatherer import ResearchGatherer
            gatherer = ResearchGatherer()

            fundamentals = state.get_data_cache(
                self.db, cycle_id, ticker, "fundamentals",
            )
            company_name = (fundamentals or {}).get("name", ticker)

            raw_research = await gatherer.gather(ticker, company_name)
            if not raw_research:
                logger.warning("No research data gathered for %s", ticker)
                state.mark_completed(self.db, step_id)
                return

            # 2. Build research prompt and send to Gemini via HB proxy
            research_prompt = gatherer.build_research_prompt(
                ticker, company_name, raw_research,
            )

            try:
                llm_response = await self.gateway.call(
                    provider="remote-researcher",
                    system_prompt=(
                        "You are a senior equity research analyst preparing a briefing "
                        "for an investment committee. Be specific with dates, numbers, "
                        "and attributions. No filler — every sentence must contain a fact."
                    ),
                    user_prompt=research_prompt,
                    model="gemini-2.5-pro",
                )
                briefing = llm_response.content
            except Exception:
                logger.warning(
                    "Gemini research synthesis failed for %s, using raw summary",
                    ticker, exc_info=True,
                )
                # Fallback: store raw headlines as minimal briefing
                briefing = gatherer.build_fallback_briefing(ticker, raw_research)

            # 3. Cache the research briefing
            state.store_data_cache(
                self.db, cycle_id, ticker, "research_briefing",
                {"briefing": briefing, "raw_sources": len(raw_research.get("articles", []))},
            )

            state.mark_completed(self.db, step_id)
            logger.info(
                "Research for %s completed (%d chars, %d sources)",
                ticker, len(briefing), len(raw_research.get("articles", [])),
            )
        except Exception as e:
            # Research failure should NOT block agents — mark completed anyway
            state.mark_completed(self.db, step_id)
            logger.warning("Research failed for %s, proceeding without: %s", ticker, e)

    # ------------------------------------------------------------------
    # Non-blocking step execution + Reaper
    # ------------------------------------------------------------------

    async def _run_step_async(
        self,
        handler,
        cycle_id: UUID,
        ticker: str,
        step_id: int,
        timeout: float = 660,
    ) -> None:
        """Run a blocking step handler as a tracked background task.

        Wraps debate/adversarial/synthesis handlers with:
        - Concurrency limiting via _llm_task_sem (max 3 concurrent)
        - Automatic cleanup of _inflight_steps and _task_registry
        - Exception catching with DB failure recording
        """
        try:
            async with self._llm_task_sem:
                await handler(cycle_id, ticker, step_id)
        except asyncio.CancelledError:
            logger.warning(
                "Step %d (%s/%s) was cancelled", step_id, handler.__name__, ticker,
            )
            try:
                step_row = state.get_step_by_id(self.db, step_id)
                if step_row and step_row["status"] == "running":
                    state.mark_failed(self.db, step_id, "Cancelled by reaper (timeout)")
            except Exception:
                pass
            raise
        except Exception:
            logger.exception(
                "Async step %d (%s/%s) failed", step_id, handler.__name__, ticker,
            )
            try:
                step_row = state.get_step_by_id(self.db, step_id)
                if step_row and step_row["status"] == "running":
                    state.mark_failed(self.db, step_id, "Uncaught exception in async wrapper")
            except Exception:
                pass
        finally:
            self._inflight_steps.discard(step_id)
            self._task_registry.untrack(step_id)

    async def _reaper_loop(self) -> None:
        """Background coroutine that detects orphans, enforces timeouts,
        and cleans up stale tracking state every 30 seconds.

        Tiers:
        1. TaskRegistry stale-done: task finished but DB not updated
        2. TaskRegistry timeouts: exceeded per-step timeout → cancel + fail
        3. DB orphans: status='running', not tracked, older than 2 min → reset
        4. Clean _cli_queued_steps set (remove entries for completed/failed steps)
        """
        REAPER_INTERVAL = 30
        logger.info("Reaper started (interval=%ds)", REAPER_INTERVAL)

        while self._running:
            try:
                await asyncio.sleep(REAPER_INTERVAL)
                if not self._running:
                    break

                recovered = 0

                # Tier 1: Tasks that finished (success or exception) but
                # the completion callback didn't clean up the registry
                stale_done = self._task_registry.get_stale_done()
                for info in stale_done:
                    step_row = state.get_step_by_id(self.db, info.step_id)
                    if step_row and step_row["status"] == "running":
                        # Task finished but DB still says running → mark failed
                        exc = info.task.exception() if not info.task.cancelled() else None
                        error_msg = f"Orphaned (task done, exception: {exc})" if exc else "Orphaned (task done, no DB update)"
                        state.mark_failed(self.db, info.step_id, error_msg)
                        logger.warning(
                            "Reaper: stale-done step %d (%s/%s) → failed",
                            info.step_id, info.step_name, info.ticker,
                        )
                        recovered += 1
                    self._inflight_steps.discard(info.step_id)
                    self._task_registry.untrack(info.step_id)

                # Tier 2: Tasks running longer than their timeout
                timed_out = self._task_registry.get_timed_out()
                for info in timed_out:
                    age = int(_time.monotonic() - info.started_at)
                    logger.warning(
                        "Reaper: step %d (%s/%s) timed out after %ds → cancelling",
                        info.step_id, info.step_name, info.ticker, age,
                    )
                    info.task.cancel()
                    # mark_failed happens in _run_step_async's CancelledError handler
                    recovered += 1

                # Tier 3: DB orphans — status='running' but not in our tracking
                if self._current_cycle_id:
                    try:
                        running_rows = self.db.execute(
                            "SELECT id, ticker, step, started_at "
                            "FROM invest.pipeline_state "
                            "WHERE cycle_id = %s AND status = 'running' "
                            "AND started_at < NOW() - INTERVAL '2 minutes'",
                            (str(self._current_cycle_id),),
                        )
                        for row in running_rows:
                            sid = row["id"]
                            if (
                                not self._task_registry.is_tracked(sid)
                                and sid not in self._cli_queued_steps
                            ):
                                state.mark_failed(
                                    self.db, sid,
                                    "Reaper: DB orphan (running >2min, not tracked)",
                                )
                                logger.warning(
                                    "Reaper: DB orphan step %d (%s/%s) → failed",
                                    sid, row["step"], row["ticker"],
                                )
                                recovered += 1
                    except Exception:
                        logger.debug("Reaper tier-3 query failed", exc_info=True)

                # Tier 4: Clean _cli_queued_steps — remove entries for steps
                # that are no longer pending/running in the DB
                if self._cli_queued_steps and self._current_cycle_id:
                    try:
                        stale_queued = set()
                        for sid in self._cli_queued_steps:
                            step_row = state.get_step_by_id(self.db, sid)
                            if step_row and step_row["status"] not in ("pending", "running"):
                                stale_queued.add(sid)
                            elif not step_row:
                                stale_queued.add(sid)
                        if stale_queued:
                            self._cli_queued_steps -= stale_queued
                            logger.debug(
                                "Reaper: cleaned %d stale CLI queue entries",
                                len(stale_queued),
                            )
                    except Exception:
                        logger.debug("Reaper tier-4 cleanup failed", exc_info=True)

                # Log summary
                summary = self._task_registry.summary()
                if summary["tracked"] > 0 or recovered > 0:
                    logger.info(
                        "Reaper: tracked=%d running=%d recovered=%d cli_queued=%d",
                        summary["tracked"], summary["running"],
                        recovered, len(self._cli_queued_steps),
                    )

            except asyncio.CancelledError:
                logger.info("Reaper stopped")
                raise
            except Exception:
                logger.exception("Reaper iteration failed")

    async def _handle_debate(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Trigger debate if agents disagree significantly.

        Uses a soft completeness gate: proceeds when enough agents have
        finished (completed or failed) rather than waiting for all.
        """
        statuses = state.count_agent_step_statuses(
            self.db, cycle_id, ticker, PRIMARY_AGENT_NAMES,
        )
        completed = statuses.get("completed", 0)
        failed = statuses.get("failed", 0)
        expired = statuses.get("expired", 0)
        finished = completed + failed + expired
        total = len(PRIMARY_AGENT_NAMES)

        # Soft gate: need 4+ completed, OR all agents finished (completed/failed/expired)
        if not synthesis_ready(completed, total, True, True) and finished < total:
            return

        if failed or expired:
            logger.info(
                "Debate for %s proceeding with %d/%d completed (%d failed, %d expired)",
                ticker, completed, total, failed, expired,
            )

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

    async def _handle_adversarial(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Run Munger adversarial review if warranted.

        Checks if adversarial review triggers (unanimous bullishness,
        dangerous disagreement, or conviction buy patterns). If triggered,
        runs bias check, Kill the Company, and pre-mortem via DeepSeek.
        """
        if not state.is_step_completed(
            self.db, cycle_id, ticker, state.STEP_DEBATE,
        ):
            return

        state.mark_running(self.db, step_id)
        try:
            # Load agent signals
            signal_rows = state.get_agent_signals_for_ticker(
                self.db, cycle_id, ticker,
            )
            if not signal_rows:
                state.mark_completed(self.db, step_id)
                return

            agent_signal_sets = self._reconstruct_signal_sets(signal_rows)
            primary_signals = [
                ss for ss in agent_signal_sets
                if ss.agent_name in PRIMARY_AGENT_NAMES
            ]

            if not primary_signals:
                state.mark_completed(self.db, step_id)
                return

            # Check if adversarial review is warranted
            from investmentology.adversarial.munger import MungerOrchestrator

            munger = MungerOrchestrator(self.gateway)
            if not munger.should_trigger(primary_signals):
                logger.info("Adversarial check for %s: not triggered (no red patterns)", ticker)
                state.mark_completed(self.db, step_id)
                return

            # Build inputs for the review
            fundamentals = state.get_data_cache(
                self.db, cycle_id, ticker, "fundamentals",
            )
            fundamentals_summary = ""
            if fundamentals:
                fundamentals_summary = (
                    f"Market cap: ${fundamentals.get('market_cap', 0):,.0f}, "
                    f"Revenue: ${fundamentals.get('revenue', 0):,.0f}, "
                    f"Net income: ${fundamentals.get('net_income', 0):,.0f}, "
                    f"Debt: ${fundamentals.get('total_debt', 0):,.0f}, "
                    f"Cash: ${fundamentals.get('cash', 0):,.0f}"
                )

            # Combine agent reasoning as the thesis
            thesis_parts = [
                f"{ss.agent_name}: {ss.reasoning[:200]}"
                for ss in primary_signals if ss.reasoning
            ]
            thesis = "\n".join(thesis_parts)

            sector = (fundamentals or {}).get("sector", "")

            # Run the adversarial review
            result = await munger.review(
                ticker=ticker,
                fundamentals_summary=fundamentals_summary,
                thesis=thesis,
                agent_signals=primary_signals,
                sector=sector,
            )

            # Cache the result for synthesis/board
            adversarial_data = {
                "verdict": result.verdict.value,
                "reasoning": result.reasoning,
                "bias_count": len([b for b in result.bias_flags if b.is_flagged]),
                "kill_scenario_count": len(result.kill_scenarios),
                "fatal_scenarios": [
                    {"scenario": s.scenario, "impact": s.impact, "likelihood": s.likelihood}
                    for s in result.kill_scenarios if s.impact == "fatal"
                ],
                "premortem_probability": (
                    result.premortem.probability_estimate if result.premortem else None
                ),
            }
            state.store_data_cache(
                self.db, cycle_id, ticker, "adversarial_result", adversarial_data,
            )

            state.mark_completed(self.db, step_id)
            logger.info(
                "Adversarial for %s: %s (%d biases, %d kill scenarios, premortem=%s)",
                ticker,
                result.verdict.value,
                adversarial_data["bias_count"],
                adversarial_data["kill_scenario_count"],
                adversarial_data.get("premortem_probability"),
            )
        except Exception as e:
            # Adversarial failure should NOT block synthesis
            state.mark_completed(self.db, step_id)
            logger.warning(
                "Adversarial review failed for %s, proceeding without: %s",
                ticker, e,
            )

    async def _handle_synthesis(
        self, cycle_id: UUID, ticker: str, step_id: int,
    ) -> None:
        """Run verdict synthesis + advisory board + CIO narrative."""
        if not state.is_step_completed(
            self.db, cycle_id, ticker, state.STEP_ADVERSARIAL,
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

            # 2. Build weights from skills, adjusted by calibration accuracy
            weights = {
                name: Decimal(str(skill.base_weight))
                for name, skill in SKILLS.items()
                if skill.base_weight > 0
            }
            # Include weights for dynamically-created agents (sector specialists)
            for ss in agent_signal_sets:
                if ss.agent_name not in weights and ss.agent_name in self._runners:
                    runner = self._runners[ss.agent_name]
                    weights[ss.agent_name] = Decimal(str(runner.skill.base_weight))
            weights = self._apply_calibration_weights(weights)

            # 3. Verdict synthesis (deterministic vote aggregation)
            # Use cached calibrator (fit once per cycle, reuse for all tickers)
            agent_calibrator = None
            try:
                if self._calibrator_cycle_id != cycle_id:
                    from investmentology.learning.calibration import AgentCalibrator
                    from investmentology.registry.queries import Registry as _Reg
                    _reg = _Reg(self.db)
                    cal = AgentCalibrator(_reg)
                    cal.fit_all()
                    self._cached_calibrator = cal
                    self._calibrator_cycle_id = cycle_id
                agent_calibrator = self._cached_calibrator
            except Exception:
                pass

            from investmentology.verdict import synthesize
            verdict_result = synthesize(
                agent_signal_sets,
                weights=weights,
                calibrator=agent_calibrator,
            )
            logger.info(
                "Verdict for %s: %s (conf=%.2f, consensus=%.2f)",
                ticker, verdict_result.verdict.value,
                verdict_result.confidence, verdict_result.consensus_score,
            )

            # 3b. Load adversarial result if available
            adversarial_result = None
            if cycle_id:
                adversarial_result = state.get_data_cache(
                    self.db, cycle_id, ticker, "adversarial_result",
                )

            # Apply Munger override if VETO
            if adversarial_result and adversarial_result.get("verdict") == "VETO":
                verdict_result.munger_override = (
                    f"VETO: {adversarial_result.get('reasoning', 'Adversarial review vetoed')}"
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
                    adversarial=adversarial_result,
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

            # 7a. Watchlist enrichment — store blocking factors & graduation criteria
            if effective_verdict == "WATCHLIST":
                try:
                    from investmentology.pipeline.watchlist_enrichment import (
                        extract_watchlist_metadata,
                        upsert_watchlist_entry,
                    )
                    raw_fund = state.get_data_cache(
                        self.db, cycle_id, ticker, "fundamentals",
                    )
                    synthesis_data = {
                        "reasoning": verdict_result.reasoning,
                        "board_narrative": board_narrative_dict,
                    }
                    wl_metadata = extract_watchlist_metadata(
                        ticker, signal_rows, synthesis_data, raw_fund,
                    )
                    upsert_watchlist_entry(
                        self.db, ticker, wl_metadata, verdict_id,
                    )
                except Exception:
                    logger.warning(
                        "Watchlist enrichment failed for %s, continuing",
                        ticker, exc_info=True,
                    )

            # 7b. Record calibration prediction for feedback loop
            try:
                from investmentology.learning.calibration import CalibrationTracker
                cal_tracker = CalibrationTracker(registry)

                # Get current price for snapshot
                request = self._build_request(ticker)
                current_price = float(
                    getattr(request.fundamentals, "current_price", 0)
                    or getattr(request.fundamentals, "price", 0) or 0
                )
                if current_price > 0:
                    # Build agent contributions for snapshot
                    agent_contribs = [
                        {
                            "name": s.name,
                            "sentiment": s.sentiment,
                            "confidence": float(s.confidence),
                            "weight": float(weights.get(s.name, 0)),
                        }
                        for s in verdict_result.agent_stances
                    ]
                    cal_tracker.record_verdict(
                        ticker=ticker,
                        verdict=effective_verdict,
                        sentiment=verdict_result.consensus_score,
                        confidence=float(verdict_result.confidence),
                        price_at_verdict=current_price,
                        agent_contributions=agent_contribs,
                        position_type=getattr(
                            verdict_result, "position_type", None,
                        ),
                        regime_label=getattr(
                            verdict_result, "regime_label", None,
                        ),
                    )
                    # Per-agent calibration data
                    for s in verdict_result.agent_stances:
                        cal_tracker.record_agent_data(
                            agent_name=s.name,
                            ticker=ticker,
                            raw_confidence=float(s.confidence),
                            sentiment=s.sentiment,
                            price_at_verdict=current_price,
                        )
            except Exception:
                logger.debug("Calibration recording failed for %s", ticker)

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

    async def _ensure_macro_regime(self, cycle_id: UUID) -> None:
        """Run macro regime classification once per cycle.

        Uses FRED data from the enricher to classify the current macro
        environment. Result is stored in pipeline_data_cache with
        ticker='__cycle__' so all agents receive the same factual context.
        """
        # Check if already classified this cycle
        existing = state.get_data_cache(
            self.db, cycle_id, "__cycle__", "macro_regime",
        )
        if existing:
            return

        try:
            from investmentology.data.macro_regime import (
                classify_macro_regime,
                macro_regime_to_dict,
            )

            # Try to get FRED macro context from this cycle's cache first
            macro_ctx = state.get_data_cache(
                self.db, cycle_id, "__cycle__", "macro_context",
            )

            # Fall back to fetching fresh FRED data
            if not macro_ctx and self._enricher and self._enricher._fred:
                loop = asyncio.get_event_loop()
                macro_ctx = await loop.run_in_executor(
                    None, self._enricher._fred.get_macro_context,
                )
                if macro_ctx:
                    state.store_data_cache(
                        self.db, cycle_id, "__cycle__", "macro_context",
                        macro_ctx,
                    )

            if not macro_ctx:
                logger.warning("No FRED data available for macro regime classification")
                return

            result = classify_macro_regime(macro_ctx)
            state.store_data_cache(
                self.db, cycle_id, "__cycle__", "macro_regime",
                macro_regime_to_dict(result),
            )
            logger.info(
                "Macro regime: %s (confidence=%.0f%%): %s",
                result.regime, result.confidence * 100, result.summary,
            )
        except Exception:
            logger.warning("Macro regime classification failed", exc_info=True)

    def _ensure_backtest_calibration(self, cycle_id: UUID) -> None:
        """Load latest quant backtest IC data once per cycle.

        Queries invest.quant_backtest_runs for the most recent result and
        stores regime-conditioned IC data in the pipeline cache so agents
        receive historical factor accuracy context.
        """
        existing = state.get_data_cache(
            self.db, cycle_id, "__cycle__", "backtest_calibration",
        )
        if existing:
            return

        try:
            rows = self.db.execute(
                "SELECT regime_data, summary FROM invest.quant_backtest_runs "
                "ORDER BY created_at DESC LIMIT 1",
            )
            if not rows:
                logger.debug("No quant backtest results available for calibration")
                return

            row = rows[0]
            calibration = {
                "regime_ics": row.get("regime_data", {}),
                "summary": row.get("summary", {}),
            }
            state.store_data_cache(
                self.db, cycle_id, "__cycle__", "backtest_calibration",
                calibration,
            )
            logger.info("Loaded backtest calibration into cycle cache")
        except Exception:
            logger.debug("Backtest calibration load failed", exc_info=True)

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
        """Check if the cycle is complete and mark it if so.

        Also verifies no in-flight tasks remain in the TaskRegistry
        to prevent premature cycle completion.
        """
        summary = state.get_cycle_summary(self.db, cycle_id)
        if summary["pending"] == 0 and summary["running"] == 0:
            # Don't close if we still have tracked tasks (they may
            # be between mark_running and mark_completed)
            if self._task_registry.count > 0:
                logger.debug(
                    "Cycle completion deferred: %d tasks still tracked",
                    self._task_registry.count,
                )
                return
            if summary["completed"] > 0 or summary["failed"] > 0:
                state.complete_cycle(self.db, cycle_id)
                logger.info(
                    "Pipeline cycle %s completed: %s", cycle_id, summary,
                )

    async def _staleness_sweep(self, cycle_id: UUID) -> None:
        """Check portfolio tickers for stale data and auto-queue refreshes.

        Runs every 10th tick (~10 minutes). Only refreshes portfolio tickers
        to avoid wasting API calls on watchlist data that's acceptable stale.
        """
        if not self._portfolio_tickers:
            return

        try:
            stale = freshness.get_stale_tickers(
                self.db, str(cycle_id), self._portfolio_tickers,
            )
            for ticker, stale_keys in stale.items():
                if freshness.should_auto_refresh(stale_keys, is_portfolio=True):
                    step_id, action = state.reset_or_create_step(
                        self.db, cycle_id, ticker, state.STEP_DATA_FETCH,
                    )
                    if action in ("created", "reset"):
                        logger.info(
                            "Staleness sweep: auto-refreshing %s (%s stale: %s)",
                            ticker, action, ", ".join(stale_keys[:3]),
                        )
        except Exception:
            logger.debug("Staleness sweep failed", exc_info=True)

    async def _attempt_gap_fill(
        self, cycle_id: UUID, ticker: str, missing_keys: list[str],
    ) -> list[str]:
        """Try FallbackProvider for each missing key. Returns keys still missing.

        Uses the existing web_search_provider.FallbackProvider for:
        - analyst_ratings, short_interest, insider_context → yfinance fallback
        - news_context, social_sentiment, filing_context → SearXNG fallback
        """
        if not missing_keys:
            return []

        loop = asyncio.get_event_loop()
        still_missing = await loop.run_in_executor(
            None, self._run_web_fallbacks_for_gaps, cycle_id, ticker, missing_keys,
        )
        filled = len(missing_keys) - len(still_missing)
        if filled:
            logger.info(
                "Gap-fill for %s: filled %d/%d keys", ticker, filled, len(missing_keys),
            )
        return still_missing

    def _run_web_fallbacks_for_gaps(
        self, cycle_id: UUID, ticker: str, missing_keys: list[str],
    ) -> list[str]:
        """Synchronous gap-fill via FallbackProvider. Returns still-missing keys."""
        ok, fail = self._run_web_fallbacks(cycle_id, ticker, missing_keys)
        # Keys that weren't filled = still missing
        # We can't tell exactly which ones failed, so re-check cache
        still_missing = []
        for key in missing_keys:
            cached = state.get_data_cache(self.db, cycle_id, ticker, key)
            if not cached:
                still_missing.append(key)
        return still_missing

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

    def _apply_calibration_weights(
        self, weights: dict[str, Decimal],
    ) -> dict[str, Decimal]:
        """Adjust agent weights using calibration accuracy from settled predictions.

        Agents with above-average accuracy get a boost (up to +20%),
        those below average get a penalty (up to -20%). Requires at least
        10 settled predictions per agent to adjust.
        """
        try:
            from investmentology.learning.predictions import PredictionManager
            from investmentology.registry.queries import Registry

            registry = Registry(self.db)
            pm = PredictionManager(registry)
            cal = pm.get_calibration_data(window_days=90)
            agent_acc = cal.get("agent_accuracy", {})

            if not agent_acc:
                return weights

            # Filter to agents with enough data
            qualified = {
                k: v for k, v in agent_acc.items()
                if v.get("total", 0) >= 10
            }
            if not qualified:
                return weights

            # Compute mean accuracy across qualified agents
            mean_acc = sum(v["accuracy"] for v in qualified.values()) / len(qualified)

            adjusted = dict(weights)
            for agent_name, base_w in weights.items():
                if agent_name not in qualified:
                    continue
                acc = qualified[agent_name]["accuracy"]
                # Scale: +/-20% max adjustment, proportional to deviation from mean
                deviation = acc - mean_acc
                # Clamp to [-0.20, +0.20]
                factor = Decimal(str(max(-0.20, min(0.20, deviation))))
                adjusted[agent_name] = base_w * (1 + factor)

            # Re-normalize so weights sum to 1.0
            total = sum(adjusted.values())
            if total > 0:
                adjusted = {k: v / total for k, v in adjusted.items()}

            logger.info(
                "Calibration-adjusted weights (%d agents qualified, mean_acc=%.2f): %s",
                len(qualified), mean_acc,
                {k: f"{float(v):.3f}" for k, v in adjusted.items()},
            )
            return adjusted
        except Exception:
            logger.debug("Calibration weight adjustment failed, using base weights")
            return weights

    def _reconstruct_signal_sets(self, signal_rows: list[dict]) -> list:
        """Reconstruct AgentSignalSet objects from DB rows."""
        from investmentology.pipeline.builder import reconstruct_signal_sets
        return reconstruct_signal_sets(signal_rows)

    def _build_request(self, ticker: str) -> AnalysisRequest:
        """Build an AnalysisRequest from cached pipeline data or DB fallback."""
        from investmentology.pipeline.builder import build_analysis_request
        return build_analysis_request(self.db, ticker, self._current_cycle_id)

    def _get_analysis_tickers(self) -> list[str]:
        """Get tickers that need analysis, portfolio-first.

        Sources: watchlist, quant gate candidates, held positions.
        Excludes: blocked tickers (reentry gate).
        Returns: portfolio tickers first, then watchlist (budget-capped).
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

        unblocked = sorted(t for t in candidates if t not in blocked)
        if not unblocked:
            return []

        # L2 Selection Desk: portfolio-first selection with guaranteed slots
        # During overnight window, remove watchlist cap so all tickers get
        # data_fetch + screening. CLI queue throughput is the natural throttle.
        if self._is_overnight:
            selection = select_tickers(self.db, unblocked, max_watchlist=999)
        else:
            selection = select_tickers(self.db, unblocked)
        all_tickers = selection.all_tickers
        logger.info(
            "Analysis tickers: %d portfolio + %d watchlist from %d candidates (%d blocked, overnight=%s)",
            len(selection.portfolio), len(selection.watchlist),
            len(unblocked), len(candidates) - len(unblocked),
            self._is_overnight,
        )
        return all_tickers

    def _get_portfolio_context(self, ticker: str) -> dict | None:
        """Get portfolio context for a ticker if it's a held position."""
        from investmentology.pipeline.builder import get_portfolio_context
        return get_portfolio_context(self.db, ticker)

    @staticmethod
    def _dict_to_snapshot(ticker: str, raw: dict):
        """Convert a raw yfinance/cache dict to a FundamentalsSnapshot."""
        from investmentology.pipeline.builder import dict_to_snapshot
        return dict_to_snapshot(ticker, raw)

    @staticmethod
    def _snapshot_to_dict(snap) -> dict:
        """Convert a FundamentalsSnapshot back to a dict."""
        from investmentology.pipeline.builder import snapshot_to_dict
        return snapshot_to_dict(snap)

    @staticmethod
    def _empty_snapshot(ticker: str):
        """Create a zero-filled FundamentalsSnapshot."""
        from investmentology.pipeline.builder import empty_snapshot
        return empty_snapshot(ticker)
