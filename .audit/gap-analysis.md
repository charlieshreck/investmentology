# Gap Analysis: Frontend vs Backend — Investmentology PWA
*Generated: 2026-03-04*
*Cross-reference of backend-report.md and frontend-report.md*

---

## Executive Summary

The PWA renders a high proportion of backend data correctly. The primary gaps fall into five categories:

1. **Advisory board opinions are partially surfaced** — the `reasoning` field (2-3 sentences per advisor) is available but never rendered; only the 140-char `assessment` is shown.
2. **Adversarial content is structurally absent** — kill scenarios and pre-mortem narrative are not stored by the backend, so the PWA cannot display them regardless of implementation.
3. **Per-agent target prices are not surfaced** — agents produce individual `target_price` values but the API doesn't expose them and the PWA has no display for them.
4. **Several numerical scores are produced but not rendered** — `portfolioFit.diversificationScore`, `convictionTrend`, `heldPosition.reasoning`, `decision.outcome`/`settledAt`.
5. **Some useful analytics views exist in the API with no PWA counterpart** — attribution/learning data is partially shown in the Learning view but more detail is available.

---

## 1. LLM Content Produced But NOT Shown

### CRITICAL — High-Value IP Being Wasted

| Content | Backend Location | PWA Status | Impact |
|---------|-----------------|------------|--------|
| **Advisory board `reasoning`** (2-3 sentences per advisor, 8 advisors) | `advisoryOpinions[].reasoning` | **NOT SHOWN** — only `assessment` (140 chars) displayed | 8 unique investment philosophy analyses lost. This IS the IP. |
| **Adversarial kill scenarios** (5 failure scenarios with likelihood/impact/timeframe) | Computed in adversarial layer | **EPHEMERAL — not stored in DB or API** | Most valuable bear-case content never reaches user |
| **Adversarial pre-mortem narrative** ("It's 2028, we lost 50% because...") | Computed in adversarial layer | **EPHEMERAL — not stored** | Compelling risk narrative lost |
| **Individual agent target prices** | Each agent produces `target_price` | **NOT RETURNED via API** — only `position.fairValue` (manual) shown | Price target range from 8 agents would be highly informative |
| **Signal `detail` prose** (per-tag reasoning) | `signals[].signals[].detail` | **NOT SHOWN** — only tag name + strength displayed in SignalTagCloud | Agent reasoning for each specific signal is the explanation of WHY |
| **Agent `philosophy`** field | AgentSkill definition | **NOT RENDERED** on Agents page | Users can't understand why each agent thinks differently |
| **Pendulum `components`** (VIX score, put/call, SPY momentum, etc.) | `briefing.pendulum.components` | **NOT SHOWN** — only aggregate score/label displayed | Users see a number but not what drives it |
| **Pendulum `sizing_multiplier`** | `briefing.pendulum.sizing_multiplier` | **NOT SHOWN** | Concrete "buy 75% of normal size" signal hidden |

### MODERATE — Useful Context Missing

| Content | Backend Location | PWA Status |
|---------|-----------------|------------|
| `decision.outcome` + `decision.settledAt` | Decision model | Never rendered — prediction settlement invisible |
| `heldPosition.reasoning` | Recommendation model | Not shown (only `entryThesis`) |
| `heldPosition.convictionTrend` | Recommendation model | Not shown |
| `portfolioFit.diversificationScore/balanceScore/capacityScore` | PortfolioFit sub-scores | Only aggregate `score` + `reasoning` shown |
| `earningsMomentum.upwardRevisions/downwardRevisions` | EarningsMomentum model | Only label shown, not the raw revision counts |
| `WatchlistItem.lastAnalysis` date | Watchlist model | Not shown — user can't see when stock was last analyzed |
| `div_growth_5y`, `payout_ratio`, `last_div_date` | Dividend data | Not surfaced in dividend view |
| `performance.dispositionRatio`, `avgWinPct`, `avgLossPct`, `expectancy` | Portfolio performance | Not shown (only alpha, Sharpe, Sortino, winRate, drawdown) |
| `riskSummary.concentrationWarnings/drawdownAlerts/sectorImbalances` | Daily briefing | Only `overallRiskLevel` and `alertCount` shown on Today |
| `learningSummary` (pending/settled predictions, ECE) | Daily briefing | Not shown on Today view |
| `macroSignals[]` (human-readable regime observations) | Daily briefing | Not shown on Today view |
| Agent `token_usage` and `latency_ms` | Per-signal metadata | Not shown (pipeline health only) |
| `quant-gate/delta` (universe changes) | Dedicated endpoint | No UI for this |

