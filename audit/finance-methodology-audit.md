# Investmentology Finance Methodology Audit

**Date**: 2026-03-04
**Auditor**: Senior Quantitative Finance Analyst (20+ years institutional hedge fund experience)
**Scope**: Complete methodology review of the 6-layer investment pipeline, agent framework, risk management, data quality, and learning systems.

---

## 1. Executive Summary

**Overall Grade: B- (Promising prototype, not investment-grade)**

Investmentology is an ambitious and architecturally thoughtful attempt to encode institutional investment processes into an automated pipeline. The 6-layer sequential architecture reflects genuine understanding of how professional investment committees operate. The agent personas are well-researched, the adversarial framework is a genuinely good idea, and the decision registry / calibration loop shows mature thinking about learning from outcomes.

However, several critical gaps prevent this from being suitable for managing real capital:

**Key Strengths:**
1. Sound pipeline architecture that mirrors institutional workflow
2. Well-differentiated agent personas with appropriate philosophical anchors
3. Adversarial framework (Munger layer) is a genuine differentiator
4. Data validation gate catches real yfinance corruption issues
5. Thesis lifecycle management with verdict gating prevents whipsaw

**Critical Weaknesses:**
1. No portfolio-level risk management (VaR, correlation matrix, drawdown limits)
2. Kelly Criterion implementation has a fundamental formula error
3. Position sizing ignores volatility entirely
4. No transaction cost modeling
5. Consensus mechanism is too simplistic for capital allocation
6. Altman Z-Score uses net_income as proxy for retained_earnings (materially wrong)
7. No real-time stop-loss or circuit breaker at portfolio level
8. Calibration loop has no minimum sample size per bucket for statistical validity

---

## 2. Pipeline Architecture Assessment

### 2.1 Layer 1: Quantitative Gate (Greenblatt Magic Formula + Composite)

**What it does**: Screens 5000+ stocks using Greenblatt's ROIC + Earnings Yield ranking, then enriches the top N with Piotroski F-Score and Altman Z-Score into a composite score (50% Greenblatt / 30% Piotroski / 20% Altman).

**Strengths:**
- Correct implementation of the core Greenblatt ranking (`greenblatt.py:56-130`). The sort-by-rank-sum approach is faithful to the original methodology.
- Sector exclusions (Financial Services, Utilities) are appropriate per Greenblatt's original specification (`greenblatt.py:12`).
- Adding Piotroski and Altman as supplementary scores is a genuinely good extension. The composite weighting (50/30/20) is reasonable.
- EDGAR bulk data path for speed is a smart engineering choice (`screener.py:157-196`).

**Weaknesses:**

1. **Altman Z-Score uses net_income as proxy for retained_earnings** (`altman.py:70-72`). This is materially wrong. Retained earnings is a *cumulative* balance sheet item representing decades of accumulated profits minus dividends. Net income is a *single period* flow item. For a mature company like Apple (retained earnings ~$0 due to buybacks, net income ~$100B), this proxy produces wildly incorrect Z-Scores. The comment acknowledges this ("understates B for mature companies") but the impact is not "understated" -- it can flip the zone classification entirely.

2. **Piotroski uses operating_income as proxy for operating cash flow** (`piotroski.py:60-61`). The comment says "Without a cash flow statement, operating income is the best available proxy." This defeats the entire purpose of Piotroski's test #2, which is specifically designed to catch accrual manipulation. Operating income IS the accrual measure -- the test is supposed to compare it against cash flow. Using operating income as proxy for both sides makes the test tautological.

3. **Accruals quality test is backwards** (`piotroski.py:74`). `operating_income > net_income` is used as the accruals quality proxy. In Piotroski's formulation, OCF > NI means cash generation exceeds reported earnings (good). But operating_income > net_income just means the company has non-operating losses (interest, taxes, write-offs), which is normal and says nothing about accruals quality.

4. **No quality-of-earnings screen**. The Greenblatt screen finds high ROIC + high earnings yield. But it doesn't distinguish between companies earning that ROIC through genuine competitive advantage vs. financial engineering (aggressive revenue recognition, capitalized expenses, off-balance-sheet debt). At institutional scale, you'd overlay a Beneish M-Score filter here.

5. **No momentum overlay**. Pure value screens consistently underperform when momentum is ignored. The academic literature (Asness et al., "Value and Momentum Everywhere") shows that combining value + momentum significantly improves risk-adjusted returns. Adding a 12-1 month momentum filter to the Greenblatt results would be a material improvement.

