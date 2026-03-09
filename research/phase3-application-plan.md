# Phase 3: Application Plan — Evolving Haute-Banque

*Created: 2026-03-08*
*Input: Phase 1 research (5 documents), Phase 2 synthesis (gaps + top 10 opportunities)*
*Target: Concrete, prioritized workstreams with file-level specificity*

---

## Executive Summary

The app's current architecture — 6-layer pipeline, 9 agents, Magic Formula screening, thesis lifecycle tracking, sell engine, portfolio fit scoring — is a strong foundation for stock *selection*. The Phase 2 synthesis identified that the highest-impact improvements are in what happens *after* selection: sell discipline, portfolio-level thinking, behavioral debiasing, and quality scoring.

This plan organizes 30 concrete improvements across three workstreams and four priority phases, grounded in what exists today and realistic about constraints (CLI agents, homelab scale, free data, single user).

---

## Workstream A: Assessment Methodology

*How the app evaluates, ranks, and manages stocks. Changes to agents, scoring, pipeline, screening.*

### A1. Composite Quality Score — Expand Quant Gate

**What changes**: The quant gate currently runs Greenblatt (ROIC + Earnings Yield) as the primary screen, with Piotroski F-Score and Altman Z-Score already implemented but used only as supplementary signals. Unify these into a single composite quality score that ranks stocks along multiple dimensions simultaneously.

**Specifically**:
1. Add **Beneish M-Score** (earnings manipulation detection) — 8 variable model using existing yfinance fundamentals (DSRI, GMI, AQI, SGI, DEPI, SGAI, TATA, LVGI)
2. Add **Accruals Ratio** calculation: `(net_income - operating_cash_flow) / total_assets` — high accruals predict earnings disappointment
3. Add **FCF Conversion** ratio: `free_cash_flow / net_income` — measures cash backing of reported earnings
4. Create `CompositeQualityScore` dataclass combining: Greenblatt combined rank, Piotroski F-Score (0-9), Altman Z-Score zone, Beneish M-Score (manipulator flag), Accruals ratio, FCF conversion ratio
5. Expose composite score in the quant gate API response and PWA QuantGate view

**Where in codebase**:
- New file: `src/investmentology/quant_gate/beneish.py` — M-Score calculation
- New file: `src/investmentology/quant_gate/composite.py` — `CompositeQualityScore` combining all metrics
- Modify: `src/investmentology/quant_gate/greenblatt.py` — call composite scorer after ranking
- Modify: `src/investmentology/api/routes/quant_gate.py` — include composite score in response
- Modify: `pwa/src/views/QuantGate.tsx` — display quality radar/breakdown

**Data requirements**: All inputs available from existing yfinance fundamentals (revenue, COGS, receivables, depreciation, SGA, total assets, current assets, current liabilities, long-term debt, net income, cash flow from operations). No new data sources needed.

**Effort**: Medium (half day)
**Dependencies**: None
**Impact**: High — catches value traps (Beneish), predicts earnings quality (accruals), validates cash generation (FCF conversion). The combination is far more robust than any single metric.

---

### A2. Enhanced Dividend Growth Framework for Income Analyst

**What changes**: The Income Analyst agent currently activates for dividend yield > 1.5% but lacks structured dividend growth metrics. Add a dedicated dividend growth scoring framework.

**Specifically**:
1. Calculate **consecutive dividend increase streak** from yfinance dividend history
2. Calculate **payout ratio** (dividends / EPS) and **FCF payout ratio** (dividends / FCF per share)
3. Calculate **5-year dividend growth CAGR** from historical dividends
4. Calculate **Chowder Number** (current yield + 5-year dividend growth rate; > 12 is strong for non-utilities)
5. Classify as Dividend **King** (50+yr), **Champion/Aristocrat** (25+yr), **Contender** (10+yr), **Challenger** (5+yr)
6. Compute **dividend safety score** (0-100) based on: payout ratio sustainability, FCF coverage, debt/equity trend, earnings stability
7. Inject these metrics into the Income Analyst's prompt context so the agent can reason about dividend growth quality

**Where in codebase**:
- New file: `src/investmentology/quant_gate/dividend_growth.py` — all dividend calculations
- Modify: `src/investmentology/agents/skills.py` — add dividend metrics to Income Analyst's `required_data`
- Modify: `src/investmentology/agents/runner.py` — include dividend data block in Income Analyst prompt
- Modify: `src/investmentology/data/yfinance_client.py` — add `get_dividend_history()` method (yfinance has this via `ticker.dividends`)
- Modify: `pwa/src/components/portfolio/DividendCard.tsx` — show enhanced metrics

**Data requirements**: yfinance `ticker.dividends` (historical dividend payments), `ticker.info` (payout ratio, dividend yield). All free.

