# Methodology Mapping: How Successful Investors and Funds Actually Make Money

*Compiled: 2026-03-09*
*Author: Methodology Mapper Agent*
*Purpose: Map winning investment processes to codifiable, step-by-step rules — no gut feel*

---

## Thesis

If we can replicate exactly how proven investors and funds systematize their approach — as structured, codifiable rules — we can build a wealth tool that approaches the accuracy levels seen in the best discretionary and quantitative strategies. This document maps each major proven methodology to its exact process, verified returns, what can be automated, and what is currently missing from the Investmentology pipeline.

---

## Part A: Quantitative Methodologies (Published Track Records)

---

### 1. Greenblatt Magic Formula

**Published Returns**
- Greenblatt's book (2005): 30.8% annualized, 1988–2004, US stocks above $50M market cap
- Martin independent backtest (2003–2015): 11.4% annualized vs 8.7% S&P 500 (~+2.7% alpha)
- Norway study (2003–2022): 21.56% CAGR — but pre-transaction costs
- France (1999–2019): 5–9% annual market beat across quality definitions
- Hong Kong (2001–2014): 6–15% outperformance depending on company size
- Nordic (1998–2008): Outperformed market averages
- 2024 SSRN study (1963–2022): All formula strategies generate significant raw and risk-adjusted returns; Magic Formula exhibits highest remaining alpha after adjusting for common factors

**Note on Greenblatt's 30.8% claim**: This period (1988–2004) included extraordinary value conditions. Independent replications post-2005 consistently show +2–5% alpha over S&P 500, not 30%+ absolute returns. The 30.8% figure reflects a specific backtested period including the early recovery from 1988 recession; independent researchers using different periods get 11–21%.

**Exact Process (Codifiable)**

Step 1 — Universe Definition
- Start: All US-listed stocks
- Minimum market cap: $50M (book); practical floor is now $200M for liquidity
- Exclude: Financial Services, Utilities (EBIT/EV meaningless for these)
- Exclude: ADRs (different accounting standards)
- Exclude: REITs, BDCs (capital structure incompatible)

Step 2 — Earnings Yield Calculation
```
Earnings Yield = EBIT / Enterprise Value
where Enterprise Value = Market Cap + Total Debt - Cash
```
- Rank all eligible stocks from highest to lowest earnings yield
- Assign rank 1 = most attractive

Step 3 — Return on Capital Calculation
```
Return on Capital (ROC) = EBIT / (Net Fixed Assets + Net Working Capital)
where Net Working Capital = Current Assets - Current Liabilities (non-interest-bearing only)
```
- Rank all eligible stocks from highest to lowest ROC
- Assign rank 1 = most attractive

Step 4 — Combined Ranking
```
Combined Rank = Earnings Yield Rank + Return on Capital Rank
```
- Sort by Combined Rank ascending (lowest = best)
- Take top 20–30 stocks

Step 5 — Portfolio Construction
- Accumulate 2–3 positions per month over 12 months (avoid concentration timing risk)
- Equal-weight all positions

Step 6 — Rebalancing
- Hold exactly 12 months
- Sell losers 1 week BEFORE the 12-month mark (capture short-term tax loss)
- Sell winners 1 week AFTER the 12-month mark (defer capital gains to next tax year)
- Replace with new top-ranked stocks

Step 7 — Horizon
- Minimum 5 years to overcome short-term underperformance (strategy can lag market 2–3 consecutive years)

**Hit Rate** (from independent analysis)
- Greenblatt reports roughly 75% of stocks in the top decile outperform over 3-year periods
- Year-by-year: strategy underperformed in ~30% of calendar years in independent backtests

**What's Codifiable**
- 100% — every step is formula-driven with no judgment

**What Requires Judgment**
- None in the original formula. Judgment is deliberately excluded.

**Limitations**
- Ignores earnings quality (accruals can inflate EBIT)
- Ignores debt structure quality (high-yield debt companies can have attractive earnings yield)
- No momentum filter — captures value traps in declining industries
- EBIT can be manipulated; FCF yield is harder to distort

**How It Maps to Investmentology**
- Layer 1 (Quant Gate): **Already implemented** as the primary screen
- Critical gap: Greenblatt percentile calculation bug (combined_rank vs ordinal position) — **documented in deep-review-quant-gate.md**
- Enhancement: Add FCF yield as secondary earnings yield cross-check

**What's MISSING from Current Pipeline vs Pure Greenblatt**
- Annual rebalancing schedule not yet operational on 5000+ stock universe
- Tax-aware sell timing (sell losers before 12 months, winners after)
- No ADR exclusion currently implemented

---

### 2. Piotroski F-Score

**Published Returns**
- Original paper (Piotroski, 2000): 23% annual return from 1976–1996, long high-F-score/short low-F-score
- Applied to value stocks only (high book-to-market universe): strategy generates 7.5% annual alpha over passive value
- Hit rate: High F-Score (8–9) vs Low F-Score (0–2) — 69% of high-F-score value stocks were profitable vs 43% of low-F-score
- 2024 SSRN study (1963–2022 US): F-Score generates significant risk-adjusted returns as standalone and in combination

**Exact Process (Codifiable)**

Step 1 — Apply to Value Universe Only
- Piotroski is most powerful when applied AFTER a value screen (low P/B, low EV/EBIT)
- Works poorly as standalone (tested across all stocks, signal weakens)

Step 2 — Score 9 Binary Signals (0 or 1 each, max = 9)

**Profitability (4 signals)**
```
F1: ROA > 0 (net_income / beginning_total_assets > 0)
F2: CFO > 0 (operating_cash_flow > 0)
F3: ΔROA > 0 (current ROA > prior year ROA)
F4: CFO / Total Assets > Net Income / Total Assets (accruals quality — cash backs earnings)
```

**Leverage, Liquidity, Funding (3 signals)**
```
F5: Long-term debt ratio decreased YoY (long_term_debt / avg_total_assets)
F6: Current ratio improved YoY (current_assets / current_liabilities)
F7: No new shares issued (shares_outstanding_current <= shares_outstanding_prior)
```

**Operating Efficiency (2 signals)**
```
F8: Gross margin improved YoY (gross_profit / revenue — NOT operating margin)
F9: Asset turnover improved YoY (revenue / total_assets)
```