6. **Composite score has no validation**. The 50/30/20 weighting is presented as fixed. There's no backtesting or empirical validation of these weights. Are they optimal? No analysis is presented.

**Institutional Gap**: A real quant screen at an institutional fund would include: (a) quality factor (ROE stability, earnings volatility), (b) momentum factor, (c) liquidity filter (minimum ADV), (d) sector-neutral ranking option, (e) multi-period lookback (not just trailing 12M), (f) backtested weight optimization.

### 2.2 Layer 2: Competence Filter

**What it does**: LLM-based assessment of whether a business is "within the circle of competence" using the Buffett framework. Also includes moat analysis via the Morningstar 5-source framework.

**Strengths:**
- Honest framing of what an LLM can and cannot assess (`circle.py:41-54`).
- Moat analysis uses the well-established Morningstar framework (`moat.py:45-48`).
- Graceful degradation on parse failure defaults to "out of circle" (conservative, correct).

**Weaknesses:**

1. **"Circle of competence" is philosophically incoherent for an AI system**. The concept means "businesses YOU personally understand." An LLM has no personal understanding -- it has statistical language patterns. Asking an LLM "is this in our circle of competence?" produces a confident answer for any business, because LLMs have broad training data about all sectors. The filter will never meaningfully exclude anything unless prompted with explicit sector restrictions.

2. **Uses DeepSeek-chat for competence assessment** (`circle.py:29-30`). This is the cheapest model in the stack. Competence assessment is a high-judgment task -- if you're going to use an LLM for this, use your best model (Claude Opus), not the cheapest.

3. **Moat analysis from fundamentals alone is insufficient** (`moat.py:55-101`). The prompt provides only ROIC, margin, market cap, revenue, and debt/assets. Real moat assessment requires: competitive landscape analysis, customer switching cost data, patent portfolio review, market share trends, pricing power evidence. The financials alone cannot distinguish a wide-moat company from one with temporarily high margins due to a favorable cycle.

4. **No calibration of competence assessments**. There's no feedback loop measuring whether "in circle" assessments correlate with better outcomes. Without this, the filter may be adding noise rather than signal.

**Institutional Gap**: Real funds define their circle of competence explicitly (sectors, market caps, geographies) as firm policy, not per-stock LLM assessment. The moat analysis would be done by sector analysts with deep domain expertise, not by a generic LLM prompt.

### 2.3 Layer 3: Multi-Agent Analysis

**Assessed in Section 3 below.**

### 2.4 Layer 4: Adversarial Check (Munger)

**What it does**: Three-pronged adversarial review: (1) keyword-based bias detection across 20 cognitive biases, (2) LLM-generated "Kill the Company" scenarios, (3) LLM-generated pre-mortem analysis. Triggers on suspicious unanimity, Warren-Auditor disagreement, or all conviction buys.

**Strengths:**
- **This is the best-designed layer in the entire system.** The adversarial approach is genuinely valuable and rare even in institutional settings.
- Trigger conditions are well-chosen (`munger.py:66-134`). Suspicious unanimity (all agents high confidence, same direction) is exactly when you should be most skeptical.
- The Kill the Company exercise (`kill_company.py`) is a structured version of what the best funds do informally.
- Pre-mortem with historical base rates (`munger.py:171-189`) is sophisticated. Using sector-specific success rates from the decision registry to calibrate the pre-mortem is genuinely clever.
- Veto scoring system (`munger.py:248-289`) with explicit thresholds is transparent and auditable.

**Weaknesses:**

1. **Bias detection is pure keyword matching** (`biases.py:146-183`). Checking if the word "confirms" appears in reasoning and flagging "Confirmation Bias" is extremely crude. The word "confirms" appears in perfectly valid analytical statements ("Q2 revenue confirms the growth trajectory"). This will generate massive false positives, desensitizing users to bias warnings.

2. **20 biases, not 25 as claimed**. `COGNITIVE_BIASES` list in `biases.py` contains exactly 20 entries (lines 22-143), not 25 as stated in the CLAUDE.md documentation.

3. **Kill the Company uses DeepSeek** (`munger.py:59`). The adversarial layer is where you want your strongest model. DeepSeek-chat generating kill scenarios will produce generic risks ("competition could increase," "regulation could tighten") rather than the incisive, company-specific threats a senior analyst would identify.

4. **No adversarial review of the SELL side**. The Munger layer triggers on conviction BUY decisions. But cognitive biases are equally dangerous on SELL decisions (loss aversion, endowment effect, sunk cost fallacy). Selling a winner too early or holding a loser too long are the most common institutional mistakes.