**Effort**: Small (1-2 hours)
**Dependencies**: None
**Impact**: Medium-High — makes the Income Analyst agent substantially more useful for dividend-focused positions. Dividend safety score catches impending cuts before they happen.

---

### A3. Thesis-Based Sell Discipline System

**What changes**: The app already has thesis lifecycle tracking (`invest.thesis_events`, `thesis_health.py`, `sell/engine.py`). The gap is that thesis invalidation criteria are stored as free text, not as monitorable conditions. Build a structured thesis monitoring system that automates invalidation detection.

**Specifically**:
1. Define a `ThesisInvalidationCriteria` schema with monitorable conditions:
   - Price below X (stop loss)
   - ROIC below X% for N quarters
   - Revenue growth below X% for N quarters
   - Piotroski F-Score drops below N
   - Debt/Equity exceeds X
   - Dividend cut (for income positions)
   - Custom text condition (for qualitative criteria LLM agents flag)
2. Store structured invalidation criteria in `thesis_events.break_conditions` JSONB (column already exists)
3. Build `ThesisMonitor` class that checks all active positions against their invalidation criteria on every pipeline run
4. Generate `ThesisBreakAlert` when criteria are triggered — surface in briefing and push notifications
5. Add "Would you buy this today?" periodic prompt — for every held position, run a simplified re-evaluation every 30 days and surface the result

**Where in codebase**:
- Modify: `src/investmentology/advisory/thesis_health.py` — add `ThesisInvalidationCriteria` dataclass, `ThesisMonitor` class
- Modify: `src/investmentology/sell/engine.py` — integrate thesis monitor results into sell signal evaluation
- Modify: `src/investmentology/advisory/briefing.py` — add thesis alerts section to daily briefing
- Modify: `src/investmentology/api/routes/thesis.py` — endpoint for setting/viewing invalidation criteria per position
- Modify: `pwa/src/views/Portfolio.tsx` or `StockDeepDive.tsx` — UI for setting thesis criteria at entry and viewing thesis health

**Data requirements**: All from existing data sources. The monitor runs against fundamentals already fetched by the pipeline.

**Effort**: Large (1-2 days)
**Dependencies**: A1 (composite quality score provides the metrics to monitor)
**Impact**: Very High — the #1 alpha source for retail investors per Phase 2 synthesis. Systematic sell discipline is rare and addresses the disposition effect directly.

---

### A4. Position Lifecycle Management

**What changes**: Currently, buy/sell is binary. Add support for staged position building and trimming.

**Specifically**:
1. Add `position_stage` field to portfolio positions: `STARTER` (1/3), `BUILDING` (2/3), `FULL`, `TRIMMING`
2. Define stage transition rules per position type:
   - Starter -> Building: After 30 days + thesis confirmed by re-analysis
   - Building -> Full: After next earnings + thesis intact
   - Full -> Trimming: When price > 120% fair value (take profit) or portfolio concentration > 10%
3. Add averaging-down logic: When price drops but thesis is INTACT and F-Score improving, suggest adding (Building stage) vs. cutting (when thesis CHALLENGED)
4. Surface position stage and suggested actions in the portfolio view

**Where in codebase**:
- Modify: `src/investmentology/models/position.py` — add `position_stage` field
- New migration: `registry/migrations/021_position_stages.sql`
- Modify: `src/investmentology/sell/engine.py` — add trim signals based on stage
- Modify: `src/investmentology/advisory/briefing.py` — include stage progression suggestions
- Modify: `src/investmentology/api/routes/portfolio.py` — expose stage info
- Modify: `pwa/src/views/Portfolio.tsx` — show stage badges and transition suggestions

**Data requirements**: Uses existing fundamentals and price data.

**Effort**: Medium (half day)
**Dependencies**: A3 (thesis monitoring drives stage transitions)
**Impact**: Medium-High — prevents the common mistake of going "all in" on a position before confirming the thesis. Forces discipline on profit-taking.

---

### A5. Contrarian Assessment Trigger

**What changes**: When a stock has declined >30% from its 52-week high but has improving or stable fundamentals, automatically trigger a "contrarian assessment" workflow.

**Specifically**:
1. In the overnight pipeline pre-filter, flag stocks where: `current_price < 0.7 * 52_week_high` AND (`piotroski_current >= piotroski_previous` OR `altman_zone != "distress"`)
2. For flagged stocks, inject a "contrarian context" block into agent prompts that includes: magnitude of decline, balance sheet strength (cash/debt), insider activity during decline, short interest trend
3. Ask agents to explicitly assess: "Is this a temporary overreaction (contrarian opportunity) or permanent impairment (value trap)?"
4. Surface contrarian opportunities separately in the recommendations view

