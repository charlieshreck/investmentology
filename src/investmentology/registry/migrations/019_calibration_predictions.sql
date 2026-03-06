-- Migration 019: Calibration predictions table for verdict feedback loop
-- Records every verdict with a price snapshot for later settlement

CREATE TABLE IF NOT EXISTS invest.calibration_predictions (
    id                  SERIAL PRIMARY KEY,
    ticker              TEXT NOT NULL,
    verdict_date        DATE NOT NULL,
    verdict             TEXT NOT NULL,
    sentiment           NUMERIC,
    confidence          NUMERIC,
    price_at_verdict    NUMERIC NOT NULL,
    -- Per-agent contributions snapshot (JSONB array)
    agent_contributions JSONB,
    -- Position type at time of verdict
    position_type       TEXT,
    -- Regime at time of verdict
    regime_label        TEXT,
    -- Settlement fields (filled later)
    settled_30d         BOOLEAN DEFAULT FALSE,
    price_30d           NUMERIC,
    return_30d          NUMERIC,
    correct_30d         BOOLEAN,
    settled_90d         BOOLEAN DEFAULT FALSE,
    price_90d           NUMERIC,
    return_90d          NUMERIC,
    correct_90d         BOOLEAN,
    settled_180d        BOOLEAN DEFAULT FALSE,
    price_180d          NUMERIC,
    return_180d         NUMERIC,
    correct_180d        BOOLEAN,
    settled_365d        BOOLEAN DEFAULT FALSE,
    price_365d          NUMERIC,
    return_365d         NUMERIC,
    correct_365d        BOOLEAN,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cal_pred_ticker ON invest.calibration_predictions(ticker);
CREATE INDEX IF NOT EXISTS idx_cal_pred_verdict_date ON invest.calibration_predictions(verdict_date);
CREATE INDEX IF NOT EXISTS idx_cal_pred_unsettled_30d ON invest.calibration_predictions(settled_30d) WHERE settled_30d = FALSE;
CREATE INDEX IF NOT EXISTS idx_cal_pred_unsettled_90d ON invest.calibration_predictions(settled_90d) WHERE settled_90d = FALSE;

-- Per-agent calibration (for isotonic regression data)
CREATE TABLE IF NOT EXISTS invest.agent_calibration_data (
    id                  SERIAL PRIMARY KEY,
    agent_name          TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    verdict_date        DATE NOT NULL,
    raw_confidence      NUMERIC NOT NULL,
    sentiment           NUMERIC,
    price_at_verdict    NUMERIC NOT NULL,
    -- Settlement
    settled             BOOLEAN DEFAULT FALSE,
    actual_return_90d   NUMERIC,
    was_correct         BOOLEAN,
    settled_at          DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_cal_agent ON invest.agent_calibration_data(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_cal_unsettled ON invest.agent_calibration_data(settled) WHERE settled = FALSE;
