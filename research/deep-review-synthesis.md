# Investmentology Deep Review: Unified Synthesis & Actionable Roadmap

*Author: Synthesizer Agent (Claude Sonnet 4.6)*
*Date: 2026-03-08*
*Source: 6 deep review documents + Phase 2 synthesis + Phase 3 application plan*

---

## 1. TOP 5 CRITICAL BUGS (Fix Immediately)

These mathematical errors are actively degrading screening and analysis quality on every pipeline run.

---

### Bug #1 — Greenblatt Composite: `combined_rank` passed where ordinal position expected

**Severity**: CRITICAL — affects composite scoring for ~50% of all candidates.

**Location**: `src/investmentology/quant_gate/screener.py:313–314`

**The Bug**:
```python
score = composite_score(
    greenblatt_rank=gr.combined_rank,  # WRONG: combined_rank = ey_rank + roic_rank (range: 2 to 2N)
    total_ranked=total_ranked,         # total_ranked = N
```

`combined_rank` is the sum of two rank components, ranging from 2 (best: rank 1 on both EY and ROIC) to 2×N (worst). But `composite_score()` treats it as an ordinal position (1 to N). For 500 stocks, the formula:
```
greenblatt_pct = (500 - combined_rank) / (500 - 1)
```
goes negative for any stock with `combined_rank > 500` (i.e., the bottom ~50%), gets clamped to 0.0. **The median Greenblatt stock scores 0.0 on the Greenblatt component** and is ranked only by Piotroski + Altman + Momentum.

**The Fix** (one line):
```python
# In screener.py, use loop enumeration:
for ordinal, gr in enumerate(ranked, start=1):
    score = composite_score(
        greenblatt_rank=ordinal,   # 1 = best, N = worst
        total_ranked=len(ranked),
        ...
    )
```

---

### Bug #2 — Altman Z-Score: Manufacturing formula applied to all companies

**Severity**: HIGH — Z-scores systematically wrong for ~70% of the screened universe.

**Location**: `src/investmentology/quant_gate/altman.py`

**The Bug**: The 1968 manufacturing formula (with Sales/Assets as X5 coefficient 1.0) is applied to every company. Most screened stocks are technology, services, healthcare, and consumer companies that should use the 1995 Z'' (non-manufacturer) formula:
```
Z'' = 6.56*X1 + 3.26*X2 + 6.72*X3 + 1.05*X4  (no X5 term)
```
With Z'' thresholds: > 2.6 safe, 1.1–2.6 grey, < 1.1 distress (vs. 2.99/1.81 for original).

Asset-light tech companies get artificially inflated Z-scores under the manufacturing formula (high Sales/Assets inflates X5). Z-score zone assignments are wrong for most non-manufacturers.

**The Fix**:
```python
def compute_z_score(snapshot, sector: str) -> AltmanResult:
    manufacturing_sectors = {"Industrials", "Materials", "Consumer Staples"}
    if sector in manufacturing_sectors:
        return _compute_z_original(snapshot)
    else:
        return _compute_z_double_prime(snapshot)
```

---

### Bug #3 — Piotroski F8: Operating margin used instead of gross margin

**Severity**: HIGH — misclassifies efficiency signals, especially for tech and high-SG&A companies.

