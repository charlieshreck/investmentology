Weekly portfolio review. Run the weekly investment review process.

Steps:
1. Pull current paper portfolio positions and P&L from Alpaca (or local tracking)
2. Check for any settled predictions in the Decision Registry
3. Run the Quant Gate to identify new candidates
4. Review watchlist items for entry triggers
5. Check portfolio concentration and correlation
6. Generate weekly summary:

```
=== Weekly Review: YYYY-MM-DD ===

Portfolio Performance:
- Total P&L: +X.XX%
- vs S&P 500: +/-X.XX%
- Sharpe Ratio: X.XX

Settled Predictions: N
- Correct: X (XX%)
- Incorrect: X (XX%)

New Candidates: N from Quant Gate
Watchlist Triggers: N items approaching entry

Actions Required:
- [ ] Review candidate: TICKER1
- [ ] Settle prediction: TICKER2
```

Log the review itself as a decision in the Registry.
