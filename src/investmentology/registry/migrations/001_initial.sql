-- 001_initial.sql
-- Investmentology: Full PostgreSQL schema
-- Creates all tables for the 6-layer investment pipeline

BEGIN;

-- ============================================================
-- 0. SCHEMA
-- ============================================================
CREATE SCHEMA IF NOT EXISTS invest;

-- ============================================================
-- 1. ENUM TYPES
-- ============================================================

-- ~102 signal tags across 6 categories
CREATE TYPE invest.signal_tag AS ENUM (
    -- Fundamental (19)
    'UNDERVALUED', 'OVERVALUED', 'FAIRLY_VALUED', 'DEEP_VALUE',
    'MOAT_WIDENING', 'MOAT_STABLE', 'MOAT_NARROWING', 'NO_MOAT',
    'EARNINGS_QUALITY_HIGH', 'EARNINGS_QUALITY_LOW',
    'REVENUE_ACCELERATING', 'REVENUE_DECELERATING',
    'MARGIN_EXPANDING', 'MARGIN_COMPRESSING',
    'BALANCE_SHEET_STRONG', 'BALANCE_SHEET_WEAK',
    'DIVIDEND_GROWING', 'BUYBACK_ACTIVE', 'MANAGEMENT_ALIGNED',
    -- Macro/Cycle (21)
    'REGIME_BULL', 'REGIME_BEAR', 'REGIME_NEUTRAL', 'REGIME_TRANSITION',
    'SECTOR_ROTATION_INTO', 'SECTOR_ROTATION_OUT',
    'CREDIT_TIGHTENING', 'CREDIT_EASING',
    'RATE_RISING', 'RATE_FALLING',
    'INFLATION_HIGH', 'INFLATION_LOW',
    'DOLLAR_STRONG', 'DOLLAR_WEAK',
    'GEOPOLITICAL_RISK', 'SUPPLY_CHAIN_DISRUPTION',
    'FISCAL_STIMULUS', 'FISCAL_CONTRACTION',
    'LIQUIDITY_ABUNDANT', 'LIQUIDITY_TIGHT',
    'REFLEXIVITY_DETECTED',
    -- Technical/Timing (19)
    'TREND_UPTREND', 'TREND_DOWNTREND', 'TREND_SIDEWAYS',
    'MOMENTUM_STRONG', 'MOMENTUM_WEAK', 'MOMENTUM_DIVERGENCE',
    'BREAKOUT_CONFIRMED', 'BREAKDOWN_CONFIRMED',
    'SUPPORT_NEAR', 'RESISTANCE_NEAR',
    'VOLUME_SURGE', 'VOLUME_DRY', 'VOLUME_CLIMAX',
    'RSI_OVERSOLD', 'RSI_OVERBOUGHT',
    'GOLDEN_CROSS', 'DEATH_CROSS',
    'RELATIVE_STRENGTH_HIGH', 'RELATIVE_STRENGTH_LOW',
    -- Risk/Portfolio (14)
    'CONCENTRATION', 'CORRELATION_HIGH', 'CORRELATION_LOW',
    'LIQUIDITY_LOW', 'LIQUIDITY_OK',
    'DRAWDOWN_RISK', 'ACCOUNTING_RED_FLAG', 'GOVERNANCE_CONCERN',
    'LEVERAGE_HIGH', 'LEVERAGE_OK',
    'VOLATILITY_HIGH', 'VOLATILITY_LOW',
    'SECTOR_OVERWEIGHT', 'SECTOR_UNDERWEIGHT',
    -- Special Situation (11)
    'SPINOFF_ANNOUNCED', 'MERGER_TARGET',
    'INSIDER_CLUSTER_BUY', 'INSIDER_CLUSTER_SELL',
    'ACTIVIST_INVOLVED', 'MANAGEMENT_CHANGE', 'REGULATORY_CHANGE',
    'PATENT_CATALYST', 'EARNINGS_SURPRISE',
    'GUIDANCE_RAISED', 'GUIDANCE_LOWERED',
    -- Decision/Action (18)
    'BUY_NEW', 'BUY_ADD', 'TRIM', 'SELL_FULL', 'SELL_PARTIAL',
    'HOLD', 'HOLD_STRONG',
    'WATCHLIST_ADD', 'WATCHLIST_REMOVE', 'WATCHLIST_PROMOTE',
    'REJECT', 'REJECT_HARD',
    'CONFLICT_FLAG', 'REVIEW_REQUIRED',
    'MUNGER_PROCEED', 'MUNGER_CAUTION', 'MUNGER_VETO',
    'NO_ACTION'
);

