-- 005: Stock profiles — business info cache from yfinance
BEGIN;

CREATE TABLE IF NOT EXISTS invest.stock_profiles (
    ticker              TEXT PRIMARY KEY REFERENCES invest.stocks(ticker),
    sector              TEXT,
    industry            TEXT,
    business_summary    TEXT,
    website             TEXT,
    employees           INTEGER,
    city                TEXT,
    country             TEXT,
    beta                NUMERIC,
    dividend_yield      NUMERIC,
    trailing_pe         NUMERIC,
    forward_pe          NUMERIC,
    price_to_book       NUMERIC,
    price_to_sales      NUMERIC,
    fifty_two_week_high NUMERIC,
    fifty_two_week_low  NUMERIC,
    average_volume      BIGINT,
    analyst_target      NUMERIC,
    analyst_recommendation TEXT,
    analyst_count       INTEGER,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_profiles_updated
    ON invest.stock_profiles (updated_at);

-- Also update stocks table sector/industry from profiles
-- (will be done in application code)

INSERT INTO invest.migrations (filename) VALUES ('005_stock_profiles.sql')
ON CONFLICT DO NOTHING;

COMMIT;
