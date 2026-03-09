# Haute-Banque Phase 2: The Path to Wealth Growth

*Author: Synthesis (Claude Sonnet 4.6)*
*Date: 2026-03-09*
*Supersedes: phase2-qualified-plan.md*
*Sources: backtest-design.md, methodology-mapping.md, accuracy-reality-check.md, deep-review-synthesis.md, plan-validation-practitioner.md, plan-validation-technical.md*

---

## Vision

Investmentology is a wealth growth tool. It replicates proven, published methodologies — Greenblatt, Piotroski, O'Shaughnessy, Buffett, Klarman, Howard Marks — in structured code with no gut feel and no behavioral bias. The pipeline imposes institutional discipline on a 10–20 stock concentrated portfolio managed by a single informed investor.

This is not a hedge fund simulator. It is the closest a retail investor can get to a rigorous, rules-based investment process — a family office operating on discipline, not intuition.

**The target**: 60–65% overall stock-level accuracy. 80%+ on the highest-conviction subset where ALL signals align. 20–30% annual portfolio returns. £50k doubling in 3–4 years.

---

## How We Prove It

We do not wait 60 days to see if the pipeline works. We use historical data to prove it has always worked — and to show precisely what the math bugs were costing us.

### Backtest Approach

**Data source**: EDGAR XBRL bulk frames API (`data.sec.gov/api/xbrl/frames/`). Annual calendar-year snapshots: CY2020 through CY2024. True point-in-time fundamentals — the same data that existed at each historical screen date.

**Price data**: yfinance `history()` endpoint with explicit `end=screen_date` parameter. Forward returns measured at +6 months and +12 months.

**Four screen dates**: January 2021, 2022, 2023, 2024. Four complete years covering COVID recovery, rate cycle, bear market of 2022, and AI boom. 400 annual return data points minimum.

### Before/After Bug Fix Comparison

The most compelling deliverable: run the same historical screens with buggy vs. fixed code.

| Bug | Expected before/after impact |
|-----|------------------------------|
| Greenblatt ordinal rank | ~15–30 stocks change position in top-100. Spearman IC improves 0.05–0.15 |
| Altman formula variant | ~20–40% of tech/service companies change zone classification |
| Piotroski F8 (gross vs operating margin) | ~25–35% of companies change F8 signal direction |
| Momentum skip-month subtraction | Correlation between buggy/fixed scores: 0.70–0.85. Boundary stocks shift |
| Piotroski without-prior normalization | 10–25% of universe inflated — these companies drop in ranking post-fix |

### Factor Validation Metrics

For each of four annual screens:
- **Factor IC** (Information Coefficient): Spearman correlation between composite score rank and 12-month forward return rank. Target: IC > 0.05 consistently; good: > 0.10
- **Quintile hit rate**: % of periods where Q1 (top quintile) outperforms Q5. Target: > 60% of periods
- **Top-20 vs SPY**: Equal-weight top-20 vs SPY at 6m and 12m. Target: alpha in 3 of 4 years

### Accuracy Definition

A BUY verdict is accurate if the stock's total return over 12 months from verdict date exceeds SPY total return for the same period. Absolute positive return is not sufficient — we measure benchmark-relative alpha.

### Survivorship Bias Acknowledgment

EDGAR CY20XX frames include companies that later failed — this gives us a cleaner universe than yfinance alone. We document any survivorship bias explicitly. For large-cap universes, the inflation is ~2–5%.

---

## Methodology Foundation

Each proven strategy mapped to published returns, our implementation, and what is currently missing.

| Strategy | Published CAGR | Mechanism | Pipeline Implementation | Missing |
|----------|---------------|-----------|------------------------|---------|
| **Greenblatt Magic Formula** | 30.8% (1988–2004, own backtest); 11–21% (independent) | EBIT/EV × ROIC ranks combined. Top 20–30 equal-weight. | Layer 1 Quant Gate — 40% of composite score | Ordinal rank bug; FCF cross-check; annual rebalancing on 5000+ universe |
| **Piotroski F-Score** | 23% long/short (1976–1996); 7.5% alpha over passive value (long only) | 9 binary financial health signals; most powerful within value stock universe | Layer 1 — 25% of composite score | F8 uses operating margin, not gross margin; gross_profit field missing |
| **O'Shaughnessy QVMM** | 21.2% CAGR (1964–2009); "What Works on Wall Street" | 6-factor composite: value (EV/EBIT), quality (ROA, gross profitability), momentum (12-1 month), shareholder yield | Only 2 Greenblatt factors currently. Missing shareholder yield, gross profitability (Novy-Marx), expanded factor composite | Shareholder yield; gross profitability factor; QVMM composite structure |
| **Altman Z-Score** | Predicts bankruptcy 2 years in advance with ~72% accuracy | 5-factor discriminant analysis. Manufacturing formula vs. Z'' for non-manufacturers | Layer 1 — 15% of composite score | Manufacturing formula applied to all. Z'' missing for tech/services (~70% of universe) |
| **Beneish M-Score** | Identified Enron 1998; detects ~76% of manipulation cases | 8-factor earnings manipulation detector. M > -1.78 = likely manipulator | Not implemented (blocked by gross_profit data) | Requires gross_profit, receivables, depreciation, SGA fields |
| **Warren Buffett / Munger** | ~20% CAGR (1965–2023, Berkshire) | Economic moat (durable competitive advantage), owner earnings, management quality. Buy at significant discount to intrinsic value | Warren agent (primary, 0.18 weight). Adversarial layer (Munger) | No FCF-based owner earnings calculation in quant gate; moat assessment is qualitative only |
| **Seth Klarman / Baupost** | ~19% CAGR (1982–2016, estimated) | Margin of safety as primary principle. Deep value with asymmetric risk/reward. Explicit downside-first analysis | Klarman agent (primary, 0.12 weight). Adversarial bear-case DCF | No hard margin-of-safety threshold in quant gate; Klarman weight arguably too low |
| **Howard Marks / Oaktree** | Oaktree: ~19% since inception (distressed debt + credit) | Second-level thinking: "not what is good, but is the market right about what is good?" Credit and market cycle pendulum | Layer 5 (Timing) — partially. No dedicated agent | No dedicated second-level thinking agent; credit cycle analysis absent |
| **Stanley Druckenmiller** | ~30% CAGR (1987–2010, Duquesne) | Macro + catalyst focus. Concentrated positions when macro and micro align. Decisive sizing changes at conviction inflection | Druckenmiller agent (primary, 0.11 weight) | Catalyst identification weak; concentration guidance not surfaced to user |
| **Jim Simons (statistical)** | 66% gross (1988–2018, Medallion); not comparable to fundamental analysis | Statistical pattern recognition. 12-1 month momentum persistence is the one replicable signal | Simons agent (scout, 0.07 weight) — WRONG PERSONA. Currently uses RSI/MACD | Agent persona fundamentally wrong. Should be pure J-T momentum + mean reversion + volatility regime. Abstain if no signal |
| **Peter Lynch (GARP)** | 29.2% CAGR (1977–1990, Magellan) | Growth at reasonable price. PEG ratio. "Two-minute story" — if you cannot explain the thesis simply, don't invest | Lynch agent (scout, 0.07 weight) | PEG ratio not in quant gate; Lynch weight arguably too low |
| **Jegadeesh-Titman Momentum** | ~12% excess annual return (1993 paper); replicated across asset classes | 12-1 month price return (skip last month to avoid short-term reversal). Strongest published price-based anomaly | Layer 1 — 20% of composite score — but with formula bug | Skip-month subtraction bug; minimum data threshold too permissive (30 days vs 252) |