**Where in codebase**:
- Modify: `src/investmentology/pipeline/pre_filter.py` — add contrarian flagging logic
- Modify: `src/investmentology/agents/runner.py` — inject contrarian context when flag is set
- Modify: `src/investmentology/api/routes/recommendations.py` — separate contrarian opportunities
- Modify: `pwa/src/views/Recommendations.tsx` — contrarian section

**Data requirements**: 52-week high from yfinance (`ticker.info['fiftyTwoWeekHigh']`), Piotroski/Altman from existing quant gate. Insider data from existing Finnhub integration.

**Effort**: Small (1-2 hours)
**Dependencies**: A1 (composite quality score for fundamental assessment)
**Impact**: Medium — identifies asymmetric risk/reward opportunities that the current pipeline might miss because Magic Formula penalizes recently-declining stocks.

---

### A6. Value vs. Momentum Disagreement Flagging

**What changes**: When technical/momentum signals conflict with value signals from agent analysis, explicitly flag this as a "value vs. momentum disagreement" rather than averaging into a consensus score.

**Specifically**:
1. After synthesis, check if momentum-oriented agents (Soros, Druckenmiller) and value-oriented agents (Warren, Klarman, Auditor) have divergent verdicts (>2 category spread, e.g. STRONG_BUY vs HOLD)
2. Surface this as a named disagreement type: "Value/Momentum Divergence"
3. Include which side each agent is on and why
4. In the PWA, show a visual "tug of war" indicator on the stock deep dive

**Where in codebase**:
- Modify: `src/investmentology/pipeline/convergence.py` — detect value/momentum divergence after agent results
- Modify: `src/investmentology/api/routes/analyse.py` or `stocks.py` — include divergence info in response
- Modify: `pwa/src/components/deepdive/AgentAnalysisPanel.tsx` — show divergence indicator

**Data requirements**: Already available from agent stances.

**Effort**: Small (1-2 hours)
**Dependencies**: None
**Impact**: Medium — makes agent disagreement interpretable rather than hiding it in a blended score. Directly addresses Phase 2 finding: "show the disagreement, don't resolve it into a single score."

---

### A7. Sell-Side Consensus as Contrarian Input

**What changes**: Add analyst consensus data to agent context — not to follow consensus, but to identify where HB's agents diverge from sell-side.

**Specifically**:
1. Fetch analyst ratings (buy/hold/sell counts) and mean target price from yfinance (`ticker.info['recommendationMean']`, `ticker.info['targetMeanPrice']`, `ticker.info['numberOfAnalystOpinions']`)
2. Fetch consensus EPS estimates from yfinance (`ticker.earnings_estimate`)
3. Compute divergence score: when HB's verdict diverges from sell-side consensus by 2+ categories, flag as "consensus divergence"
4. Inject consensus data into agent prompts as context (not as a signal to follow)
5. Surface divergence points in the daily briefing as "Where HB disagrees with Wall Street"

**Where in codebase**:
- Modify: `src/investmentology/data/enricher.py` — add `_enrich_consensus()` method (already has `_enrich_analyst_ratings()` — extend it)
- Modify: `src/investmentology/agents/base.py` — add consensus fields to `AnalysisRequest`
- Modify: `src/investmentology/advisory/briefing.py` — add consensus divergence section
- Modify: `pwa/src/views/Today.tsx` — show divergence highlights

**Data requirements**: yfinance (already integrated). The data is in `ticker.info` and `ticker.recommendations`.

**Effort**: Small (1-2 hours)
**Dependencies**: None
**Impact**: Medium — consensus divergence is where alpha potential exists. The value is in identifying *when and why* HB disagrees with Wall Street.

---

## Workstream B: Data Gathering & Quality

*New data sources, validation improvements, freshness management.*

### B1. FRED Macro Regime Dashboard

**What changes**: The FRED provider (`data/fred_provider.py`) already fetches 12 macro series. Build a structured "regime indicator" that classifies the current macro environment and adjusts portfolio posture recommendations.

**Specifically**:
1. Compute **yield curve signal**: Categorize 2s10s spread into inverted (<0), flat (0-50bp), normal (50-200bp), steep (>200bp)
2. Compute **credit stress signal**: HY spread < 300bp (easy), 300-500bp (normal), 500-800bp (stressed), >800bp (crisis)
3. Compute **volatility regime**: VIX < 15 (complacent), 15-25 (normal), 25-35 (elevated), >35 (fear)
4. Derive composite **regime label**: Expansion, Late Cycle, Contraction, Early Recovery — using rules-based classification from the three signals above
5. Store regime in `invest.market_snapshots` (already exists) and inject into agent prompts
6. Display regime dashboard in PWA Today view as a "Market Backdrop" card