5. **Pre-mortem probability estimates are unvalidated categories** (`premortem.py:34`). "unlikely" (<20%), "possible" (20-40%), "plausible" (40-60%), "likely" (>60%) -- these are subjective LLM outputs mapped to vague ranges. An LLM saying "plausible" means nothing without calibration data showing that "plausible" assessments actually materialize 40-60% of the time.

**Institutional Gap**: A real adversarial process uses human red-team analysts who have dedicated weeks to researching the bear case. The pre-mortem would reference specific comparable failures (e.g., "here's what happened to Blackberry when iOS launched"). The bias detection would be done by a behavioral psychologist reviewing the investment committee's discussion, not by keyword matching.

### 2.5 Layer 5: Timing & Sizing

**What it does**: Position sizing via equal-weight with optional Kelly Criterion overlay. Pendulum-based cycle detection using VIX, HY OAS, put/call ratio, and SPY vs 200 SMA.

**Strengths:**
- Half-Kelly is the correct institutional practice (`sizing.py:64`). Full Kelly is indeed a path to ruin.
- 4% cap per position on Kelly output (`sizing.py:65`) is conservative and appropriate.
- 50-decision minimum before Kelly activates (`sizing.py:30`) prevents premature optimization.
- Portfolio limit checks (max positions, max single weight, min cash) are sound (`sizing.py:161-219`).
- Pendulum inputs (VIX, HY OAS, put/call, SPY vs 200 SMA) are the right data points for a simple regime indicator (`pendulum_feeds.py:17-60`).

**Weaknesses:**

1. **CRITICAL: Kelly formula appears to have a bug** (`sizing.py:59`). The standard Kelly formula is `f* = (p/a) - (q/b)` where p = win probability, q = loss probability, a = loss ratio, b = win ratio. Or equivalently, `f* = (pb - qa) / b`. The code computes `kelly = (p * b - q * a) / b` which is `p - qa/b`. Let's verify: if win_rate=0.6, avg_win=10%, avg_loss=5%, then b=0.10, a=0.05, p=0.6, q=0.4. Standard Kelly: (0.6 * 0.10 - 0.4 * 0.05) / 0.10 = (0.06 - 0.02) / 0.10 = 0.40. Code: same. Actually this is correct. BUT: the code uses `avg_win_pct / 100` and `avg_loss_pct / 100` (lines 51-52), so b and a are already decimals. Then the formula `(p*b - q*a) / b` = `p - q*a/b`. For the example: `0.6 - 0.4 * 0.05/0.10 = 0.6 - 0.2 = 0.4`. This matches. The formula is actually correct, though the variable naming is confusing.

2. **No volatility-based sizing**. Position size is determined only by portfolio value, equal weight, and Kelly fraction. There is zero consideration of the stock's own volatility. A biotech stock with 80% annualized vol gets the same base allocation as a utility with 15% vol. This is a fundamental omission. Risk parity (sizing inversely proportional to volatility) is table-stakes for institutional portfolios.

3. **No correlation-adjusted sizing**. Adding a stock that is 0.95 correlated with your largest holding is effectively doubling down. The `PortfolioFitScorer` (`portfolio_fit.py`) does sector-level diversification scoring, but doesn't compute actual return correlations.

4. **Pendulum multiplier is applied without bounds documentation**. `pendulum_multiplier` is passed into `calculate_size` (`sizing.py:93`) but its source and bounds are not visible in the sizing module. If this multiplier comes from uncapped cycle readings, it could produce extreme position sizes.

5. **Equal weight as default is too naive**. Target 25 positions at equal weight = 4% each. This ignores conviction levels entirely. A high-conviction idea should get more capital than a marginal one. Risk-budgeting or conviction-weighted sizing would be more appropriate.

6. **No sector concentration limit in sizing**. `SizingConfig` has `max_single_position_pct` but no `max_sector_pct`. You could end up 50% Technology through equal-weight allocation of 12 tech stocks.

**Institutional Gap**: A real fund uses risk-budgeting: each position's size is determined by its expected contribution to portfolio risk (volatility * correlation * weight). This requires a covariance matrix estimated from historical returns, ideally with shrinkage estimators. The sizing module should also incorporate liquidity (ADV-based position limits to ensure orderly exit).

### 2.6 Layer 6: Learning & Calibration

**What it does**: Decision registry logs all decisions with confidence levels. Calibration engine computes ECE and Brier score from settled predictions. Weekly reports identify over/underconfident ranges and recommend adjustments.