### What O'Shaughnessy Adds That We're Missing

O'Shaughnessy's 6-factor Value Composite is the best-documented systematic strategy at 21.2% CAGR over 45 years. The factors beyond what we have:

1. **Shareholder yield** = dividend yield + net buyback yield. Companies returning cash to shareholders systematically outperform. Not in current pipeline.
2. **Gross profitability** (Novy-Marx, 2013) = gross profit / total assets. Predicts returns as powerfully as book-to-market. Not in current pipeline.
3. **Value-momentum intersection** — stocks that are both cheap AND have 12-month price momentum outperform either signal alone. Currently momentum and value are additive components, not intersection-tested.

Adding these three items to the quant gate composite would complete the transition from "2-factor Greenblatt" to "6-factor O'Shaughnessy-style composite."

---

## Accuracy Framework

### Calibrated Expectations

| Accuracy Type | Target | What This Means |
|---------------|--------|-----------------|
| Overall stock-level hit rate | 60–65% | % of BUY picks that beat SPY over 12 months |
| High-conviction subset (all signals aligned) | 70–80% | Top 10–20 picks where quant + quality + momentum + multi-agent consensus + macro all agree. Conservative estimate; achieving the upper end requires 12+ months of calibration data. |
| Portfolio annual return target | 20–30% | Consistent with top 1–2% of investors globally |
| Maximum drawdown target | < 25% | Achievable with sector limits and thesis monitoring |

### Why 80%+ Overall Is Not the Target

No systematic strategy based on public fundamental and price data has achieved and maintained 70%+ stock-level accuracy over multiple market cycles. The ceiling with public data is 62–70%, achievable only after 18–24 months of calibration.

The academic evidence is clear:
- Random S&P 500 stock picking: ~45–50% hit rate
- Magic Formula top decile: ~55–60% estimated
- Piotroski high F-score on value stocks: ~60–68% (relative, not vs SPY)
- Multi-factor composite (value + quality + momentum): ~58–65%
- No published systematic strategy: **> 70% sustained**

**The 70–80% is achievable on a specific subset**: the top 10–20 highest-conviction picks where ALL signals simultaneously align — quant gate top decile, high Piotroski, Altman safe, strong momentum, multi-agent BUY consensus, favorable macro regime, no earnings event imminent. In any given cycle, 5–10 stocks will meet all these criteria. On that subset, 70–80% accuracy is a realistic target. Gemini review challenged even this range as ambitious — the lower bound (70%) is the safer planning assumption until calibration data proves otherwise.

### What Actually Generates Returns

Beyond 65% accuracy, marginal improvement in screening quality has less impact than:

1. **Position sizing** (Kelly-weighted sizing can add 3–5% to portfolio returns with the same selection accuracy)
2. **Sell discipline** (preventing losers from becoming 25%+ disasters while letting winners run to 30–50%)
3. **Correlation management** (15 "diversified" tech positions is a sector fund, not a portfolio)
4. **Macro regime awareness** (reducing exposure in late-cycle adds 2–3% annually)

At 65%+, process beats screening improvement as the marginal alpha generator.

### The £50k Math

**£50k growth at 20–30% CAGR:**

| Year | 20% CAGR | 25% CAGR | 30% CAGR |
|------|-----------|-----------|-----------|
| 0 | £50,000 | £50,000 | £50,000 |
| 1 | £60,000 | £62,500 | £65,000 |
| 2 | £72,000 | £78,125 | £84,500 |
| 3 | £86,400 | £97,656 | £109,850 |
| 4 | £103,680 | £122,070 | £142,805 |
| 5 | £124,416 | £152,588 | £185,647 |
| 7 | £179,000 | £238,000 | £314,000 |
| 10 | £309,000 | £465,000 | £688,000 |

**Why doubling in one year is not the target**: At 80% accuracy with reasonable win sizes (+20% per winner, -10% per loser), portfolio return is ~+32% — excellent but not 100%. Doubling in one year requires either concentrated positions in 5–6 multi-bagger picks (very high variance) or extreme leverage. Neither is consistent with a disciplined wealth-building approach. The sustainable path is 3.8 years at 20%/year to reach £100k, then compounding from there.

---

## Phase 0: Fix the Math (Day 1–2)

All five bugs confirmed in the codebase by the technical reviewer. These produce wrong screens on every pipeline run. Fix before any other work.

### Commit 1: Pure Logic Fixes (no data dependencies)

#### Fix 1.1 — Greenblatt Ordinal Rank

**File**: `src/investmentology/quant_gate/screener.py:313–314`

**Bug**: `gr.combined_rank` (range: 2 to 2N) is passed where an ordinal position (1 to N) is expected. For 500 stocks, roughly half the universe has `combined_rank > 500`, scoring 0.0 on the 40%-weighted Greenblatt component.

**Fix**:
```python
for ordinal, gr in enumerate(top_ranked, start=1):
    score = composite_score(
        greenblatt_rank=ordinal,   # 1 = best, N = worst
        total_ranked=len(top_ranked),
        ...
    )
```

