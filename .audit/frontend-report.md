# Investmentology PWA — Frontend Audit Report

**Auditor:** frontend-auditor
**Date:** 2026-03-04
**Source:** `/home/investmentology/pwa/src/`

---

## TypeScript Type Summary (models.ts / api.ts)

Key interfaces used across the PWA:

| Type | Key Fields |
|------|-----------|
| `Position` | ticker, shares, avgCost, currentPrice, marketValue, unrealizedPnl/Pct, dayChange/Pct, weight, entryDate, positionType, name, dividendYield/PerShare/Annual/Monthly, dividendFrequency, exDividendDate |
| `Recommendation` | ticker, name, sector, industry, currentPrice, marketCap, verdict, confidence, consensusScore, consensusTier, reasoning, agentStances, riskFlags, auditorOverride, mungerOverride, successProbability, stabilityScore/Label, buzzScore/Label, headlineSentiment, contrarianFlag, earningsMomentum, portfolioFit, dividendYield, changePct, suggestedType/Label, heldPosition, advisoryOpinions, boardNarrative, boardAdjustedVerdict |
| `WatchlistItem` | ticker, name, sector, state, addedAt, lastAnalysis, priceAtAdd, currentPrice, marketCap, compositeScore, piotroskiScore, altmanZone/ZScore, combinedRank, verdict (WatchlistVerdict), notes, successProbability, changePct, priceHistory |
| `Decision` | id, ticker, decisionType, confidence, reasoning, createdAt, layer, outcome, settledAt |
| `AgentStance` | name, sentiment, confidence, key_signals[], summary |
| `AdvisoryOpinion` | advisor_name, display_name, vote, confidence, assessment, key_concern, key_endorsement, reasoning |
| `BoardNarrative` | headline, narrative, risk_summary, pre_mortem, conflict_resolution, advisor_consensus |
| `StockResponse` (deepdive) | ticker, name, sector, industry, profile, fundamentals, quantGate, competence, verdict, verdictHistory, signals, decisions, watchlist, position, briefing, buzz, earningsMomentum, stabilityScore/Label, consensusTier |

---

## 1. Today View (`/`)

**API calls:** `/api/invest/daily/briefing/summary`, `/api/invest/portfolio/advisor`, `/api/invest/portfolio/thesis-summary`, portfolio hook

### Always Visible

| Section | Fields Rendered |
|---------|----------------|
| **Market Pendulum** (SVG arc gauge) | `briefing.pendulumScore` (0-100), `briefing.pendulumLabel` (extreme_fear/fear/neutral/greed/extreme_greed) mapped to display string + explanatory sentence |
| **Portfolio Pulse — Value** | `totalValue` (animated number) |
| **Portfolio Pulse — Day P&L** | `dayPnl` (animated, color-coded), `dayPnlPct` (%) |
| **Portfolio Pulse — Positions** | Count of thesis positions |
| **Thesis Health Dots** | Per-position: `ticker`, `thesis_health` (INTACT/UNDER_REVIEW/CHALLENGED/BROKEN) as colored dot, `pnl_pct` shown in hover tooltip |
| **Alert Banner** | `briefing.criticalAlertCount`, `briefing.alertCount` — shown if > 0 |
| **Quick Links** | Buttons navigating to /recommendations and /watchlist |

### Action Queue (expandable per row)

**Collapsed:** Badge with `action.type` (SELL/TRIM/REVIEW/REBALANCE/BUY), `action.ticker`, `action.title` (truncated)

**Expanded:** `action.reasoning` (prose), agent stance avatar tiles (WB/RA/SK/GS/SD/RD/JS/PL/DA) with color-coded borders by sentiment, `action.consensus_score`, "Deep Dive" link

**Text walls present:** `action.reasoning` — full prose, visible only on expand.

---

## 2. Portfolio View (`/portfolio`)

