-- Migration 007: Backtests table for storing backtest run results
CREATE TABLE IF NOT EXISTS invest.backtests (
    id              SERIAL PRIMARY KEY,
    strategy_name   TEXT NOT NULL DEFAULT 'pipeline_replay',
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    initial_capital NUMERIC(14,2) NOT NULL DEFAULT 100000,
    total_return    NUMERIC(8,2),
    sharpe_ratio    NUMERIC(6,2),
    max_drawdown    NUMERIC(8,2),
    win_rate        NUMERIC(5,1),
    total_trades    INTEGER DEFAULT 0,
    result_json     JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtests_created ON invest.backtests (created_at DESC);

INSERT INTO invest.migrations (filename) VALUES ('007_backtests')
ON CONFLICT (filename) DO NOTHING;
