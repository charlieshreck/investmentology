# Deep Review: Quantitative Gate Screening Methodology

*Author: Quantitative Research Agent*
*Date: 2026-03-08*
*Scope: All code in `src/investmentology/quant_gate/` — greenblatt.py, piotroski.py, altman.py, composite.py, screener.py, models/stock.py, data/universe.py*

---

## Executive Summary

The quantitative gate is the foundational Layer 1 of the 6-layer investment pipeline. It screens 5,000+ stocks to a top-N shortlist using four factors: Greenblatt Magic Formula (40%), Piotroski F-Score (25%), Altman Z-Score (15%), and Jegadeesh-Titman momentum (20%). The implementation is broadly correct and architecturally sound. However, there are **six material issues** and **several enhancements** that would significantly improve accuracy and predictive power.

**Critical bugs (fix immediately):**
1. Piotroski signal #1 uses ROA (net_income > 0) but the paper specifies ROA > 0, not just net income — the code calls it `positive_net_income` but scores it correctly. However, signals #4 and #8 have meaningful deviations from the original paper.
2. Altman Z-Score uses the original 1968 **manufacturing formula** (D = market cap / total liabilities) for all companies. Most of the universe are non-manufacturers and should use the Z'' (Z-double-prime) formula with different coefficients.
3. Piotroski without prior-year data normalizes to 3/9 denominator (4 tests scoreable, normalized to 3) — there is an off-by-one: 4 tests can fire without prior-year data (positive_net_income, positive_ocf, accruals_quality, and the implicit fourth), but the code sets `PIOTROSKI_MAX_WITHOUT_PRIOR = 3`.

**Material methodological issues:**
4. ROIC uses EBIT / invested_capital, but the standard ROIC formula is NOPAT / invested_capital. Greenblatt himself specifies EBIT in the book, but NOPAT is the theoretically correct measure and the one actually used in Greenblatt's website implementation.
5. Gross margin proxy: Piotroski signal #8 should use gross margin (revenue - COGS) / revenue, not operating margin. The code uses operating_income / revenue (operating margin). These can diverge significantly for companies with high SG&A.
6. Momentum computation uses the full 12-month window from the first available price to latest, but Jegadeesh-Titman (1993) specifies months 2-12 (skipping the most recent month) to avoid short-term reversal contamination.

---

## 1. Greenblatt Magic Formula

### 1.1 Formula Correctness

**Reference:** Greenblatt (2005), *The Little Book That Beats the Market*

The original formula specifies:
- **Earnings Yield** = EBIT / Enterprise Value
- **Return on Capital (ROC)** = EBIT / (Net Fixed Assets + Working Capital)
- Universe: US-listed stocks above minimum market cap
- Exclusions: Financial Services, Utilities, ADRs

**The code's implementation in `stock.py`:**
```python
@property
def earnings_yield(self) -> Decimal | None:
    ev = self.enterprise_value  # market_cap + total_debt - cash
    if ev <= 0:
        return None
    return self.operating_income / ev  # EBIT / EV ✓

@property
def invested_capital(self) -> Decimal:
    return self.net_working_capital + self.net_ppe  # net_wc + net_fixed ✓

@property
def roic(self) -> Decimal | None:
    ic = self.invested_capital
    if ic <= 0:
        return None
    return self.operating_income / ic  # EBIT / IC ✓ (matches book)
```

**Verdict: Structurally correct** for earnings yield and capital structure. The formula matches Greenblatt's 2005 book specification exactly.

### 1.2 EBIT vs NOPAT Debate

The code uses `operating_income` (EBIT) as the numerator for both earnings yield and ROIC. Greenblatt explicitly chose EBIT for its simplicity and tax-neutrality across companies. However:

- The standard academic ROIC formula (Wikipedia, Damodaran) is `ROIC = NOPAT / Invested Capital` where NOPAT = EBIT × (1 - tax rate).
- Greenblatt's public website implementation at magicformulainvesting.com reportedly uses pre-tax ROIC (EBIT) consistent with the book.
- Using EBIT overstates ROIC for high-tax companies relative to low-tax companies. A company paying 30% effective tax rate has 43% higher apparent ROIC than the same company post-tax.
- **For screening purposes** (ranking, not absolute valuation), EBIT-based ROIC is defensible if applied consistently. The ranking distortion from tax rate differences is real but modest unless you are comparing companies with very different tax profiles (e.g., tech companies with heavy international income vs. domestic manufacturers).

**Recommendation:** Keep EBIT for simplicity and fidelity to Greenblatt's stated methodology. If NOPAT is desired, it requires the effective tax rate which yfinance/EDGAR provides but adds data dependency. Document the choice explicitly.

### 1.3 Enterprise Value Construction

```python
@property
def enterprise_value(self) -> Decimal:
    return self.market_cap + self.total_debt - self.cash
```

**Issues:**
- **Preferred stock** is excluded. Greenblatt's strict formula should include preferred stock in the EV numerator. Most screeners omit this for simplicity, but it creates a systematic bias for companies with preferred equity (utilities, some REITs — though these are excluded anyway).
- **Minority interest** is excluded. For conglomerates with significant minority interests (GE, Berkshire subsidiaries), this understates EV. Minor impact for most companies.
- **Cash**: Uses total cash. Some practitioners use only "excess cash" (cash above operating needs, typically defined as cash exceeding 2% of revenue). This matters for capital-light businesses with large cash balances like Apple or Microsoft.

