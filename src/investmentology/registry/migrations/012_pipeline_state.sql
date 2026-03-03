-- Pipeline state machine: tracks per-ticker-per-step progress for the
-- agent-first event-driven pipeline.  All rows expire after 24 hours.

-- Cycle tracking — one row per daily pipeline run
CREATE TABLE IF NOT EXISTS invest.pipeline_cycles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    ticker_count    INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'active' CHECK (status IN ('active', 'completed', 'expired'))
);

-- Per-ticker-per-step state
CREATE TABLE IF NOT EXISTS invest.pipeline_state (
    id              SERIAL PRIMARY KEY,
    cycle_id        UUID NOT NULL REFERENCES invest.pipeline_cycles(id),
    ticker          TEXT NOT NULL,
    step            TEXT NOT NULL,
    -- step values: 'data_fetch', 'data_validate', 'agent:<name>', 'debate', 'synthesis'
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'failed', 'expired')),
    result_ref      INTEGER,  -- FK to agent_signals.id or verdicts.id (polymorphic)
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ NOT NULL,
    error           TEXT,
    retry_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(cycle_id, ticker, step)
);

-- Find pending/running work efficiently
CREATE INDEX IF NOT EXISTS idx_pipeline_state_pending
    ON invest.pipeline_state (ticker, step) WHERE status IN ('pending', 'running');

-- Cycle-level queries
CREATE INDEX IF NOT EXISTS idx_pipeline_state_cycle
    ON invest.pipeline_state (cycle_id);

-- Expiry checks
CREATE INDEX IF NOT EXISTS idx_pipeline_state_expires
    ON invest.pipeline_state (expires_at) WHERE status NOT IN ('expired', 'completed');
