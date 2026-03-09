-- Migration 021: Quant gate historical backtest results
-- Stores factor IC, quintile returns, top-N vs SPY, and regime analysis
-- Separate from invest.backtests (which stores pipeline replay results)

CREATE TABLE IF NOT EXISTS invest.quant_backtest_runs (
    id              SERIAL PRIMARY KEY,
    run_mode        TEXT NOT NULL DEFAULT 'post_fix',
    screen_years    INTEGER[] NOT NULL,
    ic_data         JSONB NOT NULL DEFAULT '{}',
    quintile_data   JSONB NOT NULL DEFAULT '{}',
    top_n_data      JSONB NOT NULL DEFAULT '{}',
    regime_data     JSONB NOT NULL DEFAULT '{}',
    ticker_details  JSONB NOT NULL DEFAULT '[]',
    summary         JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_qbt_runs_created
    ON invest.quant_backtest_runs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_qbt_runs_mode
    ON invest.quant_backtest_runs (run_mode, created_at DESC);

INSERT INTO invest.migrations (filename) VALUES ('021_quant_backtest')
ON CONFLICT (filename) DO NOTHING;