Step 3 — Classify
- F-Score 8–9: Strong financial position → BUY within value screen
- F-Score 5–7: Average → HOLD
- F-Score 0–2: Weak → AVOID or SHORT in long/short implementation

Step 4 — Holding Period
- Original paper uses annual rebalancing
- Monthly rebalancing increases turnover but may capture improving trajectories faster

**Hit Rate**
- Among value stocks: 69% of high-F-score outperformed vs 43% of low-F-score over 2-year periods
- The short side (low F-score, high book-to-market) is equally powerful: high-quality short universe

**What's Codifiable**
- All 9 signals are formula-driven
- Requires 2 years of financial data per company

**What Requires Judgment**
- None — fully mechanical

**Key Constraint**
- Requires prior-year financial data (6 of 9 signals need YoY comparison)
- New listings or companies with data gaps will have incomplete F-scores

**How It Maps to Investmentology**
- Layer 1 (Quant Gate): **Already implemented** at 25% weight in composite
- Known bugs in current implementation (deep-review-quant-gate.md):
  - Signal #8 uses operating margin instead of gross margin — **material misclassification**
  - Prior-year normalization inflates companies with missing history

**What's MISSING**
- Gross profit field not yet in FundamentalsSnapshot (blocks correct F8 calculation)
- Piotroski signal used within full universe rather than value-stock subset — weakens signal
- No distinction between high-F-score value stocks (BUY) and high-F-score growth stocks (less predictive)

---

### 3. AQR Value + Momentum + Quality (Multi-Factor)

**Published Returns**
- "Value and Momentum Everywhere" (Asness, Moskowitz, Pedersen, 2013 Journal of Finance):
  - Value premium alone: ~3–5% annual risk-adjusted alpha
  - Momentum premium alone: ~4–8% annual risk-adjusted alpha
  - Combined value + momentum: ~7–10% annual Sharpe improvement vs either alone
  - The combination works because the two factors are negatively correlated (ρ ≈ -0.50)
- Quality Minus Junk (Asness, Frazzini, Pedersen): High-quality stocks earn ~4% annual premium over low-quality stocks on risk-adjusted basis
- AQR Funds (Diversified Arbitrage, Large Cap Multi-Style): Live fund returns circa 2–5% annual alpha net of fees (2012–2025)

**Exact Process (Codifiable)**

Step 1 — Universe Definition
- Large + mid-cap stocks to ensure liquidity
- Exclude financials for standard metric comparability

Step 2 — Value Score (Z-scored within sector)
```
Value Composite = Equal weight of:
  - Book-to-Price (B/P = 1 / P/B)
  - Earnings-to-Price (E/P = 1 / P/E)
  - EV-to-Operating-Cash-Flow
  (optionally: Dividend Yield, Forward Earnings/Price)
```
- Z-score each metric separately (subtract sector mean, divide by sector std dev)
- Average z-scores to get composite Value signal

Step 3 — Momentum Signal
```
Momentum = 12-month total return, SKIPPING most recent month (t-12 to t-1)
```
- Cross-sectional rank across full universe
- Risk-adjust by dividing by trailing volatility (MSCI convention)

Step 4 — Quality Signal
```
Quality Composite = Z-score of:
  - Profitability: (Revenue - COGS - SG&A - Depreciation) / Book Equity (Operating ROE)
  - ROA: Net Income / Total Assets
  - Cash Flow / Total Assets
  - Low Accruals: -(Net Income - Operating CFO) / Total Assets (low = high quality)
  - Gross Profitability: (Revenue - COGS) / Total Assets
```
- Z-score and equal-weight

Step 5 — Combine Factors
```
Final Score = Equal weight of (Value Signal, Momentum Signal, Quality Signal)
```
- Rank stocks by Final Score
- Buy top quintile, sell (or underweight) bottom quintile

Step 6 — Rebalancing
- Monthly for momentum (fast-decaying signal)
- Quarterly for value (slow-moving signal)
- Practical compromise: quarterly rebalancing for all (reduces transaction costs)

Step 7 — Portfolio Construction
- Diversify across 50–100 stocks for the long-only implementation
- Equal-risk weighting preferred (not equal-dollar weight) for better diversification

**Combination Logic**
- Value and momentum are negatively correlated: when value is working, momentum often isn't (market reversals)
- Combining creates more consistent returns through the cycle
- Adding quality further reduces drawdowns (quality = survivorship in downturns)

**What's Codifiable**
- Factor calculations: 100% formulaic
- Rebalancing: rule-based
- Portfolio weights: inverse-volatility or equal-weight

**What Requires Judgment**
- Factor weights (AQR uses equal weights but publishes sensitivity analysis)
- Which quality metrics to include (some add redundancy)
- Handling of regime shifts (AQR has proprietary macro overlays)

**How It Maps to Investmentology**
- Layer 1 (Quant Gate): Value = Greenblatt (EY + ROC); Momentum = Jegadeesh-Titman; Quality = Piotroski + Altman
- The AQR insight of equal-weighting factors is partially implemented but not explicitly articulated
- Gap: AQR z-scores within sector — current implementation scores across full universe, which disadvantages cyclical-sector value stocks in comparison to tech/growth

**What's MISSING**
- Sector-relative z-scoring (would make value comparisons within-sector, not cross-sector)
- Monthly momentum signal decay — current pipeline runs weekly at best
- Quality signal not separately computed — it's embedded in Piotroski/Altman composite

---

### 4. O'Shaughnessy "What Works on Wall Street" — Trending Value

**Published Returns**
- O'Shaughnessy Asset Management (OSAM) backtests, 4th edition (2011), 52-year dataset (1963–2013):
  - Simple value strategies (P/B, P/S, EV/EBITDA single-factor): 13–15% annualized
  - Growth strategies: 10–12% annualized
  - **Trending Value (top strategy)**: 21.2% annualized over 1964–2009
  - S&P 500 benchmark: 11.2% annualized same period
  - Excess return: +10 percentage points per year
  - Maximum drawdown: -60% (significant; required patience)
- More recent replication (post-2013): Returns have moderated to +4–6% over S&P 500 as value premium has compressed

**Trending Value — Exact Process**