**Test to add**: `test_composite_score_uses_ordinal_not_combined_rank()` — verify 500 stocks where `combined_rank > total_ranked` get scores > 0.

---

#### Fix 1.2 — Momentum Skip-Month Formula

**File**: `src/investmentology/quant_gate/screener.py:118–122`

**Bug**: `ret_12m - ret_1m` is not mathematically equivalent to Jegadeesh-Titman skip-month return. Minimum data guard `< 30` is far too permissive — any series with fewer than 252 rows will cause `series.iloc[-252]` index error.

**Fix**:
```python
if len(series) < 252:
    continue
momentum_raw[ticker] = float((series.iloc[-22] / series.iloc[-252]) - 1)
```

**Note**: Use `< 252` (not 220) to prevent index-out-of-bounds on the `series.iloc[-252]` access.

---

#### Fix 1.3 — Piotroski Without-Prior Normalization

**File**: `src/investmentology/quant_gate/composite.py:25,64–65`

**Bug**: A company with 3/3 available points (no prior year) scores 1.0 on the Piotroski component — identical to a company with 9/9. Inflates composite scores for newly-listed or data-poor companies.

**Fix**:
```python
piotroski_raw = Decimal(piotroski_score) / Decimal(9)
if not has_prior_year:
    piotroski_pct = min(piotroski_raw, Decimal("0.5"))  # Cap at neutral
else:
    piotroski_pct = piotroski_raw
```

**Test to update**: `test_without_prior_year_normalizes_to_4` — update assertion from `> 0.8` to `≈ 0.5`.

---

#### Fix 1.4 — Sell-Side Verdict Asymmetry

**File**: `src/investmentology/verdict.py:551–560`

**Bug**: BUY requires `sentiment > 0.30 AND confidence > 0.50`, but REDUCE and SELL have no confidence gate. Low-confidence bearish calls create excessive sell signals.

**Fix**: Mirror the buy-side dual threshold on the sell side:
```python
if sent <= Decimal("-0.30") and confidence < reduce_confidence_threshold:
    return Verdict.WATCHLIST, ...
if sent <= Decimal("-0.50") and confidence < sell_confidence_threshold:
    return Verdict.REDUCE, ...
```

**Tests to add**: `test_reduce_requires_confidence_gate()`, `test_sell_requires_confidence_gate()`.

---

### Commit 2: Altman Z'' Formula Routing

#### Fix 2.1 — Altman Z-Score Formula Variant

**File**: `src/investmentology/quant_gate/altman.py`

**Bug**: 1968 manufacturing formula (with X5 = Revenue/Assets, coefficient 1.0) applied to all companies. ~70% of screened universe are technology, services, healthcare — they should use Altman's 1995 Z'' formula (no X5 term).

**Fix**:
```python
def compute_z_score(snapshot: FundamentalsSnapshot, sector: str) -> AltmanResult:
    manufacturing_sectors = {"Industrials", "Materials", "Consumer Staples"}
    if sector in manufacturing_sectors:
        return _compute_z_original(snapshot)
    else:
        return _compute_z_double_prime(snapshot)

# Z'' coefficients: 6.56, 3.26, 6.72, 1.05 (no X5)
# Z'' thresholds: > 2.6 safe, 1.1–2.6 grey, < 1.1 distress
```

**Threading**: `screener.py:310` must pass `sector=sectors.get(gr.ticker, "")`. The `sectors` dict is already built at `screener.py:193`.

**Tests to update/add**: Update `test_z_score_formula_manual`. Add `test_z_double_prime_for_tech()`, `test_z_original_for_industrials()`.

**Effort**: 3–4 hours (not 2 — sector threading required). Risk: MEDIUM.

---

### Commit 3: gross_profit Data Field + Piotroski F8

#### Fix 3.1 — gross_profit Field (Critical Blocker)

**Files**: `src/investmentology/models/stock.py`, `src/investmentology/data/yfinance_client.py`

**Bug**: `FundamentalsSnapshot` has no `gross_profit` field. Zero occurrences in the codebase. This blocks Piotroski F8 fix AND Beneish M-Score.

**Fix**:
1. Add `gross_profit: Decimal = Decimal(0)` to `FundamentalsSnapshot`
2. Populate from `ticker.income_stmt` or `info['grossProfits']` in `yfinance_client.py`
3. Add edgartools as fallback: `pip install edgartools` provides `us-gaap:GrossProfit` from XBRL

**Note on edgartools**: Use as supplemental fallback for tickers where yfinance lacks `grossProfits`, not as a wholesale migration. yfinance first, edgartools fallback. edgartools (1,806 stars, Python) is production-ready for this additive use.

#### Fix 3.2 — Piotroski F8 (Gross vs Operating Margin)

**File**: `src/investmentology/quant_gate/piotroski.py:108`

**Bug**: F8 uses `operating_income / revenue` (operating margin) instead of `gross_profit / revenue` (gross margin). Piotroski (2000) specifies gross margin explicitly. A company scaling sales team (rising SGA) with improving gross margins fails F8 under the current code but should pass.

**Fix** (after Fix 3.1):
```python
current_margin = current.gross_profit / current.revenue   # was: operating_income
```

**Test to add**: `test_f8_uses_gross_margin_not_operating_margin()` — scenario where gross margin improves but operating margin falls (rising SGA).

---

### Phase 0.5: Backtest Framework (Day 3–5)

**"Build the mirror before the surgery."** (Gemini review) — The backtest framework must exist before AND after bug fixes to measure their impact. Build it immediately after Phase 0 commits, then run the before/after comparison.

#### 0.5.1 — Backtest Infrastructure

**Files**:
- `src/investmentology/backtest/historical_data.py` — EDGAR XBRL annual frame loader + historical prices
- `src/investmentology/backtest/runner.py` — screen executor with buggy vs. fixed comparison
- `src/investmentology/backtest/metrics.py` — Factor IC, quintile returns, hit rate calculation

**Approach**: Build the framework using current (buggy) code first. Run "before" screens on January 2021–2024 EDGAR data. Record baseline. Then apply Phase 0 fixes. Run "after" screens on the same data.

#### 0.5.2 — Before/After Comparison

