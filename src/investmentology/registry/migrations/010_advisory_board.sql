-- 010_advisory_board.sql
-- Add Advisory Board (L5.5) and CIO Synthesis (L6) columns to verdicts

BEGIN;

ALTER TABLE invest.verdicts
    ADD COLUMN IF NOT EXISTS advisory_opinions    JSONB,
    ADD COLUMN IF NOT EXISTS board_narrative       JSONB,
    ADD COLUMN IF NOT EXISTS board_adjusted_verdict TEXT;

INSERT INTO invest.migrations (filename) VALUES ('010_advisory_board.sql');

COMMIT;
