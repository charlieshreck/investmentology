-- Add composite_score column to quant_gate_results
-- Composite = weighted blend of Greenblatt rank percentile, Piotroski, and Altman Z
ALTER TABLE invest.quant_gate_results
    ADD COLUMN IF NOT EXISTS composite_score NUMERIC;

-- Add altman_zone for convenience
ALTER TABLE invest.quant_gate_results
    ADD COLUMN IF NOT EXISTS altman_zone TEXT;

-- Index for sorting by composite score within a run
CREATE INDEX IF NOT EXISTS idx_qg_results_composite
    ON invest.quant_gate_results (run_id, composite_score DESC);
