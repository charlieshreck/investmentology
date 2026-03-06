"""Pipeline state DB operations — CRUD, expiry, readiness checks.

All queries target the invest.pipeline_state and invest.pipeline_cycles
tables created in migration 012.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from investmentology.registry.db import Database

logger = logging.getLogger(__name__)

# Default staleness window
STALENESS_HOURS = 24

# Steps in dependency order
STEP_DATA_FETCH = "data_fetch"
STEP_DATA_VALIDATE = "data_validate"
STEP_PRE_FILTER = "pre_filter"
STEP_SCREENER_PREFIX = "screener:"
STEP_GATE_DECISION = "gate_decision"
STEP_RESEARCH = "research"
STEP_AGENT_PREFIX = "agent:"
STEP_DEBATE = "debate"
STEP_ADVERSARIAL = "adversarial"
STEP_SYNTHESIS = "synthesis"


# ---------------------------------------------------------------------------
# Cycle management
# ---------------------------------------------------------------------------

def create_cycle(db: Database, ticker_count: int = 0) -> UUID:
    """Create a new pipeline cycle and return its id."""
    rows = db.execute(
        "INSERT INTO invest.pipeline_cycles (ticker_count) "
        "VALUES (%s) RETURNING id",
        (ticker_count,),
    )
    cycle_id = rows[0]["id"]
    logger.info("Created pipeline cycle %s (%d tickers)", cycle_id, ticker_count)
    return cycle_id


def complete_cycle(db: Database, cycle_id: UUID) -> None:
    """Mark a cycle as completed."""
    db.execute(
        "UPDATE invest.pipeline_cycles "
        "SET status = 'completed', completed_at = NOW() "
        "WHERE id = %s",
        (cycle_id,),
    )


def expire_old_cycles(db: Database) -> int:
    """Mark active cycles older than STALENESS_HOURS as expired."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALENESS_HOURS)
    rows = db.execute(
        "UPDATE invest.pipeline_cycles "
        "SET status = 'expired' "
        "WHERE status = 'active' AND started_at < %s "
        "RETURNING id",
        (cutoff,),
    )
    if rows:
        logger.info("Expired %d old cycles", len(rows))
    return len(rows)


# ---------------------------------------------------------------------------
# State row operations
# ---------------------------------------------------------------------------

def create_step(
    db: Database,
    cycle_id: UUID,
    ticker: str,
    step: str,
) -> int:
    """Insert a pending pipeline step. Returns the row id."""
    expires = datetime.now(timezone.utc) + timedelta(hours=STALENESS_HOURS)
    rows = db.execute(
        "INSERT INTO invest.pipeline_state "
        "(cycle_id, ticker, step, status, expires_at) "
        "VALUES (%s, %s, %s, 'pending', %s) "
        "ON CONFLICT (cycle_id, ticker, step) DO NOTHING "
        "RETURNING id",
        (cycle_id, ticker, step, expires),
    )
    if rows:
        return rows[0]["id"]
    # Already exists — return existing id
    existing = db.execute(
        "SELECT id FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND ticker = %s AND step = %s",
        (cycle_id, ticker, step),
    )
    return existing[0]["id"] if existing else 0


def mark_running(db: Database, step_id: int) -> None:
    """Mark a step as running."""
    db.execute(
        "UPDATE invest.pipeline_state "
        "SET status = 'running', started_at = NOW() "
        "WHERE id = %s AND status = 'pending'",
        (step_id,),
    )


def mark_completed(
    db: Database, step_id: int, result_ref: int | None = None,
) -> None:
    """Mark a step as completed with an optional result reference."""
    db.execute(
        "UPDATE invest.pipeline_state "
        "SET status = 'completed', completed_at = NOW(), result_ref = %s "
        "WHERE id = %s",
        (result_ref, step_id),
    )


def mark_failed(db: Database, step_id: int, error: str) -> None:
    """Mark a step as failed with an error message."""
    db.execute(
        "UPDATE invest.pipeline_state "
        "SET status = 'failed', completed_at = NOW(), error = %s, "
        "retry_count = retry_count + 1 "
        "WHERE id = %s",
        (error, step_id),
    )


def reset_for_retry(db: Database, step_id: int) -> bool:
    """Reset a failed step to pending for retry. Returns False if max retries exceeded."""
    rows = db.execute(
        "SELECT retry_count FROM invest.pipeline_state WHERE id = %s",
        (step_id,),
    )
    if not rows or rows[0]["retry_count"] >= 2:
        return False

    db.execute(
        "UPDATE invest.pipeline_state "
        "SET status = 'pending', started_at = NULL, completed_at = NULL, error = NULL "
        "WHERE id = %s",
        (step_id,),
    )
    return True


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------