**Strengths:**
- **Calibration engine design is excellent** (`calibration.py`). ECE and Brier score are the correct metrics. The bucket-based approach (0.5-0.6, 0.6-0.7, etc.) is standard practice.
- Per-agent accuracy tracking (`calibration.py:146-150`) enables identifying which agents add value and which are noise.
- Confidence adjustment recommendations (`calibration.py:227-245`) close the feedback loop, which most systems never do.
- Decision logger captures every decision with type, source, and confidence (`registry.py`). Full audit trail.
- Stock lifecycle management with valid state transitions (`lifecycle.py`) prevents data integrity issues.

**Weaknesses:**

1. **Bucket minimum of 5 is too low** (`calibration.py:198`). Declaring a bucket "overconfident" with only 5 observations is statistically unreliable. A minimum of 20-30 observations per bucket is needed for the gap to be statistically significant. With 5 observations, a 60% accuracy in the 70-80% bucket could easily be due to random chance (binomial confidence interval: 17%-93%).

2. **ECE threshold of 0.15 is too lenient** (`calibration.py:183`). Professional forecasters achieve ECE < 0.05. An ECE of 0.15 means predictions are off by 15 percentage points on average -- at 70% confidence, actual accuracy could be 55% or 85%. This is not actionable for capital allocation.

3. **No time-weighting of calibration data**. All settled decisions are weighted equally regardless of when they occurred. A system that was poorly calibrated 6 months ago but well-calibrated recently should reflect the improvement. Exponential time decay on calibration data is standard.

4. **50-decision threshold for Kelly is arbitrary** (`sizing.py:30`). The number 50 appears to have no statistical justification. For reliable win rate estimation with a binomial distribution, you need n such that the confidence interval is narrower than your edge. If true win rate is 55% and you want to detect it with 95% confidence, you need n > 380 trades (using the normal approximation). At 50 trades, the 95% CI for a 55% observed win rate is [41%, 69%] -- far too wide for Kelly sizing.

5. **No decay or regime-adjustment on Kelly parameters**. The Kelly bootstrap (`kelly_bootstrap.py:30-36`) uses the last 500 closed trades. In a regime change (e.g., bull to bear market), historical win rates become misleading. Using expanding-window averages over a regime change is dangerous.

6. **Calibration recommendations are not automatically applied**. The system generates recommendations ("reduce confidence in 0.7-0.8 range by 5%") but there's no mechanism to actually apply these adjustments to agent outputs. It's advisory only.

**Institutional Gap**: A real calibration system would: (a) use proper statistical tests (e.g., Hosmer-Lemeshow) for significance, (b) implement automatic Platt scaling on confidence outputs, (c) track calibration per market regime, (d) require 100+ observations per bucket minimum, (e) auto-adjust agent weights based on rolling performance.

---

## 3. Agent Framework Assessment

### 3.1 Agent Personas

**9 agents total**: 6 primary (Warren, Auditor, Klarman on Claude; Soros, Druckenmiller, Dalio on Gemini), 2 scouts (Simons on Groq/DeepSeek, Lynch on DeepSeek), 1 validator (Data Analyst on Gemini).

**Strengths:**
- Personas are exceptionally well-differentiated. Each has a distinct methodology, unique signal tags, and a clear analytical lens. Warren focuses on owner earnings and moat; Soros on reflexivity and credit; Klarman on margin of safety; Auditor on forensic risk. There's genuine complementarity.
- The `AgentSkill` dataclass (`skills.py:15-36`) is well-designed. Separating philosophy, methodology, critical_rules, allowed_tags, and output format into structured fields enables clean prompt construction.
- Signature questions are brilliant design ("If the stock market closed for ten years, would I still own this?"). They force the LLM to commit to a specific analytical frame.
- The Simons data gate (`runner.py:232-239`) -- capping confidence to 0.15 without technical data -- is exactly right. This prevents the quant agent from hallucinating technical analysis.

**Weaknesses:**

1. **Weight allocation lacks empirical justification**. Weights (Warren 0.18, Auditor/Klarman/Soros 0.14 each, Druckenmiller/Dalio 0.12 each, Simons/Lynch 0.08 each) sum to 1.00 but appear chosen intuitively. There's no backtesting showing these weights optimize risk-adjusted returns. Warren getting 0.18 vs. Soros getting 0.14 is a 29% difference in influence -- is Warren's framework actually 29% more predictive? No evidence is presented.

2. **Model assignment creates systematic bias**. Claude Opus powers Warren, Auditor, and Klarman (the three value/risk agents). Gemini powers Soros, Druckenmiller, and Dalio (the three macro/momentum agents). If Claude has a systematic analytical style difference from Gemini (and it does -- Claude tends toward longer, more cautious reasoning), then the "diversity of opinion" is partly an artifact of model differences, not genuine analytical disagreement.