**Where in codebase**:
- New file: `src/investmentology/data/macro_regime.py` — regime classification logic
- Modify: `src/investmentology/data/fred_provider.py` — add `get_regime()` returning structured regime data
- Modify: `src/investmentology/data/enricher.py` — inject regime into all analysis requests
- Modify: `src/investmentology/advisory/briefing.py` — include regime section
- Modify: `src/investmentology/api/routes/daily.py` — expose regime endpoint
- Modify: `pwa/src/views/Today.tsx` — market regime card

**Data requirements**: FRED API (already integrated). The 12 series in `FRED_SERIES` cover all needed inputs.

**Effort**: Medium (half day)
**Dependencies**: None
**Impact**: Medium — provides context for all position decisions. Late cycle = favor quality/defensive; early recovery = favor cyclicals. Prevents pro-cyclical mistakes.

---

### B2. Insider Activity Enhancement

**What changes**: Finnhub already provides insider transactions. Enhance the processing to detect "cluster buys" (multiple insiders buying within 30 days) and "insider confidence score."

**Specifically**:
1. From existing Finnhub insider data, compute:
   - Number of unique insiders buying in last 90 days
   - Total $ value of insider purchases vs. sales
   - "Cluster buy" flag: 3+ insiders buying within 30 days
   - "Insider confidence ratio": buy_value / (buy_value + sell_value)
2. Flag insider cluster buys as a high-priority catalyst in agent prompts
3. Add insider activity summary to stock deep dive page

**Where in codebase**:
- Modify: `src/investmentology/data/finnhub_provider.py` — add `get_insider_summary()` that computes aggregated metrics
- Modify: `src/investmentology/data/enricher.py` — pass insider summary to agents
- Modify: `pwa/src/components/deepdive/MetricsPanel.tsx` — show insider activity card

**Data requirements**: Finnhub API (already integrated). Free tier includes insider transactions.

**Effort**: Small (1-2 hours)
**Dependencies**: None
**Impact**: Medium-High — insider cluster buying is one of the most predictive free signals. Academic research (Lakonishok & Lee, 2001) shows clustered insider purchases predict 8-12% outperformance over 12 months.

---

### B3. Earnings Calendar & Event Tracking

**What changes**: Build a per-position event calendar tracking upcoming catalysts.

**Specifically**:
1. Fetch next earnings date from yfinance (`ticker.calendar`) and Finnhub earnings calendar
2. Track days-to-earnings for each portfolio position and watchlist stock
3. Detect management changes from SEC 8-K filings (item 5.02 — departure/appointment of officers)
4. Detect significant buyback authorizations from 8-K filings (item 8.01)
5. Create event calendar API endpoint returning upcoming events sorted by date
6. Surface "Upcoming Events" section in Today view and portfolio position cards

**Where in codebase**:
- New file: `src/investmentology/data/event_tracker.py` — event aggregation from multiple sources
- Modify: `src/investmentology/data/enricher.py` — add `_enrich_events()` method
- Modify: `src/investmentology/data/edgar_client.py` or `edgar_tools.py` — add 8-K parsing for management changes and buybacks
- New API route or extend: `src/investmentology/api/routes/daily.py` — events endpoint
- Modify: `pwa/src/views/Today.tsx` — upcoming events card
- Modify: `pwa/src/views/Portfolio.tsx` — per-position event indicator

**Data requirements**: yfinance calendar (free), Finnhub earnings calendar (free tier), SEC EDGAR 8-K filings (free, existing integration).

**Effort**: Medium (half day)
**Dependencies**: None
**Impact**: Medium-High — knowing that earnings are in 3 days changes the risk profile of every position action. Prevents accidental trades right before catalysts.

---

### B4. Management Quality Signals (Quantitative)

**What changes**: Add quantifiable management quality signals from existing data sources.

**Specifically**:
1. **SBC/Revenue ratio**: Stock-based compensation / revenue from yfinance (`stock_based_compensation` / `total_revenue`). Flag when > 10% for mature companies.
2. **Return on Incremental Capital**: `delta_NOPAT / delta_invested_capital` over 3-year rolling window. Measures capital allocation skill.
3. **Insider ownership %**: From yfinance `ticker.major_holders` — officers and directors combined.
4. **Goodwill/Total Assets ratio**: Persistent high goodwill suggests M&A-driven growth (potentially value-destructive).
5. Inject these as a "Management Scorecard" section in agent prompts.

**Where in codebase**:
- New file: `src/investmentology/quant_gate/management_quality.py` — all management metrics
- Modify: `src/investmentology/data/yfinance_client.py` — ensure SBC, goodwill fields are extracted
- Modify: `src/investmentology/data/enricher.py` — inject management scorecard into agent context
- Modify: `pwa/src/components/deepdive/MetricsPanel.tsx` — management quality section

