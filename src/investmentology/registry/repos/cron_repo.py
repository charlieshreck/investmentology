from __future__ import annotations

from investmentology.registry.db import Database


class CronRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def log_cron_start(self, job_name: str) -> int:
        rows = self._db.execute(
            "INSERT INTO invest.cron_runs (job_name, started_at, status) "
            "VALUES (%s, NOW(), 'running') RETURNING id",
            (job_name,),
        )
        return rows[0]["id"]

    def log_cron_finish(self, cron_id: int, status: str, error: str | None = None) -> None:
        self._db.execute(
            "UPDATE invest.cron_runs SET finished_at = NOW(), status = %s, error = %s WHERE id = %s",
            (status, error, cron_id),
        )
