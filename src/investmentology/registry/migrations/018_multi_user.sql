-- Migration 018: Multi-user support
-- Adds users table and user_id foreign keys to user-scoped tables.
-- user_id is nullable for backward compatibility — NULL = legacy/default user.

CREATE TABLE IF NOT EXISTS invest.users (
    id              SERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    display_name    TEXT NOT NULL DEFAULT '',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Add user_id to user-scoped tables (nullable for backward compat)
ALTER TABLE invest.portfolio_positions ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES invest.users(id);
ALTER TABLE invest.portfolio_budget ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES invest.users(id);
ALTER TABLE invest.decisions ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES invest.users(id);
ALTER TABLE invest.watchlist ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES invest.users(id);
ALTER TABLE invest.predictions ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES invest.users(id);
ALTER TABLE invest.push_subscriptions ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES invest.users(id);
ALTER TABLE invest.backtests ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES invest.users(id);

CREATE INDEX IF NOT EXISTS idx_users_email ON invest.users (email);
CREATE INDEX IF NOT EXISTS idx_positions_user ON invest.portfolio_positions (user_id);
CREATE INDEX IF NOT EXISTS idx_decisions_user ON invest.decisions (user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_user ON invest.watchlist (user_id);

INSERT INTO invest.migrations (filename) VALUES ('018_multi_user')
ON CONFLICT (filename) DO NOTHING;