**API calls:** portfolio hook, `/api/invest/portfolio/advisor`, `/api/invest/daily/briefing/summary`, `/api/invest/portfolio/risk-snapshot`, `/api/invest/portfolio/thesis-summary`, `/api/invest/portfolio/balance`, correlations hook, `/api/invest/stock/{ticker}/chart`
**WebSocket:** live price updates for enriched P&L
**Tabs:** Positions, Thesis, Risk, History

### Positions Tab

#### Hero Banner (always visible)
- Animated total portfolio value (large font)
- Day P&L strip: `liveDayPnl` (currency), `liveDayPnlPct` (%)
- Floating bar appears when hero scrolls out of view (value, day P&L, position count)

#### Metric Cards (2-up)
- **Total P&L:** `unrealizedPnl` sum (animated, gradient color), `totalPnlPct`
- **Cash:** `cash` amount, `cashPct` (% of portfolio)

#### Allocation (collapsible, default closed)
- SVG donut chart: current equities vs cash
- Target donut (hardcoded: 70% equities, 15% bonds, 10% gold, 5% cash)

#### Performance (collapsible, from store `performance`)
- `alphaPct`, `sharpeRatio`, `sortinoRatio`, `winRate`, `maxDrawdownPct`

#### Daily Intel Card
- Mini pendulum gauge: `briefing.pendulumLabel`, `briefing.pendulumScore`
- Risk level: `briefing.overallRiskLevel` (icon color-coded)
- Alert count: `briefing.alertCount`
- Action Items: merged advisor actions + `briefing.topActions` (up to 5). Each row expandable with fetched reasoning.

#### Positions Section (with filter: All/Winners/Losers/Dividends)

**PositionCard — 3-page swipeable carousel:**

*Default page (center):*
- Mini sparkline (since entry, with avg cost reference line)
- `unrealizedPnlPct` ("since buy" label, color-coded)
- `currentPrice`, `dayChangePct` (today)

*Swipe right (page -1):*
- `marketValue`, `positionType`, days held, `dayChange` (currency)

*Swipe left (page +1):*
- `avgCost`, cost basis (avgCost×shares), `unrealizedPnl` ($), `shares`, `weight`, days held

*Always visible (left panel):*
- `ticker`, `positionType` badge (core/speculative/other)
- `name` (truncated), shares count, `weight` %

*Click → opens StockDeepDive overlay*

**Dividend Cards (dividends filter):**
- `ticker`, shares, `currentPrice`, `dividendYield` %, `monthlyDividend`, `annualDividend`
- Totals banner: total monthly + annual dividend income

#### Balance Section (collapsible, default closed)
- 3D tilted exploded pie chart by sector
- Health badge (`balance.health`: excellent/good/fair/poor)
- Sector rows: `name`, `pct`, zone (green/amber/red based on softMax/warnMax), tickers in sector
- Risk categories: name, pct, zone, idealMin/idealMax
- Insight text strings (`balance.insights[]`)

### Thesis Tab
- Per-position thesis health: `ticker`, `position_type`, `thesis_health`, `entry_thesis`, `pnl_pct`, `days_held`, `conviction_trend`

### Risk Tab
- From `/api/invest/portfolio/risk-snapshot`: `risk_level`, `top_position_weight`, `avg_thesis_health_score`, `sector_concentration` map, per-position details

### History Tab
- Closed positions list (ClosedTradeCard)
- Each card: `ticker`, `holdingDays`, entry→exit price, `realizedPnlPct`, `realizedPnl`
- **Expandable "What Could Have Been":** fetches current price → shows "If Held" P&L and "Missed/Saved" vs current
- Total realized P&L banner

---

## 3. Watchlist View (`/watchlist`)

**API calls:** watchlist hook (`groupedByState`), analysis context

**Per ItemCard — collapsed (always visible):**

| Field | Display |
|-------|---------|
| `successProbability` | SVG ring chart (color thresholds: ≥70% green, ≥40% amber, else red) |
| `ticker` | Monospaced bold |
| `addedAt` | Relative date (today / Nd ago / Nw ago / Nmo ago) |
| `name` | Muted small text |
| `marketCap` | Formatted (T/B/M suffix) |
| Agent stances | Mini sentiment bars per agent (9 agents abbreviated 3-char), bullish green / bearish red |
| `riskFlags.length` | Risk flag count warning |
| Board votes | Approve/veto count pill (green if ≥75% approve, red if any veto) |
| Price column | `currentPrice`, `priceAtAdd` ("from $X"), `changePct` since add |
| Sparkline | `priceHistory` (7-30 day) color-coded by changePct |