Step 1 — Composite Value Score (6-factor composite)
```
Value Composite 2 (VC2) components, Z-scored:
  1. Price-to-Book (P/B)        — lower is better
  2. Price-to-Earnings (P/E)    — lower is better
  3. Price-to-Sales (P/S)       — lower is better
  4. Price-to-Cashflow (P/CF)   — lower is better
  5. EV/EBITDA                  — lower is better
  6. Shareholder Yield           — higher is better (dividends + buybacks as % of market cap)
```
- For each metric: rank all stocks from 1 (most attractive) to N (least attractive)
- Sum the 6 ranks into a composite value rank
- Take the top 10% (cheapest decile on composite value)

Step 2 — Apply Momentum Filter (the "Trending" part)
- From the top 10% value stocks, rank by 6-month price momentum
- Buy only the top 25% by momentum within the value screen (i.e., top 2.5% of universe by value + top-momentum within that group)
- This is the "Trending Value" strategy — value + momentum combined

Step 3 — Portfolio Size
- Hold approximately 25–50 stocks from this filtered universe
- Equal-weight

Step 4 — Rebalancing
- Annual rebalancing
- O'Shaughnessy found monthly rebalancing added turnover costs without proportional return improvement for this strategy

**Why Trending Value Was His Top Strategy**
1. Multi-metric value composite reduces sensitivity to any single valuation multiple being gamed
2. Momentum filter (6-month price return) within the value set eliminates value traps — stocks that are cheap and STAYING cheap are filtered out
3. Shareholder yield (buybacks + dividends) captures capital return discipline; management returning cash is evidence that earnings are real

**Shareholder Yield Calculation**
```
Shareholder Yield = (Dividends Paid + Share Buybacks) / Market Cap
```
- High shareholder yield: management believes stock is undervalued AND has free cash flow to return
- This is one of the most robust single-factor strategies O'Shaughnessy found

**What's Codifiable**
- All 6 value metrics: 100% formulaic
- Composite ranking: mechanical
- Momentum filter: formula-based
- Rebalancing: rule-based

**What Requires Judgment**
- None — fully systematic in original design
- Factor weights if using weighted rather than equal-rank composite

**How It Maps to Investmentology**
- Layer 1 (Quant Gate): Partially maps — Greenblatt uses only 2 of O'Shaughnessy's 6 value metrics
- Enhancement: Adding P/B, P/S, Shareholder Yield to the value composite would broaden the screen and reduce exposure to earnings manipulation (since EBIT-based metrics are manipulable)
- Layer 5 (Timing): The 6-month momentum filter within the value set is a timing mechanism — could be implemented as a Layer 1.5 filter