1. Screen January 2021, 2022, 2023, 2024 with **buggy** code on historical EDGAR data
2. Screen the same dates with **fixed** code
3. Measure: stocks that changed in top-100, Spearman IC improvement, Altman zone reclassifications
4. Document the quantified impact in `/home/investmentology/research/backtest-results-YYYY-MM-DD.md`

This is the evidence base. Before/after comparison on real historical data proves the fixes matter — it is not asserted but measured.

**Timeline**: 4–5 days. Begins immediately after Phase 0 commits (overlap with PR review).

---

#### Fix 0.4 — Liquidity Filter (ADV)

**What**: Filter out illiquid stocks from the quant gate. No point recommending a stock the user can't efficiently trade.

**Why added** (Gemini review): The current pipeline has zero volume or liquidity checks. A micro-cap with $50K/day volume is useless for a £50k portfolio — a single position entry would move the price.

**Filter**: Average Daily Volume × Average Price over 20 trading days > $500,000. Stocks below this threshold are excluded before composite scoring.

**File**: `src/investmentology/quant_gate/screener.py` — add after the market cap filter, before composite scoring.

**Implementation**: yfinance `ticker.history(period="1mo")` provides volume + close price. ~2 hours. Risk: LOW.

---

## Phase 1: Methodology Precision (Week 1–3)

These items complete the analytical foundation. Each is independent and can be developed in parallel.

### 1.1 — Macro Regime Pre-Classifier

**What**: Add a `macro_classify` pipeline step that runs once per cycle, before all agents. Produces a `MacroRegimeResult` (expansion / late-cycle / contraction / recovery + confidence) using FRED data (yield curve inversion, credit spreads, PMI, unemployment trajectory).

**Why**: Currently 9 agents independently interpret macro conditions — 9 redundant, potentially divergent assessments of the same public data. Pre-classification shares factual context (not opinions) without creating information cascades.

**Implementation**:
- New `data/macro_regime.py` — FRED API call + regime classifier (2 hours)
- `controller.py:_tick()` — run `macro_classify` once at cycle start, store in `pipeline_data_cache` with `ticker="__cycle__"` (1 hour)
- `pipeline/state.py` — add `STEP_MACRO_CLASSIFY = "macro_classify"` (15 min)
- `runner.py` — inject `macro_regime` from cycle cache into agent prompt assembly (1 hour)

**Total estimate**: 4–5 hours. Risk: LOW.

**Success criterion**: Macro pre-classifier produces a `MacroRegimeResult` on every pipeline cycle.

---

### 1.2 — Simons Agent Redesign

**What**: Replace the RSI/MACD/moving-average technical analyst persona with statistically rigorous pattern recognition. No narrative, no thesis. If no statistical signal exists, abstain.

**Redesigned methodology**:
1. **Do NOT recalculate momentum** — the quant gate already computes J-T 12-1 month momentum as a math function (20% composite weight). Simons should not duplicate this via LLM. (Gemini review: "momentum should be a math library function, not an LLM prompt")
2. **Volatility regime interpretation** — classify the current vol environment (low/normal/high/crisis) and assess whether momentum signals are reliable in this regime. High-vol regimes reduce momentum persistence.
3. **Momentum quality assessment** — is the momentum driven by a one-off event (earnings spike, acquisition rumor) or sustained business improvement? LLMs are good at this; math isn't.
4. Short-term reversal check (1-week return as weak contrarian predictor)
5. Hard rule: < 10 months of consistent price data → confidence capped at 0.20
6. No signal detected → return WATCHLIST/NEUTRAL, do not fabricate conviction

**Why this matters**: The current Simons persona is a conventional retail technical analyst — RSI/MACD — which has nothing to do with Renaissance Technologies. Jim Simons banned investment theses. The redesigned Simons uses the LLM for what it's good at (interpreting patterns, assessing momentum quality) while leaving the raw momentum calculation to the quant gate math.

**Implementation**: Pure prompt change in `agents/skills.py`. 1–2 hours. Risk: NONE.

**Success criterion**: Simons abstains (returns NEUTRAL/WATCHLIST) on ≥ 30% of stocks where momentum is statistically unclear.

---

### 1.3 — Howard Marks Agent (API, not CLI)

**What**: Add Howard Marks (Oaktree Capital) as 7th primary agent. Second-level thinking framework: "Not what is good, but what does the market believe about it — and is the market wrong?"

**Why this is the missing perspective**: No current agent asks explicitly whether the market has already priced in the quality or cheapness. Warren asks "is this business good?" Klarman asks "is this cheap?" Marks asks "does the market know it's cheap, and if it does, why isn't the price correcting?" That is a distinct and complementary question.

**Critical implementation constraint**: Cannot be Claude CLI. Adding a 4th agent to the Claude queue extends overnight cycle time by ~160 minutes (480 → 640 min), leaving only 50 minutes of margin before market open. A single pipeline failure would miss morning briefing.

**Provider**: OpenRouter with Gemini 2.5 Pro via API (parallel execution, scout-tier). Near-zero cycle time impact.

**Framework**:
- Second-level thinking: market consensus vs. reality gap
- Cycle position: early (aggressive) / mid (patient) / late (defensive) / peak (reduce exposure)
- Required context: `macro_regime`, credit spreads, VIX, investor sentiment
- Explicit abstention: if cycle position is unclear, reduce confidence rather than fabricate certainty

**Weight reallocation**: Dalio 0.12 → 0.10, Soros 0.10 → 0.08, Marks: 0.09 (new). Total unchanged.

**Implementation**: New `AgentSkill` in `skills.py` + gateway entry + weight updates. 4 hours. Risk: MEDIUM (API reliability — test before adding to overnight pipeline).

**Success criterion**: Howard Marks agent produces a verdict on ≥ 80% of analyzed stocks.

---

### 1.4 — Beneish M-Score as Binary Exclusion Filter

**What**: Add the Beneish M-Score (8-variable earnings manipulation detector). Companies with M > -1.78 are excluded from the pipeline before scoring. Binary exclusion — not a composite component.

**Why**: The Beneish model identified Enron in 1998 before collapse. Allowing manipulators through wastes expensive CLI agent analysis and risks real capital.

**Blocked by**: Fix 3.1 (gross_profit). Also requires 3 additional fields: `receivables`, `depreciation`, `SGA`.