**Data requirements**: All from yfinance. SBC is in the income statement, goodwill in the balance sheet, insider ownership in `major_holders`.

**Effort**: Medium (half day)
**Dependencies**: None
**Impact**: Medium — capital allocation skill is the hardest signal for retail investors to assess and one of the most predictive of long-term returns.

---

### B5. Data Freshness Dashboard

**What changes**: Make data staleness visible to the user. Currently data freshness is managed internally (`pipeline_state` staleness, yfinance cache TTL). Surface it.

**Specifically**:
1. For each stock in portfolio/watchlist, show: last fundamentals update timestamp, last price update, last agent analysis date, last insider data refresh
2. Flag stocks where any critical data source is > 7 days stale
3. Add a "Data Health" indicator to the System Health view
4. Allow manual refresh trigger for individual stocks

**Where in codebase**:
- Modify: `src/investmentology/api/routes/system.py` — add data freshness endpoint
- Modify: `src/investmentology/pipeline/state.py` — expose per-ticker staleness
- Modify: `pwa/src/views/SystemHealth.tsx` — data freshness section
- Modify: `pwa/src/views/StockDeepDive.tsx` — per-stock freshness indicator

**Data requirements**: All from internal pipeline state (already tracked).

**Effort**: Small (1-2 hours)
**Dependencies**: None
**Impact**: Low-Medium — primarily trust and transparency. Users should never see data without knowing how fresh it is.

---

## Workstream C: Communication & Decision Support

*How the app presents information to help the user make better decisions.*

### C1. Behavioral Debiasing UI Patterns

**What changes**: Implement specific UI patterns that counteract documented cognitive biases.

**Specifically**:
1. **Disposition effect counter**: In portfolio view, show thesis-relative status prominently (thesis health badge: INTACT/CHALLENGED/BROKEN) alongside P&L. Color code by thesis health, not by profit/loss.
2. **Anchoring counter**: Show fair value estimate vs. current price (not cost basis vs. current price) as the primary comparison on position cards.
3. **"Would you buy today?" prompt**: Monthly or on-demand per position — surface as an action card in the Today view. "Position X is up 40%. The thesis says Y. Would you initiate a new position at today's price?"
4. **Action bias counter**: When all positions are healthy and no sell signals are firing, show a prominent "Portfolio is healthy — no action needed" card. Make "do nothing" feel like a positive outcome.
5. **FOMO counter**: When social buzz score is high but fundamentals are weak, show warning: "High social interest but weak fundamentals — review carefully before acting."

**Where in codebase**:
- Modify: `pwa/src/views/Portfolio.tsx` — thesis-first display, fair value vs. price comparison
- Modify: `pwa/src/views/Today.tsx` — "would you buy today" cards, "no action needed" card
- Modify: `pwa/src/components/deepdive/HeroVerdictStrip.tsx` — anchor to fair value not cost basis
- Modify: `src/investmentology/advisory/briefing.py` — generate behavioral nudges in briefing
- Modify: `pwa/src/components/shared/BentoCard.tsx` — new card variants for behavioral prompts

**Data requirements**: All from existing data (thesis health, fair value estimates, social buzz scores).

**Effort**: Medium (half day)
**Dependencies**: A3 (thesis monitoring provides the health status)
**Impact**: High — behavioral debiasing is the #3 alpha source per Phase 2 synthesis. Small UI changes can have outsized impact on decision quality.

---

### C2. Newsletter-Style Briefings

**What changes**: Restructure the daily briefing from raw data summaries to narrative briefings following the pattern: event -> implication -> context -> perspective -> what to watch.

**Specifically**:
1. Refactor `briefing.py` output format from data tables to structured narrative blocks
2. Each briefing section follows: "What happened" -> "Why it matters for your portfolio" -> "Historical context" -> "What to watch next"
3. For each position: Instead of "AAPL: +2.3%, P/E 28, F-Score 7", write "AAPL rose 2.3% on strong services revenue guidance. This supports the thesis (recurring revenue growth). Watch: iPhone sell-through data next quarter."
4. Use the CIO synthesis agent to generate the narrative (it already has all the data)
5. Add a "Weekly Digest" mode that aggregates daily events into a weekly narrative

**Where in codebase**:
- Modify: `src/investmentology/advisory/briefing.py` — restructure output format from `MarketOverview`/`PortfolioSnapshot` to `NarrativeBriefing`
- Modify: `src/investmentology/api/routes/daily.py` — serve narrative format alongside raw data
- Modify: `pwa/src/views/Today.tsx` — render narrative briefing with progressive disclosure (summary first, detail on tap)
- New: `pwa/src/components/shared/NarrativeCard.tsx` — reusable narrative block component