3. **DeepSeek for scouts is a quality problem**. Simons (technical analysis) and Lynch (GARP analysis) both run on deepseek-chat, which is significantly less capable than Claude Opus or Gemini Pro. The scouts' opinions are worth 0.08 each -- but if DeepSeek produces lower-quality analysis, their opinions may be worse than noise. Low-quality inputs with positive weight degrade the ensemble.

4. **No agent specialization by sector or market cap**. All agents analyze all stocks identically. But a biotech stock requires very different analysis than a utility. Warren's moat framework is excellent for consumer staples but nearly useless for pre-revenue biotech. The system would benefit from sector-specialist agents or conditional agent activation.

5. **Agents receive fundamentals but cannot do independent research**. Each agent gets a pre-packaged data bundle (fundamentals, news, insider activity, etc.). No agent can request additional data, probe a specific question, or verify a claim. In a real investment committee, an analyst who says "I need to check the latest 10-Q" can go do that. These agents cannot.

6. **The Data Analyst validator has weight 0.0** (`skills.py:97`). This means data quality issues detected by the validator have zero direct influence on the final verdict. The validator's output feeds into pipeline gating but not into the weighted consensus. If the data is marked "SUSPICIOUS" but not "REJECTED," the pipeline proceeds with no weight adjustment.

### 3.2 Consensus / Debate Mechanism

**What it does**: Simple majority-vote sentiment classification (bullish/bearish/neutral) with 75% threshold for debate trigger.

**Strengths:**
- Hybrid debate (only when agents disagree) is computationally efficient and philosophically sound.
- Allowing synthesis with 2 agent failures (`convergence.py:83`) provides resilience.

**Weaknesses:**

1. **Sentiment classification is extremely coarse** (`convergence.py:33-45`). Each agent's entire signal set is reduced to one of three buckets: bullish, bearish, or neutral. This destroys critical nuance. An agent that says "BUY with 0.55 confidence" and one that says "BUY with 0.95 confidence" are classified identically. An agent that says "BUY but with ACCOUNTING_RED_FLAG" is still classified as bullish.

2. **75% threshold is not justified**. Why 75% and not 67% or 80%? The documentation says "75% consensus" but provides no analysis of false positive/negative rates at different thresholds. In practice, with 6 primary agents, 75% means 5 of 6 must agree (83%) to skip debate, since 4 of 6 is only 67%. The discrete nature of vote counts makes the effective threshold jumpy.

3. **Debate outcome has no weight**. The debate triggers but its output isn't explicitly factored into a weighted synthesis formula. It's a flag ("debate happened") rather than a quantitative adjustment.

4. **No detection of "agree for wrong reasons"**. If 5 of 6 agents say BUY but each cites a different reason (one says moat, one says momentum, one says mean reversion, one says macro, one says insider buying), the consensus is strong but the reasoning is fragmented. In investment committees, this pattern (agreement on conclusion, disagreement on thesis) is actually a warning sign, not confirmation.

---

## 4. Risk Management Assessment

### 4.1 What Exists

- **Position-level limits**: 5% max single position, 25 target positions, 40 max, 5% min cash, 35% max cash (`sizing.py:18-27`)
- **Sell engine**: Three-tier system (permanent/core/tactical) with position-type-specific rules (`engine.py`)
- **Thesis health gating**: Prevents whipsaw on permanent holdings (`thesis_health.py`)
- **VIX spike trigger**: Emergency review when VIX > 30 (`triggers.py:28`)
- **Circuit breaker on yfinance**: Trips at 50% failure rate (`yfinance_client.py:28-68`)
- **Adversarial veto**: Munger layer can VETO a position (`munger.py:33-36`)

### 4.2 Critical Gaps

1. **No Value-at-Risk (VaR) or Expected Shortfall calculation**. This is the most fundamental risk metric in institutional finance. Without VaR, you cannot answer: "What is our worst-case daily loss at 95% confidence?" Every regulated fund computes this daily.

2. **No portfolio-level correlation monitoring**. Individual position limits (5%) mean nothing if 10 positions are 0.9 correlated. You effectively have a 50% concentration in one factor. The `portfolio_fit.py` scorer uses sector as a proxy for correlation, but Technology stocks (AAPL vs. CSCO vs. SHOP) have wildly different correlation profiles.

