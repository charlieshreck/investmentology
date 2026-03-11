-- Agent accuracy tracking: measure per-agent signal accuracy over time.
-- Tracks whether each agent's BUY/SELL/HOLD signals were correct at 30/90 day horizons.
-- Enables dynamic weight adjustment based on who's actually been right.

CREATE TABLE IF NOT EXISTS invest.agent_accuracy (
    id              SERIAL PRIMARY KEY,
    agent_name      TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    signal_date     DATE NOT NULL,       -- when the signal was emitted
    signal_type     TEXT NOT NULL,        -- BUY, SELL, HOLD
    confidence      REAL,                -- agent's stated confidence
    regime          TEXT,                -- market regime at signal time
    price_at_signal REAL,                -- price when signal was emitted
    price_30d       REAL,                -- price 30 days later
    price_90d       REAL,                -- price 90 days later
    return_30d      REAL,                -- computed return at 30d
    return_90d      REAL,                -- computed return at 90d
    correct_30d     BOOLEAN,             -- was the signal direction correct at 30d?
    correct_90d     BOOLEAN,             -- was the signal direction correct at 90d?
    settled_30d     BOOLEAN DEFAULT FALSE,
    settled_90d     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_accuracy_agent ON invest.agent_accuracy (agent_name, signal_date DESC);
CREATE INDEX IF NOT EXISTS idx_agent_accuracy_unsettled ON invest.agent_accuracy (settled_30d, settled_90d)
    WHERE settled_30d = FALSE OR settled_90d = FALSE;

-- Materialized view for quick per-agent accuracy stats
CREATE MATERIALIZED VIEW IF NOT EXISTS invest.agent_accuracy_stats AS
SELECT
    agent_name,
    regime,
    COUNT(*) AS total_signals,
    COUNT(*) FILTER (WHERE settled_30d) AS settled_30d,
    COUNT(*) FILTER (WHERE settled_90d) AS settled_90d,
    AVG(CASE WHEN correct_30d THEN 1.0 ELSE 0.0 END) FILTER (WHERE settled_30d) AS accuracy_30d,
    AVG(CASE WHEN correct_90d THEN 1.0 ELSE 0.0 END) FILTER (WHERE settled_90d) AS accuracy_90d,
    AVG(confidence) AS avg_confidence,
    AVG(return_30d) FILTER (WHERE settled_30d) AS avg_return_30d,
    AVG(return_90d) FILTER (WHERE settled_90d) AS avg_return_90d
FROM invest.agent_accuracy
GROUP BY agent_name, regime;

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_accuracy_stats_pk
    ON invest.agent_accuracy_stats (agent_name, regime);
