-- Add unique constraint on snapshot_date (missing from 009)
-- Required for ON CONFLICT upsert in DrawdownEngine.save_snapshot()
ALTER TABLE invest.portfolio_risk_snapshots
  ADD CONSTRAINT portfolio_risk_snapshots_date_uq UNIQUE (snapshot_date);