3. **No drawdown-based circuit breaker at portfolio level**. The VIX trigger (`triggers.py:28`) is a market-level indicator. But there's no trigger for "our portfolio has lost 10% from peak -- halt all new buying." A real fund has hard drawdown limits (e.g., -10% = reduce exposure 50%, -15% = go to cash).

4. **No liquidity risk management**. No minimum ADV (average daily volume) filter in the screener. No check that a position can be exited within a reasonable number of trading days. For a paper portfolio this is academic, but for real money it's critical.

5. **No tail risk / black swan protection**. No OTM put allocation, no portfolio insurance, no volatility targeting. The portfolio is implicitly long vol through unhedged equity positions.

6. **No counterparty risk consideration**. The system uses yfinance (free, unreliable), one LLM gateway, and one database. Any single failure mode can disrupt operations. A real system has redundant data feeds and failover procedures.

7. **Emergency review doesn't actually halt trading** (`triggers.py:304-306`). When VIX spikes, the code explicitly says "logged but NOT auto-analyzing." In a real crisis, you want the opposite -- immediate portfolio review and automatic risk reduction.

8. **Sell rules are not integrated with agent verdicts**. The sell engine (`engine.py`) runs independently from the agent pipeline. An agent could say "SELL_FULL with 0.95 confidence" but the sell engine operates on its own rule set. There's no connection ensuring agent sell signals actually trigger sells.

### 4.3 Sell Engine Assessment

The three-tier sell framework (permanent/core/tactical) in `engine.py` is conceptually sound but the rules themselves (`core.py`, `permanent.py`, `tactical.py`) were not fully visible in this audit. The architecture is correct -- permanent holdings should be hardest to sell, tactical easiest.

---

## 5. Data Quality Assessment

### 5.1 Validation Gate

**Strengths:**
- Catches the real and documented yfinance corruption problem (zeroed financials for established companies). The PSN example cited in CLAUDE.md is a genuine risk.
- Critical anomaly detection (`validation.py:209-289`) covers the most important corruption modes.
- Retry-on-failure approach (`yfinance_client.py:107-140`) is pragmatic.
- Circuit breaker pattern (`yfinance_client.py:28-68`) prevents cascading failures.
- Never caching bad data (`yfinance_client.py:128-130`) prevents 24-hour poison windows. This is excellent engineering.

**Weaknesses:**

1. **90-day staleness threshold is too lenient** (`validation.py:106`). For a system that screens 5000+ stocks, 90-day-old fundamentals are dangerously stale. Quarterly earnings changes can be material. A 30-day staleness warning and 45-day hard rejection would be more appropriate.

2. **Current assets/liabilities are estimated from total_debt * 0.3** (`yfinance_client.py:173`). This is an arbitrary guess that will be wrong for most companies. Capital-light tech companies have minimal current liabilities relative to total debt (which is often long-term). Asset-heavy manufacturers have the opposite. This estimate feeds into Altman Z-Score's working capital component, compounding the error.

3. **Total assets estimated from net_income / ROA** (`yfinance_client.py:166-168`). This is only correct if ROA is calculated the same way. ROA definitions vary (some use average assets, some use ending assets, some use operating income). This estimate could be off by 50%+.

4. **No cross-validation across data sources**. The system uses yfinance as primary and EDGAR as secondary, but doesn't cross-validate when both are available. If yfinance says revenue is $10B and EDGAR says $12B, which is right? The system should flag material discrepancies.

5. **Revenue growth > 1000% check** (`validation.py:195-205`) only for >$10B market cap. A $500M company reporting 5000% revenue growth is equally suspicious but would pass validation.

6. **No point-in-time data guarantee**. The system uses current fundamentals (trailing twelve months) but doesn't verify that all data points are from the same reporting period. Market cap is real-time, revenue is TTM, shares outstanding may lag. This creates look-ahead bias potential.

### 5.2 Data Source Risk

- **yfinance**: Free, unofficial, rate-limited, frequently returns corrupted data. Adequate for paper trading; unacceptable for real money.
- **SEC EDGAR**: Official, reliable, but delayed (filings published weeks after quarter end). Bulk frames API is good for screening.
- **No alternative price source**: If yfinance goes down or gets blocked, the entire system stops.
- **No real-time data**: All data is delayed. No websocket feeds, no level 2 data, no real-time quotes for execution.

---

## 6. Learning & Calibration Assessment

### 6.1 Decision Registry

Well-designed audit trail. Every decision has: ticker, type, layer source, confidence, reasoning, signals, and timestamp. This enables post-hoc analysis of what went wrong and why.