**Implementation**: New `quant_gate/beneish.py` + extended `FundamentalsSnapshot` + pre-filter integration. 6–8 hours. Risk: MEDIUM.

**Sequencing**: Begin development in parallel with Phase 1.3, but deploy only after gross_profit data is confirmed working.

---

### 1.5 — Earnings Calendar with Sizing Guidance

**What**: For every held position and watchlist stock, surface days-to-earnings prominently in the PWA and briefing. Add sizing guidance: standard position when > 30 days to earnings; defer entry or reduce to starter position when < 15 days.

**Why elevated to Phase 1**: This prevents the most common retail investment mistake — initiating or adding to a position immediately before a binary event where there is no informational edge. A PM who adds to a position the week before earnings is taking uncompensated binary risk.

**Implementation**: yfinance `ticker.calendar`, surfaced in portfolio view and Monday briefing. Store expected earnings dates per position. 1–2 days.

---

### 1.6 — Monday Morning Briefing (Narrative Format)

**What**: Restructure the existing briefing from data tables to narrative-first format. Lead with thesis health alerts, then actionable events, then monitoring items.

**Why elevated to Phase 1**: If the system produces brilliant analysis that nobody reads because it's formatted as a database dump, the entire pipeline is wasted. Communication is the leverage point on everything else.

**Format**:
1. **Immediate attention**: any position with thesis health = CHALLENGED or BROKEN
2. **This week's events**: earnings in < 10 days, major macro data releases
3. **Watchlist gap**: BUY-rated stocks not yet in portfolio (the hesitation zone)
4. **Monitoring**: F-Score changes, quant gate rank movements
5. **Portfolio posture**: cash level, sector concentration, vs SPY

**Implementation**: Restructure `advisory/briefing.py`. 1–2 days.

---

---

## Phase 2: Process and Discipline (Week 4–8)

These items transform the system from a screening tool into a decision-support instrument a practitioner would actually use.

### 2.1 — Thesis Monitoring with Forced Criteria at Entry

**What**: Structured invalidation criteria stored at buy time and automatically monitored on each pipeline cycle. Criteria breach generates a thesis health alert.

**The critical requirement**: It must be mechanically impossible to record a BUY decision without entering at least one quantifiable invalidation criterion (e.g., "ROIC floor ≥ 12%") and one qualitative criterion (e.g., "thesis breaks if they lose the DOD contract"). Without this forcing function, the system becomes another note-taking tool that nobody acts on.

**The correct software role**: Thesis monitoring surfaces that a threshold has been crossed and requires review. The sell decision remains human. "A threshold has been crossed." Not "sell this."

**Stop-loss philosophy**: Price-only stop-losses are wrong for value investing. Stop-losses should be thesis-dependent:
- `PERMANENT` position type: price stop triggers only if thesis is also CHALLENGED or BROKEN
- `TACTICAL` position type: price-based stop is appropriate (shorter time horizon)

**Schema**:
```sql
-- invest.thesis_criteria
position_id      UUID references positions(id),
criteria_type    ENUM(roic_floor, fscore_floor, revenue_growth_floor,
                      debt_ceiling, dividend_cut, custom_llm),
threshold_value  DECIMAL,
qualitative_text TEXT,
monitoring_active BOOLEAN DEFAULT TRUE,
created_at       TIMESTAMPTZ DEFAULT NOW()
```

**Monitoring**: `ThesisMonitor` runs after each pipeline cycle for held positions. Breaches emit `ThesisBreakEvent` to `thesis_events` table. Appears in Monday briefing immediately.

**Implementation**: `advisory/thesis_health.py` extensions + DB migration + PWA entry screen with forced criteria. ~1 week.

---

### 2.2 — Sector Heatmap and Correlation

**What**: Two specific tools from the Portfolio Analytics concept:
1. Sector concentration by portfolio weight with 30% warning threshold
2. Pairwise correlation matrix for held positions (60-day rolling)

**Why not full Black-Litterman**: B-L was designed for 200+ stock institutional portfolios where Markowitz optimization produces extreme corner solutions. At 10–20 positions, simple conviction weighting achieves the same outcome. The real portfolio risk at this scale is hidden correlation — you think you have 15 uncorrelated ideas but you have 6 tech theses that all correlate 0.75. During a sector rotation, your "diversified" portfolio behaves like a 3-stock portfolio.

**Risk management scoping**: This is the correct risk tool at retail scale. VaR assumes normal distributions and fails exactly during fat-tail crashes when it is most needed. Replace VaR with: sector limits (30% threshold), correlation matrix, minimum 15% cash buffer, and a simple historical stress test.

**Implementation**: `advisory/portfolio_fit.py` extensions + new PWA portfolio analytics view. 1–2 days.

---

### 2.3 — Cash Regime Rule (Macro → Allocation)

**What**: Translate the macro regime pre-classifier (Phase 1.1) into explicit portfolio allocation guidance. The macro regime is computed but currently nothing acts on it.

**Why added** (Gemini review): "There is no rule for when to go 50% cash in bear markets — critical omission." Without this, the system recommends buying during market crashes with the same conviction as during recoveries.

**Rules**:
- `expansion` → standard allocation (70–85% equity, 15–30% cash)
- `late-cycle` → reduce to 60–70% equity, raise cash to 30–40%, tighten entry criteria (require ALL SIGNALS ALIGNED tier)
- `contraction` → reduce to 40–50% equity, 50–60% cash. Only enter positions with highest conviction AND counter-cyclical thesis
- `recovery` → aggressive allocation (80–90% equity), broader entry criteria

**Implementation**: Extend `advisory/portfolio_fit.py` to consume `MacroRegimeResult` from cycle cache and produce allocation guidance. Surface in Monday briefing and on portfolio dashboard. ~1 day.

**Important**: These are advisory guardrails, not hard blocks. The user can override, but the system makes them explicitly acknowledge they are acting against the regime signal.

---

### 2.4 — O'Shaughnessy Factors: Completing the Composite

**What**: Add the three O'Shaughnessy factors missing from the current composite to complete the transition from "2-factor Greenblatt" to "6-factor proven composite":
1. **Shareholder yield** = dividend yield + net buyback yield
2. **Gross profitability** = gross profit / total assets (Novy-Marx, 2013)
3. **Value-momentum intersection** threshold: stocks that are both in value top-quartile AND momentum top-quartile receive composite boost