**Expandable per card:**
1. **AgentConsensusPanel:** ring showing net sentiment, avatar tiles per agent with sentiment/confidence, `consensusScore`
2. **EntryTriggerChecklist:**
   - Verdict gate: check mark/cross vs BUY+ verdict needed
   - Quant rank: `combinedRank` vs top-50 threshold
   - Catalyst note: `notes` field
   - Progress bar (0/3 to 3/3)
   - "Since added" price change %

**Text walls:** None collapsed. `reasoning` not shown in list view.
**Header:** "N stocks tagged by agents", Analyze All button, MarketStatus indicator

---

## 4. Recommendations View (`/recommendations`)

**API calls:** `/api/invest/recommendations`, sparkline from `/api/invest/stock/{ticker}/chart?period=3mo`

**Grouped by verdict** in order: STRONG_BUY → BUY → ACCUMULATE → HOLD → WATCHLIST → REDUCE → SELL → AVOID → DISCARD
**Group header:** icon, title (e.g. "High Conviction"), tagline

### RecCard — Collapsed (always visible)

| Field | Display |
|-------|---------|
| `successProbability` | Large SVG ring (56px, color-coded) |
| `ticker` | Large bold monospaced |
| verdict label | Colored by verdict |
| `confidence` | "XX% conf" muted |
| `name` | Company name |
| `sector`, `marketCap` | Small muted |
| 3-month sparkline | SVG price chart with area fill |
| `currentPrice` | Current price |
| `changePct` | Day change % with trend icon |
| Agent consensus bar | Proportional bull/hold/bear pill segments (from agentStances sentiments) |
| Signal pills | `riskFlags` count, `consensusTier`, `stabilityLabel`, `buzzLabel`, `earningsMomentum` label+beat streak, `suggestedLabel`, contrarian flag, `dividendYield`, `consensusScore` |
| Board summary strip | `boardNarrative.headline` (italic truncated), approve/veto pill, `boardAdjustedVerdict` if different |
| Held position strip | Position type, thesis health dot, days held, `pnlPct`, `entryThesis` (italic) |

### RecCard — Expanded ("Why VERDICT?" button)

| Section | Fields |
|---------|--------|
| AgentConsensusPanel | Full ring + per-agent avatar tiles (name, sentiment bar, confidence) |
| SignalTagCloud | Frequency-weighted tag cloud from `agentStances[].key_signals` |
| Advisory Board votes | Per-advisor: `display_name`, vote label, confidence %, `assessment` (truncated 140 chars), `key_concern` (italic red), `key_endorsement` (italic green) |
| Portfolio Fit | `portfolioFit.score` %, `portfolioFit.reasoning` (prose) |

**Text walls:** `reasoning` is NOT shown in this view (only in deep dive).
**Interactive:** "Add to Portfolio" button → AddToPortfolioModal with shares/price/type/thesis fields.

---

## 5. StockDeepDive (overlay, from any ticker link)

**API calls:** `/api/invest/stock/{ticker}`, `/api/invest/stock/{ticker}/news`
**Triggered by:** clicking any ticker across views (setOverlayTicker → LayerOverlay)

### Layer 1 — Always Above Fold

**Header:**
- `ticker`, `watchlist.state` badge
- `name`, `industry` / `sector`, `profile.city` + `profile.country`, `profile.website` link
- `fundamentals.price`, `fundamentals.market_cap` formatted
- `profile.employees`
- MarketStatus indicator
- Analyze button, + Portfolio button

**PriceChart:** Interactive price chart (period selector 1W/1M/3M/6M/1Y)

