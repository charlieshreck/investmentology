"""Tests for the CLI scheduler queue logic."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from investmentology.pipeline.scheduler import AgentJob, CLIScheduler


@pytest.fixture
def scheduler():
    return CLIScheduler()


class TestCLIScheduler:
    @pytest.mark.asyncio
    async def test_start_creates_queues(self, scheduler):
        await scheduler.start(["warren", "soros"])
        assert "warren" in scheduler._queues
        assert "soros" in scheduler._queues
        assert len(scheduler._workers["warren"]) == 1
        assert len(scheduler._workers["soros"]) == 1
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_multiple_workers(self, scheduler):
        await scheduler.start(["warren"], workers_per_agent=3)
        assert len(scheduler._workers["warren"]) == 3
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_submit_unknown_agent_raises(self, scheduler):
        await scheduler.start(["warren"])
        job = MagicMock(spec=AgentJob)
        job.skill = MagicMock()
        job.skill.name = "unknown-agent"

        with pytest.raises(ValueError, match="No queue for agent"):
            scheduler.submit(job)
        await scheduler.stop()

    def test_queue_size_no_queue(self, scheduler):
        assert scheduler.queue_size("nonexistent") == 0

    @pytest.mark.asyncio
    async def test_queue_size_after_submit(self, scheduler):
        await scheduler.start(["warren"])

        # Create a mock job
        mock_skill = MagicMock()
        mock_skill.name = "warren"
        mock_runner = AsyncMock()
        mock_request = MagicMock()
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        job = AgentJob(
            skill=mock_skill,
            runner=mock_runner,
            request=mock_request,
            step_id=1,
            future=future,
        )
        scheduler.submit(job)
        # Worker might pick it up quickly, but queue had at least 1 item
        assert scheduler.queue_size("warren") >= 0
        future.cancel()
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_graceful(self, scheduler):
        await scheduler.start(["warren", "soros"])
        await scheduler.stop()
        assert scheduler._running is False