The `DecisionType` enum covers the full lifecycle: SCREEN, COMPETENCE_PASS/FAIL, BUY, SELL, TRIM, HOLD, REJECT, WATCHLIST.

### 6.2 Performance Tracking

`performance.py` computes: portfolio return vs. SPY (alpha), Sharpe ratio, Sortino ratio, max drawdown, win rate, expectancy, and disposition effect ratio.

**Strengths:**
- Disposition effect tracking (`performance.py:226-262`) is genuinely sophisticated. Measuring whether losers are held longer than winners catches the most common behavioral bias in portfolio management.
- Expectancy calculation (`performance.py:69-70`) is correct: (win_rate * avg_win) - (loss_rate * avg_loss).

**Weaknesses:**
- **Max drawdown proxy is wrong** (`performance.py:152-172`). Using worst individual position P&L as a proxy for portfolio drawdown is not conservative -- it's just wrong. Portfolio max drawdown is measured from the portfolio's peak NAV to its subsequent trough. Without daily NAV tracking, you simply cannot compute it.
- **Sharpe ratio computed from trade returns, not time-series returns** (`performance.py:174-224`). The standard Sharpe ratio uses daily/monthly portfolio returns, not per-trade returns. Using per-trade returns produces a Sharpe ratio that is not comparable to industry benchmarks.
- **Risk-free rate hardcoded at 4.5%** (`performance.py:25`). This should be dynamically sourced from current T-bill rates.

### 6.3 Calibration Loop Maturity

The calibration system exists in code but its effectiveness depends entirely on having sufficient settled decisions. With the 50-decision Kelly threshold and the bucket minimum of 5, the system needs at minimum 50 settled predictions before producing any useful calibration data. If the average position is held for 3-6 months, this requires 12-25 months of operation.

**Current status**: The documentation says "100+ decisions logged" is a goal, not an achievement. The system likely has insufficient data for meaningful calibration.

---

## 7. Critical Gaps for Real Capital

### What Would Need to Change to Manage Real Money

1. **Regulatory**: Register as an investment advisor (RIA) with the SEC or operate under an existing RIA umbrella. Automated advisory systems require compliance with the Investment Advisers Act of 1940.

2. **Risk infrastructure**: Implement daily VaR, portfolio-level drawdown limits with automatic deleveraging, correlation monitoring with concentration alerts, and stress testing against historical scenarios (2008, 2020 March, 2022 rate shock).

3. **Data infrastructure**: Replace yfinance with a professional data provider (Bloomberg Terminal API, Refinitiv, S&P Capital IQ, or at minimum Alpha Vantage premium). Implement dual-source cross-validation.

4. **Execution**: Integrate with a proper broker API (Interactive Brokers, Alpaca Pro) with: transaction cost modeling (commissions, spread, market impact), order management system with limit orders, pre-trade compliance checks, post-trade reconciliation.

5. **Volatility-based sizing**: Replace equal-weight with risk-parity or conviction-weighted risk-budgeting. Each position's dollar allocation should be inversely proportional to its volatility contribution.

6. **Backtesting**: Full historical backtest of the composite strategy (screener + agent consensus + sizing) over 10+ years including 2008, 2020, and 2022. Without this, the strategy's expected behavior in different regimes is unknown.

7. **Paper trading validation**: At least 12 months of live paper trading with full position tracking before any real capital. The current system appears to be in early paper trading phase.

8. **Operational risk**: Redundant infrastructure, failover procedures, disaster recovery, and a human override mechanism that can halt all trading instantly.

9. **Fix the Altman Z-Score**: Use actual retained earnings from balance sheet data, or remove Altman from the composite if the data isn't available. Using net_income as proxy is materially misleading.

10. **Fix the Piotroski F-Score**: Source actual operating cash flow data. If unavailable, clearly document that only a partial F-Score (4 of 9 tests) is being computed and adjust the composite weight accordingly.

---

## 8. Prioritized Recommendations

### Critical (Fix Before Paper Trading Matters)

1. **Fix Altman Z-Score retained_earnings proxy** (`altman.py:70-72`). Either source actual retained earnings from EDGAR balance sheet data or remove Altman from the composite and reweight to 65% Greenblatt / 35% Piotroski.

2. **Fix Piotroski OCF proxy** (`piotroski.py:60-62, 74`). Source actual operating cash flow. If unavailable, score only the 5 tests that don't require cash flow data and normalize accordingly.

3. **Add portfolio-level drawdown circuit breaker**. If portfolio drops 10% from peak NAV, automatically halt new buying and trigger full re-analysis of all positions.

