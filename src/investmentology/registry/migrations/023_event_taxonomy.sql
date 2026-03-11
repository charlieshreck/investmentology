-- Event taxonomy: historical corporate event outcomes for agent context.
-- Tracks event types with statistical outcome data so agents can ground
-- qualitative events in quantitative historical precedent.

CREATE TABLE IF NOT EXISTS invest.event_taxonomy (
    id              SERIAL PRIMARY KEY,
    event_category  TEXT NOT NULL,       -- leadership, capital, regulatory, financial, strategic, market
    event_type      TEXT NOT NULL,       -- ceo_departure, buyback_announced, fda_approval, etc.
    sector          TEXT,                -- sector-specific stats (NULL = all sectors)
    avg_return_30d  REAL,                -- average return 30 days post-event
    avg_return_90d  REAL,                -- average return 90 days post-event
    avg_return_180d REAL,                -- average return 180 days post-event
    win_rate_30d    REAL,                -- % positive outcomes at 30d
    win_rate_90d    REAL,                -- % positive outcomes at 90d
    n_observations  INT DEFAULT 0,       -- number of historical observations
    std_dev_30d     REAL,                -- standard deviation of 30d returns
    description     TEXT,                -- human-readable event description
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (event_category, event_type, sector)
);

-- Observed events: log each detected event for a ticker to build history
CREATE TABLE IF NOT EXISTS invest.event_log (
    id              SERIAL PRIMARY KEY,
    ticker          TEXT NOT NULL,
    event_category  TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    detected_at     TIMESTAMPTZ DEFAULT NOW(),
    price_at_event  REAL,                -- price when event detected
    price_30d       REAL,                -- price 30 days later (filled by settlement job)
    price_90d       REAL,                -- price 90 days later
    return_30d      REAL,                -- computed return
    return_90d      REAL,                -- computed return
    settled         BOOLEAN DEFAULT FALSE,
    source          TEXT,                -- news, earnings, filing, etc.
    detail          TEXT                 -- event-specific detail
);

CREATE INDEX IF NOT EXISTS idx_event_log_ticker ON invest.event_log (ticker, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_unsettled ON invest.event_log (settled) WHERE settled = FALSE;

-- Seed the taxonomy with baseline data from financial research literature
INSERT INTO invest.event_taxonomy (event_category, event_type, description, avg_return_30d, avg_return_90d, win_rate_30d, n_observations)
VALUES
    ('leadership', 'ceo_departure',        'CEO leaves (resigned/fired)',          -0.032, -0.045, 0.38, 500),
    ('leadership', 'ceo_appointment',      'New CEO announced',                     0.015,  0.028, 0.55, 400),
    ('leadership', 'cfo_departure',        'CFO leaves',                           -0.041, -0.052, 0.35, 300),
    ('leadership', 'founder_exit',         'Founder departs company',              -0.055, -0.068, 0.32, 150),
    ('capital',    'buyback_announced',    'Share buyback program announced',       0.022,  0.038, 0.62, 800),
    ('capital',    'secondary_offering',   'Secondary stock offering',             -0.048, -0.035, 0.35, 600),
    ('capital',    'dividend_increase',    'Dividend raised',                       0.012,  0.025, 0.58, 700),
    ('capital',    'dividend_cut',         'Dividend reduced or suspended',        -0.082, -0.065, 0.28, 300),
    ('capital',    'debt_restructure',     'Major debt restructuring',             -0.035, -0.015, 0.42, 200),
    ('regulatory', 'fda_approval',        'FDA drug/device approval',              0.085,  0.065, 0.72, 400),
    ('regulatory', 'fda_rejection',       'FDA rejection/CRL',                    -0.155, -0.120, 0.18, 250),
    ('regulatory', 'antitrust_action',    'Antitrust investigation/suit',         -0.045, -0.038, 0.38, 200),
    ('regulatory', 'patent_ruling',       'Major patent win/loss',                 0.025,  0.032, 0.52, 150),
    ('financial',  'earnings_beat',       'Earnings beat consensus >5%',           0.028,  0.042, 0.63, 2000),
    ('financial',  'earnings_miss',       'Earnings miss consensus >5%',          -0.055, -0.048, 0.32, 1800),
    ('financial',  'guidance_raise',      'Forward guidance raised',               0.035,  0.052, 0.65, 1000),
    ('financial',  'guidance_cut',        'Forward guidance lowered',             -0.068, -0.055, 0.28, 800),
    ('strategic',  'acquisition_announced', 'Major acquisition announced',        -0.015,  0.008, 0.45, 600),
    ('strategic',  'spinoff_announced',   'Spin-off or divestiture',               0.032,  0.055, 0.60, 300),
    ('strategic',  'activist_entry',      'Activist investor takes position',      0.045,  0.065, 0.62, 250),
    ('strategic',  'major_partnership',   'Major strategic partnership',           0.018,  0.025, 0.55, 400),
    ('market',     'index_inclusion',     'Added to major index (S&P 500, etc)',   0.042,  0.028, 0.65, 300),
    ('market',     'index_exclusion',     'Removed from major index',             -0.055, -0.042, 0.30, 200),
    ('market',     'analyst_upgrade',     'Major analyst upgrade',                 0.018,  0.022, 0.58, 1500),
    ('market',     'analyst_downgrade',   'Major analyst downgrade',              -0.025, -0.018, 0.40, 1400),
    ('market',     'short_squeeze',       'Significant short covering event',      0.085,  0.015, 0.55, 100)
ON CONFLICT (event_category, event_type, sector) DO NOTHING;