**Location**: `src/investmentology/quant_gate/piotroski.py` (signal #8)

**The Bug**:
```python
# F8: Gross margin improving (proxy: operating margin = operating_income/revenue)
current_margin = current.operating_income / current.revenue   # WRONG
```
Piotroski (2000) specifies F8 as `gross_profit / revenue` (gross margin), NOT `operating_income / revenue` (operating margin). The difference: operating margin subtracts SG&A and D&A. A company with improving gross margins but rising SG&A (e.g., scaling sales team) scores 0 on F8 under the current code but should score 1.

**The Fix**:
1. Add `gross_profit: Decimal = Decimal(0)` to `FundamentalsSnapshot`
2. Populate from yfinance `info['grossProfits']` or income statement
3. Update signal #8: `current_margin = current.gross_profit / current.revenue`

---

### Bug #4 — Momentum: Wrong formula for Jegadeesh-Titman skip-month

**Severity**: MEDIUM — directionally correct but mathematically imprecise.

**Location**: `src/investmentology/quant_gate/screener.py:97–100`

**The Bug**:
```python
ret_12m = (series.iloc[-1] / series.iloc[0]) - 1
ret_1m = (series.iloc[-1] / series.iloc[-22]) - 1 if len(series) > 22 else 0
momentum_raw[ticker] = float(ret_12m - ret_1m)   # WRONG
```
The subtraction `ret_12m - ret_1m` is NOT mathematically equivalent to the J-T skip-month return due to compounding. The correct calculation:
```python
# Correct: return from 12 months ago to 1 month ago (skip last month)
if len(series) >= 252:
    momentum_raw[ticker] = float((series.iloc[-22] / series.iloc[-252]) - 1)
```
Also: minimum data check `len(series) < 30` should be `< 220` — IPOs with < 10 months data should not receive momentum scores.

---

### Bug #5 — Piotroski: Prior-year normalization inflates scores for new entries

**Severity**: MEDIUM — systematic bias upward for companies without historical data.

**Location**: `src/investmentology/quant_gate/composite.py:25`

**The Bug**:
```python
PIOTROSKI_MAX_WITHOUT_PRIOR = 3
# ...
piotroski_pct = Decimal(piotroski_score) / Decimal(piotroski_max)
```
A company passing all 3 available single-year tests (no prior data) gets `3/3 = 1.0` — identical Piotroski component score as a company that scores 9/9 with full history. This inflates composite scores for newly-listed or data-poor companies.

**The Fix**: Always normalize against 9. Cap without-prior result at 0.5 (neutral):
```python
# composite.py
piotroski_raw = Decimal(piotroski_score) / Decimal(9)
if not has_prior_year:
    piotroski_pct = min(piotroski_raw, Decimal("0.5"))  # Cap at neutral
else:
    piotroski_pct = piotroski_raw
```

---

## 2. TOP 10 HIGHEST-IMPACT IMPROVEMENTS

Ranked by expected alpha generation and risk reduction.

---

### #1 — Thesis-Based Sell Discipline System

**What**: For each position, store structured invalidation criteria (ROIC threshold, F-Score floor, revenue growth floor, dividend cut trigger, custom LLM-assessed conditions). Auto-monitor and alert when thresholds are breached.

**Why it matters**: The single most documented source of retail investor underperformance is poor sell discipline — holding losers too long (disposition effect, Shefrin & Statman 1985) and selling winners too early. No commercial tool systematically counteracts this.

**Complexity**: M (thesis storage schema + monitoring loop + alert generation)

**Expected impact**: Very High — directly addresses the #1 alpha gap identified in Phase 2 synthesis.

**Files**: `advisory/thesis_health.py`, `sell/engine.py`, `advisory/briefing.py`

---

### #2 — Greenblatt ROIC Working Capital Adjustment

**What**: Exclude excess cash from current assets and interest-bearing short-term debt from current liabilities per Greenblatt's exact definition.

**Why it matters**: Current formula overcounts invested capital for cash-rich or credit-facility companies (Apple, Microsoft, etc.), systematically understating ROIC. This is a foundational metric — errors here propagate through every screen.

**Complexity**: S (add `short_term_debt` field, adjust `net_working_capital`)

**Expected impact**: High — corrects ROIC for the universe's most prominent companies.

**Files**: `models/stock.py:52–56`, `data/yfinance_client.py`

---

### #3 — Beneish M-Score as Binary Exclusion Filter

**What**: Add the Beneish M-Score (8-variable earnings manipulation detector). Companies flagged as likely manipulators (M > -1.78) are excluded from the pipeline before scoring.

**Why it matters**: The Beneish model identified Enron as a likely manipulator in 1998, before its collapse. Allowing manipulators through the pipeline wastes expensive CLI agent analysis on fraudulent companies and risks real capital.

**Complexity**: M (new `beneish.py` + required data fields: gross_profit, receivables, depreciation, SGA)

**Expected impact**: High — risk avoidance + screening quality improvement.

**Files**: New `quant_gate/beneish.py`, `quant_gate/pre_filter.py`

---

### #4 — Macro Regime Pre-Classifier

**What**: Add a `macro_classify` pipeline step running BEFORE agents. Outputs a structured `MacroRegimeResult` (expansion/late-cycle/contraction/recovery + confidence) using FRED data (yield curve, credit spreads, PMI, unemployment). All agents receive the pre-classified regime rather than raw FRED data.

**Why it matters**: Currently each of 9 agents independently interprets macro conditions — 9 redundant, potentially divergent interpretations. A shared pre-classification reduces variance, eliminates redundancy, and ensures agents work within a consistent macro context.

**Complexity**: S–M (1 new pipeline step, 1 new data class, prompt changes)

**Expected impact**: High — reduces analysis variance, improves macro-context consistency.

**Files**: New `data/macro_regime.py`, `pipeline/controller.py`, `pipeline/state.py`

---

### #5 — Sell-Side Verdict Asymmetry Fix

**What**: Mirror the dual-threshold design on the sell side. Currently, BUY requires sentiment > 0.30 AND confidence > 0.50, but SELL/REDUCE has no confidence requirement. Low-confidence bearish calls should map to WATCHLIST, not REDUCE.

**Why it matters**: The asymmetry means the system is much more willing to reduce/sell (low bar) than to buy (high bar). For a buy-and-hold system, this creates excessive turnover when agents are uncertain.

**Complexity**: S (verdict.py threshold logic)

**Expected impact**: High — reduces unnecessary sell signals, aligns with the long-term investment philosophy.

**Files**: `verdict.py:551–560`

---

### #6 — Howard Marks Agent (Credit Cycle + Market Cycle Analysis)

**What**: Add Howard Marks (Oaktree Capital) as a new primary agent. His "second-level thinking" framework ("not what is good, but what does the market think is good, and is the market right?") and explicit credit/market cycle analysis fills a significant gap.

**Why it matters**: The current agent suite has no explicit credit cycle analyst. Dalio covers macro debt cycles, Soros covers reflexivity, but Marks's "pendulum" and "where are we in the cycle?" framework is distinct and has strong empirical grounding. His framework explicitly addresses risk-adjusted return, which the current agents underweight.

**Complexity**: M (new AgentSkill definition + prompt + weight reallocation)

**Expected impact**: High — adds missing market-cycle risk awareness to every verdict.

**Provider**: Claude Opus 4.6 (CLI). **Suggested weight**: 0.09–0.10.

---

### #7 — Portfolio-Level Analytics Dashboard

**What**: Add portfolio-level analytics: sector concentration heatmap, factor exposure breakdown (value/growth/momentum/quality tilt), correlation matrix, "if sector X drops 20%, portfolio impact is Y%" scenario analysis.

**Why it matters**: The system currently analyzes stocks in isolation. A portfolio of 15 high-ROIC tech companies with 5% each looks diversified by count but has enormous concentration risk. No amount of individual stock quality compensates for hidden portfolio-level correlation.

**Complexity**: L (extends `advisory/portfolio_fit.py` + new dashboard components)

**Expected impact**: High — transforms the app from "stock picker" to "portfolio advisor."

**Files**: `advisory/portfolio_fit.py`, `api/routes/portfolio.py`, `pwa/src/views/Portfolio.tsx`

---

### #8 — edgartools Integration for EDGAR Parsing

**What**: Replace raw EDGAR HTTP calls with `edgartools` (pip install, 1,802 GitHub stars). Provides structured XBRL extraction of balance sheet, income statement, cash flows as DataFrames + 10-K/10-Q text extraction.

**Why it matters**: yfinance is flaky (intermittent zeros, delayed updates). edgartools + direct SEC provides more reliable fundamental data — directly improving Piotroski, Altman, and Beneish calculations that depend on accurate income statement items (gross_profit, retained_earnings, SGA).

**Complexity**: M (new client + migration of existing EDGAR calls)

**Expected impact**: High — improves data reliability across all quant gate calculations.

---

### #9 — OctagonAI MCP for Earnings Transcripts

**What**: Add OctagonAI MCP to the agent context. Free MCP server providing earnings call transcripts, private market comparable data, and structured SEC filings. Klarman and Auditor agents particularly benefit from earnings transcript access.

**Why it matters**: Earnings call transcript tone analysis is one of the highest-signal free data sources. Management language changes (increasing hedging language, reduced forward guidance specificity) predict financial deterioration before it appears in numbers. Currently the system has zero transcript analysis.

**Complexity**: S (MCP config entry + agent prompt modifications)

**Expected impact**: Medium-High — significantly enriches qualitative analysis for all primary agents.

---

### #10 — Simons Agent Redesign as Statistical Pattern Recognition

**What**: Completely replace the current Simons "technical analyst" persona with a statistically rigorous pattern recognition framework: momentum persistence check (12-1 month J-T), mean reversion signals, volatility regime classification, short-term reversal. No narrative, no opinions — if no statistical signal exists, abstain.

**Why it matters**: The current Simons agent uses RSI/MACD/moving averages — retail-level technical analysis that has nothing to do with Renaissance Technologies. Jim Simons banned his researchers from generating investment theses. The current persona actively misrepresents what quantitative investing means and produces low-quality signals.

**Complexity**: S (skills.py prompt redesign)

**Expected impact**: Medium-High — eliminates a low-quality signal source and replaces it with genuine statistical pattern recognition.

---

## 3. TOP 5 MISSING CAPABILITIES

Transformational additions that would elevate the platform from "good stock screener" to "serious investment management system."

---

### Missing Capability #1 — Structured Thesis Lifecycle with Automated Monitoring

**What's missing**: The thesis_events table exists, but invalidation criteria are free text and not automatically monitored. No system checks whether a thesis is being confirmed or broken on each pipeline run.

**Why transformational**: Every serious investment firm maintains a thesis log and monitors it systematically. Without this, positions are managed by feel, not by systematic process. The disposition effect (holding losers, selling winners) is almost guaranteed without automated thesis monitoring.

**Architecture sketch**:
```
invest.thesis_criteria (new table):
  - position_id, criteria_type (enum: roic_floor, fscore_floor, revenue_growth_floor,
    debt_ceiling, dividend_cut, custom_llm), threshold_value, monitoring_active

ThesisMonitor (new class):
  - Runs after each pipeline cycle for held positions
  - Checks each criterion against latest fundamentals
  - Emits ThesisBreakEvent to thesis_events table
  - Triggers sell/engine.py evaluation
```

---

### Missing Capability #2 — Risk Management Framework (Stop-Losses, VaR, Sector Limits)

**What's missing**: The system has no stop-loss logic, no portfolio-level maximum drawdown control, no sector concentration limits, no VaR/CVaR. The theory review rated Risk Management D — the lowest score in the system.

**Why transformational**: An analysis system without risk management is like a car without brakes. A portfolio can have 15 perfect individual BUY signals while having catastrophic sector concentration or correlation risk.

**Architecture sketch**:
```
RiskManager (new class in timing/):
  - check_stop_loss(position) → SELL if drawdown > type_threshold
  - check_sector_concentration(portfolio) → WARNING if sector > 30%
  - compute_portfolio_var(portfolio, confidence=0.95) → expected 1-day loss
  - check_correlation_concentration(portfolio) → identify correlated clusters

Applied in sell/engine.py BEFORE agent verdicts are consulted.
```

---

### Missing Capability #3 — Company Knowledge Graph (Supply Chain + Competitor Relationships)

**What's missing**: No mapping of how companies relate to each other — suppliers, customers, competitors, regulatory dependencies.

**Why transformational**: A TSMC supply constraint affects NVIDIA, Apple, AMD, Qualcomm simultaneously. Without relationship data, the system analyzes each company as if it exists in isolation. When macro events hit supply chains, the system would give BUY signals on multiple companies all about to be hurt by the same event.

**Architecture sketch**:
```
Neo4j (already in Kernow stack via knowledge-mcp):
  Company nodes: {ticker, name, sector, industry}
  Relationships: SUPPLIES_TO, CUSTOMER_OF, COMPETES_WITH, REGULATED_BY

Population: Extract from 10-K risk factors using edgartools + LLM extraction
  Cost: ~$10–50 one-time compute
  Maintenance: Quarterly re-extraction for top 200 holdings/watchlist

Agent enrichment: Soros/Druckenmiller receive supply chain exposure context
  "This company's 3 major suppliers are X, Y, Z. Currently: X is distressed."
```

---

### Missing Capability #4 — Black-Litterman Portfolio Optimization

**What's missing**: Position sizing is based on Kelly Criterion applied to individual conviction scores. There's no portfolio-level optimization that accounts for expected returns, covariance structure, and risk budget simultaneously.

**Why transformational**: The current approach treats each position independently. Black-Litterman (Litterman & He, 1991) combines the market equilibrium return vector with agent-expressed views and uncertainty. The multi-agent confidence scores map perfectly to B-L "investor views with confidence." The result: mathematically optimal position weights rather than heuristic Kelly fractions.

**Architecture sketch**:
```python
# PyPortfolioOpt (pip install)
from pypfopt import BlackLittermanModel, EfficientFrontier

# Agent verdicts → B-L views
views = {ticker: agent_consensus_return for ticker, verdict in verdicts.items()}
view_confidences = {ticker: verdict.confidence for ...}

bl = BlackLittermanModel(cov_matrix, pi=market_weights, Q=views, P=view_matrix)
optimal_weights = bl.bl_weights()
```

---

### Missing Capability #5 — Calibrated Confidence with Outcome Tracking and Agent Leaderboard

**What's missing**: The calibration infrastructure exists (ECE, Brier score, isotonic regression) but requires 100+ settled predictions per agent — estimated 3–6 months of operation to accumulate. No leaderboard or agent-level performance attribution exists.

**Why transformational**: Without calibration feedback, the system cannot improve. Agent weights are currently static. After 12 months of operation, you should know empirically: "Warren Buffett is correct 73% of the time when he says BUY with 0.7 confidence; Soros is correct 61% of the time at the same confidence level." These empirical weights should replace the hand-tuned prior weights.

**Architecture sketch**:
```
invest.agent_calibration_history (new table):
  - agent_name, ticker, sentiment, confidence, verdict, outcome_return,
    outcome_beat_benchmark, settled_at

AgentLeaderboard view (new API + PWA):
  - Per-agent: accuracy@70%confidence, Brier score, ECE
  - Cross-agent: correlation matrix, diversity score
  - Temporal: calibration improving or declining?
```

---

## 4. AGENT ARCHITECTURE RECOMMENDATIONS

### Team vs. Individual: The Wisdom-of-Crowds Finding

**Keep agents independent for first-pass analysis.** The Galton–Surowiecki "wisdom of crowds" requires four conditions: diversity of opinion, independence, decentralization, and an aggregation mechanism. The current system satisfies all four. Breaking independence by letting agents see each other's preliminary outputs would cause information cascades (Banerjee 1992) — agents would anchor to the first response rather than reasoning from their own information.

**The one exception**: All agents should receive a pre-computed `MacroRegimeResult` (expansion/contraction/etc.) BEFORE running. This is sharing factual context, not opinion — it eliminates 9 redundant macro regime assessments without creating cascade risk.

**Debate should stay conditional** (< 75% consensus trigger) but should allow direction changes with mandatory justification strings. The current hard direction-lock (cannot flip from bullish to bearish in debate) preserves diversity but prevents genuine learning when new information surfaces.

---

### Simons Redesign

**The current Simons agent is a conventional technical analyst (RSI/MACD), not a quantitative researcher.** This is the single largest persona inaccuracy in the system. Renaissance Technologies explicitly banned investment theses — they traded statistically validated patterns without narrative.

**Redesigned Simons agent**:
- **Philosophy**: "Pure statistical pattern recognition. No narrative, no thesis. If no statistically significant pattern in the price/volume data, abstain."
- **Step 1**: Momentum persistence (12-1 month J-T, skip month)
- **Step 2**: Volatility regime classification (high-vol regime reduces momentum reliability)
- **Step 3**: Short-term reversal check (1-week return as weak predictor of next week's direction)
- **Critical rule**: "Without at least 10 months of consistent price data, confidence is capped at 0.20. The Medallion Fund required massive datasets; a single stock is not statistically meaningful."
- **Cap**: Confidence capped at 0.15 without `technical_data` (unchanged)

---

### Howard Marks Addition

**Add Howard Marks as 7th primary agent.** No current agent explicitly asks "where are we in the market cycle?" and "what is the market pricing in vs. what is the reality?"

**Agent design**:
- **Philosophy**: Second-level thinking ("not what is good, but what does the market believe about what is good, and is the consensus wrong?")
- **Framework**: Credit cycle + asset price pendulum. Explicit cycle position: early-cycle (aggressive), mid-cycle (patient), late-cycle (defensive), peak (reduce exposure)
- **Required data**: macro_context, credit spreads, VIX term structure, investor sentiment surveys
- **Weight**: 0.09 (drawing from reductions in Dalio: 0.12→0.10, Soros: 0.10→0.08)
- **Provider**: Claude Opus 4.6 (CLI — requires deep qualitative reasoning)

---

### Provider Assignment Changes

| Agent | Current | Recommendation | Rationale |
|-------|---------|---------------|-----------|
| Warren | Claude Opus (CLI) | Keep | Deep qualitative moat analysis requires best model |
| Auditor | Claude Opus (CLI) | Keep | Forensic accounting requires careful reasoning |
| Klarman | Claude Opus (CLI) | Keep | Conservative bear-case DCF requires Opus |
| Soros | Gemini 2.5 Pro (CLI) | Keep | Macro narrative suits Gemini's breadth |
| Druckenmiller | Gemini 2.5 Pro (CLI) | Keep | Macro + catalyst suits Gemini |
| Dalio | Gemini 2.5 Pro (CLI) | Keep | Economic machine model suits Gemini |
| Howard Marks (NEW) | Claude Opus (CLI) | New | Credit cycle reasoning requires Opus |
| Simons | DeepSeek Chat (API) | Keep model, redesign persona | Fast/cheap appropriate for quant; persona is wrong |
| Lynch | DeepSeek Chat (API) | Consider deepseek-reasoner | Qualitative "two-minute story" judgment benefits from reasoner |

---

### Weight Adjustments

| Agent | Current | Recommended | Change |
|-------|---------|-------------|--------|
| Warren | 0.18 | 0.17 | Slight reduction — well-established, not underweighted |
| Auditor | 0.17 | 0.17 | Keep — risk gate value is high |
| Klarman | 0.12 | 0.13 | Slight increase — margin of safety underweighted |
| Druckenmiller | 0.11 | 0.11 | Keep |
| Dalio | 0.12 | 0.10 | Reduce — good framework but over-systematic |
| Soros | 0.10 | 0.08 | Reduce — reflexivity harder to operationalize at stock level |
| Howard Marks (NEW) | 0.00 | 0.09 | New — fills credit cycle gap |
| Simons | 0.07 | 0.07 | Keep — appropriate for statistical role |
| Lynch | 0.07 | 0.08 | Slight increase — GARP signals underweighted |

*Total = 1.00. Conditional agents (Income Analyst 0.06, Sector Specialist 0.05) are additive when activated.*

---

## 5. MATHEMATICAL CORRECTIONS

All formula fixes, threshold adjustments, and calibration improvements consolidated from all 6 reviews.

### Immediate Formula Fixes

| Issue | File | Fix |
|-------|------|-----|
| Greenblatt composite rank (ordinal vs combined_rank) | screener.py:313 | Pass loop index, not `gr.combined_rank` |
| Altman formula variant (manufacturing for all) | altman.py | Detect sector; apply Z'' for non-manufacturers |
| Piotroski F8 (operating margin vs gross margin) | piotroski.py | Require `gross_profit` field; use `gross_profit / revenue` |
| Momentum skip-month (subtraction vs direct) | screener.py:97 | Use `series.iloc[-22] / series.iloc[-252]` directly |
| Piotroski without-prior normalization | composite.py:25 | Always normalize against 9; cap result at 0.5 |
| ROIC working capital (includes cash + ST debt) | models/stock.py:52 | Exclude excess cash and interest-bearing ST debt from NWC |
| Altman retained_earnings fallback to net_income | altman.py:71 | Remove fallback; populate field from EDGAR; flag as approximate |

### Confidence and Calibration Corrections

| Issue | Current | Fix |
|-------|---------|-----|
| Sell-side bias correction magnitude | 1.30× global | Empirical ratio ≈ 1.56×; Auditor: 1.0×, Warren: 1.30×, Soros/Druck/Dalio: 1.40× |
| Calibration method | Isotonic regression at 100+ samples | Switch to temperature scaling at 50–100 samples; isotonic at 300+; Brier score decomposition |
| Sell-side correction: no confidence gate for SELL | Single-threshold sell verdicts | Mirror buy-side dual threshold: SELL requires sentiment < -0.30 AND confidence > 0.50 |
| Auditor veto isolation | Single-agent veto allowed | Require 2+ other agents also bearish before auditor veto fires (unless auditor confidence > 0.80) |
| Sentiment formula double-penalty | `sentiment × evidence_factor` | Separate: evidence_factor scales CONFIDENCE, not sentiment direction |

### Threshold Adjustments

| Threshold | Current | Recommended | Rationale |
|-----------|---------|-------------|-----------|
| Momentum minimum data | `len(series) < 30` | `len(series) < 220` | Less than ~10 months = unreliable J-T signal |
| Piotroski without-prior max | 3 (inflates to 1.0) | Normalize against 9, cap at 0.5 | Prevents inflation |
| Calibration minimum samples | 100 per agent | 300 for isotonic; 50–100 for temperature scaling | Literature recommendation |
| Altman zone: non-manufacturers | 2.99/1.81 thresholds | Z'': 2.6/1.1 thresholds | Altman (1995) non-manufacturer specification |
| Regime adjustment for permanent positions | Fear raises buy threshold | Keep base thresholds for `permanent` type in fear | Value investing thesis: fear = opportunity |
| Debate trigger threshold | 75% consensus | Keep 75%; allow direction changes with justification | 75% is appropriate; hard direction-lock is too restrictive |

---

## 6. ECOSYSTEM INTEGRATIONS

Priority-ranked tools to integrate, with feasibility notes.

| Priority | Tool | Effort | Cost | What it Adds |
|----------|------|--------|------|-------------|
| 1 | **edgartools** (`dgunning/edgartools`) | S | Free | Structured XBRL extraction: gross_profit, retained_earnings, SGA — fixing Piotroski F8, Altman B, Beneish data requirements |
| 2 | **OctagonAI MCP** | S | Free | Earnings call transcripts + private market comparables — enriches Klarman, Auditor, Warren agents |
| 3 | **empyrical + pyfolio** | S | Free | Portfolio performance metrics (Sharpe, Sortino, drawdown) for Layer 6 calibration |
| 4 | **Quiver Quantitative API** | S | Free (20 calls/day) | Congressional trading disclosures — known alpha signal, zero cost |
| 5 | **pandas-ta or TA-Lib** | S | Free | RSI, MACD, Bollinger Bands, ATR for redesigned Simons agent (currently Simons has no quantitative data) |
| 6 | **PyPortfolioOpt** | M | Free | Black-Litterman position sizing — maps agent confidence scores to optimal portfolio weights |
| 7 | **VectorBT** | M | Free | Backtest Magic Formula top-20 historical picks (2015–2024) to validate Layer 1 |
| 8 | **Neo4j Knowledge Graph** | M | Free (K8s available) | Company relationship graph (supplier/customer/competitor) extracted from 10-K risk factors using edgartools + LLM |
| 9 | **OpenBB** | L | Free | Replace yfinance + EDGAR + Finnhub + FRED with unified 200+ connector platform. Wait until AI agent interface stabilizes. |
| 10 | **Custom Investmentology MCP** | L | Free | Expose pipeline data via MCP: `get_agent_verdicts`, `get_paper_portfolio`, `run_quant_gate` — allows HB LXC agents to query live pipeline state |

**Feasibility note**: Tools 1–5 can be added within a day. Tools 6–7 require 1–3 days of integration work each. Tools 8–10 are 1–2 week projects that make sense only after the core pipeline is stable.

---

## 7. PHASED IMPLEMENTATION ROADMAP

### Phase 0: Bug Fixes (1–2 days, do first)

These math bugs are degrading every pipeline run. Fix before any other work.

| Task | File | Time |
|------|------|------|
| Fix Greenblatt ordinal rank bug | screener.py:313 | 30 min |
| Fix sell-side verdict asymmetry (add confidence gate to SELL) | verdict.py:551 | 30 min |
| Fix momentum skip-month formula | screener.py:97 | 30 min |
| Fix Piotroski without-prior normalization | composite.py:25 | 30 min |
| Add `pip install edgartools` + populate gross_profit field | yfinance_client.py | 2 hours |
| Fix Piotroski F8 (use gross_profit/revenue) | piotroski.py | 30 min after edgartools |
| Fix Altman Z-Score formula variant routing | altman.py | 2 hours |
| Fix Altman retained_earnings fallback | altman.py:71 | 30 min |
| Fix ROIC NWC working capital adjustment | models/stock.py:52 | 1 hour |

**Commit strategy**: Two commits — (1) pure logic fixes (ordinal, momentum, piotroski, verdict asymmetry), (2) data layer + formula variant fixes (edgartools, gross_profit, Altman routing).

---

### Phase 1: Quick Wins (1–2 weeks)

High-impact, low-effort improvements that are independent of each other.

| Task | Impact | Effort |
|------|--------|--------|
| Macro Regime Pre-classifier (shared context for all agents) | High | S |
| OctagonAI MCP integration (earnings transcripts) | Medium-High | S |
| pandas-ta for Simons agent data | Medium | S |
| Redesign Simons persona to statistical pattern recognition | Medium-High | S |
| Add `short_interest` to Auditor's optional_data | Medium | S |
| Add Howard Marks agent (AgentSkill definition + prompt) | High | M |
| Beneish M-Score as binary exclusion filter | High | M |
| Add Quiver Quantitative API for congressional trades | Medium | S |
| Confidence range visualization in PWA (min/max/stddev display) | Medium | S |
| Add `agents_missing` count to VerdictResult (transparency) | Low | S |
| Insider cluster-buy detection enhancement | Medium | S |
| Value vs. Momentum disagreement flagging in synthesis | Medium | S |

---

### Phase 2: Core Upgrades (2–4 weeks)

Substantial improvements requiring more design work.

| Task | Impact | Effort |
|------|--------|--------|
| Thesis-Based Sell Discipline System (A3) | Very High | L |
| Portfolio-Level Analytics Dashboard (C3) | High | L |
| Behavioral debiasing UI patterns (thesis-first display, "would you buy today?") | High | M |
| FRED Macro Regime Dashboard in PWA | Medium | M |
| Debate: allow direction changes with justification strings | High | M |
| Add Data Analyst as neutral debate moderator | Medium | S |
| Earnings event trigger (immediate streamlined reanalysis) | High | M |
| Newsletter-style briefings restructure | Medium | M |
| Decision journal enhancement with pattern detection | Medium-High | M |
| Dead-letter alerting for consecutive failure tickers | Medium | S |
| Sell-side correction: per-agent multipliers (Auditor 1.0×, Warren 1.3×) | Medium | S |
| Earnings context to CRITICAL_KEYS (freshness.py) | Medium | S |
| empyrical + pyfolio for Layer 6 tear sheets | Medium | S |

---

### Phase 3: Advanced Capabilities (1–2 months)

Major new capabilities requiring architectural additions.

| Task | Impact | Effort |
|------|--------|--------|
| Risk Management Framework (stop-loss, VaR, sector limits) | Critical | L |
| PyPortfolioOpt Black-Litterman position sizing | High | M |
| Company Knowledge Graph in Neo4j | High | L |
| VectorBT backtesting of Magic Formula historical performance | Medium-High | M |
| Position Lifecycle Management (starter/building/full/trimming) | Medium-High | M |
| Contrarian assessment trigger (>30% decline + improving fundamentals) | Medium | S |
| Temperature scaling calibration (replace isotonic at <300 samples) | High | M |
| Calibration leaderboard + agent weight auto-adjustment | Very High | L |
| Management quality scorecard (SBC/Revenue, incremental ROIC, insider %) | Medium | M |

---

### Phase 4: Aspirational (Long-term vision)

| Capability | Description | Why Later |
|-----------|-------------|-----------|
| Full calibrated agent weights | Empirical weights from 12+ months of settled predictions | Needs data accumulation |
| OpenBB unified data platform | Replace all data sources with OpenBB 200+ connectors | Wait for AI agent interface stabilization |
| Custom Investmentology MCP | Expose pipeline state via MCP for HB LXC agents | Build after core pipeline stabilizes |
| 13D/activist tracking | EDGAR 13D filing monitoring for activist positions | Requires new parsing infrastructure |
| Industry lifecycle S-curve classification | Explicit nascent/growth/mature/decline stage per company | Agents do this implicitly; formalize when patterns emerge |
| Point-in-time data management | EDGAR XBRL filing dates for true PIT fundamental data | Needed only for rigorous backtesting |
| Benchmark-relative framing | Every verdict includes "is this better than SPY?" | Requires consistent expected-return modeling |

---

## 8. KEY INSIGHT SUMMARY

**The single most important takeaway from all 6 reviews:**

> **The Investmentology platform is architecturally correct but mathematically imprecise. Fixing the five critical bugs would immediately improve screening quality. The bigger constraint is that the system is a sophisticated stock *selector* without the infrastructure of a portfolio *manager* — it lacks sell discipline, risk management, and portfolio-level awareness. The highest-impact improvements are not new data sources or additional agents: they are systematic sell discipline (thesis monitoring), risk management (stop-losses, VaR), and portfolio construction (correlation, sector limits). These capabilities are available from free tools and require no institutional data subscriptions.**

The three pillars that transform this from "good stock screener" to "serious investment management system":

1. **Fix the math** (Phase 0 bugs — 1–2 days) — make the foundation trustworthy
2. **Add sell discipline** (thesis monitoring + risk management) — address the #1 source of retail investor losses
3. **Think in portfolios** (correlation, sector concentration, factor exposure) — because individual stock quality is necessary but not sufficient

Everything else — agent accuracy improvements, data enrichment, ecosystem integrations — is valuable enhancement that serves these three pillars.

---

## Appendix: Source Document Summary

| Document | Key Findings |
|----------|-------------|
| `deep-review-quant-gate.md` | 5 critical bugs; Altman formula variant critical; Greenblatt ordinal rank bug critical; Beneish recommended |
| `deep-review-agent-profiles.md` | Simons 3/10 accuracy (fundamental misrepresentation); Howard Marks missing; Soros lacks exit discipline |
| `deep-review-synthesis-math.md` | Sentiment double-penalty; sell-side correction 1.30 vs empirical 1.56; temperature scaling preferred over isotonic |
| `deep-review-orchestration.md` | Independence is correct; macro pre-classifier high value; debate direction-lock too restrictive |
| `deep-review-ecosystem.md` | edgartools + OctagonAI + empyrical immediate priorities; Black-Litterman + VectorBT medium-term |
| `deep-review-theory-validation.md` | ROIC NWC bug; Risk Management rated D; sell threshold asymmetry; survivorship bias in calibration |
| `phase2-synthesis.md` | Sell discipline #1 gap; portfolio construction missing; behavioral debiasing underinvested |
| `phase3-application-plan.md` | 18 concrete improvements across 3 workstreams; thesis system critical path |

---

*Generated 2026-03-08 — Investmentology Deep Review Synthesis v1.0*
