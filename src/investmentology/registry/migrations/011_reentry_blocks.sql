-- Re-entry qualification gate: block conditions that prevent wasteful re-analysis
-- When agents reject a stock (AVOID/DISCARD), we extract structured block conditions
-- from their consensus signal tags. The stock stays blocked until conditions clear.

CREATE TABLE IF NOT EXISTS invest.reentry_blocks (
    id              SERIAL PRIMARY KEY,
    ticker          TEXT NOT NULL,
    verdict_id      INTEGER REFERENCES invest.verdicts(id),
    block_type      TEXT NOT NULL CHECK (block_type IN ('quantitative', 'time_gated', 'permanent')),
    signal_tag      TEXT NOT NULL,
    condition_key   TEXT NOT NULL,
    threshold       NUMERIC,
    baseline_value  NUMERIC,
    agent_count     INTEGER DEFAULT 1,
    is_cleared      BOOLEAN DEFAULT FALSE,
    cleared_at      TIMESTAMPTZ,
    cleared_reason  TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reentry_blocks_active
    ON invest.reentry_blocks (ticker) WHERE is_cleared = FALSE;

CREATE INDEX IF NOT EXISTS idx_reentry_blocks_ticker_verdict
    ON invest.reentry_blocks (ticker, verdict_id);
