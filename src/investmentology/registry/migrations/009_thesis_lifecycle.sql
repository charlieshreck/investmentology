-- Thesis lifecycle memory system: events, diffs, snapshots, risk tracking
-- Phase 3 of the Thesis Lifecycle Memory System plan

-- Thesis events: immutable audit trail for thesis lifecycle
CREATE TABLE IF NOT EXISTS invest.thesis_events (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- ENTRY, REAFFIRM, CHALLENGE, BREAK, CLOSE, UPDATE
    thesis_text TEXT,
    thesis_type TEXT DEFAULT 'growth',  -- growth, income, value, momentum, contrarian
    thesis_state TEXT DEFAULT 'ACTIVE', -- PROPOSED, ACTIVE, MONITORING, DRIFTING, BROKEN, ARCHIVED
    break_conditions JSONB,  -- what would invalidate the thesis
    investment_horizon TEXT,  -- "1-3 years", "3-6 months", etc.
    position_type TEXT,
    verdict_at_time TEXT,
    confidence_at_time NUMERIC(4,3),
    fair_value_at_time NUMERIC(12,2),
    price_at_time NUMERIC(12,2),
    market_regime TEXT,  -- from market_snapshots or pendulum
    market_snapshot JSONB,  -- SPY, VIX, yields at event time
    agent_stances JSONB,  -- per-agent stance snapshot
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_thesis_events_ticker ON invest.thesis_events(ticker, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_thesis_events_type ON invest.thesis_events(event_type);

-- Verdict diffs: track every verdict change with drivers and gating info
CREATE TABLE IF NOT EXISTS invest.verdict_diffs (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    old_verdict TEXT NOT NULL,
    new_verdict TEXT NOT NULL,
    old_confidence NUMERIC(4,3),
    new_confidence NUMERIC(4,3),
    change_drivers JSONB,  -- which agents changed, what signals shifted
    was_gated BOOLEAN DEFAULT FALSE,  -- true if thesis filter blocked the change
    gating_reason TEXT,
    position_type TEXT,
    thesis_health TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_verdict_diffs_ticker ON invest.verdict_diffs(ticker, created_at DESC);

-- Decision snapshots: process metadata for every analysis decision
CREATE TABLE IF NOT EXISTS invest.decision_snapshots (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    verdict TEXT NOT NULL,
    confidence NUMERIC(4,3),
    consensus_score NUMERIC(6,3),
    position_type TEXT,
    thesis_health TEXT,
    market_snapshot JSONB,  -- SPY, VIX, yields at decision time
    agent_stances JSONB,
    was_gated BOOLEAN DEFAULT FALSE,
    gating_reason TEXT,
    process_metadata JSONB,  -- timing, token usage, model versions
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_decision_snapshots_ticker ON invest.decision_snapshots(ticker, created_at DESC);

-- Portfolio risk snapshots: periodic portfolio-level risk state
CREATE TABLE IF NOT EXISTS invest.portfolio_risk_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    total_value NUMERIC(14,2),
    position_count INT,
    portfolio_drawdown_pct NUMERIC(6,3),  -- from high-water mark
    high_water_mark NUMERIC(14,2),
    sector_concentration JSONB,  -- {sector: pct} map
    top_position_weight NUMERIC(6,3),
    avg_thesis_health NUMERIC(4,3),  -- avg health score across positions
    risk_level TEXT DEFAULT 'NORMAL',  -- NORMAL, ELEVATED, HIGH, CRITICAL
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_portfolio_risk_date ON invest.portfolio_risk_snapshots(snapshot_date DESC);

-- Add thesis lifecycle columns to portfolio_positions
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS entry_thesis TEXT;
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS thesis_jsonb JSONB;
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS thesis_type TEXT DEFAULT 'growth';
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS investment_horizon TEXT;
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS thesis_health TEXT DEFAULT 'INTACT';
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS thesis_state TEXT DEFAULT 'ACTIVE';
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS highest_price_since_entry NUMERIC(12,2);
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS yield_on_cost NUMERIC(6,4);
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS user_thesis_note TEXT;
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS cooling_off_until TIMESTAMPTZ;

-- Add market context to predictions for benchmarking
ALTER TABLE invest.predictions ADD COLUMN IF NOT EXISTS price_at_prediction NUMERIC(12,2);
ALTER TABLE invest.predictions ADD COLUMN IF NOT EXISTS sp500_at_prediction NUMERIC(12,2);
ALTER TABLE invest.predictions ADD COLUMN IF NOT EXISTS vix_at_prediction NUMERIC(8,2);

-- Add market snapshot ID reference to verdicts for context
ALTER TABLE invest.verdicts ADD COLUMN IF NOT EXISTS market_snapshot_id INT;
ALTER TABLE invest.verdicts ADD COLUMN IF NOT EXISTS position_type TEXT;
ALTER TABLE invest.verdicts ADD COLUMN IF NOT EXISTS thesis_health TEXT;
ALTER TABLE invest.verdicts ADD COLUMN IF NOT EXISTS was_gated BOOLEAN DEFAULT FALSE;
ALTER TABLE invest.verdicts ADD COLUMN IF NOT EXISTS gating_reason TEXT;