**Data requirements**: All from existing pipeline data. The narrative generation is an LLM task using data already collected.

**Effort**: Medium (half day)
**Dependencies**: None
**Impact**: Medium — better communication doesn't change the underlying analysis but dramatically improves decision quality by making information actionable rather than just available.

---

### C3. Portfolio-Level Analysis Dashboard

**What changes**: Add portfolio-level analytics that go beyond individual stock views.

**Specifically**:
1. **Sector concentration heatmap**: Show portfolio weight by sector with color intensity. Flag when any sector > 30%.
2. **Factor exposure breakdown**: Classify each position as value/growth/momentum/quality/income tilt. Show portfolio-level factor balance.
3. **Correlation matrix**: Use 60-day rolling correlations between held positions. Highlight hidden correlations (two "diversified" stocks that actually move together). Already have `useCorrelations.ts` hook and `CorrelationHeatmap.tsx` component — extend them.
4. **Scenario analysis**: Already have `ScenarioAnalysis.tsx` — enhance with sector-level shocks: "If tech drops 20%, your portfolio drops X%."
5. **Cash as a position**: Display cash balance as an explicit allocation with its opportunity cost. "You hold 30% cash. In the current regime (Expansion), cash drag costs approximately X% annually."
6. **"Adding X" preview**: Before adding a new position, show how it changes sector concentration, correlation profile, and factor balance.

**Where in codebase**:
- Modify: `src/investmentology/advisory/portfolio_fit.py` — expand to compute factor exposure, correlation impact
- Modify: `src/investmentology/api/routes/portfolio.py` — add `/portfolio/analytics` endpoint
- Modify: `pwa/src/views/Portfolio.tsx` — add analytics tab/section
- Modify: `pwa/src/components/charts/CorrelationHeatmap.tsx` — enhance with position labels and warnings
- Modify: `pwa/src/components/portfolio/ScenarioAnalysis.tsx` — add sector shock scenarios
- Modify: `pwa/src/components/charts/AllocationDonut.tsx` — include cash as explicit slice

**Data requirements**: Price history for correlations (yfinance, already used). Sector data (yfinance, already fetched). Factor classification from agent verdicts and quant gate scores.

**Effort**: Large (1-2 days)
**Dependencies**: A1 (composite quality score for factor classification)
**Impact**: High — transforms the app from "stock picker" to "portfolio advisor." Currently there is no way to see how positions interact. Portfolio construction is the #5 alpha source per Phase 2.

---

### C4. Decision Journal Enhancement

**What changes**: The Decision Registry exists but functions as a log, not a learning tool. Transform it into a structured decision journal with feedback loops.

**Specifically**:
1. At each buy: auto-record thesis, confidence, expected outcome, expected timeline, market regime at entry
2. At each sell: auto-record sell thesis, what changed, whether original thesis was correct
3. At settlement dates: auto-record actual outcome and compare to prediction
4. Build **calibration analysis**: "Your 70% confidence calls are actually correct X% of the time." Already have calibration infrastructure (`learning/predictions.py`, `api/routes/calibration.py`, `views/Calibration.tsx`) — feed decision journal data into it.
5. Build **pattern detection**: "You tend to be overconfident in tech stocks and underconfident in industrials." Aggregate calibration data by sector, market regime, and position type.
6. Surface top 3 behavioral patterns in the weekly briefing

**Where in codebase**:
- Modify: `src/investmentology/learning/registry.py` — add structured journal fields to decision logging
- Modify: `src/investmentology/learning/predictions.py` — auto-settle predictions from closed position data
- Modify: `src/investmentology/api/routes/calibration.py` — add sector/regime breakdowns
- Modify: `pwa/src/views/Calibration.tsx` — pattern visualization
- Modify: `src/investmentology/advisory/briefing.py` — include behavioral pattern insights

**Data requirements**: All from existing internal data. Cross-references decisions, predictions, and closed positions.

**Effort**: Medium (half day)
**Dependencies**: None
**Impact**: Medium-High — the feedback loop is what makes the system genuinely learn. Without it, the same mistakes get repeated. Kahneman's work shows that structured feedback is the single most effective debiasing intervention.

---

### C5. Progressive Disclosure in Stock Deep Dive

**What changes**: The stock deep dive page currently shows all information at once. Implement progressive disclosure: summary -> detail -> raw data, each level expandable.

**Specifically**:
1. **Level 1 (Hero)**: Verdict strip (already exists), thesis health badge, fair value vs. price, top 3 signals — visible immediately
2. **Level 2 (Analysis)**: Agent stances, signal pills, competence assessment, risk panel — collapsed by default, expand on tap
3. **Level 3 (Data)**: Full fundamentals table, all agent reasoning, historical verdicts, raw data — available but deeply nested
4. Add "Key Question" callout at top: the single most important thing the user should decide right now (e.g., "Thesis is INTACT but price is 130% of fair value — consider trimming")
5. Add "What's Changed Since Last Analysis" diff view showing which signals shifted