CREATE TYPE invest.watchlist_state AS ENUM (
    'UNIVERSE', 'CANDIDATE', 'ASSESSED',
    'CONVICTION_BUY', 'WATCHLIST_EARLY', 'WATCHLIST_CATALYST',
    'REJECTED', 'CONFLICT_REVIEW',
    'POSITION_HOLD', 'POSITION_TRIM', 'POSITION_SELL'
);

CREATE TYPE invest.decision_type AS ENUM (
    'SCREEN', 'COMPETENCE_PASS', 'COMPETENCE_FAIL',
    'AGENT_ANALYSIS', 'PATTERN_MATCH', 'ADVERSARIAL_REVIEW',
    'BUY', 'SELL', 'TRIM', 'HOLD', 'REJECT', 'WATCHLIST'
);

CREATE TYPE invest.decision_outcome AS ENUM (
    'PENDING', 'CORRECT', 'WRONG', 'PARTIAL', 'EXPIRED', 'CANCELLED'
);

CREATE TYPE invest.trigger_type AS ENUM (
    'PRICE_TARGET', 'VIX_LEVEL', 'SECTOR_ROTATION',
    'EARNINGS_DATE', 'FDA_APPROVAL', 'CATALYST_GENERIC', 'TIME_EXPIRY'
);

CREATE TYPE invest.sell_reason AS ENUM (
    'STOP_LOSS', 'TRAILING_STOP', 'THESIS_BREAK', 'OVERVALUED',
    'TIME_STOP', 'GREENBLATT_ROTATION', 'CIRCUIT_BREAKER', 'MANUAL'
);