---

## 2. Fields Available in Backend API, Not Rendered in PWA

### 2.1 Advisory Board Detail

The advisory board produces the richest LLM content in the system. Here is how much of it reaches the user:

| Content | Produced | API Returns | PWA Shows |
|---------|---------|------------|----------|
| `vote` (APPROVE/ADJUST_UP/ADJUST_DOWN/VETO) | 8 advisors | Yes | Yes — vote count pills |
| `confidence` | 8 advisors | Yes | Yes — shown in board grid |
| `assessment` (1-sentence headline) | 8 advisors | Yes | Yes — truncated to 140 chars |
| `key_concern` | 8 advisors | Yes | Yes — italic red text in board grid |
| `key_endorsement` | 8 advisors | Yes | Yes — italic green text in board grid |
| `reasoning` (2-3 sentence analysis) | 8 advisors | Yes | **NO** — available in type, not rendered |
| `boardNarrative.headline` | CIO | Yes | Yes — shown in HeroVerdictStrip |
| `boardNarrative.narrative` (3-4 paragraphs) | CIO | Yes | Yes — behind double-expand in DeepDive |
| `boardNarrative.risk_summary` | CIO | Yes | Yes — in Risk panel expand |
| `boardNarrative.pre_mortem` | CIO | Yes | Yes — in Risk panel expand |
| `boardNarrative.conflict_resolution` | CIO | Yes | Yes — behind double-expand |

**Finding:** `advisoryOpinion.reasoning` is the main missing piece. 8 advisors × 2-3 sentences = up to 24 sentences of differentiated LLM analysis that never reaches the user.

### 2.2 Moderate Gaps (Numerical Scores / Analytics)

| Field | API Location | PWA Status | Notes |
|-------|-------------|-----------|-------|
| `decision.outcome` | `decisions[].outcome` | **NOT SHOWN** | Always null currently — backend field not yet populated |
| `decision.settledAt` | `decisions[].settledAt` | **NOT SHOWN** | Same — null in DB currently |
| `portfolioFit.diversificationScore` | `rec.portfolioFit.diversificationScore` | **NOT SHOWN** | Sub-scores exist but only aggregate shown |
| `portfolioFit.balanceScore` | `rec.portfolioFit.balanceScore` | **NOT SHOWN** | Same as above |
| `portfolioFit.capacityScore` | `rec.portfolioFit.capacityScore` | **NOT SHOWN** | Same as above |
| `heldPosition.convictionTrend` | `rec.heldPosition.convictionTrend` | **NOT SHOWN** | Numeric conviction trend (-1.0 to +1.0) |
| `heldPosition.reasoning` | `rec.heldPosition.reasoning` | **NOT SHOWN** | Thesis health assessment reasoning text |
| `earningsMomentum.upwardRevisions` | `earningsMomentum.upwardRevisions` | **NOT SHOWN** | Raw revision counts not shown anywhere |
| `earningsMomentum.downwardRevisions` | `earningsMomentum.downwardRevisions` | **NOT SHOWN** | Same |
| `watchlistItem.lastAnalysis` | `watchlistItem.lastAnalysis` | **NOT SHOWN** | Useful for staleness awareness |
| `boardNarrative.advisor_consensus` | `boardNarrative.advisor_consensus` | **NOT SHOWN** | Low priority — vote tally already visible via pills |

### 2.3 Minor Gaps (Metadata / Operational)

| Field | API Location | PWA Status | Notes |
|-------|-------------|-----------|-------|
| `signal.token_usage` | `signals[].token_usage` | **NOT SHOWN** | Cost data — not user-facing |
| `signal.latency_ms` | `signals[].latency_ms` | **NOT SHOWN** | Pipeline debug — not user-facing |
| `quantGate.compositeScore` breakdown | `quantGate` | Partial | Score shown but not formula or weights |

---

## 3. Adversarial Layer: Structurally Absent

The Munger adversarial check produces valuable LLM content that is not stored by the backend. This is not a frontend bug — it is an architectural gap.

