-- Buzz scores: news volume + sentiment tracking per ticker
CREATE TABLE IF NOT EXISTS invest.buzz_scores (
    id SERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    scored_at TIMESTAMPTZ DEFAULT NOW(),
    news_count_7d INT DEFAULT 0,
    news_count_30d INT DEFAULT 0,
    headline_sentiment FLOAT DEFAULT 0.0,  -- -1.0 to 1.0
    buzz_score FLOAT DEFAULT 0.0,           -- 0-100 normalized
    buzz_label TEXT DEFAULT 'QUIET',         -- QUIET / NORMAL / ELEVATED / HIGH
    contrarian_flag BOOLEAN DEFAULT FALSE,   -- low buzz + high fundamental score
    details JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_buzz_scores_ticker ON invest.buzz_scores (ticker, scored_at DESC);

-- Earnings revision snapshots: track EPS estimate changes over time
CREATE TABLE IF NOT EXISTS invest.earnings_revisions (
    id SERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    period TEXT NOT NULL,                    -- e.g. "2026-03-31"
    eps_estimate FLOAT,
    revenue_estimate FLOAT,
    actual_eps FLOAT,
    surprise_pct FLOAT,
    source TEXT DEFAULT 'finnhub'
);

CREATE INDEX IF NOT EXISTS idx_earnings_revisions_ticker ON invest.earnings_revisions (ticker, period, captured_at DESC);

-- Earnings revision momentum: computed summary
CREATE TABLE IF NOT EXISTS invest.earnings_momentum (
    id SERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    revision_count_90d INT DEFAULT 0,
    upward_revisions INT DEFAULT 0,
    downward_revisions INT DEFAULT 0,
    momentum_score FLOAT DEFAULT 0.0,       -- -1.0 to 1.0
    momentum_label TEXT DEFAULT 'STABLE',    -- DECLINING / STABLE / IMPROVING / STRONG_UPWARD
    latest_eps_estimate FLOAT,
    beat_streak INT DEFAULT 0               -- consecutive beats
);

CREATE INDEX IF NOT EXISTS idx_earnings_momentum_ticker ON invest.earnings_momentum (ticker, computed_at DESC);
