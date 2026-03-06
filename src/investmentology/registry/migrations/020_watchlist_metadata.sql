-- Migration 020: Add structured watchlist metadata columns
-- Stores blocking factors, graduation criteria, and target entry price
-- so the PWA can display WHY a ticker is on the watchlist and WHAT it needs

ALTER TABLE invest.watchlist ADD COLUMN IF NOT EXISTS reason TEXT;
ALTER TABLE invest.watchlist ADD COLUMN IF NOT EXISTS blocking_factors JSONB DEFAULT '[]';
ALTER TABLE invest.watchlist ADD COLUMN IF NOT EXISTS graduation_criteria JSONB DEFAULT '[]';
ALTER TABLE invest.watchlist ADD COLUMN IF NOT EXISTS target_entry_price NUMERIC;
ALTER TABLE invest.watchlist ADD COLUMN IF NOT EXISTS next_catalyst_date DATE;
ALTER TABLE invest.watchlist ADD COLUMN IF NOT EXISTS qg_rank INTEGER;
ALTER TABLE invest.watchlist ADD COLUMN IF NOT EXISTS last_verdict_id INTEGER;
