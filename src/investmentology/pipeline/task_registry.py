"""In-memory registry for tracked background tasks.

Maps step_id → asyncio.Task with metadata for orphan detection,
timeout enforcement, and observability. The Reaper uses this to
detect tasks that finished without updating the DB, or that have
exceeded their timeout.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TaskInfo:
    """Metadata for a tracked background task."""

    task: asyncio.Task
    step_id: int
    ticker: str
    step_name: str
    started_at: float = field(default_factory=time.monotonic)
    timeout_seconds: float = 660  # 11 min default


class TaskRegistry:
    """Tracks in-flight background tasks for the pipeline controller.

    Provides orphan detection (task.done() but still tracked) and
    timeout enforcement (running longer than timeout_seconds).
    """

    def __init__(self, max_tasks: int = 50) -> None:
        self._tasks: dict[int, TaskInfo] = {}
        self._max = max_tasks

    def track(
        self,
        step_id: int,
        task: asyncio.Task,
        ticker: str,
        step_name: str,
        timeout: float = 660,
    ) -> None:
        """Register a background task for monitoring."""
        if len(self._tasks) >= self._max:
            # Evict completed tasks first
            self._evict_done()
            if len(self._tasks) >= self._max:
                logger.warning(
                    "TaskRegistry at capacity (%d), cannot track step %d",
                    self._max, step_id,
                )
                return
        self._tasks[step_id] = TaskInfo(
            task=task,
            step_id=step_id,
            ticker=ticker,
            step_name=step_name,
            timeout_seconds=timeout,
        )

    def untrack(self, step_id: int) -> None:
        """Remove a task from tracking."""
        self._tasks.pop(step_id, None)

    def is_tracked(self, step_id: int) -> bool:
        return step_id in self._tasks

    @property
    def count(self) -> int:
        return len(self._tasks)

    def get_stale_done(self) -> list[TaskInfo]:
        """Find tasks where asyncio.Task.done() is True but still tracked.

        These are tasks that completed (success or exception) but
        the completion callback didn't clean up the registry — likely
        due to an exception in the callback itself.
        """
        return [
            info for info in self._tasks.values()
            if info.task.done()
        ]

    def get_timed_out(self) -> list[TaskInfo]:
        """Find tasks that have exceeded their timeout_seconds."""
        now = time.monotonic()
        return [
            info for info in self._tasks.values()
            if not info.task.done()
            and (now - info.started_at) > info.timeout_seconds
        ]

    def cancel_all(self) -> int:
        """Cancel all tracked tasks. Returns count cancelled."""
        count = 0
        for info in self._tasks.values():
            if not info.task.done():
                info.task.cancel()
                count += 1
        self._tasks.clear()
        return count

    def summary(self) -> dict:
        """Return tracking stats for observability."""
        now = time.monotonic()
        running = [
            info for info in self._tasks.values()
            if not info.task.done()
        ]
        return {
            "tracked": len(self._tasks),
            "running": len(running),
            "done_not_cleaned": len(self._tasks) - len(running),
            "max": self._max,
            "oldest_age_seconds": (
                int(now - min(i.started_at for i in running))
                if running else 0
            ),
        }

    def _evict_done(self) -> None:
        """Remove completed tasks to free capacity."""
        done_ids = [
            sid for sid, info in self._tasks.items()
            if info.task.done()
        ]
        for sid in done_ids:
            del self._tasks[sid]