**Where in codebase**:
- Modify: `pwa/src/views/StockDeepDive.tsx` — restructure into progressive disclosure layers
- Modify: `pwa/src/components/deepdive/CollapsiblePanel.tsx` — enhance with level indicators
- Modify: `pwa/src/components/deepdive/HeroVerdictStrip.tsx` — add key question callout
- New: `pwa/src/components/deepdive/WhatChangedPanel.tsx` — diff view between last two analyses
- Modify: `src/investmentology/api/routes/stocks.py` — add `/stocks/{ticker}/diff` endpoint comparing latest two verdicts

**Data requirements**: All from existing verdict and analysis data. Diff computation uses `verdict_diffs` table (already exists in migration 009).

**Effort**: Medium (half day)
**Dependencies**: None
**Impact**: Medium — reduces cognitive load. The user shouldn't have to parse 9 agent opinions to understand the key takeaway.

---

### C6. Confidence Range Visualization

**What changes**: Display agent confidence as ranges rather than point estimates. Show disagreement visually.

**Specifically**:
1. For each stock, compute: min confidence across agents, max confidence, weighted mean, standard deviation
2. Display as a confidence interval bar: [min --- weighted mean --- max]
3. Color code: narrow range (green, high agreement), wide range (amber, disagreement), very wide (red, high uncertainty)
4. On the stock deep dive, show each agent's confidence as a dot on the range bar
5. In the verdict, show "70% +/- 15%" rather than just "70%"

**Where in codebase**:
- Modify: `src/investmentology/pipeline/convergence.py` — compute confidence statistics (min, max, stddev)
- Modify: `src/investmentology/api/routes/analyse.py` — include confidence range in response
- New: `pwa/src/components/shared/ConfidenceRange.tsx` — horizontal bar with agent dots
- Modify: `pwa/src/components/deepdive/VerdictMathPanel.tsx` — use range instead of point estimate
- Modify: `pwa/src/components/shared/AgentConsensusPanel.tsx` — show range bar

**Data requirements**: All from existing agent results.

**Effort**: Small (1-2 hours)
**Dependencies**: None
**Impact**: Medium — wide confidence ranges should reduce conviction and position size. Narrow ranges should increase it. Currently the user doesn't know whether "70% confidence" means all agents agree or three say 90% and three say 50%.

---

### C7. Tax-Aware Position Indicators

**What changes**: Display tax-relevant information for each position (holding period, short-term vs. long-term status, tax-loss harvesting candidates).

**Specifically**:
1. For each position, compute and display: days held, short-term vs. long-term status (>1 year = long-term), days until long-term qualification
2. At year-end (Nov-Dec), auto-flag positions with unrealized losses as "tax-loss harvesting candidates"
3. After any sell, warn about wash sale rule: "Cannot repurchase within 30 days if sold at a loss"
4. Before selling a winning position held < 1 year, show: "Short-term gain — taxed as ordinary income"

**Where in codebase**:
- Modify: `src/investmentology/sell/engine.py` — add tax-aware sell warnings
- Modify: `src/investmentology/api/routes/portfolio.py` — include tax fields in position response
- Modify: `pwa/src/views/Portfolio.tsx` — show holding period badge (ST/LT), tax-loss harvest flag
- Modify: `pwa/src/components/portfolio/ClosePositionModal.tsx` — tax impact warning

**Data requirements**: Position entry dates (already tracked). No external data needed.

**Effort**: Small (1-2 hours)
**Dependencies**: None
**Impact**: Low — paper trading now, but essential infrastructure for any real-money transition. Low effort to add and high value when it matters.

---

## Prioritized Roadmap

### Phase 1: Quick Wins (1 week)
*High impact, small/medium effort. Do first.*

| # | Item | Effort | Impact | Workstream |
|---|------|--------|--------|------------|
| 1 | A2: Enhanced Dividend Growth Framework | Small | Medium-High | A |
| 2 | A5: Contrarian Assessment Trigger | Small | Medium | A |
| 3 | A6: Value vs. Momentum Disagreement Flagging | Small | Medium | A |
| 4 | A7: Sell-Side Consensus as Contrarian Input | Small | Medium | A |
| 5 | B2: Insider Activity Enhancement | Small | Medium-High | B |
| 6 | B5: Data Freshness Dashboard | Small | Low-Medium | B |
| 7 | C6: Confidence Range Visualization | Small | Medium | C |
| 8 | C7: Tax-Aware Position Indicators | Small | Low | C |

**Total effort**: ~2-3 days for all 8 items. Each is independent and can be done in any order.

