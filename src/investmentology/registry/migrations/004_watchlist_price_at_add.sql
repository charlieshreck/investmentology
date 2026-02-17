-- Migration 004: Add price_at_add to watchlist for tracking entry price.
ALTER TABLE invest.watchlist ADD COLUMN IF NOT EXISTS price_at_add NUMERIC;

-- Backfill from the fundamentals snapshot closest to watchlist entry time.
UPDATE invest.watchlist w
SET price_at_add = sub.price
FROM (
    SELECT DISTINCT ON (fc.ticker)
        fc.ticker, fc.price
    FROM invest.fundamentals_cache fc
    INNER JOIN invest.watchlist w2 ON w2.ticker = fc.ticker
    WHERE fc.price IS NOT NULL AND fc.price > 0
    ORDER BY fc.ticker, fc.fetched_at DESC
) sub
WHERE w.ticker = sub.ticker
  AND w.price_at_add IS NULL;