**What's MISSING**
- No composite value score using 6 metrics (Investmentology uses Greenblatt's 2-factor approach only)
- Shareholder Yield not calculated anywhere in current pipeline
- P/S ratio not in current FundamentalsSnapshot model
- No within-value-set momentum filter (the most important element of Trending Value)

---

### 5. Greenblatt (Gotham) Acquirer's Multiple

**Published Returns (separate from Magic Formula)**
- Tobias Carlisle "The Acquirer's Multiple" (2017): Deep value single factor strategy
- Backtest 1974–2011: Top decile by EV/EBIT generated 17.4% annualized vs 10.4% for S&P 500
- 2024 SSRN comparison study: Acquirer's Multiple achieves highest raw returns for top decile portfolios among formula strategies
- Outperforms Magic Formula on pure return basis but has higher drawdowns

**Exact Process**
```
Acquirer's Multiple = Enterprise Value / Operating Earnings
where Operating Earnings = EBIT adjusted for one-time items
```
- Rank all eligible stocks by Acquirer's Multiple ascending (lowest = cheapest)
- Buy cheapest decile
- Annual rebalancing

**The insight**: This is simpler than Magic Formula — it drops the quality dimension (ROC) entirely and focuses purely on earnings yield (inverted Acquirer's Multiple). Works because extreme cheapness, even in lower-quality businesses, generates strong returns. The acquirer (private equity or strategic buyer) perspective: "What would I pay for this entire business?"

**How It Maps to Investmentology**
- Currently not implemented — pure deep-value screen would complement Greenblatt's quality-adjusted value approach
- Could be used as an additional signal: stocks that score high on both Magic Formula AND Acquirer's Multiple are doubly screened

---

## Part B: Discretionary (Codifiable Components)

---

### 6. Warren Buffett / Berkshire Hathaway

**Published Returns**
- Berkshire Hathaway 1965–2024: 19.9% annualized (book value basis); 19.8% (market value basis)
- S&P 500 including dividends: 10.2% annualized same period
- Excess return: ~9.7% per year for 59 years
- Buffett's Sharpe ratio: ~0.79 (1976–2017) vs S&P 500 ~0.49 — better risk-adjusted
- Academic analysis (Frazzini, Kabiller, Pedersen 2018): Buffett's alpha explained by systematic exposure to quality, value, and low-beta factors — he identified these premia decades before academic literature named them

**What's Actually Codifiable from Buffett**

The Buffett methodology has more codifiable components than widely believed:

Step 1 — Circle of Competence Filter (Binary Gate)
```
PASS if analyst can articulate:
  - Primary revenue driver in 1 sentence
  - Who the main competitors are and why this company wins
  - What event would cause this business to fail
FAIL if any of the above cannot be clearly stated
```

Step 2 — Economic Moat Assessment (5-category framework, each binary)
```
Score 1 point for each:
  1. Brand pricing power: Can they raise prices without volume loss?
  2. Switching costs: Would customers face significant cost/pain to switch?
  3. Network effects: Does value increase as more users join?
  4. Cost advantage: Can they produce at lower cost than competitors structurably?
  5. Efficient scale: Does the market only support one or two players profitably?
Moat Score: 0 = No moat, 1-2 = Narrow moat, 3-5 = Wide moat
Required: ≥ 3 to proceed
```

Step 3 — Quantitative Quality Gate (All must pass)
```
ROE > 15% for past 5 consecutive years (with low leverage, not debt-fueled)
ROIC > 12% for past 5 consecutive years
Debt/EBITDA < 3.0x (conservative capital structure)
Gross margin stable or improving over 5 years (pricing power evidence)
Owner Earnings growing at > 7% annually (5-year trend)
Owner Earnings = Net Income + Depreciation - Maintenance CapEx
```

Step 4 — Management Quality Assessment
```
$1 Test: Every $1 retained earnings → at least $1 market value created (5-year rolling)
Insider ownership: Management owns meaningful stake (skin in the game)
Capital allocation track record: Acquisitions at reasonable prices?
No compensation-driven earnings manipulation (check SBC/revenue ratio)
```

Step 5 — Intrinsic Value Estimation
```
Method: Normalized owner earnings × appropriate multiple
Not a formal DCF — Buffett uses:
  "If I owned 100% of this business, what would I pay for the earnings stream?"
  Fair Value Range = Owner Earnings × (15x to 25x) depending on growth and durability
```

Step 6 — Margin of Safety
```
Buy only when: Price < 65–75% of estimated intrinsic value
(implied 25–35% margin of safety)
```

Step 7 — Holding Period
- Intended to be permanent ("our favorite holding period is forever")
- Practical trigger to sell: business economics fundamentally change, not price moves

**Hit Rate**
- No single-year hit rate published; Buffett frames investment horizon in decades
- Academic analysis: 70%+ of Berkshire's equity picks outperformed in the 3 years following purchase (based on 13F analysis by researchers)

**What's Codifiable**
- Steps 2–4: Moat scoring, financial quality gates — 100% formulaic
- Step 5: Partially — earnings normalization requires judgment on what's "normal"
- Step 1: Binary gate but requires analyst input (LLM can do this)
- Step 6: Mechanical once intrinsic value is estimated

**What Requires Judgment**
- Moat category classification (but can be structured as LLM prompt with criteria)
- Earnings normalization (which years were cyclically depressed vs structural?)
- "Circle of competence" — requires analyst opinion

**How It Maps to Investmentology**
- **Warren agent** (weight 0.18): Implements this methodology
- Deep-review-agent-profiles.md notes: **9/10 accuracy on current implementation**
- Key gap: Missing "commodity vs. franchise" binary classification step
- Missing: 5-year ROIC/ROE trend data (current implementation uses single-year metrics)

**What's MISSING from Current Pipeline**
- Consecutive year quality requirement (5-year stability check, not just current snapshot)
- Owner Earnings calculation (net income + D&A - maintenance CapEx) — current model uses EBIT
- Formal intrinsic value range computation as output (currently LLM-generated qualitatively)

---

### 7. Peter Lynch PEG Ratio Strategy

**Published Returns**
- Lynch ran Fidelity Magellan 1977–1990: 29.2% annualized (13 years)
- S&P 500 same period: ~15.8% annualized
- Excess return: ~13.4% per year for 13 consecutive years
- Magellan grew from $18M to $14B under Lynch

**What's Codifiable from Lynch**

Step 1 — Stock Category Classification (6 categories, mutually exclusive)
```
1. Slow Grower: Revenue/EPS growth < 5% annually. Hold only for dividend yield.
2. Stalwart: Large company, 5–12% annual growth. Sell after 20–30% price appreciation.
3. Fast Grower: 15–25%+ annual growth, small/mid-cap. Lynch's favorite — seek the "ten-baggers".
4. Cyclical: Revenue follows economic cycle. Buy at trough (P/E looks high), sell at peak (P/E looks low).
5. Turnaround: Near-bankruptcy recovery story. Requires specific catalyst and survival proof.
6. Asset Play: Hidden assets not reflected in stock price (real estate at book, excess cash, etc.)
```

Step 2 — PEG Ratio Filter (applies primarily to Fast Growers and Stalwarts)
```
PEG = P/E Ratio / Annual EPS Growth Rate
PEG < 0.5: Very attractive
PEG 0.5–1.0: Attractive — buy zone
PEG 1.0–2.0: Fair value — hold zone
PEG > 2.0: Overvalued — avoid
```

Step 3 — The Two-Minute Story Test
```
PASS criteria (each must be stated in one sentence):
  - Why will the company grow?
  - What is the catalyst for growth?
  - What is the risk that the thesis is wrong?
  - Why haven't institutions discovered this yet (low institutional ownership)?
FAIL if any part requires extended explanation
```

Step 4 — Institutional Ownership Check
```
Low institutional ownership (< 30%) for Fast Growers = positive signal
High institutional coverage = stock already "discovered" = less upside
```

Step 5 — "Boring Is Beautiful" Filter
```
Positive signals:
  - Unglamorous product/service name
  - Industry is boring or depressing (funeral homes, garbage collection, pest control)
  - Institutional neglect (not followed by major banks)
  - No institutional ownership recently initiated
```

Step 6 — Category-Specific Valuation
```
Fast Growers: PEG < 1.0 at sustainable growth rate
Cyclicals: Buy when P/E is HIGH (trough earnings), sell when P/E is LOW (peak earnings)
Turnarounds: Has the company done something to fix the problem? Can it survive until recovery?
Asset Plays: NAV = (hidden asset market value) - total liabilities; buy at discount to NAV
```

**Hit Rate**
- Lynch reported: roughly 60% of his individual picks were winners
- His edge came from position sizing: winners could be 10x (ten-baggers), losers capped at -100%
- Asymmetric outcome + reasonable hit rate = excellent portfolio returns
- Lynch: "You only need to find a few big winners in a lifetime"

**What's Codifiable**
- Category classification: ~80% rule-based (LLM can do remaining 20%)
- PEG ratio: 100% formulaic
- Institutional ownership: 100% formulaic (data available from 13F filings)
- Two-minute story: LLM-assessable with structured prompt

**What Requires Judgment**
- Growth rate normalization (which years are "real" growth vs one-time?)
- Turnaround judgment (has management actually fixed the problem?)

**How It Maps to Investmentology**
- **Lynch agent** (weight 0.07): Implements this methodology
- Deep-review-agent-profiles.md: 7.5/10 accuracy
- Missing: Institutional ownership data in pipeline inputs
- Missing: Cyclical timing logic (buy when P/E is HIGH for cyclicals)

**What's MISSING from Current Pipeline**
- Stock category classification as a formal step in Layer 1 or 2
- Institutional ownership percentage from 13F data
- PEG ratio explicitly computed using forward growth rates (not just trailing P/E)
- Cyclical stocks penalized in quant gate because high P/E looks bad — Lynch would WANT high P/E cyclicals at trough

---

### 8. Seth Klarman Margin of Safety

**Published Returns**
- Baupost Group (Klarman), 1982–2020: ~16.4% annualized net of fees
- S&P 500 same period: ~9.7% annualized
- Excess return: ~6.7% per year for 38 years, with large cash positions (20–50% cash at times)
- Absolute performance: Never had a losing calendar decade

**What's Codifiable from Klarman**

Step 1 — Bear Case First (mandatory)
```
Before computing intrinsic value, compute the maximum downside scenario:
  - What happens in a severe recession (revenue -30%, margins compress)?
  - What if the business model is disrupted by technology?
  - What is the liquidation value if the company closes?
  - Can the company survive 3 years of cash burn at current rate?
REJECT if any scenario results in permanent capital loss
```

Step 2 — Three-Method Intrinsic Value
```
Method A: NPV of Free Cash Flows
  - Conservative FCF estimate (use 3-year average or below consensus)
  - Discount at 10-12% (not lower — margin of safety requires conservative rate)
  - Terminal value: 3x terminal FCF (conservative perpetuity)

Method B: Liquidation Value
  - Current assets at 70-80 cents per dollar (collections take time)
  - Inventory at 50 cents per dollar
  - PP&E at 50 cents per dollar (forced sale discount)
  - Deduct all liabilities at par
  - Result: "Floor value" — what you'd get if company closed today

Method C: Private Market Value
  - What would a strategic or financial buyer pay?
  - Reference: Recent M&A transactions in same sector (EV/EBITDA multiples paid)
  - Apply sector-appropriate multiple to normalized EBITDA
```

Step 3 — Anchor to Lowest Estimate
```
Intrinsic Value = Minimum (Method A, Method B, Method C)
```
This is deliberately conservative — Klarman prefers underestimating to overestimating.

Step 4 — Margin of Safety Gate
```
REJECT if Current Price > 70% of Intrinsic Value (insufficient margin of safety)
CONSIDER if Current Price = 50-70% of Intrinsic Value (30-50% MoS)
STRONG BUY if Current Price < 50% of Intrinsic Value (>50% MoS)
```

Step 5 — Forced Seller / Structural Discount Check
```
Bonus signals (increase conviction):
  - Stock recently deleted from a major index (forced selling pressure)
  - Spin-off from a larger company (institutional restrictions on holding small spinoffs)
  - Post-bankruptcy reorganization (most institutional investors cannot hold)
  - Rights offering (complex for institutional investors to participate)
  - Foreign ordinary shares listed in obscure markets
```

Step 6 — Position Sizing
```
Risk = Permanent Capital Loss potential, NOT price volatility
Initial position: Smaller than target
Add to position only when thesis strengthens AND price falls (averaging down only when thesis intact)
Maximum position: 5-10% of portfolio (Baupost typically runs 30-40 positions at $30B)
```

**What's Codifiable**
- Step 2 (liquidation value, M&A comps): 70% formulaic
- Step 4 (margin of safety gate): 100% mechanical once IV is computed
- Step 5 (structural discount signals): 100% data-driven (SEC filings, index changes)
- Steps 1 and 3: LLM-assessable with structured prompts

**What Requires Judgment**
- FCF normalization (picking the "right" steady-state cash flow)
- Private market multiple (requires sector expertise)
- Identifying "structurally discounted" situations

**How It Maps to Investmentology**
- **Klarman agent** (weight 0.12): Implements this methodology
- Deep-review-agent-profiles.md: 8.5/10 accuracy
- Key gap: Three-method IV calculation not explicitly forced; agent may skip liquidation value
- Missing: Structural discount flag from SEC 8-K (spinoff, index deletion, post-bankruptcy)

**What's MISSING from Current Pipeline**
- Liquidation value calculation (requires balance sheet line-item detail)
- Private market comparable transactions data (M&A comps by sector)
- Index deletion / spinoff event tracking (catalyst for structural discount)
- Formal "can the company survive 3 years of cash burn?" test

---

### 9. Howard Marks Cycle Positioning (Oaktree Capital)

**Published Returns**
- Oaktree Capital, credit-focused (1995–2024): ~15% annualized gross (net ~12%)
- Credit cycles + distress investing; absolute return, not equity-benchmark-relative
- Marks' "memos" are among the most cited investment documents in the industry

**What's Codifiable from Marks**

Step 1 — Credit Spread as Cycle Indicator
```
Investment Grade (IG) OAS spread (over US Treasuries):
  < 80 bps: Low risk premium — investors are complacent → defensive posture
  80-150 bps: Normal risk pricing → balanced positioning
  > 200 bps: Elevated risk premium → opportunities emerging
  > 350 bps: Crisis-level → aggressive opportunity hunting

High Yield (HY) OAS spread:
  < 300 bps: Compressed — credit cycle peak → reduce credit risk
  300-500 bps: Normal
  500-800 bps: Stressed — selective opportunity
  > 800 bps: Panic — significant opportunity for quality HY
```

Step 2 — Yield Curve Shape
```
10-year Treasury yield - 2-year Treasury yield (2s10s spread):
  > 150 bps: Steep curve → economic expansion beginning → risk-on
  50-150 bps: Normal
  Flat (0-50 bps): Late cycle → begin defensive rotation
  Inverted (< 0 bps): Recession predictor (6-18 month lag historically) → maximum defensive
```

Step 3 — Market Risk Premium Calibration
```
Equity Risk Premium = Earnings Yield (S&P 500) - 10-Year Treasury Yield
  > 4%: Equities cheap relative to bonds → equities preferred
  2-4%: Normal range
  < 2%: Equities expensive relative to bonds → reduce equity allocation
  < 0%: Bonds offer better risk-adjusted return than equities → significant warning
```

Step 4 — Cycle Position Assessment (Marks' "Pendulum")
```
GREED indicators (sell signal territory — pendulum swung to greed):
  - IPO volume exceeds 200/quarter
  - VIX < 12 (complacency)
  - Credit spreads at decade lows
  - Retail participation in speculative assets (crypto, meme stocks) elevated
  - Fund managers reporting "fully invested" (no dry powder)
  - Media narrative: "this time is different" / "new paradigm"

FEAR indicators (buy signal territory — pendulum swung to fear):
  - VIX > 40
  - IG spreads > 200 bps
  - HY spreads > 600 bps
  - IPO market closed
  - Fund redemptions forcing sales
  - Media narrative: "market will never recover"
```

Step 5 — Portfolio Posture Decision
```
Greed territory: Reduce position sizes, raise cash (Marks targets 20-40% cash at cycle peaks)
Neutral: Normal position sizing
Fear territory: Deploy cash aggressively into highest-conviction positions
```

**What's Codifiable**
- Credit spread monitoring: 100% formula-based (FRED free data for IG/HY OAS)
- Yield curve calculation: 100% formula-based (FRED free data)
- ERP calculation: 100% formula-based
- VIX level: 100% observable
- IPO volume: Data available (Renaissance Capital, Dealogic)

**What Requires Judgment**
- Identifying whether the narrative "sounds like greed" or "sounds like fear" (LLM-assessable)
- How aggressively to deploy at fear extremes

**How It Maps to Investmentology**
- Layer 5 (Timing / Sizing): Howard Marks framework partially implemented
- **No Howard Marks agent** exists — significant gap identified in deep-review-agent-profiles.md
- Credit spread data not currently ingested from FRED

**What's MISSING from Current Pipeline**
- Howard Marks agent entirely absent (recommended as Priority 1 addition in agent review)
- IG/HY credit spread data not fetched or used
- Yield curve shape not computed or used for position sizing
- ERP not computed
- No "cycle position" output that feeds into Kelly criterion sizing

---

## Part C: Institutional Methodologies

---

### 10. Morningstar Wide Moat Focus Index

**Published Returns**
- VanEck Wide Moat ETF (MOAT): Since inception October 2012 through December 2024 — 395% cumulative vs S&P 500 196% cumulative (approximately)
- Annualized: MOAT ~14.2% vs S&P 500 ~11.7% (2012–2024), ~+2.5% per year
- Source: VanEck fund factsheet, Morningstar Index data

**Exact Methodology (Rules-Based, Published)**

Step 1 — Identify Wide Moat Companies
```
Morningstar analyst coverage: ~1,500 companies have moat ratings
Moat ratings:
  - Wide Moat: Analyst expects competitive advantage to last > 20 years
  - Narrow Moat: Advantage expected to last 10-20 years
  - No Moat: No sustainable advantage

Wide Moat is assigned when company demonstrates at least one of 5 sources:
  1. Intangible assets (brand, patent, regulatory license)
  2. Switching costs (customers locked in)
  3. Network effect (value increases with users)
  4. Cost advantage (scale, better process, unique geography)
  5. Efficient scale (market too small for additional entrants)
```

Step 2 — Fair Value Estimation
```
Morningstar DCF methodology:
  - Project 5-year detailed cash flow forecast
  - Project 5-10 year "fade" period (margins and growth revert toward sector average)
  - Terminal value at long-run GDP growth (typically 3%)
  - Discount at WACC (Morningstar uses their own WACC estimates)
  - Fair Value = PV of all projected cash flows
```

Step 3 — Price-to-Fair-Value (P/FV) Ratio
```
P/FV = Current Price / Morningstar Fair Value Estimate
P/FV < 0.80: "Attractively priced" (> 20% discount to fair value)
P/FV 0.80–1.00: Fair value range
P/FV > 1.00: Premium to fair value
P/FV > 1.25: Overvalued
```

Step 4 — Index Construction
```
Wide Moat Focus Index:
  - Universe: All Morningstar-rated Wide Moat companies
  - Select: Those trading at the LARGEST discount to fair value (lowest P/FV ratios)
  - Target size: 40–50 companies
  - Equal-weight the selected companies
  - Rebalance: Quarterly (March, June, September, December)
```

Step 5 — Rebalancing Rules
```
At each quarterly review:
  - Recalculate P/FV for all Wide Moat companies
  - If existing holding P/FV > 1.10 (approaching or exceeding fair value), consider replacing
  - Bring in cheaper Wide Moat stocks that are now more attractively priced
  - Maintains roughly 40-50 positions, equal weight
```

**What's Codifiable**
- Moat identification: Requires analyst judgment (but once classified, is static until review)
- Fair value estimation: Requires DCF model (complex but codifiable with assumptions)
- P/FV ratio: 100% formulaic once fair value is estimated
- Index selection (cheapest Wide Moat stocks): 100% mechanical
- Rebalancing: Rule-based

**What Requires Judgment**
- Moat classification (requires domain expertise but Morningstar publishes their ratings)
- Fair value estimate (hundreds of inputs, requires annual update)

**How It Maps to Investmentology**
- Layer 2 (Competence Filter): Moat assessment maps here
- Layer 3 (Multi-Agent): Warren and Klarman agents perform DCF-like intrinsic value
- Missing: No explicit "moat durability rating" output (20-year vs 10-year horizon)
- Missing: No P/FV ratio computed — agents give qualitative verdicts, not quantitative fair value with discount %

**What's MISSING from Current Pipeline**
- Formal fair value estimate as numeric output (currently qualitative only from agents)
- Moat durability rating (narrow vs wide moat — 10 vs 20 year horizon)
- P/FV ratio tracking per position (required for valuation-based sell discipline)
- Quarterly rebalancing trigger based on P/FV exceeding 1.10

---

### 11. Goldman Sachs Conviction List

**Published Returns / Hit Rate**
- Academic study (Barber, Lehavy, McNichols, Trueman): Buy recommendations from research firms generate ~4% abnormal return in the 6 months following initiation (before the recommendation is widely known)
- After the stock reacts to the recommendation (within 5 days), the post-adjustment alpha is near zero for hold-to-maturity strategies
- Goldman's Conviction List specifically: Independent research (Chen & Liang, 2007) found Conviction List upgrades generated ~2.4% positive abnormal return in month of change, with subsequent alpha near zero
- **Bottom line**: Sell-side conviction calls generate alpha on the day of announcement; the market absorbs the information rapidly. Day-T alpha is real; T+30 alpha is near zero.

**Goldman's Conviction List Methodology (Published Characteristics)**

The methodology is NOT publicly published step-by-step, but the structural elements are known:

```
1. Analyst must have highest conviction in the stock relative to their full coverage universe
2. Investment review committee must approve addition to the list
3. Stock must have: (a) defined positive catalyst in 6-12 months, (b) quantified upside to target price, (c) risk/reward > 2:1
4. Conviction List is actively managed — additions and removals are frequent
5. Stocks are held on the Conviction List until: target price reached, thesis wrong, or better opportunity emerges
```

**What's Codifiable**
- Catalyst identification: Partially (LLM can assess catalyst quality)
- Risk/reward ratio: Formulaic once upside and downside are estimated
- 2:1 minimum ratio rule: 100% mechanical

**What Requires Judgment**
- Conviction assessment (by definition subjective)
- Committee approval process

**How It Maps to Investmentology**
- Not directly implemented; most relevant as validation signal
- Goldman Conviction List status (when available) should be an input to Layer 3 agents
- Use as contra-indicator when Conviction List is very crowded (consensus = less alpha)

**What's MISSING**
- Sell-side consensus data not ingested into pipeline
- Goldman Conviction List status not tracked per stock

---

### 12. S&P 500 Quality Index

**Published Returns**
- S&P 500 Quality Index: Since index inception (2014) through December 2024
- SPDR Portfolio S&P 500 High Quality ETF (SPHQ): Since inception 2005: ~11.4% annualized vs S&P 500 ~10.1% (2005–2024)
- Morningstar analysis: S&P 500 Quality Index has outperformed S&P 500 by ~1.5% annualized with lower volatility
- Sharpe ratio of quality index: typically 0.7–0.9 vs 0.5–0.7 for S&P 500

**Exact Methodology (S&P Published)**

Step 1 — Universe
- S&P 500 constituent companies only

Step 2 — Score 3 Quality Factors (each Z-scored)
```
Factor 1: Return on Equity (ROE)
  = Net Income / Book Equity
  Higher ROE = higher quality score

Factor 2: Accruals Ratio (Earnings Quality)
  = (Operating Cash Flow - Net Income) / Average Total Assets
  Higher = more cash-backed earnings = BETTER quality
  NOTE: This is NEGATIVE of traditional accruals (high accruals = bad)
  S&P uses: low accruals ratio = high quality

Factor 3: Financial Leverage
  = Total Debt / Book Equity (D/E ratio)
  LOWER leverage = higher quality score
```

Step 3 — Composite Score
```
Quality Score = Z(ROE) + Z(Accruals Quality) + Z(Low Leverage)
Where each Z-score is computed within the S&P 500 universe
```

Step 4 — Index Construction
```
Rank all S&P 500 companies by Quality Score descending
Select top 100 companies (top quintile by quality)
Weight by: Quality Score × Market Cap (quality-tilted market cap weighting)
Apply diversification constraint: max weight = smaller of 5% or 10× index weight
Rebalance: Semi-annually (May and November)
```

**What's Codifiable**
- All 3 metrics: 100% formulaic
- Composite scoring: 100% mechanical
- Index construction: Fully systematic

**What Requires Judgment**
- None — completely systematic

**How It Maps to Investmentology**
- Layer 1 (Quant Gate): Quality dimension partially captured via Piotroski
- The S&P Quality Index uses 3 simpler metrics than Piotroski's 9 — but it focuses on ROE (not in Piotroski), accruals (in Piotroski F4), and leverage (in Piotroski F5)
- Enhancement: Adding ROE and D/E ratio explicitly to composite alongside Piotroski

**What's MISSING from Current Pipeline**
- ROE not currently a standalone factor in Quant Gate
- Leverage explicitly penalized via Altman Z-Score, but not via D/E as a direct quality metric
- S&P Quality's accruals ratio uses a slightly different formula than Piotroski's — worth computing both

---

## Part D: Synthesis — What Makes the Best Methodologies Work

### The Common Codifiable Thread

Across all 12 methodologies, the strategies that generate the most consistent, durable alpha share these characteristics:

**1. Multi-Dimensional Value**
- No single valuation metric is sufficient. Magic Formula uses 2 (EY + ROC). O'Shaughnessy uses 6. Klarman uses 3 (NPV, liquidation, private market). More metrics = harder to "game" or have false positives from accounting choices.

**2. Quality Filter Layered on Value**
- Pure value without quality = value traps (cheap for a reason)
- Quality alone = too expensive
- Value × Quality = the powerful combination (Greenblatt, AQR, Morningstar, Buffett all arrive at this)

**3. Momentum as a Timing/Validation Signal**
- Value + Momentum > Value alone (O'Shaughnessy Trending Value, AQR, Jegadeesh-Titman)
- Momentum proves the market is beginning to recognize the value — eliminates "dead money" value stocks
- The 6-month window within the value set (O'Shaughnessy) or 12-month window cross-sectionally (AQR)

**4. Earnings Quality / Accruals**
- Every successful methodology explicitly or implicitly tests whether earnings are "real"
- Piotroski F4 (CFO > Net Income), S&P Quality (accruals ratio), Beneish M-Score, Klarman's FCF focus, Lynch's cash flow check for fast growers
- **Accruals manipulation is the most common way value traps form**

**5. Systematic Rebalancing with Tax Awareness**
- The best quantitative methodologies specify exactly when to rebalance and even tax-aware timing (Greenblatt: losers before year-end, winners after)
- Irregular or emotional rebalancing is the largest implementation gap for retail investors

**6. Cycle Awareness at the Portfolio Level**
- Marks: Credit spreads as cycle detector
- Dalio: Debt cycle position
- Druckenmiller: Liquidity (Fed policy)
- Individual stock selection works better when macro tailwinds support it

**7. Defined Exit Rules (Sell Discipline)**
- Morningstar: Sell when P/FV > 1.10
- Klarman: Sell when margin of safety is gone
- Lynch: Sell Stalwarts at +20-30%, sell Fast Growers when growth story is over
- Greenblatt: Sell at 12-month mark regardless
- **Most retail losses come from failing to sell when the thesis is complete or broken**

---

## Part E: Mapping to Investmentology Pipeline — Gap Analysis

### Current Pipeline vs Best Practices

| Methodology Component | Current Implementation | Gap | Priority |
|----------------------|----------------------|-----|---------|
| Greenblatt Magic Formula (2-factor EY + ROC) | ✅ Implemented (Layer 1) | Composite rank bug (ordinal vs combined_rank) | HIGH |
| Multi-factor value composite (6 factors) | Partial (only 2 factors) | Missing P/B, P/S, P/CF, Shareholder Yield | HIGH |
| Piotroski F-Score (9 signals) | ✅ Implemented (Layer 1) | Signal #8 uses operating not gross margin | HIGH |
| Jegadeesh-Titman Momentum (12-1 month) | ✅ Implemented (Layer 1) | Skip-month calculation slightly wrong | MEDIUM |
| Altman Z-Score | ✅ Implemented (Layer 1) | Manufacturing formula applied to all sectors | HIGH |
| Beneish M-Score | ❌ Not implemented | Needed as binary exclusion filter | HIGH |
| FCF Yield | ❌ Not computed | Supplement to EBIT/EV | MEDIUM |
| Sector-relative z-scoring | ❌ Not implemented | Full-universe z-scoring biases against cyclicals | MEDIUM |
| Momentum within value set (O'Shaughnessy) | ❌ Not implemented | Critical for eliminating value traps | HIGH |
| Shareholder Yield | ❌ Not computed | Missing from all value calculations | HIGH |
| Liquidation value estimate (Klarman) | ❌ Not implemented | Required for true margin of safety | MEDIUM |
| Owner Earnings calculation | ❌ Not implemented | Buffett uses this not EBIT | MEDIUM |
| 5-year ROIC/ROE stability | ❌ Single-year only | Need multi-year quality verification | HIGH |
| Credit spread monitoring (Marks) | ❌ Not fetched | Required for cycle-aware position sizing | HIGH |
| Yield curve monitoring | ❌ Not implemented | Required for macro regime detection | HIGH |
| Formal intrinsic value estimate (numeric) | ❌ Qualitative only | Need $ per share estimate with confidence interval | MEDIUM |
| P/FV ratio tracking | ❌ Not implemented | Required for valuation-based sell discipline | HIGH |
| Howard Marks agent | ❌ Not implemented | Cycle/credit risk analyst missing entirely | HIGH |
| Institutional ownership data | ❌ Not implemented | Lynch's key signal | MEDIUM |
| ADR exclusion in universe | ❌ Not implemented | Required per Greenblatt specification | LOW |
| Tax-aware sell timing | ❌ Not implemented | Greenblatt-specific optimization | LOW |
| Formal sell trigger system | ❌ Not implemented | Biggest gap vs all methodologies | CRITICAL |

### Priority Enhancement Roadmap (Ranked by Impact)

**Tier 1 — Fix Bugs in Existing Implementation (Immediate)**
1. Fix Greenblatt composite rank (ordinal vs combined_rank) — distorts ~50% of candidates
2. Fix Piotroski signal #8 (gross margin, not operating margin) — requires gross_profit field
3. Fix Altman Z-Score formula routing (Z'' for non-manufacturers)

**Tier 2 — Add Missing High-Value Signals (Phase 2)**
4. Add Beneish M-Score as binary exclusion filter
5. Add Shareholder Yield to value composite
6. Add momentum filter WITHIN the value screen (O'Shaughnessy Trending Value approach)
7. Fetch credit spreads and yield curve from FRED → feed to Marks/Soros/Dalio agents

**Tier 3 — Add Missing Infrastructure (Phase 3)**
8. Add Howard Marks agent (cycle positioning, credit analysis)
9. Build formal intrinsic value estimation (numeric output) from Warren/Klarman agents
10. Implement P/FV ratio tracking and automated sell triggers
11. Add 5-year historical quality trends (not just current snapshot)

**Tier 4 — Enhance with Full O'Shaughnessy Composite (Phase 4)**
12. Expand value composite from 2 factors to 6 factors
13. Add institutional ownership data from 13F
14. Add sector-relative z-scoring

---

## Part F: What 80%+ Accuracy Actually Requires

Based on the above methodology mapping, the path to 80%+ directional accuracy (stock will outperform market) over a 12-month horizon requires:

### Necessary Conditions

**1. Strong Quant Gate (Tier 1 filter)**
- Piotroski F-Score 7+ (removes low-quality value traps)
- Beneish M-Score < -1.78 (removes earnings manipulators)
- Altman Z-Score in safe zone (removes distress companies)
- Value ranking in top 25% on composite multi-metric screen

Published hit rate with all four conditions met (estimated from combined literature):
- 60-65% outperform over 12 months (purely quantitative)

**2. Quality Assessment (Tier 2 filter)**
- Wide moat score ≥ 3/5 (Buffett framework)
- 5-year ROIC stability ≥ 12%
- Gross margin stability (Piotroski F8 correctly computed)

Adding quality filter to strong quant gate (estimated):
- 65-70% outperform over 12 months

**3. Momentum Confirmation**
- 6-month price momentum positive within value set (O'Shaughnessy)
- Not in severe downtrend (eliminates deteriorating businesses)

Adding momentum filter (estimated from academic literature):
- 70-75% outperform over 12 months

**4. Multi-Agent Consensus**
- 5+ of 8 primary agents agree on direction
- No adversarial kill signals
- Macro cycle not in "late cycle defensive" mode

Adding qualitative multi-agent confirmation (estimated):
- 75-80% outperform over 12 months

**5. Favorable Macro Regime**
- IG credit spreads in normal range (not panic)
- Yield curve not inverted for > 12 months
- ERP positive (equities not overvalued vs bonds)

Macro tailwind condition adds ~3-5% hit rate when conditions are favorable.

### The Hard Ceiling

Academic research suggests: even the best multi-factor systematic strategies achieve 60-70% hit rate on 12-month individual stock predictions. The "80%+" target requires:
- Either longer holding periods (3-5 years, where fundamental selection is more predictive)
- Or exceptional "cherry picking" (using all filters simultaneously, which drastically reduces the number of actionable picks — perhaps 10-20 stocks per year from 5000+ universe)

**The path to 80%+ accuracy is not 80% of all stocks analyzed. It is 80% accuracy on the most highly filtered, highest-conviction subset of opportunities where all signals align.**

---

*Sources: Greenblatt (2005), Piotroski (2000), O'Shaughnessy (2011), Klarman (1991), Lynch (1989), Marks (2011), AQR Research Library, Morningstar methodology documentation, S&P Factor Index methodology, Wikipedia (Magic Formula Investing, Piotroski F-Score), Martin (2020) backtest, Norway HHN (2022) backtest, SSRN Schwartz & Hanauer (2024), Frazzini, Kabiller & Pedersen (2018) on Buffett's alpha, existing Investmentology research files (deep-review-quant-gate.md, deep-review-agent-profiles.md, phase2-synthesis.md, index-methodologies.md, quant-academic.md)*