**Verdict:** Acceptable simplification for a broad screen. The Greenblatt book uses the simplified form. Flag in documentation.

### 1.4 Sector Exclusions

```python
EXCLUDED_SECTORS = frozenset({"Financial Services", "Utilities"})
```

Per Greenblatt's book and the canonical methodology, this is correct. The reasons:
- **Financials**: EBIT / EV is not meaningful (banks operate with leverage as a core business; interest is revenue, not expense).
- **Utilities**: Highly regulated with mandated returns; ROIC-based screening is not meaningful.

The code also correctly excludes REITs and BDCs in `universe.py`. **This is correct.**

**Missing: ADR exclusion.** Greenblatt's original methodology explicitly excludes ADRs (foreign companies listed on US exchanges). The `universe.py` code does not explicitly filter ADRs. The NASDAQ screener data may or may not label them clearly. ADRs have different accounting standards (IFRS vs GAAP) that can make EBIT and ROIC comparisons misleading.

**Recommendation:** Add explicit ADR detection. Common patterns: tickers with specific suffixes are often ADRs, but the most reliable method is checking the `country` field in NASDAQ screener data and filtering out non-US companies.

### 1.5 Ranking Method

```python
# Sort by combined rank ascending (lowest = best)
results.sort(key=lambda r: r.combined_rank)
```

Combined rank = ey_rank + roic_rank. This is exactly Greenblatt's method: rank by EY, rank by ROIC, add ranks, sort by sum. **Correct.**

One known issue with this approach: **it breaks down when the universe size changes significantly between runs**. Rank 50 out of 500 stocks is very different from rank 50 out of 1000 stocks, but both get a rank of 50. This is fine for within-run ranking but affects cross-run comparisons.

### 1.6 Survivorship Bias in Universe Loading

