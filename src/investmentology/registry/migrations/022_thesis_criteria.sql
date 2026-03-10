-- Thesis invalidation criteria — forced at position entry time.
-- Every BUY must have at least one quantifiable and one qualitative criterion.

CREATE TABLE IF NOT EXISTS invest.thesis_criteria (
    id BIGSERIAL PRIMARY KEY,
    position_id INT NOT NULL REFERENCES invest.portfolio_positions(id),
    criteria_type TEXT NOT NULL,  -- roic_floor, fscore_floor, revenue_growth_floor, debt_ceiling, dividend_cut, custom_quantitative, custom_qualitative
    threshold_value NUMERIC(14,4),  -- numeric threshold (NULL for qualitative)
    qualitative_text TEXT,  -- description for qualitative criteria
    is_quantitative BOOLEAN NOT NULL DEFAULT TRUE,
    monitoring_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_checked_at TIMESTAMPTZ,
    last_status TEXT DEFAULT 'OK',  -- OK, BREACHED, WARNING
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_thesis_criteria_position ON invest.thesis_criteria(position_id);
CREATE INDEX IF NOT EXISTS idx_thesis_criteria_active ON invest.thesis_criteria(monitoring_active) WHERE monitoring_active = TRUE;

-- Add break_conditions JSONB to portfolio_positions for quick access
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS break_conditions JSONB;
