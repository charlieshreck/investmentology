-- 006: Portfolio position closing — add exit/P&L tracking fields
BEGIN;

ALTER TABLE invest.portfolio_positions
    ADD COLUMN IF NOT EXISTS exit_date DATE,
    ADD COLUMN IF NOT EXISTS exit_price NUMERIC,
    ADD COLUMN IF NOT EXISTS is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS realized_pnl NUMERIC;

CREATE INDEX IF NOT EXISTS idx_portfolio_is_closed
    ON invest.portfolio_positions (is_closed);

INSERT INTO invest.migrations (filename) VALUES ('006_portfolio_close.sql')
ON CONFLICT DO NOTHING;

COMMIT;