**HeroVerdictStrip** (glowing orbit border, verdict-color-matched):
- Verdict label (huge font, color), `auditorOverride` badge, `mungerOverride` badge
- `boardNarrative.headline` (italic subtitle)
- Vote tally: N Approve / N Adjust / N Veto
- `consensusScore` raw value
- Confidence ring (64px, color-coded): `confidence` %
- Analysis timestamp

**PositionTile** (if held):
- Compact P&L display with shares, entry, current, pnl

**SignalPills:**
- `consensusTier`, `stabilityLabel`/`stabilityScore`, `buzz` data (buzzScore, buzzLabel, headlineSentiment, articleCount, contrarianFlag), `earningsMomentum` (score, label, upward/downward revisions, beat streak)

### Layer 2 — Collapsible Panels

#### Agent Analysis Panel
**Collapsed preview:** top 3 key signal tags, vote tally
**Expanded:**
- AgentConsensusPanel (ring + per-agent avatar tiles with name/sentiment bar/confidence)
- SignalTagCloud (frequency-weighted tags)
- `verdict.reasoning` (full prose via FormattedProse)
- Advisory Board grid: per-advisor card with name, vote label (APPROVE/ADJUST/VETO), confidence %, `assessment` (140 char), `key_concern` (red), `key_endorsement` (green)
- Vote bar (proportional green/accent/red segments)
- `boardAdjustedVerdict` if board overrode
- **CIO Synthesis** (nested expand): `boardNarrative.narrative`, `boardNarrative.conflict_resolution`

**Text walls:** `verdict.reasoning` (often multi-paragraph), `boardNarrative.narrative` behind second expand, per-advisor `reasoning` field NOT shown (only assessment).

#### Metrics & Valuation Panel
**Collapsed preview:** P/E, EY, Composite score, Piotroski
**Expanded:**
- Valuation: `trailingPE`, `forwardPE`, `priceToBook`, `priceToSales`, `earnings_yield`, `roic`, `beta`, `dividendYield`, `averageVolume`
- 52-week range bar: `fiftyTwoWeekLow`, `fiftyTwoWeekHigh`, current price marker
- Analyst consensus: `analystRecommendation` badge, `analystCount`, `analystTarget` $ with upside %
- Quant Gate: `compositeScore` (large), `piotroskiScore` /9, `altmanZScore` + zone badge, `combinedRank`, `eyRank`, `roicRank`
- Fundamentals: `market_cap`, `enterprise_value`, `revenue`, `net_income`, `operating_income`, `cash`, `total_debt`, `shares_outstanding`, data freshness date

#### Risk & Red Flags Panel (only shown if risks exist)
**Collapsed preview:** "N risk items identified"
**Expanded:**
- `verdict.riskFlags[]` (each as red left-border block)
- Advisor concerns: per-advisor `key_concern` with advisor name
- CIO Risk Assessment: `boardNarrative.risk_summary` (formatted prose)
- Pre-Mortem: `boardNarrative.pre_mortem` (formatted prose)
- Moat durability warning if < 10 years

#### Position Detail Panel (if position held)
- `shares`, `entryPrice`, `currentPrice`, `pnl` (+ %), `weight`, days held, `stopLoss`, `fairValue`
- `thesis` (italic prose, below metrics)
- Sell button → exit price modal

#### Competence & Moat Panel
- `competence.passed` badge ("In Circle"/"Outside Circle"), `confidence` %
- `sector_familiarity` badge
- `competence.reasoning` (full prose)
- Moat: `type`, `trajectory`, `durability_years`, `sources[]` badges, `moat.reasoning` prose

### Layer 3 — Full Archive (below separator)

| Section | Fields |
|---------|--------|
| **Verdict History** | Timeline of past verdicts: verdict label + confidence + consensusScore + date |
| **Agent Signals** | Per-signal row: agentName, model, confidence badge. Expandable: full `reasoning` prose |
| **Decision History** | Per decision: `decisionType` badge, `layer`, date, `confidence` badge |
| **Recent News** | Title, summary (160 char), publisher, date, clickable link |
| **Business** | `profile.businessSummary` (full text) |
| **Watchlist** | State badge, `notes`, `updated_at` |

