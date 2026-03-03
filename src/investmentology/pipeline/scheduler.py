"""CLI queue scheduler — serializes agent work per CLI screen.

Two async workers process queues:
- Claude worker: Warren → Auditor → Klarman → Debate → Synthesis
- Gemini worker: Data Analyst → Soros → Druckenmiller → Dalio

Each worker processes one job at a time since both CLI subscriptions
are single-session on the HB LXC.  API-only agents (Simons, Lynch)
bypass the queues entirely and run in parallel.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from investmentology.agents.base import AnalysisRequest
from investmentology.agents.runner import AgentRunner
from investmentology.agents.skills import AgentSkill

logger = logging.getLogger(__name__)


@dataclass
class AgentJob:
    """A unit of work for the CLI scheduler."""
    skill: AgentSkill
    runner: AgentRunner
    request: AnalysisRequest
    step_id: int  # pipeline_state row id
    future: asyncio.Future  # Set result when complete
    on_start: Callable[[], None] | None = field(default=None)  # Called when worker picks up job


class CLIScheduler:
    """Manages two serial queues for Claude and Gemini CLI screens."""

    def __init__(self) -> None:
        self._claude_queue: asyncio.Queue[AgentJob] = asyncio.Queue()
        self._gemini_queue: asyncio.Queue[AgentJob] = asyncio.Queue()
        self._claude_task: asyncio.Task | None = None
        self._gemini_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the queue worker tasks."""
        self._running = True
        self._claude_task = asyncio.create_task(
            self._worker("claude", self._claude_queue),
            name="claude-cli-worker",
        )
        self._gemini_task = asyncio.create_task(
            self._worker("gemini", self._gemini_queue),
            name="gemini-cli-worker",
        )
        logger.info("CLI scheduler started (claude + gemini workers)")

    async def stop(self) -> None:
        """Stop the queue workers gracefully."""
        self._running = False
        # Send sentinel values to unblock workers
        sentinel_future = asyncio.get_event_loop().create_future()
        sentinel_future.set_result(None)
        await self._claude_queue.put(None)  # type: ignore[arg-type]
        await self._gemini_queue.put(None)  # type: ignore[arg-type]
        if self._claude_task:
            await self._claude_task
        if self._gemini_task:
            await self._gemini_task
        logger.info("CLI scheduler stopped")

    def submit(self, job: AgentJob) -> asyncio.Future:
        """Submit a job to the appropriate queue. Returns a future for the result."""
        screen = job.skill.cli_screen
        if screen == "claude":
            self._claude_queue.put_nowait(job)
        elif screen == "gemini":
            self._gemini_queue.put_nowait(job)
        else:
            raise ValueError(
                f"Skill {job.skill.name} has cli_screen={screen}, "
                f"cannot schedule on CLI queue"
            )
        return job.future

    @property
    def claude_queue_size(self) -> int:
        return self._claude_queue.qsize()

    @property
    def gemini_queue_size(self) -> int:
        return self._gemini_queue.qsize()

    async def _worker(self, screen: str, queue: asyncio.Queue[AgentJob]) -> None:
        """Process jobs from a queue one at a time."""
        logger.info("%s CLI worker started", screen)
        while self._running:
            try:
                job = await queue.get()
            except asyncio.CancelledError:
                break

            if job is None:  # Sentinel for shutdown
                break

            logger.info(
                "%s CLI: running %s for %s (step_id=%d, queue=%d remaining)",
                screen, job.skill.name, job.request.ticker,
                job.step_id, queue.qsize(),
            )

            # Mark the step as running NOW (when the worker actually starts it)
            if job.on_start:
                try:
                    job.on_start()
                except Exception:
                    logger.exception("on_start callback failed for step %d", job.step_id)

            try:
                response = await job.runner.analyze(job.request)
                job.future.set_result(response)
                logger.info(
                    "%s CLI: %s/%s completed (conf=%.2f, latency=%dms)",
                    screen, job.skill.name, job.request.ticker,
                    response.signal_set.confidence, response.latency_ms,
                )
            except Exception as e:
                logger.exception(
                    "%s CLI: %s/%s failed: %s",
                    screen, job.skill.name, job.request.ticker, e,
                )
                job.future.set_exception(e)

            queue.task_done()

        logger.info("%s CLI worker stopped", screen)
