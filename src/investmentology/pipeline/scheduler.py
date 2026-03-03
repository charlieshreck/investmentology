"""CLI queue scheduler — per-agent parallel workers.

Each CLI agent (warren, auditor, klarman, soros, druckenmiller, dalio,
data-analyst, debate, synthesis) gets its own async queue and worker.
All workers run in parallel, so 3 Claude + 3 Gemini CLI processes
execute concurrently on the HB LXC.

API-only agents (Simons, Lynch) bypass the queues entirely.
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
    """Per-agent queue workers for CLI-based agents."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[AgentJob]] = {}
        self._workers: dict[str, list[asyncio.Task]] = {}
        self._running = False

    async def start(self, agent_names: list[str], workers_per_agent: int = 1) -> None:
        """Start workers for each agent. Multiple workers per agent share a queue."""
        self._running = True
        total = 0
        for name in agent_names:
            queue: asyncio.Queue[AgentJob] = asyncio.Queue()
            self._queues[name] = queue
            self._workers[name] = []
            for i in range(workers_per_agent):
                label = name if workers_per_agent == 1 else f"{name}-{i+1}"
                task = asyncio.create_task(
                    self._worker(label, queue),
                    name=f"cli-worker-{label}",
                )
                self._workers[name].append(task)
                total += 1
        logger.info(
            "CLI scheduler started (%d workers across %d agents, %d per agent)",
            total, len(agent_names), workers_per_agent,
        )

    async def stop(self) -> None:
        """Stop all queue workers gracefully."""
        self._running = False
        for name, tasks in self._workers.items():
            for _ in tasks:
                await self._queues[name].put(None)  # type: ignore[arg-type]
        for tasks in self._workers.values():
            for task in tasks:
                await task
        logger.info("CLI scheduler stopped")

    def submit(self, job: AgentJob) -> asyncio.Future:
        """Submit a job to the agent's dedicated queue."""
        name = job.skill.name
        if name not in self._queues:
            raise ValueError(
                f"No queue for agent {name!r} — "
                f"registered: {list(self._queues.keys())}"
            )
        self._queues[name].put_nowait(job)
        return job.future

    def queue_size(self, agent_name: str) -> int:
        """Get the queue size for a specific agent."""
        q = self._queues.get(agent_name)
        return q.qsize() if q else 0

    @property
    def claude_queue_size(self) -> int:
        """Aggregate queue size for Claude-side agents."""
        from investmentology.agents.skills import SKILLS
        return sum(
            q.qsize() for name, q in self._queues.items()
            if SKILLS.get(name) and SKILLS[name].cli_screen == "claude"
        )

    @property
    def gemini_queue_size(self) -> int:
        """Aggregate queue size for Gemini-side agents."""
        from investmentology.agents.skills import SKILLS
        return sum(
            q.qsize() for name, q in self._queues.items()
            if SKILLS.get(name) and SKILLS[name].cli_screen == "gemini"
        )

    async def _worker(self, agent_name: str, queue: asyncio.Queue[AgentJob]) -> None:
        """Process jobs from a queue one at a time."""
        logger.info("Worker %s started", agent_name)
        while self._running:
            try:
                job = await queue.get()
            except asyncio.CancelledError:
                break

            if job is None:  # Sentinel for shutdown
                break

            logger.info(
                "%s: running %s (step_id=%d, queue=%d remaining)",
                agent_name, job.request.ticker,
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
                    "%s: %s completed (conf=%.2f, latency=%dms)",
                    agent_name, job.request.ticker,
                    response.signal_set.confidence, response.latency_ms,
                )
            except Exception as e:
                logger.exception(
                    "%s: %s failed: %s",
                    agent_name, job.request.ticker, e,
                )
                job.future.set_exception(e)

            queue.task_done()

        logger.info("Worker %s stopped", agent_name)