**Why**: O'Shaughnessy's 6-factor composite delivered 21.2% CAGR over 1964–2009. These specific factors have documented independent and combined alpha. Gross profitability is available after Fix 3.1. Shareholder yield requires adding `dividends_paid` and `net_buybacks` to `FundamentalsSnapshot`.

**Implementation**: Extend composite formula in `composite.py`. Add required data fields to `FundamentalsSnapshot` and `yfinance_client.py`. 2–3 days.

---

### 2.5 — Sell Discipline Triggers

**What**: Specific, enforceable sell trigger conditions that the briefing surfaces as "requires decision":
- Fair value ratio P/FV > 1.0 → "position may be fully valued, review thesis"
- Piotroski F-Score drops ≥ 2 points in one cycle → "financial health deteriorating"
- Composite rank drops from top-quartile to bottom-half → "quant gate no longer supports this"
- Thesis criteria breached (from 2.1) → "original thesis condition no longer holds"

**What we explicitly do NOT do**: Automated sell execution. All triggers generate alerts requiring human review. The "Would you buy today?" question is the synthesized decision gate.

**Implementation**: Extend `sell/engine.py` to evaluate all triggers on each held position. Surface in briefing as structured alerts. 1–2 days.

---

### 2.6 — Prediction Card (Stock Outcome View)

**What**: For every analyzed stock, the PWA shows a single prediction card that tells the user everything they need to make a decision:

```
AAPL — BUY (Strong Conviction)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fair value: $245  |  Current: $198  |  Upside: +24%
Range:   $200 – $290  (bear to bull case)
Bear case:  $165  |  Downside: -17%
Risk/reward ratio: 1.4:1

Confidence: 72% chance of beating SPY over 12 months
(calibrated from 147 settled predictions)

Hold for: 12-18 months
Catalyst: iPhone cycle + services growth inflection
Earnings: 47 days away (safe to enter)

Compare against: SPY at $512 today
Check back: September 2027
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Conviction tier: ALL SIGNALS ALIGNED
  Quant gate: top 15  |  Piotroski: 8/9  |  Altman: safe
  Momentum: top quartile  |  Agent consensus: 87%
```

**Components**:
1. **Composite target price** — weighted average of agent targets (Warren, Klarman, Druckenmiller all produce targets)
2. **Price range / confidence interval** — bear-to-bull spread showing the range of agent estimates (Gemini review: "show range, not just point estimate"). Computed from min(agent targets) to max(agent targets). Wider spread = more agent disagreement = lower confidence.
3. **Bear case price** — from Klarman (always produces this) + Auditor risk quantification
4. **Risk/reward ratio** — upside to target ÷ downside to bear case
5. **Calibrated probability** — "72% chance" from temperature-scaled confidence (Phase 3.3), initially from raw confidence
6. **Holding period** — from catalyst timeline (Druckenmiller 3-6 month catalyst + Lynch category)
7. **Settlement benchmark** — SPY price at verdict date, auto-compared at settlement
8. **Conviction tier** — visual summary of which signals align

**Why this is Phase 2**: The prediction card is the presentation layer for everything the pipeline produces. Without it, brilliant analysis is trapped in database tables. This is what the user actually sees and acts on.

**Settlement tracking**: When the hold period expires, the app automatically compares actual outcome vs prediction. The card updates to show: "Predicted +24%, actual +18%, beat SPY by 7%. CORRECT." This feeds the calibration system.

**Implementation**: New `PredictionCard` component + API endpoint aggregating agent targets, bear cases, catalysts, and conviction tier. Extends existing `calibration_predictions` table. ~3 days.

---

### 2.7 — Debate Direction-Lock Removal

**What**: The current debate hard-locks direction (cannot flip from bullish to bearish during debate). Allow direction changes with mandatory justification strings.

**Why**: Wisdom-of-crowds requires authentic updating when new information surfaces during debate. Hard direction-lock preserves surface diversity while preventing genuine learning. An agent that encounters compelling new evidence should be able to update.

**Implementation**: 2–3 hours in `pipeline/convergence.py`. Risk: LOW.

---

## Phase 3: Optimization (Month 3+)

Only items that survived all validation rounds. Gated behind the 60-day measurement baseline from Phase 1–2.

### 60-Day Measurement Baseline (Gate for Phase 3)

After Phase 1 and Phase 2 are deployed, measure:

| Metric | Target | Action if missed |
|--------|--------|-----------------|
| Overnight success rate | ≥ 90% of runs complete before market open | Fix pipeline reliability before Phase 3 |
| Agent agreement rate | Pairwise correlation < 0.75 | Redesign agent prompts if > 0.85 |
| Quant gate stability | 60–70% week-over-week top-100 overlap | Investigate if < 50% |
| Paper portfolio vs SPY | Record baseline now; measure at 6-month mark | N/A (just measure) |

**Phase 3 does not begin until this data exists.**

### 3.1 — Position Lifecycle Management

Conviction weighting framework with enforced position limits:
- **Full position** (8–10%): Maximum 3 positions. Done full analysis, thesis clear, margin of safety confirmed.
- **Core position** (5–7%): Standard allocation for confirmed thesis.
- **Starter position** (2–3%): Initial entry while continuing research. Maximum 4–5 positions.
- **Cash** (15–30%): Not a failure. If fewer than 4 high-conviction ideas exist, cash is the correct answer.

Enforced by UI: cannot record a position transition without updating the conviction tier.

### 3.2 — Fractional Kelly Position Sizing

After 100+ settled predictions per agent, implement empirical Kelly sizing:
- Compute per-agent win rate and win/loss ratio from calibration data
- Apply fractional Kelly (50% of full Kelly) to avoid overbetting on imperfect calibration
- High-conviction tier (all signals aligned): 1.0× fractional Kelly weight
- Mixed signals: 0.5× fractional Kelly weight
- Gate: requires 100+ settled predictions. Do not implement on hand-tuned priors.

### 3.3 — Temperature Scaling Calibration

Switch from isotonic regression (requires 300+ samples) to temperature scaling (viable at 50–100 samples per agent). Temperature scaling learns a single scalar `T` that divides the agent's raw logits, calibrating the confidence distribution without overfitting.