| Content | Produced | Stored | API Returns | PWA Shows |
|---------|---------|--------|------------|----------|
| 20 bias flag checks (keyword) | Yes | **No** | No | No |
| 5 kill scenarios (LLM text) | Yes | **No** | No | No |
| Pre-mortem narrative (LLM) | Yes | **No** | No | No |
| Pre-mortem key risks list | Yes | **No** | No | No |
| `munger_override` (bool) | Yes | Yes | Yes | Yes — badge in DeepDive |
| Truncated summary in reasoning | Yes | Partial (in reasoning field) | Yes | Partial (in verdict.reasoning prose) |

**Recommendation:** Store adversarial content in a dedicated `invest.adversarial_results` table. The kill scenarios and pre-mortem could then be surfaced in the Risk panel alongside the CIO pre-mortem.

---

## 4. Per-Agent Target Prices: Invisible Pipeline

Every primary agent optionally produces a `target_price` float representing their individual fair value estimate.

| Step | Status |
|------|--------|
| LLM produces `target_price` in JSON | Yes |
| `AgentRunner.parse_response()` extracts it | Yes |
| Stored in `agent_signals.signals JSONB` | Yes (inside signals blob) |
| Returned as dedicated field in API | **No** — embedded in signals JSONB blob only |
| PWA renders individual agent target prices | **No** |
| `position.fairValue` shown | Yes — but this is manually set, not agent-derived |

**Recommendation:** Aggregate individual agent target prices (mean, min, max) and return them as dedicated fields in the verdict/stock response. This could power a "Fair Value Range" bar in the DeepDive overlay.

---

## 5. Signal Detail (Prose): Silently Dropped

Every signal has three fields: `tag`, `strength`, and `detail`. The `detail` field is the agent's specific reasoning for emitting that signal. Current rendering:

| View | What Is Shown | What Is Dropped |
|------|--------------|----------------|
| Recommendations — collapsed | Tag name in consensus bar proportions | `strength`, `detail` |
| DeepDive — SignalTagCloud | Tag name frequency (from key_signals) | `detail` |
| DeepDive — Archive > Signals expanded | `reasoning` (overall agent summary) | Signal-level `detail` |
| Pipeline — screener step | Tags + confidence | `detail` |

**Finding:** The `detail` field (per-signal prose) never appears anywhere in the PWA. To access this level of reasoning, a user must read the overall `reasoning` summary which aggregates across all signals.

---

## 6. Backend Endpoints With No PWA View

| Endpoint | Data Available | PWA Coverage |
|----------|---------------|-------------|
| `GET /learning/pendulum` | Live pendulum reading with components | No dedicated route; only summary data via briefing |
| `GET /daily/reanalysis` | Active trigger conditions, recent verdict changes | No PWA panel |
| `GET /quant-gate/delta` | Stocks entering/leaving universe between runs | No delta UI |
| `GET /stock/{ticker}/signals` (dedicated) | Signals with `token_usage` and `latency_ms` | Not called directly by PWA |
| `POST /learning/settle` | Trigger prediction settlement | No PWA button |

---

## 7. Duplication

| Content | Shown In | Notes |
|---------|----------|-------|
| **AgentConsensusPanel** (ring + avatars) | Watchlist expanded, Recommendations expanded, StockDeepDive Agent Analysis | Appropriate reuse — each context adds depth |
| **Signal pills** (consensusTier, stability, buzz, earnings) | Recommendations collapsed, StockDeepDive SignalPills | Same data at two zoom levels — appropriate |
| **Board headline** | Recommendations collapsed (truncated), StockDeepDive HeroVerdictStrip | Same text, different truncation — fine |
| **Portfolio P&L** | Today (summary), Portfolio hero | Summary vs detail — appropriate |
| **Pendulum gauge** | Today (large), Portfolio Daily Intel (mini) | Two views of same metric — minor redundancy |
| **Action items** | Today action queue, Portfolio Daily Intel | **ACTUAL DUPLICATION** — both fetch advisor actions + briefing.topActions, merged differently |

**Verdict on duplication**: Minimal problematic duplication. The action items overlap is the only real issue.

---

## 8. Finance Terminology Without Explanation

| Term | Where Used | Explanation Available? |
|------|-----------|------------------------|
| **Piotroski F-Score** | QuantGate, DeepDive Metrics | GlossaryTooltip on QuantGate headers only |
| **Altman Z-Score** | QuantGate, DeepDive Metrics | GlossaryTooltip on QuantGate headers only |
| **ROIC** | QuantGate, DeepDive Metrics | Column header tooltip only |
| **Sharpe / Sortino Ratio** | Portfolio Performance | No explanation |
| **Alpha** | Portfolio Performance | No explanation |
| **Max Drawdown** | Portfolio Performance | No explanation |
| **Consensus Score** (-1 to +1) | Everywhere | Number shown but meaning not explained |
| **Sentiment** (-1 to +1) | Agent stances | Number shown but scale not explained |
| **Success Probability** | Watchlist, Recommendations | Ring chart but no explanation of inputs |
| **Brier Score** | Learning view | Calibration metric, unexplained |

