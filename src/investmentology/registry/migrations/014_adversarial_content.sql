-- 014_adversarial_content.sql
-- Store adversarial layer output (kill scenarios, pre-mortem, bias flags)
-- Currently computed but ephemeral — this persists it alongside the verdict.

BEGIN;

ALTER TABLE invest.verdicts
    ADD COLUMN IF NOT EXISTS adversarial_result JSONB;

INSERT INTO invest.migrations (filename) VALUES ('014_adversarial_content.sql');

COMMIT;
