-- Push notification subscriptions (Web Push API)
CREATE TABLE IF NOT EXISTS invest.push_subscriptions (
    id SERIAL PRIMARY KEY,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