---

### Phase 2: Core Improvements (2-3 weeks)
*High impact, medium/large effort. Do next.*

| # | Item | Effort | Impact | Depends On |
|---|------|--------|--------|------------|
| 1 | A1: Composite Quality Score | Medium | High | — |
| 2 | A3: Thesis-Based Sell Discipline | Large | Very High | A1 |
| 3 | B1: FRED Macro Regime Dashboard | Medium | Medium | — |
| 4 | B3: Earnings Calendar & Event Tracking | Medium | Medium-High | — |
| 5 | C1: Behavioral Debiasing UI Patterns | Medium | High | A3 |
| 6 | C2: Newsletter-Style Briefings | Medium | Medium | — |
| 7 | C4: Decision Journal Enhancement | Medium | Medium-High | — |
| 8 | C5: Progressive Disclosure in Deep Dive | Medium | Medium | — |

**Critical path**: A1 -> A3 -> C1. Start A1 first. B1, B3, C2, C4, C5 can run in parallel.

---

### Phase 3: Advanced (2-4 weeks)
*High impact but larger effort or depends on Phase 2 foundations.*

| # | Item | Effort | Impact | Depends On |
|---|------|--------|--------|------------|
| 1 | A4: Position Lifecycle Management | Medium | Medium-High | A3 |
| 2 | B4: Management Quality Signals | Medium | Medium | — |
| 3 | C3: Portfolio-Level Analysis Dashboard | Large | High | A1 |

**Note**: C3 is the largest single item and has the highest payoff in this phase. It transforms the app from "stock picker" to "portfolio advisor."

---

### Phase 4: Aspirational (when foundations are solid)
*Lower priority or requires significant new infrastructure.*

| # | Item | Description | Why Later |
|---|------|-------------|-----------|
| 1 | 13D/activist tracking | Monitor EDGAR 13D filings for activist positions | Requires new EDGAR parsing infrastructure for a specific filing type |
| 2 | Spin-off detection | Identify upcoming spin-offs from 8-K/proxy filings | Complex event detection; rare events |
| 3 | Industry lifecycle classification | S-curve positioning for each stock | Qualitative judgment; agents already do this implicitly |
| 4 | Alternative data (job postings, app rankings) | Web scraping for hiring trends and app store data | Scraping infrastructure needed; maintenance burden |
| 5 | Portfolio optimization | Mean-variance optimization with constraints | Requires meaningful historical portfolio data (need 6+ months of tracked positions) |
| 6 | Backtesting the pipeline itself | Run historical Magic Formula + agents on past data | Huge scope; look-ahead bias concerns; existing backtest view covers simpler scenarios |

---

## Implementation Notes

### What NOT to change
- The overnight pipeline architecture (CronJob + controller polling) works well — don't rearchitect it
- The agent skills framework is clean and extensible — add data to prompts, don't change the framework
- The CLI proxy pattern (HB LXC screens) is the right approach for subscription-based models
- The 6-layer pipeline structure is sound — improvements are *within* layers, not new layers
- The existing sell engine with position-type-specific rules is well-designed

### Key Technical Constraints
- **CLI agents can't be programmatically introspected** — improve their output by improving their input (richer context, better prompts)
- **No GPU on homelab** — all new computations must be pure math or API calls, not ML training
- **Single user** — no need for access control, rate limiting on internal endpoints, or multi-tenant data isolation
- **Pipeline processes 100+ stocks overnight** — new calculations must be efficient (O(n) per stock, not O(n^2))
- **Free data only** — every new metric must be computable from yfinance, EDGAR, Finnhub, or FRED

### Testing Approach
- Each item should include unit tests for new calculations (Beneish, dividend growth, management quality)
- Integration test: run quant gate on 10 known stocks and verify composite scores are reasonable
- Before/after comparison on the daily briefing output to validate narrative quality
- Paper trading validation: track whether new sell signals would have improved historical outcomes

---

## Summary: Where the Alpha Is

Phase 2's key insight — "the real alpha is in better process, not better data" — drives this plan. The top 3 items by expected impact on investment outcomes:

1. **A3: Thesis-Based Sell Discipline** — addresses the #1 source of retail investor losses
2. **C3: Portfolio-Level Analysis Dashboard** — transforms stock picking into portfolio management
3. **A1 + C1: Composite Quality Score + Behavioral Debiasing** — catches value traps quantitatively and counteracts cognitive biases through UI design

Everything else supports, enhances, or builds on these three pillars.

---

*This plan contains 18 concrete improvements across 3 workstreams, organized into 4 priority phases. Total estimated effort: 4-6 weeks for Phases 1-3. Each item includes specific file paths, data requirements, and dependencies to enable immediate implementation.*