Gate: requires 50+ settled predictions per agent (3–4 months of operation at current pipeline frequency).

### 3.4 — Conviction Tier System

Apply the accuracy framework in practice:
- "All signals aligned" tier: quant gate top-20, Piotroski ≥ 7, Altman safe, momentum positive, macro favorable, multi-agent BUY consensus ≥ 75%, no earnings in 30 days → Full position + 8–10% weight
- "Mixed signals" tier: quant gate top-50, most agents BUY but dissent exists → Core position 5–7%
- "Watchlist only" tier: quant gate qualifies but agent consensus < 75% → Starter position or cash

### 3.5 — Incremental Analysis Optimization

Skip agent re-analysis when fundamental data hasn't changed materially between cycles. Define "material change" as: ≥ 5% change in revenue, operating income, or debt levels, OR a new earnings report, OR the pipeline cycle coincides with a thesis check date.

This reduces overnight API costs by 30–50% for positions that have been stable for 2+ cycles.

### 3.6 — Agent Calibration Leaderboard

Per-agent accuracy tracking after 100+ settled predictions:
- Brier score, ECE (Expected Calibration Error), accuracy@70%confidence per agent
- Cross-agent correlation matrix (if Warren and Klarman correlate > 0.85, ensemble is not independent)
- Temporal calibration trend (improving or declining?)

Empirical weights from this leaderboard should replace hand-tuned priors after 300+ settled predictions per agent.

### 3.7 — OctagonAI MCP (Earnings Transcripts)

Revisit OctagonAI integration after pipeline stability is demonstrated. The low star count (103) and architectural mismatch (client-side MCP vs. server-side pipeline) make it premature for Phase 1–2. Earnings transcript tone analysis is a high-signal free data source — worth integrating once the pipeline is stable and reliable.

---

## Accuracy Roadmap

| Milestone | Expected Stock-Level Hit Rate | Annual Return Target | Key Driver |
|-----------|-------------------------------|---------------------|------------|
| Current (buggy, uncalibrated) | 50–55% | Unknown | Pipeline operational but math errors + uncalibrated |
| After Phase 0 (bugs fixed) | 55–60% | 15–20% | Better screening → better candidates |
| After Phase 1 (methodology precision) | 57–62% | 18–24% | Correct Piotroski F8, Altman Z'', Simons redesign, O'Shaughnessy factors |
| After Phase 2 (process discipline) | 60–67% | 20–30% | Thesis monitoring + sell discipline + correlation management prevent alpha leakage |
| High-conviction subset (all signals aligned) | 70–80% | N/A (subset, not full portfolio) | Only 10–20 picks/year meet all criteria simultaneously |
| Theoretical ceiling (public data) | 62–70% | 25–40% | Limit of what public fundamental + price data supports |

**The path to 70–80% accuracy on the highest-conviction subset**: Focus the screening criteria to identify where ALL of the following simultaneously agree: (1) quant gate top-20, (2) Piotroski ≥ 7, (3) Altman safe, (4) positive momentum top-quartile, (5) agent consensus ≥ 80%, (6) favorable macro regime, (7) no earnings event imminent, (8) adequate liquidity (ADV > $500K/day). In any given pipeline cycle, 5–15 stocks will meet all criteria. On that subset, 70–80% is achievable and evidence-based.

---

## What We're Replicating

| Proven Investor/Strategy | Published Returns | Our Replication | Status |
|--------------------------|-------------------|-----------------|--------|
| **Greenblatt Magic Formula** | 30.8% (1988–2004 own), 11–21% (independent) | Layer 1 Quant Gate — EBIT/EV + ROIC ranks | Implemented. Ordinal bug to fix. |
| **Piotroski F-Score** | 23% long/short (1976–1996), 7.5% alpha over passive value | Layer 1 — 9-signal quality filter | Implemented. F8 bug to fix (gross margin). |
| **O'Shaughnessy QVMM** | 21.2% CAGR (1964–2009) | Layer 1 composite — need shareholder yield + gross profitability | Partial. Phase 2.3 completes it. |
| **Altman Z-Score** | 72% bankruptcy prediction, 2-year advance warning | Layer 1 — risk filter | Implemented. Z'' formula variant to fix. |
| **Beneish M-Score** | ~76% manipulation detection; identified Enron 1998 | Pre-filter — binary exclusion | Not yet. Phase 1.4. |
| **Jegadeesh-Titman Momentum** | ~12% annual excess return (1993 paper) | Layer 1 — 20% composite weight | Implemented. Formula bug to fix. |
| **Warren Buffett** | ~20% CAGR (1965–2023, Berkshire) | Warren agent (0.18 weight) — moat + owner earnings | Implemented. Persona accurate. |
| **Seth Klarman** | ~19% CAGR (estimated, Baupost 1982–2016) | Klarman agent (0.12 weight) — margin of safety | Implemented. Weight may need increase. |
| **Howard Marks** | Oaktree ~19% since inception | Layer 5 Timing (partial) + new agent | Phase 1.3 adds dedicated agent. |
| **Stanley Druckenmiller** | ~30% CAGR (1987–2010, Duquesne) | Druckenmiller agent (0.11 weight) | Implemented. |
| **Ray Dalio** | Bridgewater All Weather: 10–12% CAGR | Dalio agent (0.12 weight) — macro framework | Implemented. Weight reducing to 0.10 for Marks. |
| **George Soros** | ~28% CAGR (1969–2011, Quantum) | Soros agent (0.10 weight) — reflexivity | Implemented. Weight reducing to 0.08 for Marks. |
| **Peter Lynch** | 29.2% CAGR (1977–1990, Magellan) | Lynch agent (0.07 weight) — GARP, two-minute story | Implemented. PEG ratio not in quant gate. |
| **Jim Simons (statistical pattern)** | 66% gross (Medallion, leveraged, HFT — not comparable) | Simons agent (0.07 weight) — WRONG PERSONA | Phase 1.2 redesigns to J-T momentum. |

---

## Success Metrics

These are testable, not asserted. Each has a specific measurement method.

### Phase 0 (Mathematical Correctness)

