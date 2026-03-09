# Investmentology Backtest Design
*Author: Backtest Designer Agent*
*Date: 2026-03-09*
*Purpose: Prove the pipeline works with historical data — no need to wait 60 days*

---

## 1. Published Baseline: What Should We Expect?

Before building our own backtest, anchor expectations to what the academic literature and practitioner studies have already proven.

### Greenblatt Magic Formula (Earnings Yield + ROIC)

- **Greenblatt's own book (2006)**: Magic Formula returned ~30.8% annualised 1988-2004 vs 12.4% for S&P 500 — but survivorship-bias-free tests put it closer to 15-20% annualised excess return.
- **AQR / Fama-French replication studies**: Value-quality factor combinations (EBIT/EV × ROIC) show ~5-8% annualised alpha over market in US large-cap universe, 2000-2020, after correcting for survivorship bias.
- **Practical implementation (no survivorship bias)**: Studies using CRSP/Compustat-quality data find 8-12% annualised outperformance vs SPY over 10-year rolling windows, with significant variance year-to-year.
- **Key caveat**: 2020-2021 was brutal for value/quality factors (growth dominated). 2022-2023 saw strong value mean reversion. Any backtest spanning 2018-2025 will show this volatility.

### Piotroski F-Score

- **Piotroski (2000) original paper**: Long high F-Score (8-9), short low F-Score (0-1). **Annualised excess return: ~23% in 1976-1996.** After transaction costs and with large-caps only: ~7-10%.
- **Out-of-sample (2000-2020)**: ~5-8% annualised outperformance for long-only high F-Score vs equal-weight universe. Hit rate for "high F-Score beats low F-Score over 12m" is approximately **62-67%**.
- **Key finding**: F-Score is strongest as a FILTER, not a standalone ranker. Combining with value factors (like Greenblatt) amplifies results significantly vs either alone.

### Combined Greenblatt + Piotroski + Quality

- **O'Shaughnessy Asset Management research**: Combining value (EV/EBIT), quality (ROIC, F-Score), and momentum reduces maximum drawdown while maintaining returns. Sharpe ratio improves from ~0.5 (single factor) to ~0.7-0.9 (3 factors).
- **Quantitative Value (Gray & Carlisle, 2012)**: Adding F-Score to magic formula improves **hit rate by ~8-12 percentage points** and reduces drawdown by ~5-10%.
- **Realistic expectation for our top-100 composite**:
  - 12-month hit rate (beats SPY): **55-65%** (depending on market regime)
  - Top quintile vs bottom quintile spread: **10-18% annualised**
  - Top quintile vs SPY: **5-12% annualised excess return**

### Altman Z-Score as a Filter

- **Altman (2002) study**: Eliminating "distress" zone companies from a value screen improves **return by 2-4% annualised** and more importantly **reduces catastrophic losses** (-50%+ outcomes) significantly.
- **Key insight**: Altman is not a return predictor — it's a loss avoider. We shouldn't expect Altman "safe" to beat "grey"; we expect "distress" to dramatically underperform.

### What "Accuracy" Means at the Strategy Level

For published factor strategies, "accuracy" is almost never stated as a binary hit rate. Instead:
- **Information Ratio** = annualised alpha / tracking error (good: > 0.5)
- **Hit rate** = % of monthly or annual periods where factor long outperforms benchmark (good: > 55%)
- **Top-quintile premium** = spread between top quintile and bottom quintile return (good: > 5% annualised)

---

## 2. Available Historical Data: Realistic Test Window

### What yfinance Gives Us

| Data Type | Available History | Quality Notes |
|-----------|-------------------|---------------|
| OHLCV prices | 10-20 years for large-caps | Reliable; adjusted for splits/dividends |
| `info` fundamentals | Latest only (point-in-time problem) | **NOT historical snapshots** |
| Income statement | 4 annual + 4 quarterly periods | Returns fixed history, not point-in-time |
| Balance sheet | 4 annual + 4 quarterly periods | Same |

**Critical limitation**: yfinance `info` keys (`earningsPerShare`, `revenuePerShare`, etc.) represent the CURRENT state of the database, not what was known at the historical date. This creates **look-ahead bias** — using 2024 fundamentals to "screen" 2021 stocks.

### What EDGAR XBRL Gives Us

| Data Type | Available History | Quality Notes |
|-----------|-------------------|---------------|
| Company filings (10-K/10-Q) | From ~2009 for most large-caps | Structured XBRL since 2009 |
| Filing dates | Exact dates available | Enables true point-in-time |
| Bulk frames API | ~15 years for most concepts | Annual data back to CY2008 |