**Text walls in archive:** agent signal `reasoning` per expand, `businessSummary` (full, untruncated).

**NOT SHOWN in DeepDive:**
- `profile.analystRecommendation` full text detail beyond badge (shown in Metrics)
- Per-advisor full `reasoning` (only `assessment` 140 chars shown)
- `boardNarrative.pre_mortem` full text (behind Risk expand)
- `EarningsMomentum.upwardRevisions`, `downwardRevisions` raw numbers (only shown as badge label)

---

## 6. Decisions View (`/decisions`)

**API calls:** paginated `/api/invest/decisions`
**Filters:** ticker search (text input), type dropdown (12 types)
**Infinite scroll**

Per decision card (always visible):
- `ticker` (accent color)
- `decisionType` badge (BUY/SELL/TRIM/HOLD/REJECT/WATCHLIST/SCREEN/COMPETENCE_PASS/COMPETENCE_FAIL/AGENT_ANALYSIS/PATTERN_MATCH/ADVERSARIAL_REVIEW)
- `confidence` % (mono, right-aligned)
- `reasoning` (full prose, always visible — NO expand)
- `layer`, `createdAt` timestamp

**Text walls:** `reasoning` always fully shown (not expandable). Can be very long.
**NOT SHOWN:** `outcome`, `settledAt` (available in type but not rendered)

---

## 7. Agents View (`/agents`)

**API calls:** `/api/invest/agents/panel` (optional `?ticker=` for per-ticker opinions)

**Per AgentCard — collapsed (always visible):**
- `name`, "Devil's Advocate" badge (auditor only), online status dot
- `provider`, `model`, `totalSignals` count, `avgLatencyMs`
- Confidence ring: `avgConfidence`
- Signal Fingerprint bar: `allowed_tags` classified into Fund/Macro/Tech/Risk/Act proportional colored bar
- Mantra chips: first 4 sentences from `critical_rules[]`
- Latest analysis preview: `latestAnalysis.ticker`, confidence ring (24px), first sentence of `reasoning`

**Expanded:**
- `agent.focus` (italic)
- Full `critical_rules[]` list (left-border text)
- Signal vocabulary: all `allowed_tags` as colored chips (classified by type)
- Full latest analysis: `ticker`, confidence badge, full `reasoning`, timestamp

**Text walls:** `critical_rules` and full `reasoning` behind expand.

**NOT SHOWN:** `philosophy` field (in interface but not rendered beyond `focus`)

---

## 8. QuantGate View (`/quant-gate`)

**API calls:** latest QuantGate run

**Run summary:** `runDate`, `stocksScreened`, `stocksPassed`, `analyzedCount`
**Funnel chart:** visual pipeline stages
**Table per stock:**

| Column | Field |
|--------|-------|
| Rank | `combinedRank` |
| Ticker | `ticker`, `name` (truncated), `sector` |
| Composite | `compositeScore` bar + value |
| ROIC | `roic` % |
| EY | `earningsYield` % |
| Piotroski | `piotroskiScore` /9 badge |
| Altman Z | `altmanZScore`, zone badge |
| Verdict | `verdict` badge (if analyzed), `verdictConfidence` % |
| Analyze | button |

**Glossary tooltips** on column headers (GlossaryTooltip component).
**Click row** → StockDeepDive overlay.

---

## 9. Pipeline View (`/pipeline`)

**API calls:** pipeline hooks (status, tickers, funnel, health)
**Auto-refresh:** 10s interval

### Summary Funnel
- Stage counts: dataFetch, preFilter (passed/rejected with reasons), screeners, gate, analysis
- FunnelChart visual

### Ticker Cards (collapsible)
Per ticker summary:
- `ticker`, step progress (completed/total), `gateOutcome` badge (pre_filtered/passed/rejected)
- Pre-filter fail reason if applicable
- Step dots: per step with color (pending/running/completed/failed/expired)

