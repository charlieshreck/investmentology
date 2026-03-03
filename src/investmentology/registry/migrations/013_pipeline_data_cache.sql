-- Migration 013: Pipeline data cache table
-- Stores per-cycle fetched data (fundamentals, technical indicators, validation results)
-- so pipeline steps don't re-fetch within a cycle.

CREATE TABLE IF NOT EXISTS invest.pipeline_data_cache (
    cycle_id    UUID NOT NULL REFERENCES invest.pipeline_cycles(id) ON DELETE CASCADE,
    ticker      TEXT NOT NULL,
    data_key    TEXT NOT NULL,
    data_value  JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (cycle_id, ticker, data_key)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_data_cache_ticker
    ON invest.pipeline_data_cache (cycle_id, ticker);