The NASDAQ screener API returns currently-listed stocks. It does not include delisted companies. For backtesting purposes, this creates survivorship bias. For live screening (the system's purpose), this is correct behavior — you can only invest in currently-traded stocks.

---

## 2. Piotroski F-Score

### 2.1 Original Paper vs Implementation

**Reference:** Piotroski, J.D. (2000). "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers." *Journal of Accounting Research*, Vol. 38.

The original 9 criteria from the paper:

| # | Signal | Group | Paper Definition | Code Implementation |
|---|--------|-------|-----------------|---------------------|
| 1 | ROA > 0 | Profitability | Net income before extraordinary items / beginning total assets > 0 | `current.net_income > ZERO` — **Correct intent, minor variance** |
| 2 | CFO > 0 | Profitability | Cash flow from operations > 0 | Uses `operating_cash_flow` fallback to `operating_income` — **Acceptable** |
| 3 | ΔROA > 0 | Profitability | Current ROA > prior ROA | `current_roa > previous_roa` — **Correct** |
| 4 | Accruals | Profitability | CFO/Total Assets > ROA (Net Income/Total Assets) | `ocf > current.net_income` — **WRONG: missing asset normalization** |
| 5 | ΔLeverage | Leverage | Long-term debt ratio decreased | Uses total_debt/total_assets — **Minor variance: paper uses long-term debt only** |
| 6 | ΔLiquidity | Leverage | Current ratio improved | `current_cr > previous_cr` — **Correct** |
| 7 | No dilution | Leverage | No new common shares issued | `current.shares_outstanding <= previous.shares_outstanding` — **Correct** |
| 8 | ΔGross Margin | Efficiency | Gross margin improved | Uses `operating_income/revenue` (operating margin) — **WRONG: should be gross profit/revenue** |
| 9 | ΔAsset Turnover | Efficiency | Asset turnover improved | `revenue/total_assets` — **Correct** |

### 2.2 Bug: Signal #4 — Accruals Quality

**Paper definition:** F4 = 1 if CFO/Total_Assets > Net_Income/Total_Assets (both divided by total assets).

**Code implementation:**
```python
# 4. Accruals quality: OCF > net income (low accruals = higher quality)
details["accruals_quality"] = ocf > current.net_income
```

**The bug:** The paper normalizes both sides by total assets. The code compares absolute CFO to absolute net income. For large companies with large asset bases, this rarely changes the sign of the comparison (since both are divided by the same denominator). However, for companies with very different asset turnover characteristics (capital-light software vs. capital-heavy manufacturing), comparing raw cash flow vs. net income without normalization can produce different outcomes than the paper's specification.

The correct implementation:
```python
if current.total_assets > ZERO:
    cfo_roa = ocf / current.total_assets
    ni_roa = current.net_income / current.total_assets
    details["accruals_quality"] = cfo_roa > ni_roa
```

In practice, since both sides are divided by the same value (total_assets), the comparison `ocf/ta > net_income/ta` is mathematically equivalent to `ocf > net_income` **only when total_assets > 0**, which is always true for the stocks that pass the prior checks. So this is functionally equivalent for valid snapshots, but the intent diverges from the paper for documentation purposes.

**Verdict:** Functionally equivalent but not documented correctly. Low priority fix.

### 2.3 Bug: Signal #8 — Gross Margin vs Operating Margin

**Paper definition:** F8 = 1 if current gross margin (gross profit / revenue) > prior gross margin.

**Code implementation:**
```python
# 8. Gross margin improving (proxy: operating margin = operating_income/revenue)
if previous is not None and current.revenue > ZERO and previous.revenue > ZERO:
    current_margin = current.operating_income / current.revenue
    previous_margin = previous.operating_income / previous.revenue
    details["gross_margin_improving"] = current_margin > previous_margin
```

**The bug:** `operating_income / revenue` = operating margin, NOT gross margin.

- Gross margin = (Revenue - COGS) / Revenue
- Operating margin = (Revenue - COGS - SG&A - D&A - Other OpEx) / Revenue

These diverge significantly. A company can have improving gross margins while operating margins decline (rising SG&A, increased D&A from capex). The paper explicitly specifies gross margin, which measures production efficiency before overhead.

**Data availability:** `gross_profit` is not in `FundamentalsSnapshot`. It would need to be added as a field and fetched from yfinance/EDGAR. yfinance provides `gross_profit` via `info['grossProfits']` or the income statement. EDGAR provides it directly.

**Impact:** Material. Technology companies especially have high SG&A ratios that can obscure gross margin trends. Using operating margin instead of gross margin misclassifies the efficiency signal for a meaningful subset of companies.

**Fix required:**
1. Add `gross_profit: Decimal = Decimal(0)` to `FundamentalsSnapshot`
2. Populate from yfinance/EDGAR in the data clients
3. Update signal #8 to use `gross_profit / revenue`

### 2.4 Prior-Year Normalization Issue

**Code:**
```python
PIOTROSKI_MAX_WITHOUT_PRIOR = 3
PIOTROSKI_MAX_WITH_PRIOR = 9
```

**Analysis:** Without prior-year data, the following signals CAN fire:
1. `positive_net_income` — single-year ✓
2. `positive_ocf` — single-year ✓
4. `accruals_quality` — single-year ✓

Signals 3, 5, 6, 7, 8, 9 all require prior-year data (YoY comparisons).

So without prior-year data, **3 out of 9 signals** can score (not 4 as the comment says). The constant `PIOTROSKI_MAX_WITHOUT_PRIOR = 3` is **correct**.

However, normalizing 3/3 gives a score of 1.0 for a company that passes all 3 available tests. This over-rates companies without prior-year data relative to those with full 9/9 scoring. A company with score 3/3 (100%) is treated equivalently to one with 9/9 (100%), but the former has passed far fewer quality gates.

**Recommended approaches:**
- **Option A (current):** Normalize to available max — simple but inflates companies missing prior-year data.
- **Option B:** Apply a confidence penalty: score = (raw_score / 9) × (tests_available / 9). This penalizes missing data.
- **Option C:** Treat missing prior-year data as 0 for all YoY signals (i.e., assume no improvement). Score becomes raw_score / 9. This is conservative and discourages investing in companies without history.

**Recommendation:** Option C is most conservative and aligns with the spirit of the F-Score (designed for value stocks with established history). Option A inflates scores for newer companies or those with data gaps.

### 2.5 Long-term Debt vs Total Debt (Signal #5)

**Paper definition:** Long-term debt / average total assets should decrease YoY.

**Code implementation:** Uses `total_debt / total_assets`. Total debt includes short-term debt and current portion of long-term debt.

**Impact:** Minor. For most companies, the direction of change is the same. However, for companies that are refinancing (paying down long-term debt while taking short-term credit), the signals can diverge. The paper specifically targeted long-term leverage as a financial health signal.

**Fix:** Would require a `long_term_debt` field. Currently the model has `total_debt`. Low priority.

---

## 3. Altman Z-Score

### 3.1 Formula Variant Selection — Critical Issue

**The code uses the 1968 original manufacturing formula for ALL companies:**

```python
# D: Market Cap / Total Liabilities  ← original formula
d = snapshot.market_cap / snapshot.total_liabilities
```

**The Altman Z-Score has THREE variants:**

| Variant | Published | Target | D definition | Coefficients |
|---------|-----------|--------|--------------|-------------|
| Z (original) | 1968 | Public manufacturers | Market cap / total liabilities | 1.2, 1.4, 3.3, 0.6, 1.0 |
| Z' (Z-prime) | 1983 | Private companies | Book value equity / total liabilities | Different |
| Z'' (Z-double-prime) | 1995 | Non-manufacturers, service firms | Book value equity / total liabilities | 6.56, 3.26, 6.72, 1.05 |

The screened universe is 5,000+ US listed stocks. The majority are:
- Service companies (tech, healthcare, retail) — should use Z''
- Manufacturing companies — can use original Z
- Financial services — excluded (no Z-score applies)

**Using the manufacturing formula (Z) for service companies systematically misstates their distress probability.** The X5 variable (sales/assets) is particularly volatile — asset-light technology companies have very high asset turnover which inflates their Z-score artificially using the original formula.

**The Z'' formula (non-manufacturers) does NOT include X5 (sales/assets)**:
```
Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4
```

Where X4 = **book value of equity** / total liabilities (not market cap).

The thresholds also differ:
- Z'' > 2.6: Safe
- 1.1 < Z'' < 2.6: Grey
- Z'' < 1.1: Distress

**Fix required:** Detect company sector/industry and apply the appropriate formula variant:
- Manufacturing stocks: original Z formula
- Service, technology, healthcare, consumer: Z'' formula
- The `sectors` dict is already passed through the screener pipeline and available

### 3.2 Retained Earnings Fallback

```python
# B: Retained Earnings / Total Assets
re = snapshot.retained_earnings if snapshot.retained_earnings != ZERO else snapshot.net_income
b = re / ta
```

**Analysis:** Using `net_income` as a fallback for `retained_earnings` is **unsound** for several reasons:

1. Retained earnings is a **balance sheet** item reflecting accumulated historical earnings. Net income is the **current-period** earnings flow. They are fundamentally different.
2. A mature company with large retained earnings (e.g., $5B) but a moderate current-year net income (e.g., $500M) would have a 10x understated B ratio.
3. Retained earnings can be **negative** (accumulated deficit) for young or distressed companies. Net income may be positive in the same period. The fallback masks this distinction.
4. The Altman paper specifically chose retained earnings as an age/profitability proxy — longer-operating profitable companies accumulate more retained earnings. Net income removes this age signal entirely.

**Impact:** When retained earnings data is missing (which the `is_approximate` flag tracks), the Z-score is materially wrong. A high-growth startup with $0 retained earnings (all profits reinvested or negative) should score lower on B than an established company. Using net_income instead gives the startup a possibly positive B score.

**Fix:** EDGAR's balance sheet data (available via the edgar_client) typically provides retained earnings. yfinance also provides it via `balance_sheet.loc['RetainedEarnings']`. The existing `retained_earnings` field should be populated more reliably rather than using a fallback.

**Short-term mitigation:** When `is_approximate=True`, apply a score penalty or flag the result for review rather than using net_income blindly.

### 3.3 Coefficient Accuracy

```python
COEFF_A = Decimal("1.2")
COEFF_B = Decimal("1.4")
COEFF_C = Decimal("3.3")
COEFF_D = Decimal("0.6")
COEFF_E = Decimal("1.0")
```

These match the original 1968 Altman formula exactly. **Correct for the manufacturing variant.**

### 3.4 Zone Thresholds

```python
SAFE_THRESHOLD = Decimal("2.99")
GREY_THRESHOLD = Decimal("1.81")
```

These match the original Z formula thresholds. **Correct for the manufacturing variant.** The Z'' thresholds (2.6 and 1.1) are not implemented, which is consistent with the finding that only the original formula is implemented.

### 3.5 Financial Company Handling

The code returns `None` for Z-scores with zero total_liabilities, but this does not explicitly catch financial companies. Since financials are excluded from the universe in `universe.py`, this is not a practical issue. However, the Wikipedia article explicitly notes: "Neither the Altman models nor other balance sheet-based models are recommended for use with financial companies." The existing exclusion is the right approach.

---

## 4. Momentum

### 4.1 Jegadeesh-Titman Implementation

**Reference:** Jegadeesh & Titman (1993). "Returns to Buying Winners and Selling Losers." *Journal of Finance*, 48(1).

**The standard J-T momentum:** 12-month return, **skipping the most recent month** (i.e., months t-12 to t-2, not t-12 to t-1).

**Code implementation:**
```python
ret_12m = (series.iloc[-1] / series.iloc[0]) - 1
ret_1m = (series.iloc[-1] / series.iloc[-22]) - 1 if len(series) > 22 else 0
momentum_raw[ticker] = float(ret_12m - ret_1m)
```

This computes: (12-month total return) - (1-month return) = approximately the return from month -12 to month -1.

**The intent is correct** — subtracting the 1-month return from the 12-month return approximates the J-T skip-month convention. However:

1. `series.iloc[0]` is the **first available price** in a 1-year download, not exactly 12 months ago. If the stock was only available for 9 months, `series.iloc[0]` gives a 9-month return, not a 12-month return.
2. `series.iloc[-22]` assumes 22 trading days = 1 month. This is a reasonable approximation (typical trading month is 21-22 days).
3. The subtraction `ret_12m - ret_1m` is not mathematically equivalent to `ret_12m_skipping_1m`. It should be:
   ```python
   # Correct: return from 12 months ago to 1 month ago
   ret_skip = (series.iloc[-22] / series.iloc[0]) - 1
   ```
   The current code's approach (`ret_12m - ret_1m`) is an approximation that works when returns are small but is wrong when compounding matters.

**Fix:**
```python
# J-T: 12m-1m (skip month) momentum
if len(series) >= 252:  # Full 12 months available
    ret_12m_skip1m = (series.iloc[-22] / series.iloc[-252]) - 1
    momentum_raw[ticker] = float(ret_12m_skip1m)
elif len(series) >= 44:  # At least 2 months
    ret_12m_skip1m = (series.iloc[-22] / series.iloc[0]) - 1
    momentum_raw[ticker] = float(ret_12m_skip1m)
```

### 4.2 Cross-Sectional Ranking

```python
# Cross-sectional rank → percentile (0.0 worst, 1.0 best)
sorted_tickers = sorted(momentum_raw, key=lambda t: momentum_raw[t])
n = len(sorted_tickers)
return {t: i / (n - 1) if n > 1 else 0.5 for i, t in enumerate(sorted_tickers)}
```

**Issue:** Momentum is only computed for top-N (e.g., top-100) stocks that passed Greenblatt ranking, not the full universe. This means momentum scores are **relative to the top-N Greenblatt stocks**, not relative to the full market universe.

**Consequence:** A stock that is the best momentum performer among the Greenblatt top-100 may still have poor absolute momentum if all top-100 Greenblatt stocks are in a downtrend. The cross-sectional rank normalizes this away.

**Academic best practice:** Momentum should ideally be computed cross-sectionally across the full universe, then used as an input to the composite score. Computing momentum within the Greenblatt-filtered subset introduces a selection bias.

**Practical consideration:** Computing momentum for 5,000+ stocks requires a single bulk download (which yfinance can do with `threads=True`), but adds data volume. The current approach of computing momentum only for top-N reduces the data volume significantly.

**Recommendation:** Keep the current approach for performance reasons but document the limitation.

### 4.3 Lookback Period

The J-T 12-1 momentum is the most widely cited and implemented lookback. However, academic research shows:
- **3-12 month momentum** is the primary signal (Fama-French factor library)
- **6-month momentum** is also commonly used and has strong empirical support
- **Intermediate (2-12 month) momentum** is the Fama-French standard in their factor data

For a composite score, the 12-1 convention is appropriate and well-established.

### 4.4 Momentum Crashes

Momentum strategies are subject to severe drawdowns ("momentum crashes") during market reversals, particularly in the first weeks of a bull market recovery after a crash. The -73% momentum crash of 2009 is a canonical example. For a screening system that runs weekly/monthly, this risk is modulated but not eliminated. The Altman Z-Score acts as a partial hedge — high-momentum distressed companies (which drive momentum crashes) get penalized by the Z-score component.

---

## 5. Composite Score

### 5.1 Weight Justification

**Current weights:** Greenblatt 40%, Piotroski 25%, Altman 15%, Momentum 20%.

**Literature support:**

| Factor | Weight | Academic Basis | Notes |
|--------|--------|---------------|-------|
| Greenblatt (value + quality) | 40% | Strong: multiple backtests showing 3-9% alpha | Dominant factor in the screen |
| Momentum | 20% | Strong: J-T (1993), Carhart (1997), global replication | Value and momentum are negatively correlated, so high momentum weight provides diversification vs. Greenblatt value |
| Piotroski | 25% | Moderate: strong on value stocks, weaker as standalone | High weight relative to empirical evidence; original paper shows F-Score works best combined with value |
| Altman | 15% | Moderate: bankruptcy prediction, not return prediction | Z-score is primarily a risk filter, not a return predictor |

**Assessment:** The 40% Greenblatt weight appropriately reflects it as the primary screening mechanism. The 20% momentum weight is consistent with AQR's finding that value + momentum combines efficiently (negative correlation means the portfolio has higher Sharpe than either alone). The 25% Piotroski weight may be slightly high — Piotroski's original paper showed the F-Score works as a *within-value-stock* differentiator (buy high F-Score value stocks, short low F-Score value stocks). It is less powerful as a standalone factor.

**Concern:** The Altman weight (15%) acts as a risk-reduction filter but does NOT predict positive returns — it predicts bankruptcy avoidance. Giving it a 15% weight means distress-zone stocks are penalized but the Z-score does not identify outperformers within the safe zone. If all non-distress companies get `altman_pct = 1.0`, those 85% of stocks are undifferentiated on this dimension.

**Observation:** Safe zone (>2.99) gets score 1.0, grey zone gets 0.5, distress gets 0.0. The jump from safe to grey is massive. More granularity within the safe zone (e.g., using the actual Z-score value rather than just the zone) would provide finer discrimination.

### 5.2 Missing Data Handling

```python
if momentum_score is not None:
    score = (0.40 * greenblatt + 0.25 * piotroski + 0.15 * altman + 0.20 * momentum)
else:
    base_weight = 0.40 + 0.25 + 0.15  # = 0.80
    score = (0.40/0.80 * greenblatt + 0.25/0.80 * piotroski + 0.15/0.80 * altman)
```

This proportional redistribution is methodologically sound. When momentum is unavailable, the remaining weights are rescaled to sum to 1.0. **Correct.**

```python
ALTMAN_ZONE_SCORES: dict[str | None, Decimal] = {
    "safe": Decimal("1.0"),
    "grey": Decimal("0.5"),
    "distress": Decimal("0.0"),
    None: Decimal("0.3"),  # missing data — treated as grey-ish
}
```

Missing Altman data gets 0.3 (slightly below grey). This is a reasonable assumption — if we can't compute Z-score, treat the company as a mild risk.

### 5.3 Piotroski Normalization Edge Case

```python
piotroski_max = PIOTROSKI_MAX_WITH_PRIOR if has_prior_year else PIOTROSKI_MAX_WITHOUT_PRIOR
piotroski_pct = Decimal(piotroski_score) / Decimal(piotroski_max)
piotroski_pct = min(Decimal("1"), piotroski_pct)
```

`PIOTROSKI_MAX_WITHOUT_PRIOR = 3` and 3 signals can fire. If a company passes all 3, it gets `3/3 = 1.0` — full marks on the Piotroski component despite having no prior-year data.

A company with 9/9 with prior-year data also gets 1.0. So the two are treated identically, but the 9/9 company has passed far more rigorous testing. This over-rates companies with missing history.

**Recommendation:** Use Option C from Section 2.4: always normalize against 9 (the full score), treating unanswered signals as 0. This penalizes missing data naturally.

### 5.4 Greenblatt Percentile Conversion

```python
if total_ranked > 1:
    greenblatt_pct = Decimal(total_ranked - greenblatt_rank) / Decimal(total_ranked - 1)
```

For rank 1 of N: pct = (N - 1) / (N - 1) = 1.0. For rank N of N: pct = 0. **Correct linear percentile mapping.**

Note: `greenblatt_rank` is the **combined rank** (ey_rank + roic_rank), not the ordinal position in the sorted list. Combined rank can range from 2 (best: rank 1 on both) to 2N (worst: rank N on both). The `total_ranked` parameter is used as if it were the max possible combined rank, which it is not.

**Bug:** If `total_ranked = 500` stocks, the worst possible combined rank is `500 + 500 = 1000`, not `500`. But `greenblatt_rank` passed to `composite_score()` is `gr.combined_rank` which can be up to `2 * total_ranked`.

The greenblatt_pct formula would give a negative value for any stock with `combined_rank > total_ranked`, which is most stocks in a large universe.

Looking at the code:
```python
total_ranked = len(ranked)
# ...
score = composite_score(
    greenblatt_rank=gr.combined_rank,
    total_ranked=total_ranked,
    ...
)
```

`gr.combined_rank` for the worst stock in a 500-stock universe could be ~999 (rank 500 + 499). `total_ranked` = 500. The formula gives: `(500 - 999) / (500 - 1) = -499/499 ≈ -1.0`, which is then clamped to 0.

`greenblatt_pct = max(Decimal("0"), min(Decimal("1"), greenblatt_pct))` — the clamping saves it, but it means the bottom ~50% of Greenblatt stocks all get `greenblatt_pct = 0.0`. This is extreme: there is no differentiation among the bottom half.

**Fix:** The composite should use the ordinal position in the ranked list, not the combined rank:
```python
# In screener.py, build ordinal position mapping:
for ordinal, gr in enumerate(ranked, start=1):
    # ...
    score = composite_score(
        greenblatt_rank=ordinal,  # 1 = best, len(ranked) = worst
        total_ranked=len(ranked),
        ...
    )
```

The `GreenblattResult.combined_rank` field is the additive rank sum. The ordinal position (1st, 2nd, ...) in the sorted list is different and is what `composite_score` expects.

**This is a significant bug.** The bottom 50% of Greenblatt candidates all score 0 on the Greenblatt component and are ranked only by Piotroski + Altman + Momentum.

---

## 6. Universe Construction

### 6.1 Minimum Market Cap

```python
def load_full_universe(
    min_market_cap: int = 200_000_000,  # $200M
    min_price: float = 5.0,
    min_avg_volume: int = 100_000,
)
```

**Analysis:**
- **$200M minimum is appropriate** for avoiding micro-cap liquidity issues. Greenblatt's original used $50M but that was 2005 dollars. The $200M equivalent in 2024+ dollars is well-justified.
- **$5 minimum price** is a reasonable penny-stock filter. Standard practice.
- **100K average daily volume** — this filter may be too weak for a paper portfolio context. 100K shares * $10 average price = $1M average daily volume. A 1% position in a $100K portfolio would be $1,000, which is fine. But for institutional-scale positions, 100K ADV would be illiquid. Given this is a personal investment system, 100K ADV is adequate.

### 6.2 Sector Exclusions

From `universe.py`:
```python
EXCLUDED_SECTORS = frozenset({"Financial Services", "Utilities"})
EXCLUDED_INDUSTRIES = frozenset({
    "REIT",
    "Real Estate Investment Trusts",
    "Business Development Companies",
    "Shell Companies",
    "Blank Checks",
})
```

**Missing exclusions:**
- **ADRs/Foreign issuers**: Greenblatt explicitly excludes. Needs explicit ADR check.
- **ETFs and closed-end funds**: The special character filter (`.`, `/`, `^`) catches most, but ETF tickers without special characters would slip through.
- **Biotechnology pre-revenue**: Small biotech with no revenue and operating_income = 0 would be excluded by Greenblatt's `negative_or_zero_ebit` check, but only at the Greenblatt stage, not universe stage. Could be excluded earlier.

### 6.3 SPAC / Blank Check Filtering

```python
EXCLUDED_NAME_KEYWORDS = frozenset({
    "acquisition",
    "spac",
    "blank check",
    "merger",
})
```

This keyword filter is fragile. Many SPACs don't include "spac" in their name. Common SPAC patterns:
- "[Name] Acquisition Corp" — partially caught by "acquisition"
- "[Name] Capital Corp" — not caught
- "[Name] Holdings Inc" (blank check) — not caught

The special character filter (`-`, warrants like `XXXX.WT`) catches many SPACs by their warrant/unit tickers, but not the common shares.

**Recommendation:** The NASDAQ screener API may provide an `industry` field that marks "Blank Check Companies" explicitly. Cross-check EXCLUDED_INDUSTRIES.

---

## 7. Missing Factors — Should They Be Added?

### 7.1 Beneish M-Score (Earnings Manipulation Detection)

**Formula (8 variables, per Wikipedia/Beneish 1999):**
```
M = -4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI
```

Where TATA = (Net Income from Continuing Ops - CFO) / Total Assets, DSRI = Days Sales in Receivables Index, etc.

**Threshold:** M-score < -1.78: not a likely manipulator; M-score > -1.78: likely manipulator.

**Assessment for inclusion:**
- Requires two years of data for most ratios (current and prior year)
- Requires COGS data (for GMI and DSRI)
- Proved Enron was manipulating earnings in 1998 before the collapse

**Phase 2 synthesis recommended this as a high-priority addition.** The Beneish M-Score is a natural complement to the Piotroski F-Score: Piotroski identifies improving fundamentals, Beneish flags potential manipulation of those same fundamentals. Adding it as a binary filter (exclude manipulators, i.e., M-score > -1.78) rather than a weighted component would be clean and high-value.

**Required data additions:** `gross_profit` (needed for GMI), `receivables` (needed for DSRI), `depreciation` (needed for DEPI), `sga_expenses` (needed for SGAI). Most are available from yfinance income statement.

**Recommendation: Add as a binary exclusion filter** — stocks flagged as likely manipulators are excluded before scoring. This removes them from the pipeline entirely without requiring weighting decisions.

### 7.2 Novy-Marx Gross Profitability

**Reference:** Novy-Marx, R. (2013). "The Other Side of Value: The Gross Profitability Premium." *Journal of Financial Economics*, 108(1), 1-28.

**Formula:** Gross Profitability = (Revenue - COGS) / Total Assets

Novy-Marx found that gross profitability predicts excess returns as powerfully as book-to-market (value). High gross profitability companies outperform low gross profitability companies. Critically, gross profitability is negatively correlated with value — profitable companies are often expensive. Combining gross profitability with value creates a powerful screen similar to Greenblatt's.

**Assessment:** The Greenblatt ROIC metric captures a related concept (return on capital) but at a different level of the income statement. ROIC uses EBIT (below gross profit, after SG&A and D&A). Novy-Marx specifically argued for gross profit because it is harder to manipulate and more stable across industries.

**Recommendation:** Add gross profitability as a fifth component with a small weight (5-10%). It partially overlaps with ROIC/Greenblatt but adds signal at a higher income statement level. More importantly, it requires `gross_profit` data, which is also needed for the Piotroski gross margin fix.

### 7.3 FCF Yield (Free Cash Flow)

Multiple academic studies and practitioner approaches use FCF yield (FCF / EV or FCF / Market Cap) as an alternative or supplement to EBIT-based earnings yield:

- A 2022 Norway study found "the magic formula could be improved by using operating cash flows instead of EBIT."
- FCF is harder to manipulate than EBIT (accruals, aggressive revenue recognition affect EBIT but not FCF).
- FCF yield = (Operating Cash Flow - Capex) / Enterprise Value

The system already has `operating_cash_flow` in `FundamentalsSnapshot`. Adding a FCF yield calculation would require `capex`, which is available from yfinance cash flow statement.

**Recommendation:** Add FCF yield as an optional second earnings yield metric. When available, blend EBIT/EV with FCF/EV (50/50) as a more robust earnings yield signal.

### 7.4 Quality Minus Junk (QMJ) / Low Volatility

These require significant additional data (beta, earnings variability, financial leverage) and are better suited to the existing multi-agent analysis layer (Layer 3) where the agents already evaluate qualitative quality signals. The quant gate should remain computationally fast and data-efficient. QMJ is not recommended for the quant gate at this stage.

### 7.5 Accruals Quality (Balance Sheet Accruals)

Accruals = (Net Income - Operating Cash Flow) / Total Assets

Low accruals (negative or small number) = earnings backed by cash flow = higher quality. This is related to but distinct from Piotroski's accruals signal (which compares CFO to ROA). Balance sheet accruals have a documented negative relationship with future returns (the "accruals anomaly," Sloan 1996).

The system already computes a version of this in Piotroski signal #4. Adding it as a standalone composite component would double-count the signal. **Not recommended as separate component.**

---

## 8. Data Quality and Robustness

### 8.1 yfinance Data Reliability

The system uses yfinance as the primary data source. yfinance is a reverse-engineered Yahoo Finance API that has well-documented reliability issues:
- Intermittent zeros for revenue, net_income (explicitly addressed in `validation.py`)
- Delayed updates after earnings releases (fundamental data may lag 1-7 days)
- Some metrics like `gross_profit` and `retained_earnings` have inconsistent field naming

The EDGAR path (via `edgar_client`) is more reliable for historical data but requires additional processing. The screener correctly uses EDGAR for the full run when available, with yfinance as a fallback.

### 8.2 Stale Data Risk

The screener doesn't compute a `stale_pct` metric (line 346 has `stale_pct=0.0`):
```python
stale_pct=0.0,  # Could be computed if we track fetched_at freshness
```

Stale fundamentals data is a meaningful quality risk. A company reporting earnings on Monday, with a Tuesday screen run, would show old data if the EDGAR feed hasn't been updated. The `fetched_at` timestamp exists on `FundamentalsSnapshot` and could be used to flag data older than N days.

**Recommendation:** Implement `stale_pct` — percentage of top-N results where `fetched_at` is more than 7 days old. Alert if > 10%.

### 8.3 Point-in-Time Data

The system does not implement point-in-time data management. Ideally, the fundamental data used for screening should reflect what was *known at the time of the screen*, not what was subsequently revised. yfinance and EDGAR provide the most recent reported values, which may include retrospective restatements.

For a live system (not backtesting), this is less critical since screens use current data. For any future backtesting, this would be a critical issue. EDGAR XBRL data is partially point-in-time (filing dates are explicit).

---

## 9. Priority Recommendations

### Tier 1: Fix Now (Bugs)

| Issue | File | Impact | Fix Complexity |
|-------|------|--------|----------------|
| Greenblatt percentile uses combined_rank instead of ordinal position | screener.py | High — distorts composite scores for ~50% of candidates | Low (pass ordinal position, not combined_rank) |
| Altman uses manufacturing formula for all companies | altman.py | High — Z-scores wrong for tech/service companies | Medium (add sector routing, Z'' formula) |
| Piotroski signal #8 uses operating margin instead of gross margin | piotroski.py | Medium — misclassifies efficiency signals | Medium (requires adding gross_profit field) |
| Momentum calculation uses wrong formula for J-T skip-month | screener.py | Low-Medium — approximation is directionally correct | Low (recalculate ret_skip) |

### Tier 2: Improve Soon (Methodology)

| Issue | File | Impact | Fix Complexity |
|-------|------|--------|----------------|
| Add Beneish M-Score as binary exclusion filter | New: beneish.py | High — catches earnings manipulators before they enter pipeline | Medium (requires additional fields) |
| Fix retained_earnings fallback to net_income | altman.py | Medium | Low (remove fallback, populate field better) |
| Piotroski prior-year normalization (3/3 = 1.0) | composite.py, piotroski.py | Low-Medium | Low (normalize all against 9) |
| ADR exclusion | universe.py | Low-Medium | Low (add country check) |

### Tier 3: Enhance Later (Enhancements)

| Enhancement | Benefit | Complexity |
|------------|---------|------------|
| Add gross profitability (Novy-Marx) as composite factor | +5-10% predictive signal | Medium |
| Add FCF yield alongside EBIT/EV in Greenblatt | More manipulation-resistant earnings yield | Low |
| Implement stale data pct in data quality report | Operational quality signal | Low |
| Weight Altman by actual Z-score value (not just zone) | Better differentiation within safe zone | Low |
| Compute momentum cross-sectionally across full universe | Eliminates selection bias | Medium |

---

## 10. References and Sources

- Greenblatt, J. (2005). *The Little Book That Beats the Market*. John Wiley & Sons.
- Piotroski, J.D. (2000). "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers." *Journal of Accounting Research*, 38.
- Altman, E.I. (1968). "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy." *Journal of Finance*, 23(4), 589-609.
- Altman, E.I. (1995). "Predicting Financial Distress of Companies: Revisiting the Z-Score and ZETA Models." NYU Working Paper.
- Beneish, M.D. (1999). "The Detection of Earnings Manipulation." *Financial Analysts Journal*, 55(5), 24-36.
- Jegadeesh, N. & Titman, S. (1993). "Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency." *Journal of Finance*, 48(1), 65-91.
- Novy-Marx, R. (2013). "The Other Side of Value: The Gross Profitability Premium." *Journal of Financial Economics*, 108(1), 1-28.
- Damodaran, A. "Return on Capital (ROC), Return on Invested Capital (ROIC), and Return on Equity (ROE): Measurement and Implications." NYU Stern.
- Wikipedia: Magic Formula Investing, Piotroski F-Score, Altman Z-Score, Beneish M-Score, Return on Invested Capital, Momentum Investing, Factor Investing.
- Schwartz, M. & Hanauer, M.X. (2024). "Formula Investing." SSRN Working Paper No. 5043197.

---

*This review covers all 6 files in `/home/investmentology/src/investmentology/quant_gate/` plus the supporting `models/stock.py` and `data/universe.py`. The most critical fix is the Greenblatt composite scoring bug (Tier 1, ordinal vs combined_rank) and the Altman Z-Score formula variant selection.*