Expanded per ticker:
- PreFilter detail: `rulesChecked`, `rulesFailed[]` with tooltips
- Screener verdicts: per screener name, pass/fail, confidence, tags, latency ms
- Screener vote tally: pass/reject counts vs required

### Health Tab
- Per-step: total, completed, failed, `errorRate`
- Step timing: `avgSeconds`, `maxSeconds`, count
- Recent errors: ticker, step, error message, timestamp, retry count

---

## 10. Learning View (`/learning`)

**API calls:** `/api/invest/calibration`, `/api/invest/learning/agents`, `/api/invest/learning/attribution`

| Section | Fields |
|---------|--------|
| Score metrics | `brierScore` (3dp), `totalPredictions`, bucket count |
| Calibration chart | `buckets[]`: midpoint, accuracy, count — scatter plot |
| Per-bucket accuracy | Horizontal bars with midpoint % vs actual accuracy %, sample count |
| Agent Attribution | Per agent: overall accuracy %, bullish accuracy/total, bearish accuracy/total, total calls |
| Best/Worst signals | Signal tag name, agent name, accuracy % |
| Attribution insights | `recommendations[]` prose strings |
| Legacy agent accuracy | `accuracy`, `avgConfidence`, `totalDecisions` per agent |

---

## 11. Backtest View (`/backtest`)

Not fully read but accessed from Learning via navigate("/backtest").

---

## 12. System Health View (`/system`)

Not fully read. Shows `SystemHealth` type: `status`, `database`, `apiKeys` map, `lastQuantRun`, `decisionsLogged`, `uptime`.

---

## Summary: Text Wall Inventory

| Location | Field | Visibility |
|----------|-------|------------|
| Today > Action Queue | `action.reasoning` | Behind expand |
| Watchlist | No prose shown in list | — |
| Recommendations | `rec.reasoning` | NOT SHOWN in list view |
| DeepDive > Agent Analysis | `verdict.reasoning` | Behind panel expand |
| DeepDive > Agent Analysis | `boardNarrative.narrative` | Behind double expand (CIO Synthesis) |
| DeepDive > Agent Analysis | `boardNarrative.conflict_resolution` | Behind double expand |
| DeepDive > Risk | `boardNarrative.risk_summary` | Behind panel expand |
| DeepDive > Risk | `boardNarrative.pre_mortem` | Behind panel expand |
| DeepDive > Competence | `competence.reasoning` | Behind panel expand |
| DeepDive > Competence | `moat.reasoning` | Behind panel expand |
| DeepDive > Archive > Signals | `signal.reasoning` (per agent) | Behind row expand |
| DeepDive > Archive > Business | `profile.businessSummary` | Always visible when present |
| Decisions | `decision.reasoning` | Always visible (no expand) |
| Agents | `latestAnalysis.reasoning` | Behind card expand |

---

## Notable Gaps (Fields Available But NOT Shown)

| Field | Location in Type | Rendered? |
|-------|-----------------|-----------|
| `decision.outcome` | `Decision.outcome` | NO |
| `decision.settledAt` | `Decision.settledAt` | NO |
| `advisoryOpinion.reasoning` | `AdvisoryOpinion.reasoning` | NO (only `assessment` 140 chars) |
| `earningsMomentum.upwardRevisions` / `downwardRevisions` | `EarningsMomentum` | NO |
| `portfolioFit.diversificationScore` / `balanceScore` / `capacityScore` | `PortfolioFit` | NO (only score + reasoning) |
| `heldPosition.convictionTrend` | `HeldPosition` | NO |
| `heldPosition.reasoning` | `HeldPosition` | NO (only entryThesis) |
| `agentStance.key_signals` (full list) | `AgentStance` | Partially (first 2 per agent in tag cloud) |
| `boardNarrative.advisor_consensus` | `BoardNarrative` | NO |
| `profile.analystCount` raw | `Profile` | YES (in parentheses next to badge) |
| `quantGate.compositeScore` breakdown | `QuantGate` | Score only, no sub-components |
| `WatchlistItem.lastAnalysis` date | `WatchlistItem` | NO |
| `agent.philosophy` | `AgentProfile` | NO |