---

## 9. Completeness Summary by View

| View | Backend Data Used | Notable Gaps |
|------|------------------|-------------|
| **Today** | briefing summary, pendulum, thesis health, action queue | `macroSignals`, `learningSummary`, `pendulum.components` not shown |
| **Portfolio > Positions** | positions, P&L, dividends, performance metrics | `dispositionRatio`, `avgWinPct`, `avgLossPct`, `expectancy` not shown |
| **Portfolio > Thesis** | thesis health, conviction trend, entry thesis, pnl, days held | `convictionTrend` numeric not rendered |
| **Portfolio > Risk** | risk snapshot, sector concentration | concentrationWarnings list not shown |
| **Portfolio > History** | closed positions, realized P&L | Complete |
| **Watchlist** | successProbability, stances, votes, price, sparkline, quant scores | `lastAnalysis`, `reasoning` not shown |
| **Recommendations** | Most fields rendered | `reasoning`, `heldPosition.reasoning`, portfolio fit sub-scores not shown |
| **DeepDive** | Very comprehensive | `advisoryOpinion.reasoning`, signal `detail`, per-agent target prices |
| **Decisions** | decisionType, reasoning, confidence | `outcome`, `settledAt` null backend-side |
| **Agents** | focus, rules, latest analysis | `philosophy` not shown |
| **QuantGate** | Ranks, scores, composite | Quant delta (entries/exits) not shown |
| **Pipeline** | Status, funnel, step timing, errors | Complete |
| **Learning** | Calibration, attribution | Pendulum components, live signals not available |

---

## 10. The IP That Isn't Coming Through

The platform produces **~30 fields of LLM prose per stock** (9 agent summaries + 8 board assessments + 8 board reasonings + CIO narrative + pre-mortem + conflict resolution). The user sees **maybe 3-4** of these on first glance, and **10-12** if they expand everything.

The adversarial layer (kill scenarios, pre-mortem, bias flags) is entirely ephemeral — computed, used internally, then discarded. This is arguably the most compelling content for a retail investor.

---

## 11. Priority Recommendations

### P0 — Store and Surface Adversarial Content (Backend Change Required)
- Persist `kill_scenarios` and `pre_mortem` in the verdicts or a new `adversarial_results` table
- Surface in DeepDive Risk panel alongside CIO pre-mortem

### P1 — Show Full Advisory Board Reasoning (Frontend Change)
- In DeepDive Agent Analysis > Advisory Board grid, add a "read more" expand per advisor showing full `reasoning` text
- Each advisor brings a different lens — this is the differentiating IP

### P1 — Surface Agent Target Prices (Backend + Frontend Change)
- Return aggregated agent `target_price` values (mean/min/max) in API
- Show as a "Fair Value Range" bar in DeepDive overlay

### P1 — Signal Detail Prose (Frontend Change)
- In DeepDive > Archive > Agent Signals, show individual signals as table: tag | strength | detail text
- Currently the "why" behind each signal tag is hidden

### P2 — Pendulum Components (Frontend Change)
- Break down fear/greed score into inputs (VIX, put/call, momentum)
- Show `sizing_multiplier` ("In this market, buy 75% of normal position size")

### P2 — Decision Settlement Display (Frontend Change)
- Show `outcome` and `settledAt` on decisions once backend populates them
- "Was this call correct?" builds user trust

### P2 — Earnings Momentum Counts (Frontend Change)
- Show raw `upwardRevisions`/`downwardRevisions` alongside the label badge
- e.g. "STRONG_UPWARD (+5/-1, 3-quarter beat streak)"

### P3 — Extend GlossaryTooltip to All Views
- Currently only on QuantGate column headers
- Add to Portfolio performance metrics, DeepDive valuation section

### P3 — Attribution Dashboard
- Show per-agent accuracy prominently, not buried in Learning view
- "Warren: 72% accurate on bullish calls"

---

*Reports written by:*
- *frontend-auditor agent → frontend-report.md*
- *backend-auditor agent → backend-report.md*
- *backend-auditor agent → gap-analysis.md (this file)*