-- ============================================================
-- 2. MIGRATION TRACKING
-- ============================================================
CREATE TABLE invest.migrations (
    id          SERIAL PRIMARY KEY,
    filename    TEXT NOT NULL UNIQUE,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 3. CORE TABLES
-- ============================================================
CREATE TABLE invest.stocks (
    ticker      TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    sector      TEXT,
    industry    TEXT,
    market_cap  NUMERIC,
    exchange    TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE invest.fundamentals_cache (
    id                   SERIAL PRIMARY KEY,
    ticker               TEXT NOT NULL REFERENCES invest.stocks(ticker),
    fetched_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    operating_income     NUMERIC,
    market_cap           NUMERIC,
    total_debt           NUMERIC,
    cash                 NUMERIC,
    current_assets       NUMERIC,
    current_liabilities  NUMERIC,
    net_ppe              NUMERIC,
    revenue              NUMERIC,
    net_income           NUMERIC,
    total_assets         NUMERIC,
    total_liabilities    NUMERIC,
    shares_outstanding   NUMERIC,
    price                NUMERIC,
    -- GENERATED columns for derived metrics
    enterprise_value     NUMERIC GENERATED ALWAYS AS (market_cap + total_debt - cash) STORED,
    earnings_yield       NUMERIC GENERATED ALWAYS AS (
        CASE WHEN (market_cap + total_debt - cash) > 0
             THEN operating_income / (market_cap + total_debt - cash)
             ELSE NULL
        END
    ) STORED,
    roic                 NUMERIC GENERATED ALWAYS AS (
        CASE WHEN ((current_assets - current_liabilities) + net_ppe) > 0
             THEN operating_income / ((current_assets - current_liabilities) + net_ppe)
             ELSE NULL
        END
    ) STORED,
    net_working_capital  NUMERIC GENERATED ALWAYS AS (current_assets - current_liabilities) STORED
);

-- ============================================================
-- 4. L1 TABLES — Quant Gate (Greenblatt Magic Formula)
-- ============================================================
CREATE TABLE invest.quant_gate_runs (
    id            SERIAL PRIMARY KEY,
    run_date      DATE NOT NULL,
    universe_size INTEGER NOT NULL,
    passed_count  INTEGER NOT NULL,
    config        JSONB,
    data_quality  JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE invest.quant_gate_results (
    id              SERIAL PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES invest.quant_gate_runs(id),
    ticker          TEXT NOT NULL REFERENCES invest.stocks(ticker),
    earnings_yield  NUMERIC,
    roic            NUMERIC,
    ey_rank         INTEGER,
    roic_rank       INTEGER,
    combined_rank   INTEGER,
    piotroski_score INTEGER,
    altman_z_score  NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 5. WATCHLIST TABLES
-- ============================================================
CREATE TABLE invest.watchlist (
    id            SERIAL PRIMARY KEY,
    ticker        TEXT NOT NULL REFERENCES invest.stocks(ticker),
    state         invest.watchlist_state NOT NULL,
    source_run_id INTEGER REFERENCES invest.quant_gate_runs(id),
    entered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes         TEXT
);

CREATE TABLE invest.watchlist_triggers (
    id            SERIAL PRIMARY KEY,
    watchlist_id  INTEGER NOT NULL REFERENCES invest.watchlist(id),
    trigger_type  invest.trigger_type NOT NULL,
    trigger_value JSONB NOT NULL,
    is_fired      BOOLEAN NOT NULL DEFAULT FALSE,
    fired_at      TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 6. DECISION REGISTRY — Partitioned by created_at
-- ============================================================
CREATE TABLE invest.decisions (
    id            SERIAL,
    ticker        TEXT NOT NULL,
    decision_type invest.decision_type NOT NULL,
    layer_source  TEXT NOT NULL,
    confidence    NUMERIC(4,3),
    reasoning     TEXT,
    signals       JSONB,
    metadata      JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Partitions: 2025 Q1–Q4, 2026 Q1–Q4
CREATE TABLE invest.decisions_2025_q1 PARTITION OF invest.decisions
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE invest.decisions_2025_q2 PARTITION OF invest.decisions
    FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE invest.decisions_2025_q3 PARTITION OF invest.decisions
    FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE invest.decisions_2025_q4 PARTITION OF invest.decisions
    FOR VALUES FROM ('2025-10-01') TO ('2026-01-01');
CREATE TABLE invest.decisions_2026_q1 PARTITION OF invest.decisions
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');
CREATE TABLE invest.decisions_2026_q2 PARTITION OF invest.decisions
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');
CREATE TABLE invest.decisions_2026_q3 PARTITION OF invest.decisions
    FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');
CREATE TABLE invest.decisions_2026_q4 PARTITION OF invest.decisions
    FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');

CREATE TABLE invest.decision_outcomes (
    id           SERIAL PRIMARY KEY,
    decision_id  INTEGER NOT NULL,
    outcome      invest.decision_outcome NOT NULL,
    actual_value NUMERIC,
    notes        TEXT,
    settled_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 7. AGENT TABLES
-- ============================================================
CREATE TABLE invest.agent_signals (
    id          SERIAL PRIMARY KEY,
    ticker      TEXT NOT NULL,
    agent_name  TEXT NOT NULL,
    model       TEXT NOT NULL,
    signals     JSONB NOT NULL,
    confidence  NUMERIC(4,3),
    reasoning   TEXT,
    token_usage JSONB,
    latency_ms  INTEGER,
    run_id      INTEGER,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE invest.pattern_matches (
    id               SERIAL PRIMARY KEY,
    ticker           TEXT NOT NULL,
    pattern_name     TEXT NOT NULL,
    score            NUMERIC(4,3),
    matched_signals  JSONB,
    action           TEXT,
    agent_signals_ids INTEGER[],
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE invest.agent_disagreements (
    id           SERIAL PRIMARY KEY,
    ticker       TEXT NOT NULL,
    agent_a      TEXT NOT NULL,
    agent_b      TEXT NOT NULL,
    signal_a     TEXT NOT NULL,
    signal_b     TEXT NOT NULL,
    is_dangerous BOOLEAN NOT NULL DEFAULT FALSE,
    resolution   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 8. LEARNING TABLES
-- ============================================================
CREATE TABLE invest.predictions (
    id               SERIAL PRIMARY KEY,
    ticker           TEXT NOT NULL,
    prediction_type  TEXT NOT NULL,
    predicted_value  NUMERIC NOT NULL,
    confidence       NUMERIC(4,3),
    horizon_days     INTEGER NOT NULL,
    settlement_date  DATE NOT NULL,
    actual_value     NUMERIC,
    is_settled       BOOLEAN NOT NULL DEFAULT FALSE,
    settled_at       TIMESTAMPTZ,
    source           TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE invest.calibration_snapshots (
    id               SERIAL PRIMARY KEY,
    snapshot_date    DATE NOT NULL,
    bucket_low       NUMERIC NOT NULL,
    bucket_high      NUMERIC NOT NULL,
    prediction_count INTEGER NOT NULL,
    correct_count    INTEGER NOT NULL,
    accuracy         NUMERIC,
    ece              NUMERIC,
    brier_score      NUMERIC,
    window_days      INTEGER NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 9. PORTFOLIO
-- ============================================================
CREATE TABLE invest.portfolio_positions (
    id                  SERIAL PRIMARY KEY,
    ticker              TEXT NOT NULL REFERENCES invest.stocks(ticker),
    entry_date          DATE NOT NULL,
    entry_price         NUMERIC NOT NULL,
    current_price       NUMERIC,
    shares              NUMERIC NOT NULL,
    position_type       TEXT NOT NULL,
    weight              NUMERIC,
    stop_loss           NUMERIC,
    fair_value_estimate NUMERIC,
    thesis              TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 10. MARKET CONTEXT
-- ============================================================
CREATE TABLE invest.market_snapshots (
    id              SERIAL PRIMARY KEY,
    snapshot_date   DATE NOT NULL,
    spy_price       NUMERIC,
    qqq_price       NUMERIC,
    iwm_price       NUMERIC,
    vix             NUMERIC,
    ten_year_yield  NUMERIC,
    two_year_yield  NUMERIC,
    hy_oas          NUMERIC,
    put_call_ratio  NUMERIC,
    sector_data     JSONB,
    pendulum_score  INTEGER,
    regime_score    NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 11. ADMIN TABLES
-- ============================================================
CREATE TABLE invest.prompt_versions (
    id          SERIAL PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    version     INTEGER NOT NULL,
    prompt_text TEXT NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE invest.regime_assessments (
    id              SERIAL PRIMARY KEY,
    assessment_date DATE NOT NULL,
    regime_score    NUMERIC NOT NULL,
    regime_label    TEXT NOT NULL,
    indicators      JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE invest.pattern_performance (
    id             SERIAL PRIMARY KEY,
    pattern_name   TEXT NOT NULL,
    window_start   DATE NOT NULL,
    window_end     DATE NOT NULL,
    total_matches  INTEGER NOT NULL,
    correct        INTEGER NOT NULL,
    avg_return     NUMERIC,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE invest.system_snapshots (
    id               SERIAL PRIMARY KEY,
    snapshot_time    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    db_size_bytes    BIGINT,
    decision_count   INTEGER,
    prediction_count INTEGER,
    settled_count    INTEGER,
    position_count   INTEGER,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE invest.cron_runs (
    id          SERIAL PRIMARY KEY,
    job_name    TEXT NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status      TEXT NOT NULL,
    error       TEXT,
    metadata    JSONB
);

-- ============================================================
-- 12. INDEXES
-- ============================================================

-- decisions (partitioned — indexes apply per-partition automatically)
CREATE INDEX idx_decisions_ticker_created ON invest.decisions (ticker, created_at);
CREATE INDEX idx_decisions_layer_source   ON invest.decisions (layer_source);
CREATE INDEX idx_decisions_type           ON invest.decisions (decision_type);

-- agent_signals
CREATE INDEX idx_agent_signals_ticker_created ON invest.agent_signals (ticker, created_at);
CREATE INDEX idx_agent_signals_agent_name     ON invest.agent_signals (agent_name);

-- predictions
CREATE INDEX idx_predictions_settlement ON invest.predictions (settlement_date, is_settled);
CREATE INDEX idx_predictions_ticker     ON invest.predictions (ticker);

-- quant_gate_results
CREATE INDEX idx_qg_results_run_rank ON invest.quant_gate_results (run_id, combined_rank);

-- watchlist
CREATE INDEX idx_watchlist_state  ON invest.watchlist (state);
CREATE INDEX idx_watchlist_ticker ON invest.watchlist (ticker);

-- portfolio_positions
CREATE INDEX idx_portfolio_ticker ON invest.portfolio_positions (ticker);

-- fundamentals_cache
CREATE INDEX idx_fundamentals_ticker_fetched ON invest.fundamentals_cache (ticker, fetched_at);

-- market_snapshots
CREATE INDEX idx_market_snapshots_date ON invest.market_snapshots (snapshot_date);

-- cron_runs
CREATE INDEX idx_cron_runs_job_started ON invest.cron_runs (job_name, started_at);

-- ============================================================
-- 13. RECORD THIS MIGRATION
-- ============================================================
INSERT INTO invest.migrations (filename) VALUES ('001_initial.sql');

COMMIT;
