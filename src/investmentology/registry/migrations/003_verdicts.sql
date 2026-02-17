-- 003_verdicts.sql
-- Verdict synthesizer results — the final computed recommendation

BEGIN;

CREATE TABLE invest.verdicts (
    id               SERIAL PRIMARY KEY,
    ticker           TEXT NOT NULL,
    verdict          TEXT NOT NULL,
    confidence       NUMERIC(4,3),
    consensus_score  NUMERIC(4,3),
    reasoning        TEXT,
    agent_stances    JSONB,
    risk_flags       JSONB,
    auditor_override BOOLEAN NOT NULL DEFAULT FALSE,
    munger_override  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_verdicts_ticker_created ON invest.verdicts (ticker, created_at DESC);
CREATE INDEX idx_verdicts_verdict ON invest.verdicts (verdict);

INSERT INTO invest.migrations (filename) VALUES ('003_verdicts.sql');

COMMIT;