def expire_stale_steps(db: Database) -> int:
    """Mark steps past their expires_at as expired."""
    now = datetime.now(timezone.utc)
    rows = db.execute(
        "UPDATE invest.pipeline_state "
        "SET status = 'expired' "
        "WHERE expires_at < %s AND status NOT IN ('expired', 'completed') "
        "RETURNING id, ticker, step",
        (now,),
    )
    if rows:
        logger.info("Expired %d pipeline steps", len(rows))
    return len(rows)


# Max time a step can stay in "running" before being reset (minutes)
RUNNING_TIMEOUT_MINUTES = 20


def reset_stale_running_steps(db: Database) -> int:
    """Reset steps stuck in 'running' for too long back to 'pending'.

    This handles cases where the controller OOMKills or crashes mid-tick,
    leaving steps in 'running' that were never completed or failed.
    Steps with retry_count >= 2 are marked 'failed' instead.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=RUNNING_TIMEOUT_MINUTES)
    # Reset retriable steps back to pending
    reset_rows = db.execute(
        "UPDATE invest.pipeline_state "
        "SET status = 'pending', started_at = NULL "
        "WHERE status = 'running' AND started_at < %s AND retry_count < 2 "
        "RETURNING id, ticker, step",
        (cutoff,),
    )
    # Fail steps that have exceeded retries
    fail_rows = db.execute(
        "UPDATE invest.pipeline_state "
        "SET status = 'failed', error = 'Stale running step (max retries exceeded)', "
        "completed_at = NOW() "
        "WHERE status = 'running' AND started_at < %s AND retry_count >= 2 "
        "RETURNING id, ticker, step",
        (cutoff,),
    )
    total = len(reset_rows) + len(fail_rows)
    if total:
        logger.info(
            "Recovered %d stale running steps (%d reset, %d failed)",
            total, len(reset_rows), len(fail_rows),
        )
    return total


# ---------------------------------------------------------------------------
# Readiness queries
# ---------------------------------------------------------------------------

def get_pending_steps(
    db: Database, cycle_id: UUID,
) -> list[dict]:
    """Get all pending steps for a cycle, ordered by ticker then step."""
    return db.execute(
        "SELECT id, ticker, step, retry_count "
        "FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND status = 'pending' "
        "ORDER BY ticker, step",
        (cycle_id,),
    )


def get_step_status(
    db: Database, cycle_id: UUID, ticker: str, step: str,
) -> dict | None:
    """Get the status of a specific step."""
    rows = db.execute(
        "SELECT id, status, result_ref, error, retry_count "
        "FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND ticker = %s AND step = %s",
        (cycle_id, ticker, step),
    )
    return rows[0] if rows else None


def is_step_completed(
    db: Database, cycle_id: UUID, ticker: str, step: str,
) -> bool:
    """Check if a specific step is completed."""
    row = get_step_status(db, cycle_id, ticker, step)
    return row is not None and row["status"] == "completed"


def are_all_agent_steps_completed(
    db: Database, cycle_id: UUID, ticker: str, agent_names: list[str],
) -> bool:
    """Check if all specified agent steps are completed for a ticker."""
    placeholders = ", ".join(["%s"] * len(agent_names))
    steps = [f"agent:{name}" for name in agent_names]
    rows = db.execute(
        f"SELECT COUNT(*) AS cnt FROM invest.pipeline_state "
        f"WHERE cycle_id = %s AND ticker = %s "
        f"AND step IN ({placeholders}) "
        f"AND status = 'completed'",
        (cycle_id, ticker, *steps),
    )
    return rows[0]["cnt"] == len(agent_names) if rows else False


def count_agent_step_statuses(
    db: Database, cycle_id: UUID, ticker: str, agent_names: list[str],
) -> dict[str, int]:
    """Count agent steps by status for a ticker. Returns {status: count}."""
    placeholders = ", ".join(["%s"] * len(agent_names))
    steps = [f"agent:{name}" for name in agent_names]
    rows = db.execute(
        f"SELECT status, COUNT(*) AS cnt FROM invest.pipeline_state "
        f"WHERE cycle_id = %s AND ticker = %s "
        f"AND step IN ({placeholders}) "
        f"GROUP BY status",
        (cycle_id, ticker, *steps),
    )
    return {r["status"]: r["cnt"] for r in rows}


def get_ticker_progress(
    db: Database, cycle_id: UUID, ticker: str,
) -> list[dict]:
    """Get all pipeline steps for a ticker in the current cycle."""
    return db.execute(
        "SELECT step, status, started_at, completed_at, error, retry_count "
        "FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND ticker = %s "
        "ORDER BY id",
        (cycle_id, ticker),
    )


def get_tickers_summary(db: Database, cycle_id: UUID) -> list[dict]:
    """Per-ticker progress summary for a pipeline cycle."""
    return db.execute(
        "SELECT ticker, "
        "COUNT(*) AS total_steps, "
        "COUNT(*) FILTER (WHERE status = 'completed') AS completed, "
        "COUNT(*) FILTER (WHERE status = 'failed') AS failed, "
        "COUNT(*) FILTER (WHERE status = 'running') AS running, "
        "COUNT(*) FILTER (WHERE status = 'pending') AS pending "
        "FROM invest.pipeline_state "
        "WHERE cycle_id = %s "
        "GROUP BY ticker ORDER BY ticker",
        (cycle_id,),
    )


def get_cycle_summary(db: Database, cycle_id: UUID) -> dict:
    """Get a summary of the pipeline cycle progress."""
    rows = db.execute(
        "SELECT status, COUNT(*) AS cnt "
        "FROM invest.pipeline_state "
        "WHERE cycle_id = %s "
        "GROUP BY status",
        (cycle_id,),
    )
    summary = {r["status"]: r["cnt"] for r in rows}
    total = sum(summary.values())
    return {
        "cycle_id": str(cycle_id),
        "total_steps": total,
        "pending": summary.get("pending", 0),
        "running": summary.get("running", 0),
        "completed": summary.get("completed", 0),
        "failed": summary.get("failed", 0),
        "expired": summary.get("expired", 0),
    }


# ---------------------------------------------------------------------------
# Per-cycle data cache
# ---------------------------------------------------------------------------

def store_data_cache(
    db: Database, cycle_id: UUID, ticker: str, data_key: str, data_value: dict,
) -> None:
    """Cache data for a ticker within a pipeline cycle (upsert)."""
    db.execute(
        "INSERT INTO invest.pipeline_data_cache "
        "(cycle_id, ticker, data_key, data_value) "
        "VALUES (%s, %s, %s, %s) "
        "ON CONFLICT (cycle_id, ticker, data_key) "
        "DO UPDATE SET data_value = EXCLUDED.data_value, created_at = NOW()",
        (cycle_id, ticker, data_key, json.dumps(data_value, default=str)),
    )


def get_data_cache(
    db: Database, cycle_id: UUID, ticker: str, data_key: str,
) -> dict | None:
    """Retrieve cached data for a ticker within a pipeline cycle."""
    rows = db.execute(
        "SELECT data_value FROM invest.pipeline_data_cache "
        "WHERE cycle_id = %s AND ticker = %s AND data_key = %s",
        (cycle_id, ticker, data_key),
    )
    if not rows:
        return None
    val = rows[0]["data_value"]
    return val if isinstance(val, dict) else json.loads(val)


def get_all_data_cache(
    db: Database, cycle_id: UUID, ticker: str,
) -> dict[str, dict]:
    """Retrieve all cached data keys for a ticker within a pipeline cycle."""
    rows = db.execute(
        "SELECT data_key, data_value FROM invest.pipeline_data_cache "
        "WHERE cycle_id = %s AND ticker = %s",
        (cycle_id, ticker),
    )
    result: dict[str, dict] = {}
    for r in rows:
        val = r["data_value"]
        result[r["data_key"]] = val if isinstance(val, dict) else json.loads(val)
    return result


def get_agent_signals_for_ticker(
    db: Database, cycle_id: UUID, ticker: str,
) -> list[dict]:
    """Load all completed agent/screener signal results for a ticker in this cycle.

    Joins pipeline_state (for step tracking) with agent_signals (for signal data)
    via the result_ref foreign key. Includes both agent:* and screener:* steps.
    """
    return db.execute(
        "SELECT s.id, s.ticker, s.agent_name, s.model, s.signals, "
        "s.confidence, s.reasoning, s.latency_ms "
        "FROM invest.pipeline_state ps "
        "JOIN invest.agent_signals s ON s.id = ps.result_ref "
        "WHERE ps.cycle_id = %s AND ps.ticker = %s "
        "AND (ps.step LIKE 'agent:%%' OR ps.step LIKE 'screener:%%') "
        "AND ps.status = 'completed' "
        "AND ps.result_ref IS NOT NULL",
        (cycle_id, ticker),
    )


# ---------------------------------------------------------------------------
# Bulk step creation for a ticker
# ---------------------------------------------------------------------------

def create_ticker_steps(
    db: Database,
    cycle_id: UUID,
    ticker: str,
    agent_names: list[str],
    include_debate: bool = True,
    include_synthesis: bool = True,
) -> int:
    """Create all pipeline steps for a ticker. Returns number of steps created."""
    steps = [STEP_DATA_FETCH, STEP_DATA_VALIDATE]
    for name in agent_names:
        steps.append(f"{STEP_AGENT_PREFIX}{name}")
    if include_debate:
        steps.append(STEP_DEBATE)
    if include_synthesis:
        steps.append(STEP_SYNTHESIS)

    created = 0
    for step in steps:
        row_id = create_step(db, cycle_id, ticker, step)
        if row_id:
            created += 1

    logger.info(
        "Created %d pipeline steps for %s in cycle %s",
        created, ticker, cycle_id,
    )
    return created


def create_screening_steps(
    db: Database,
    cycle_id: UUID,
    ticker: str,
    screener_names: list[str],
) -> int:
    """Create Phase 1 steps: data_fetch, data_validate, screeners, gate_decision.

    These are the cheap, fast steps that run for ALL tickers. Phase 2 steps
    (analysis agents, debate, synthesis) are only created for tickers that pass
    the gate decision.
    """
    steps = [STEP_DATA_FETCH, STEP_DATA_VALIDATE, STEP_PRE_FILTER]
    for name in screener_names:
        steps.append(f"{STEP_SCREENER_PREFIX}{name}")
    steps.append(STEP_GATE_DECISION)

    created = 0
    for step in steps:
        row_id = create_step(db, cycle_id, ticker, step)
        if row_id:
            created += 1

    if created:
        logger.info(
            "Created %d screening steps for %s in cycle %s",
            created, ticker, cycle_id,
        )
    return created


def create_analysis_steps(
    db: Database,
    cycle_id: UUID,
    ticker: str,
    agent_names: list[str],
    include_debate: bool = True,
    include_synthesis: bool = True,
    include_research: bool = True,
    include_adversarial: bool = True,
) -> int:
    """Create Phase 2 steps: research, analysis agents, debate, adversarial, synthesis.

    Called only for tickers that pass the scout gate. Data fetch/validate
    and screener steps already exist from Phase 1.
    """
    steps = []
    if include_research:
        steps.append(STEP_RESEARCH)
    for name in agent_names:
        steps.append(f"{STEP_AGENT_PREFIX}{name}")
    if include_debate:
        steps.append(STEP_DEBATE)
    if include_adversarial:
        steps.append(STEP_ADVERSARIAL)
    if include_synthesis:
        steps.append(STEP_SYNTHESIS)

    created = 0
    for step in steps:
        row_id = create_step(db, cycle_id, ticker, step)
        if row_id:
            created += 1

    if created:
        logger.info(
            "Created %d analysis steps for %s in cycle %s (passed gate)",
            created, ticker, cycle_id,
        )
    return created


# ---------------------------------------------------------------------------
# Manual trigger helpers
# ---------------------------------------------------------------------------


def reset_or_create_step(
    db: Database,
    cycle_id: UUID,
    ticker: str,
    step: str,
) -> tuple[int, str]:
    """Reset a failed/expired step to pending, or create it if missing.

    Returns (step_id, action) where action is one of:
    'created', 'reset', 'already_pending', 'running'.
    """
    # Check if step already exists in this cycle
    rows = db.execute(
        "SELECT id, status FROM invest.pipeline_state "
        "WHERE cycle_id = %s AND ticker = %s AND step = %s",
        (cycle_id, ticker, step),
    )

    if not rows:
        # Create new step
        step_id = create_step(db, cycle_id, ticker, step)
        return (step_id, "created")

    row = rows[0]
    step_id = row["id"]
    status = row["status"]

    if status == "pending":
        return (step_id, "already_pending")

    if status == "running":
        return (step_id, "running")

    # failed, expired, or completed — reset to pending
    expires = datetime.now(timezone.utc) + timedelta(hours=STALENESS_HOURS)
    db.execute(
        "UPDATE invest.pipeline_state "
        "SET status = 'pending', started_at = NULL, completed_at = NULL, "
        "error = NULL, result_ref = NULL, expires_at = %s "
        "WHERE id = %s",
        (expires, step_id),
    )
    return (step_id, "reset")


def get_latest_agent_signals(
    db: Database,
    ticker: str,
    agent_names: list[str] | None = None,
) -> list[dict]:
    """Load most recent agent signals per agent for a ticker (cross-cycle).

    Uses DISTINCT ON (agent_name) to get the latest signal per agent,
    regardless of which pipeline cycle it came from.
    """
    if agent_names:
        return db.execute(
            "SELECT DISTINCT ON (agent_name) "
            "id, ticker, agent_name, model, signals, confidence, "
            "reasoning, latency_ms, created_at "
            "FROM invest.agent_signals "
            "WHERE ticker = %s AND agent_name = ANY(%s) "
            "ORDER BY agent_name, created_at DESC",
            (ticker, agent_names),
        )
    return db.execute(
        "SELECT DISTINCT ON (agent_name) "
        "id, ticker, agent_name, model, signals, confidence, "
        "reasoning, latency_ms, created_at "
        "FROM invest.agent_signals "
        "WHERE ticker = %s "
        "ORDER BY agent_name, created_at DESC",
        (ticker,),
    )
