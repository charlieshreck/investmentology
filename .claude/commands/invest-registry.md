Decision Registry operations. Manage the investment decision log.

Operations (pass as $ARGUMENTS or select interactively):
- `log` - Log a new decision (analysis, trade, rejection, or missed opportunity)
- `review` - Review recent decisions and their outcomes
- `calibrate` - Check prediction calibration (are 70% confidence calls correct 70% of the time?)
- `settle` - Settle predictions that have reached their settlement date
- `stats` - Show decision registry statistics

For logging, capture:
- Ticker + timestamp
- Decision type: EXECUTE | WATCHLIST | REJECT | MISSED
- Confidence score (0.0-1.0)
- Rationale (structured)
- Falsifiable prediction with settlement date
- Data sources used

For calibration, group decisions by confidence bucket (0.5-0.6, 0.6-0.7, etc.) and compare predicted vs actual accuracy.

Data location: `src/investmentology/learning/`