- [ ] All 5 bugs confirmed fixed by new regression tests
- [ ] Before/after backtest shows ≥ 15 stocks change in top-100 composition
- [ ] Before/after backtest shows Spearman IC improvement ≥ 0.03 on at least 2 of 4 screen years
- [ ] Altman zone changes: ≥ 20% of tech companies reclassified under Z'' vs manufacturing formula
- [ ] No test regressions except the intentionally-updated normalization test
- [ ] Liquidity filter (ADV > $500K/day) excludes illiquid stocks from composite scoring
- [ ] Backtest framework built and "before" baseline recorded on 4 annual screens (Phase 0.5)

### Phase 1 (Methodology Completeness)

- [ ] Macro pre-classifier produces `MacroRegimeResult` on every pipeline cycle
- [ ] Simons agent abstains on ≥ 30% of stocks (interprets momentum quality, does not recalculate J-T)
- [ ] Howard Marks produces verdict on ≥ 80% of analyzed stocks
- [ ] Earnings calendar surfaces days-to-earnings for all portfolio + watchlist positions
- [ ] Monday briefing leads with thesis health in narrative format (qualitative measure)

### Phase 2 (Process Quality)

- [ ] Every BUY decision recorded after Phase 2 launch has ≥ 1 quantifiable and ≥ 1 qualitative invalidation criterion (enforced by UI — no manual review needed)
- [ ] Cash regime rule translates macro regime into explicit allocation guidance (advisory, not blocking)
- [ ] Sector concentration dashboard shows sector weights
- [ ] Pairwise correlation matrix is visible for held positions
- [ ] Thesis monitor generates alert within 1 pipeline cycle of a criterion breach
- [ ] Prediction card shows price range (agent spread) alongside point estimate

### Phase 1–2 Combined: 60-Day Baseline

- [ ] Overnight success rate ≥ 90%
- [ ] Agent pairwise correlation < 0.75 (measured across 50+ analyses)
- [ ] Top-100 quant gate week-over-week stability: 60–70% overlap
- [ ] Paper portfolio vs. SPY baseline recorded

### Phase 3 (Optimization, gated)

- [ ] Temperature scaling calibration deployed and Brier scores tracking
- [ ] Per-agent accuracy visible in leaderboard after 100+ settled predictions
- [ ] High-conviction tier (all signals aligned) identified on each cycle with specific positions named
- [ ] Kelly-weighted position sizes computed (not just advisory)

---

## Architecture Decisions

### Decision: No Black-Litterman

B-L was designed for 200+ stock portfolios where Markowitz optimization produces extreme corner solutions. At 10–20 positions, simple conviction weighting achieves the same outcome. The real portfolio construction problem at this scale is hidden correlation, addressed by Phase 2.2.

### Decision: Howard Marks via API (OpenRouter/Gemini 2.5 Pro)

Adding a 4th Claude CLI agent would extend overnight cycle from ~480 min to ~640 min, leaving only 50 minutes of margin before market open. A single pipeline failure would miss the morning briefing. OpenRouter provides equivalent model quality without the timing risk.

### Decision: edgartools as Supplement, Not Migration

Use edgartools (yfinance first, edgartools fallback) for the subset of tickers where yfinance lacks `gross_profit`. edgartools (1,806 stars) is production-ready for additive use but has XBRL tagging inconsistencies as a younger library. Full migration carries unnecessary risk.

### Decision: Beneish Binary, Not Composite

Beneish M-Score works as a binary exclusion filter (manipulator detected → excluded from pipeline). As a continuous composite component, it adds complexity without proportional value. Binary implementation: 1 day after data is available. Composite version: much longer, much less value.

### Decision: Agent Independence Retained

Agents receive no preliminary outputs from other agents. Wisdom-of-crowds (Surowiecki) requires diversity, independence, decentralization, and aggregation. Routing preliminary outputs risks information cascades. The single exception: all agents receive the pre-computed `MacroRegimeResult` — factual context, not opinion-sharing.

### Decision: No New Agents After Howard Marks (Until Calibration Data Exists)

After adding Howard Marks, no further agents until the 60-day measurement baseline reveals whether the current ensemble is calibrated. Nine agents on a poorly-calibrated system generate confident-sounding noise. Empirical calibration data (Brier score, ECE) must replace hand-tuned priors before ensemble expansion makes sense.

---

## Commit Sequencing

| Commit | Contents | Risk |
|--------|----------|------|
| 1 | Greenblatt ordinal, momentum formula, Piotroski normalization, verdict asymmetry, ADV liquidity filter | LOW — pure logic, no data dependency |
| 2 | Altman Z'' routing + sector threading + test migration | MEDIUM — test updates required |
| 3 | gross_profit field + yfinance population + edgartools fallback + Piotroski F8 fix | MEDIUM — data availability validation needed |
| 3.5 | Backtest framework + "before" baseline on CY2021–2024 (Phase 0.5) | LOW — read-only against historical data |
| 4 | Phase 1 quick wins: Simons redesign, macro pre-classifier, Howard Marks agent | LOW–MEDIUM |
| 5 | Beneish M-Score exclusion filter (after commit 3 data confirmed working) | MEDIUM |
| 6 | Cash regime rule + prediction card price range | LOW |

---

## Gemini Review Incorporation Log

Changes incorporated from Gemini CLI review (2026-03-09):

1. **Accuracy targets adjusted** — High-conviction subset: 75–85% → 70–80%. Added caveat that lower bound is the safer planning assumption.
2. **Backtest moved to Phase 0.5** — "Build the mirror before the surgery." Framework built before bug fixes to enable before/after comparison.
3. **ADV liquidity filter added** (Fix 0.4) — $500K/day minimum. No existing volume checks in quant gate.
4. **Simons agent clarified** — LLM interprets momentum quality and volatility regime; raw J-T momentum stays in quant gate math. No duplication.
5. **Cash regime rule added** (Phase 2.3) — Macro regime now translates to explicit allocation guidance (expansion/late-cycle/contraction/recovery).
6. **Prediction card enhanced** — Added price range/confidence interval (agent spread) alongside point estimate.

Items reviewed but not changed:
- Temperature scaling data requirements — already gated behind Phase 3 (50+ predictions)
- yfinance reliability — already addressed by data quality gate + edgartools fallback

---

*Definitive plan v1.1 — 2026-03-09 (post-Gemini review)*
*Supersedes: phase2-qualified-plan.md*
*Input sources: 7 research documents, 6 deep reviews, 3 validation rounds, 1 Gemini review*