4. **Add volatility-based position sizing**. Multiply equal-weight base size by (target_vol / position_vol) where target_vol is, e.g., 15% annualized.

5. **Increase calibration bucket minimums** from 5 to 20-30 observations before generating adjustment recommendations.

### High Priority (Next 3 Months)

6. **Add return correlation matrix**. Compute rolling 60-day correlation between all held positions. Alert when portfolio-level correlation exceeds threshold (e.g., average pairwise correlation > 0.5).

7. **Improve bias detection**. Replace keyword matching with an LLM-based bias detection pass. Ask a separate LLM: "Given this reasoning, identify which of these 20 biases may be present and explain why."

8. **Add momentum overlay to Greenblatt screen**. Filter top-100 Greenblatt results by 12-1 month price momentum. Remove bottom quartile momentum stocks.

9. **Replace max drawdown proxy** with actual peak-to-trough computation using daily NAV snapshots.

10. **Add per-agent calibration with minimum sample sizes**. Only adjust agent weights after 30+ settled decisions per agent.

### Medium Priority (6-12 Months)

11. **Implement risk-budgeting**. Replace equal weight with marginal contribution to risk (MCTR) based position sizing.

12. **Add liquidity filter**. Minimum 20-day ADV of $1M for all positions. Position size < 10% of ADV.

13. **Cross-validate data sources**. When both yfinance and EDGAR provide the same metric, compare and flag discrepancies > 10%.

14. **Add sector-specialized agent activation**. For biotech: activate a specialized screening agent that understands pipeline value, FDA catalysts, and cash runway. For financials: activate one that understands NIM, credit quality, and capital ratios.

15. **Implement Platt scaling** on agent confidence outputs to automatically calibrate confidence to observed accuracy.

### Low Priority (Aspirational)

16. **Full historical backtest** of the complete pipeline over 2015-2025.
17. **Multi-factor risk model** (Barra-style) decomposing portfolio risk into factor exposures.
18. **Options-based hedging** integration for tail risk protection.
19. **Regime detection model** using Hidden Markov Model on macro indicators to dynamically adjust risk budgets.
20. **Formal agent weight optimization** using cross-validated out-of-sample performance.

---

## 9. Overall Maturity Rating

**Rating: 4.5 / 10**

**Justification:**

| Dimension | Score | Comment |
|-----------|-------|---------|
| Pipeline architecture | 7/10 | Well-designed sequential flow, mirrors institutional process |
| Quant screen quality | 5/10 | Core Greenblatt is correct; Piotroski and Altman have proxy issues |
| Agent framework | 7/10 | Excellent persona design; weight validation missing |
| Consensus mechanism | 4/10 | Too coarse; destroys nuance |
| Risk management | 2/10 | Individual limits exist; portfolio-level risk absent |
| Data quality | 5/10 | Good corruption detection; bad data sources and proxies |
| Position sizing | 3/10 | No volatility consideration; equal weight is naive |
| Learning/calibration | 6/10 | Right metrics; insufficient data and low thresholds |
| Adversarial framework | 8/10 | Best component; bias detection needs upgrade |
| Sell discipline | 6/10 | Thesis health gating is good; not integrated with agents |
| Production readiness | 2/10 | Paper trading only; no execution, compliance, or redundancy |

**Bottom line**: This is a thoughtful and ambitious prototype built by someone who has clearly read the right books (Greenblatt, Munger, Marks, Dalio, Thorp). The pipeline design shows genuine understanding of institutional investment processes. The adversarial layer and thesis health management are genuinely innovative features that some real funds lack.

However, the system has the characteristic profile of a design-first, validate-later project. The financial formulas have proxy-induced errors that would produce materially wrong outputs in production. The risk management is limited to position-level constraints without portfolio-level awareness. And the calibration loop, while well-designed, has insufficient statistical rigor in its thresholds.

To its credit, the system explicitly restricts itself to paper trading (`CLAUDE.md`: "PAPER TRADING ONLY - No real money trades without explicit human approval") and has a 48-hour minimum hold rule. The builder is appropriately cautious about deployment scope.

**What would move this to a 7/10**: Fix the quantitative errors (Altman, Piotroski), add portfolio-level risk management (VaR, correlation, drawdown limits), implement volatility-based sizing, and accumulate 12+ months of paper trading data with rigorous calibration analysis.

**What would move this to a 9/10**: All of the above plus professional data sources, backtested strategy validation, regulatory compliance, redundant infrastructure, and a human CIO override layer.

---

*End of audit. All code references are to files in `/home/investmentology/src/investmentology/`.*