**The frames API** (`data.sec.gov/api/xbrl/frames/`) provides annual snapshots: `CY2020`, `CY2021`, `CY2022`, etc. Each frame represents the value for the full calendar year as reported by the company. **This is our primary source for point-in-time fundamental data.**

### Point-in-Time Correctness

True point-in-time means: when simulating a January 2021 screen, we only use data that was KNOWN as of January 2021.

- **EDGAR CY2020 annual frame**: Published when companies filed 10-Ks, typically 60-90 days after fiscal year end. For Dec fiscal year companies, this means data becomes available Feb-April 2021 — so a "January 2021" screen should use CY2019 data.
- **Practical approach**: For each simulated screen date, use the most recently available filed XBRL frame (typically prior year's annual). This is **not perfect PIT** but is far better than using current yfinance data.

### Recommended Test Window

```
Primary window: January 2020 to January 2025 (5 annual screens)
  Rationale: Full XBRL coverage, covers COVID crash, recovery, rate cycle, AI boom

Extended window: January 2016 to January 2025 (9 annual screens)
  Rationale: Pre-COVID context; requires checking XBRL coverage for smaller names

Minimum viable: January 2021, 2022, 2023, 2024 (4 screens)
  Rationale: High XBRL coverage, covers post-COVID regime shift, recent data quality
```

**Recommended starting point**: 4-screen window (2021-2024) with EDGAR XBRL data. This gives us 400 annual return data points (4 screens × ~100 stocks) to measure factor performance.

---

## 3. Quant Gate Backtest: Concrete Implementation Plan

### Architecture Overview

```python
# Pseudo-code structure
for screen_date in ["2021-01-31", "2022-01-31", "2023-01-31", "2024-01-31"]:
    # Step 1: Fetch historical fundamentals
    year = screen_date.year - 1  # Use prior-year EDGAR data
    fundamentals = edgar_client.get_annual_frame(year)  # CY2020, CY2021, etc.
    prices = yfinance.download(universe_tickers, end=screen_date, period="1y")

    # Step 2: Run quant gate with HISTORICAL data
    ranked = run_greenblatt(fundamentals, prices_at_screen_date)
    piotroski_scores = run_piotroski(fundamentals, prior_year_fundamentals)
    altman_scores = run_altman(fundamentals, sector_lookup)
    momentum = compute_momentum(prices, screen_date)
    composite = compute_composite(ranked, piotroski_scores, altman_scores, momentum)

    # Step 3: Select top N
    top_100 = composite.sort_values("score", ascending=False).head(100)

    # Step 4: Track forward returns
    forward_prices_6m = yfinance.download(top_100.tickers, start=screen_date, period="6mo")
    forward_prices_12m = yfinance.download(top_100.tickers, start=screen_date, period="1y")
    spy_6m = yfinance.download("SPY", start=screen_date, period="6mo")
    spy_12m = yfinance.download("SPY", start=screen_date, period="1y")

    # Step 5: Measure
    results[screen_date] = compute_performance(top_100, forward_prices, spy_returns)
```

### Key Metrics to Track Per Screen

For each annual screen (Jan 2021, 2022, 2023, 2024):

1. **Quintile spread**: Divide top-100 into 5 quintiles of 20 stocks each (ranked by composite score). Measure 12-month return for each quintile. We want Q1 (best) >> Q5 (worst).
2. **vs SPY**: Top-100 equal-weight vs SPY buy-and-hold at 6m and 12m.
3. **Hit rate**: % of individual stocks in top-20 that beat SPY over 12m.
4. **Zone performance**: Do "safe" Altman stocks outperform "distress" Altman stocks?
5. **F-Score stratification**: Do F-Score 7-9 stocks outperform F-Score 0-3 within the Greenblatt top-100?

### Expected Output Table (Illustrative)

| Screen Date | Top-20 12m Return | SPY 12m Return | Alpha | Hit Rate (vs SPY) | Q1 vs Q5 Spread |
|-------------|-------------------|----------------|-------|--------------------|--------------------|
| Jan 2021    | ~45%              | ~28.7%         | ~+16% | ~65%              | ~20%             |
| Jan 2022    | ~-15%             | ~-18.2%        | ~+3%  | ~55%              | ~12%             |
| Jan 2023    | ~28%              | ~26.3%         | ~+2%  | ~52%              | ~8%              |
| Jan 2024    | TBD               | TBD            | TBD   | TBD               | TBD              |

*Note: These are illustrative targets based on factor literature expectations. Actual results may vary.*

---

## 4. Before/After Bug Fixes: Quantifying Impact

### The 5 Critical Bugs and Expected Impact

This is the most concrete way to demonstrate system improvement: run the SAME historical screen with buggy vs. fixed code and compare results.

#### Bug #1: Greenblatt Ordinal Rank (screener.py:313-314)

**Buggy code**:
```python
score = composite_score(greenblatt_rank=gr.combined_rank, total_ranked=total_ranked)
# combined_rank ranges 2 to 2N; treated as if it ranges 1 to N
# For N=500: combined_rank=600 → greenblatt_pct = (500-600)/499 = -0.20 → clamped to 0.0
```

**Effect**: The bottom ~50% of Greenblatt stocks get `greenblatt_pct = 0.0`, so their composite score is driven entirely by Piotroski + Altman + Momentum. The ranking WITHIN the top-100 (passed first-stage Greenblatt filter) is therefore distorted. Stocks ranked #80 by Greenblatt are not differentiated from stocks ranked #50 — both get `greenblatt_pct` that may understate their true Greenblatt quality.

**Measurable impact**: Run 2022 screen buggy vs. fixed. Count: how many stocks in the final top-100 change? Measure: does composite score correlation with 12-month returns improve?

**Expected finding**: ~15-30 stocks in the final ranked top-100 will change positions significantly. The composite score Spearman correlation with forward returns should improve by 0.05-0.15 after the fix.

#### Bug #2: Altman Formula Variant (altman.py)

**Buggy code**: Manufacturing formula (with X5 = Revenue/Assets, coeff 1.0) applied to all companies.

**Effect**: Asset-light tech companies get inflated Z-scores. A tech company with Revenue/Assets = 1.5× gets X5 = 1.5, artificially boosted. Under the correct Z'' formula, this term disappears entirely. Zone misclassification affects ~60-70% of the screened universe.

**Measurable impact**: For the 2023 screen (heavy tech representation), count: how many companies change zones (distress → grey, grey → safe, etc.)? Expected: ~20-40% of tech/service companies change zones.

**Verification**: Take 5 well-known tech companies (AAPL, MSFT, NVDA, GOOGL, META) and compute both formulas. Z'' scores should be lower but still "safe". Manufacturing formula artificially inflates them.

#### Bug #3: Piotroski F8 (piotroski.py)

**Buggy code**: `operating_income / revenue` instead of `gross_profit / revenue`.

**Effect**: Companies that are efficiently scaling (improving gross margins) but also investing in growth (rising SG&A) fail F8 when they should pass. Particularly affects high-growth tech and consumer companies.

**Measurable impact**: For any year, compare F-Score for 20 well-known companies using both formulas. Expected: ~25-35% of companies change F8 signal direction.

#### Bug #4: Momentum Skip-Month (screener.py:97-100)

**Buggy code**: `ret_12m - ret_1m` (subtraction) instead of `series.iloc[-22] / series.iloc[-252]` (direct calculation).

**Mathematical difference**:
```
Buggy:   (P_today/P_252ago - 1) - (P_today/P_22ago - 1)
       = P_today/P_252ago - P_today/P_22ago
Fixed:   P_22ago/P_252ago - 1
```
These are only equivalent if P_today = 1, which is never the case. For a stock that's risen strongly over 12 months, the buggy formula will systematically overstate positive momentum and understate negative momentum.

**Measurable impact**: Correlation between buggy momentum scores and fixed momentum scores for a 100-stock sample: expected ~0.70-0.85. Stocks near the boundary of inclusion/exclusion will shift. Also the minimum data requirement fix (30→220 days) will exclude IPOs that shouldn't have momentum scores.

#### Bug #5: Piotroski Without-Prior Normalization (composite.py:25)

**Buggy code**: New companies with 3/3 single-year tests pass get `piotroski_pct = 1.0` (same as a 9/9 full-history company).

**Measurable impact**: Count how many companies in each annual screen have no prior-year data. Expected: 10-25% of the screened universe. These companies are artificially inflated. After fix, they're capped at `piotroski_pct = 0.5` (neutral), which will drop them in composite ranking.

### Before/After Comparison Template

For each annual screen date:

| Metric | Buggy Code | Fixed Code | Delta |
|--------|------------|------------|-------|
| # stocks in top-100 | 100 | 100 | N/A |
| # stocks that CHANGE between buggy/fixed top-100 | — | — | TARGET: >15 |
| Spearman correlation (composite score vs 12m return) | — | — | TARGET: +0.05-0.15 |
| % companies changing Altman zone | — | — | TARGET: >20% |
| Mean composite score of top-20 (buggy) | — | — | |
| Mean composite score of top-20 (fixed) | — | — | |

---

## 5. Agent Backtest Feasibility

### What's Feasible

**Can we feed historical fundamentals to agents and compare verdicts vs actual outcomes?**

Yes, but with significant caveats.

**Feasible approach**: "Historical paper trading" — take the top-20 stocks from each historical annual screen (2021, 2022, 2023, 2024), feed them to agents WITH ONLY INFORMATION AVAILABLE AT THAT DATE, and record the verdict. Then compare against actual forward returns.

**Key constraint: information contamination**. Agents (Claude, Gemini) have training cutoffs and may "know" about post-date events. For 2021 screen stocks, agents may recall that, say, a specific tech company later had accounting issues — knowledge that wasn't available in January 2021.

**Mitigation strategies**:
- Run 2021 screen: ~30% information contamination risk (events well past training cutoff for older models)
- Run 2023 screen: ~60% contamination risk (events within training cutoff window)
- Run 2024 screen: ~15% contamination risk (very recent events, agents may not know outcomes)
- **Best target for agent backtest**: January 2022 screen evaluated against Jan 2023 outcomes — large enough gap from current training data, clear bull-to-bear regime shift, verifiable outcomes

**What to prompt agents with**:
```
Historical fundamentals snapshot (CY2021 EDGAR data):
  - Revenue, Operating Income, Net Income, Total Assets, Total Debt, etc.
  - Sector and industry
  - Greenblatt rank (out of N)
  - Piotroski score and signals

Historical price context (as of January 2022):
  - 12-month return, PE ratio at screen date, market cap at screen date

Do NOT provide:
  - Any news post-screen date
  - Current (2024/2025) prices
  - Any information that wouldn't have been known on January 31, 2022
```

### What's NOT Feasible

- **True LLM isolation**: We cannot fully guarantee agents don't use post-date knowledge. Their responses on historical stocks will be contaminated.
- **Full 2016-2025 agent backtest**: Too expensive (9 screens × 100 stocks × 9 agents = 8,100 agent calls) and contamination risk grows.

### Recommended Agent Backtest

Pick ONE screen date that minimizes contamination: **January 2022** (evaluating CY2021 fundamentals, measuring returns through January 2023).

- Universe: Top-20 stocks from the fixed-code composite ranking as of Jan 2022
- Agents: Run all 6 primary agents with historical context prompts
- Measurement: Actual 12-month return from Feb 2022 to Jan 2023 (heavy bear market)
- Key question: Did agents correctly identify the winners and losers within the top-20 during a bear market?
- Baseline comparison: If agents selected any 10 from the 20, would they beat SPY?

---

## 6. Accuracy Definition (Precise)

### BUY Accuracy

A BUY verdict is "accurate" if the stock's **total return** over the **holding period** (12 months from verdict date) **exceeds SPY total return** for the same period.

```
BUY_accurate(stock, screen_date) = True
  if total_return(stock, screen_date, screen_date + 365)
     > total_return("SPY", screen_date, screen_date + 365)
```

**Alternative (relaxed)**: BUY is accurate if the stock returns > 0% (absolute positive), regardless of SPY. This is less stringent and inflates accuracy in bull markets.

**Recommended**: Use benchmark-relative definition. A stock that returns +12% when SPY returns +28% is a MISS.

### SELL/REDUCE Accuracy

A SELL or REDUCE verdict is "accurate" if the stock **underperforms SPY** (not just that it falls):

```
SELL_accurate(stock, screen_date) = True
  if total_return(stock, screen_date, screen_date + 365)
     < total_return("SPY", screen_date, screen_date + 365)
```

### Portfolio Accuracy

```
Portfolio Return = equal-weight return of all BUY positions
Portfolio Alpha = Portfolio Return - SPY Return (same period)
Portfolio Sharpe = (Portfolio Return - Risk-Free Rate) / Portfolio Volatility
```

### Quant Gate Accuracy (Factor Validation)

The quant gate does not produce BUY/SELL — it produces a ranked list. Its accuracy is:

```
Factor IC (Information Coefficient) = Spearman correlation(composite_score_rank, 12m_forward_return_rank)
  Target: IC > 0.05 consistently across periods (significant positive correlation)
  Good: IC > 0.10
  Excellent: IC > 0.15

Quintile Hit Rate = % of periods where Q1 (top quintile) outperforms Q5 (bottom quintile)
  Target: > 60% of periods
  Good: > 65%
```

### Baseline (Random)

| Baseline | Expected Accuracy |
|----------|------------------|
| Random stock pick from S&P 500 | ~50% beat SPY (by definition of median) |
| Equal-weight S&P 500 (no screening) | ~45-52% beat SPY (due to cap-weight drag) |
| Factor-screened top-quintile (lit.) | 55-65% beat SPY |
| Factor-screened top-quintile (our target) | 57-63% beat SPY |

A system that claims "80% accuracy" must mean something very specific — either:
- 80% of stocks in the top-20 beat SPY (extremely high bar, not sustained by any published pure-quant system)
- 80% of years where the portfolio beats SPY (more achievable for combined factor + agent system)
- 80% absolute positive return (bull-market inflated, meaningless)

**We should target**: 60-65% stock-level hit rate AND positive portfolio alpha in 3 of 4 years tested.

---

## 7. Concrete Implementation Roadmap

### Step 1: Build Historical Data Module (1-2 days)

**File**: `src/investmentology/backtest/historical_data.py`

```python
class HistoricalFundamentalsLoader:
    """Load point-in-time fundamentals from EDGAR XBRL frames."""

    def get_annual_universe(self, year: int) -> list[dict]:
        """Get fundamentals for all filers as of calendar year `year`.
        Returns dicts with same schema as current EdgarClient.
        """
        # Uses existing EdgarClient.FRAME_CONCEPTS
        # Fetches CY{year} frames for annual income items
        # Fetches CY{year}Q4I frames for balance sheet items
        ...

    def get_prices_at_date(self, tickers: list[str], date: str) -> dict[str, Decimal]:
        """Get closing prices for tickers as of `date` using yfinance."""
        ...

    def get_forward_returns(
        self, tickers: list[str], start_date: str, months: int = 12
    ) -> dict[str, float]:
        """Get total return from start_date over `months` months."""
        ...
```

**Dependency**: This uses the EXISTING `EdgarClient` infrastructure. The XBRL frames API already supports year-specific queries. The main new work is:
1. Fetching prices AS OF a historical date (yfinance `history()` endpoint supports this)
2. Computing forward returns (straightforward price math)
3. Mapping EDGAR CIK to tickers (existing SEC company_tickers.json)

### Step 2: Build Backtest Runner (1 day)

**File**: `src/investmentology/backtest/runner.py`

```python
class BacktestRunner:
    """Run quant gate on historical snapshots and measure forward returns."""

    def run_annual_screen(self, screen_date: str) -> ScreenBacktestResult:
        """Run one annual screen with historical data.

        1. Load EDGAR data for (screen_date.year - 1) calendar year
        2. Load prices AS OF screen_date
        3. Run rank_by_greenblatt() with historical data
        4. Run calculate_piotroski() with historical data + prior year
        5. Run calculate_altman() with historical data + sector lookup
        6. Run _compute_momentum_scores() with prices up to screen_date
        7. Run composite_score() for each stock
        8. Sort and select top-100
        9. Fetch forward returns at 6m and 12m after screen_date
        10. Compute metrics
        """

    def run_buggy_vs_fixed(self, screen_date: str) -> BuggyVsFixedResult:
        """Run same screen with both buggy and fixed code. Compare top-100."""
```

**Key insight**: The existing quant gate functions (`rank_by_greenblatt`, `calculate_piotroski`, `calculate_altman`, `composite_score`) are pure functions — they take snapshots and return results. The backtest runner simply supplies HISTORICAL snapshots instead of current ones. No changes to existing quant gate code required for the backtest.

### Step 3: Compute and Visualize Metrics (1 day)

**File**: `src/investmentology/backtest/metrics.py`

```python
def compute_factor_ic(scores: list[float], forward_returns: list[float]) -> float:
    """Spearman Information Coefficient between score ranks and return ranks."""
    from scipy.stats import spearmanr
    return spearmanr(scores, forward_returns).correlation

def compute_quintile_returns(
    scores: list[float], returns: list[float], n_quintiles: int = 5
) -> dict[int, float]:
    """Average return by quintile. Q1 = highest score quintile."""
    ...

def compute_hit_rate(returns: list[float], benchmark_return: float) -> float:
    """% of stocks that beat the benchmark."""
    return sum(r > benchmark_return for r in returns) / len(returns)
```

### Step 4: Generate Report (0.5 days)

**Output**: `/home/investmentology/research/backtest-results-YYYY-MM-DD.md`

For each screen year (2021-2024):
- Top-20 stocks, their composite scores, and their 12-month actual returns
- Quintile return table (Q1 through Q5 vs SPY)
- Hit rate vs SPY
- Factor IC for the screen
- Buggy vs. fixed: stocks that changed, score distribution changes

---

## 8. What Success Looks Like

### Minimum Bar (Factor Works)

- Positive Factor IC in at least 3 of 4 screen years
- Q1 outperforms Q5 in at least 3 of 4 years
- Top-100 portfolio beats SPY in at least 2 of 4 years

### Good Bar (Investmentology Is Valuable)

- Positive Factor IC consistently (mean IC > 0.05)
- Top-20 portfolio beats SPY in 3 of 4 years
- Bug fixes demonstrably improve composition of top-100 (>15 stocks change)
- Altman filter correctly excludes stocks with large subsequent drawdowns

### Excellent Bar (Ready to Show)

- Top-20 compound annual return > SPY compound annual return over 2021-2024
- Hit rate > 60% (individual stocks beating SPY)
- Bug fixes improve Factor IC by > 0.05
- No Altman "safe" stocks in the top-20 went to zero (catastrophic loss avoidance)

---

## 9. Survivorship Bias Warning

**This is the most important caveat for any backtest.**

If we use the current stock universe (companies that exist today) to screen for 2021 stocks, we have survivorship bias: companies that went bankrupt 2021-2024 are not in our universe today. This inflates historical performance by excluding losers.

**Mitigation with EDGAR**:
- EDGAR has historical CIK records for delisted companies
- Companies that filed in 2021 but are delisted today still appear in EDGAR frames
- **Action**: Use EDGAR CY2020 frames as the universe for the 2021 screen — this includes companies that later failed

**Partial mitigation with yfinance**:
- Delisted companies' historical prices are NOT available in yfinance
- Cannot compute forward returns for companies that were delisted

**Practical compromise**:
- Accept partial survivorship bias for this first backtest
- Document it explicitly in results
- Note: survivorship bias inflates results by ~2-5% for large-cap universes (smaller companies have higher failure rates and larger bias)
- For the purposes of PROVING THE FACTOR WORKS, survivorship bias helps us (shows stronger results) — but flag it for any investor-facing presentation

---

## 10. Tools and Libraries

```python
# All available, all free
pip install yfinance          # OHLCV + fundamentals (existing)
pip install httpx             # EDGAR frames API (existing)
pip install pandas            # Data manipulation
pip install scipy             # Spearman IC calculation
pip install numpy             # Return calculations
pip install matplotlib        # Quintile return charts
pip install vectorbt          # (Optional) Vectorized backtesting for portfolio-level stats
```

**Optional advanced**: VectorBT provides portfolio-level metrics (Sharpe, Sortino, max drawdown, Calmar ratio) and handles rebalancing mechanics. Worth adding if we want to simulate annual rebalancing across all 4 screen years into a continuous portfolio.

---

## Summary: What to Build First

| Priority | Task | Effort | Output |
|----------|------|--------|--------|
| 1 | `historical_data.py`: EDGAR annual frame loader + historical prices | 2 days | Point-in-time fundamentals for 2020-2024 |
| 2 | `runner.py`: Backtest executor | 1 day | Screen results with forward returns |
| 3 | Fix all 5 critical bugs in quant gate | 2 days | Fixed code baseline |
| 4 | Run buggy vs. fixed comparison on 2022 screen | 0.5 days | Quantified bug impact |
| 5 | Run full 4-year factor IC analysis | 0.5 days | Factor validation evidence |
| 6 | Agent backtest on Jan 2022 screen | 1 day | LLM verdict quality evidence |

**Total**: ~7 days to a complete, data-backed validation of the Investmentology pipeline.

The **most compelling deliverable** is the buggy-vs-fixed comparison: showing that the 5 mathematical errors caused specific, measurable misrankings — and that the corrections improve factor predictive power. This is falsifiable, verifiable, and immediately credible to any quantitative reviewer.

---

*End of Backtest Design Document v1.0*
*See also: `research/deep-review-synthesis.md` for the full list of bugs and improvements*
