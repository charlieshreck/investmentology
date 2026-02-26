# Investmentology Platform Audit — 2026-02-26

Finance team synthesis of all platform improvements needed.
Stock-specific actions omitted — this is about systemic function.

## A. PORTFOLIO CONSTRUCTION RULES (Enforce Automatically)

### Position Limits
| Rule | Value |
|------|-------|
| Max single position | 20% of portfolio |
| Max single sector | 25% of portfolio |
| Mandatory stop loss | Every position (core: 15-20% trailing, permanent: 25% catastrophic) |
| Max core entry size | 12-15% |
| Explorer/starter position | 1-3% |
| Min positions for full deployment | 8-12 |

### Rebalancing Policy
- Trigger when any position drifts >5% from target weight
- Monthly review, quarterly mandatory rebalance
- Trim overweight, add to underweight from highest-conviction recs

### Portfolio-Level Risk Limits
- Max drawdown trigger: if portfolio drops 10% from peak, reduce all positions by 25%
- Correlation alert: flag when 2+ held positions have >0.7 correlation
- Trailing stop upgrade: after +10% raise stop to breakeven, after +20% lock in 10%

### Cash Deployment Protocol
- Cash >15%: deploy to highest-conviction recs at 2-3% starters
- Cash 10-15%: normal, deploy selectively
- Cash <10%: pause new entries
- Cash <5%: consider trimming weakest position

## B. SCORING & METHODOLOGY FIXES

### Sell Signal Asymmetry
- BUY confidence avg 0.655 vs SELL avg 0.420 — system is biased to hold
- Fix: sell-side confidence multiplier (1.3-1.5x) so SELL at raw 0.42 becomes 0.55-0.63

### Auditor Override Audit (40.1% rate)
- Track next 30 overrides: original verdict vs modified vs actual price outcome at 30/60/90 days
- Determine if overrides add or destroy value, adjust veto power accordingly

### Verdict Stability Score
- Last 3 verdicts all same direction = STABLE (1.0)
- 2/3 same direction = MODERATE (0.67)
- Alternating = UNSTABLE (0.33)
- Only act on STABLE verdicts. UNSTABLE requires human review.

### Consensus Score as Filter (avg is -0.015, nearly useless as aggregate)
- Positive verdict + consensus >0.3 = high conviction → full size
- Positive verdict + consensus -0.2 to +0.2 = mixed → starter only
- Positive verdict + consensus <-0.2 = contrarian → flag for review

### Competence Pre-Filter
- 83 risk flags are "Outside Circle of Competence"
- After L2: hard-reject competence score <0.4 before L3 agents waste compute

### Disposition Effect Tracking
- Track avg hold time for winners vs losers
- Rule: no position held at loss longer than 2x avg winner hold time without re-eval

## C. MEASUREMENT & CALIBRATION

### Performance Benchmarking
- Total return vs SPY same period (daily)
- Sharpe ratio, Sortino ratio (monthly)
- Max drawdown (continuous)
- Win rate, avg win/avg loss, expectancy (per trade)
- Alpha above benchmark (monthly)

### Prediction Settlement Tracking
- Every verdict should include expected price + settlement date (30/60/90 days)
- Track calibration: are 70% confidence predictions correct 70% of the time?
- Need 50+ settled predictions before calibration conclusions
- This is the foundation of Learning Layer (L6) — currently non-functional with n=1

### Override Outcome Tracking
- Log original verdict + modified verdict + outcome for both Auditor and Munger overrides
- After 30 data points per category: compute value added/destroyed

## D. DATA & SIGNAL EXPANSION

### Free Data Sources to Add
| Source | Data | Use Case | Priority |
|--------|------|----------|----------|
| FRED API | Fed Funds, CPI, PMI, yield curve, credit spreads | Soros macro inputs, Pendulum Reader | HIGH |
| SEC EDGAR Form 4 | Insider buying/selling | Conviction signal | HIGH |
| Earnings calendar | Report dates, estimate revisions | Event-driven positioning | HIGH |
| SearXNG/Reddit | Social mention frequency | Buzz score (contrarian) | HIGH |
| SEC EDGAR 13F | Institutional holdings | Smart money flow | MEDIUM |
| Yahoo options | Put/call ratios, implied vol | Per-stock fear gauge | MEDIUM |
| Short interest | Days to cover, % float | Squeeze potential | MEDIUM |

### Soros Agent Enhancement (live macro feeds from FRED)
- 10Y-2Y yield spread (recession signal)
- ISM Manufacturing PMI
- Initial Jobless Claims
- CPI YoY (inflation trajectory)
- Fed Funds Effective Rate

### Pendulum Reader Completion
- Market breadth (advance/decline)
- Credit spreads (HYG-IEF proxy)
- VIX
- Sector rotation (XLK vs XLU vs XLF relative strength)

## E. NEW ALPHA STRATEGIES

### 1. Earnings Revision Momentum Scanner
- Stocks where consensus EPS raised 3+ times in 90 days AND pass quant gate
- Pair with Simons momentum signals for timing

### 2. Insider Cluster Buying Signal
- 3+ insiders buying within 30 days (open market, not options)
- Auto-promote to STRONG_BUY candidate
- 7-10% annual outperformance in academic literature

### 3. Second-Order Beneficiary Screen
- Companies with >20% revenue from tech customers, not classified as tech
- "Picks and shovels" approach — buy the suppliers, not the hype

### 4. Social Buzz Contrarian Indicator
- Weekly buzz_score per watchlist ticker via SearXNG/Reddit
- High fundamental + LOW buzz = most mispriced
- Buzz spike on held position = retail arriving, trim signal

### 5. Per-Stock Implied Volatility Fear Gauge
- IV spike 2+ std dev above historical + thesis unchanged = buying opportunity
- IV collapse on watchlist stock = complacency, good entry window

### 6. Supply Chain Mapping
- Build customer→supplier mapping from SEC 10-K disclosures
- When customer gets positive verdict, auto-screen suppliers

## F. INTEGRATE INTO ADVICE SYSTEM

All of the above should feed into the advisory/advice system so that:
- Portfolio briefing automatically flags construction violations (concentration, missing stops, drift)
- Advice hints include benchmark comparison, calibration status, override audit results
- Recommendations include verdict stability score, consensus tier, buzz score
- The system generates its own "finance team review" periodically as part of the advice output

## G. PRIORITY ORDER (When Ready)
1. Portfolio construction rules (limits, stops, rebalancing) — enforce automatically
2. Sell signal fix (confidence multiplier) + verdict stability score
3. Measurement (SPY benchmark, Sharpe, prediction settlements)
4. Auditor override audit tracking
5. FRED macro data → Soros agent
6. Earnings calendar + insider buying signals
7. Buzz score (already have MCP tools)
8. Self-review integration into advice output
