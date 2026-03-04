# Backend Audit Report — Investmentology
*Generated: 2026-03-04*

This report maps every API endpoint, LLM output schema, and data model in the backend, focusing on what is **available** vs what the PWA may or may not be showing.

---

## 1. API Endpoints — Complete Inventory

All routes are prefixed with `/api/invest/`.

### 1.1 Portfolio Routes (`/portfolio`)

**GET /portfolio**
Returns current open positions with P&L, performance metrics, and dividend data.

Full response shape:
```json
{
  "positions": [{
    "id": int,
    "ticker": str,
    "name": str,
    "shares": float,
    "avgCost": float,
    "currentPrice": float | null,
    "marketValue": float,
    "unrealizedPnl": float,
    "unrealizedPnlPct": float,
    "dayChange": float,
    "dayChangePct": float,
    "weight": float,
    "positionType": str,             // "core", "tactical", "income", "contrarian"
    "entryDate": str | null,
    "priceUnavailable": bool,        // true if price fetch failed
    "dividendPerShare": float,
    "dividendYield": float,
    "annualDividend": float,
    "monthlyDividend": float,
    "dividendFrequency": str,        // "monthly", "quarterly", "semi-annual", "annual", "none"
    "exDividendDate": str | null
  }],
  "totalValue": float,
  "dayPnl": float,
  "dayPnlPct": float,
  "cash": float,
  "alerts": [{
    "id": str,
    "severity": str,                // "critical", "high"
    "title": str,
    "message": str,
    "ticker": str,
    "timestamp": str,
    "acknowledged": bool
  }],
  "performance": {
    "portfolioReturnPct": float,
    "spyReturnPct": float,
    "alphaPct": float,
    "sharpeRatio": float,
    "sortinoRatio": float,
    "maxDrawdownPct": float,
    "winRate": float,
    "avgWinPct": float,
    "avgLossPct": float,
    "totalTrades": int,
    "expectancy": float,
    "dispositionRatio": float,       // Winner:loser hold time ratio
    "avgWinnerHoldDays": float,
    "avgLoserHoldDays": float,
    "measurementDays": int
  } | null,
  "dividendSummary": {
    "totalAnnual": float,
    "totalMonthly": float,
    "yield": float
  }
}
```

**GET /portfolio/alerts** — Active alerts only (stop-loss, drawdown)

**POST /portfolio/position** — Create a new position
**PUT /portfolio/position/{id}** — Update existing position
**DELETE /portfolio/position/{id}** — Close/delete position

**GET /portfolio/thesis/{ticker}** — Full thesis lifecycle detail (see section 5)
**GET /portfolio/thesis-summary** — Lightweight thesis health for all positions
**GET /portfolio/risk-snapshot** — Portfolio-level risk snapshot

---

### 1.2 Stock Routes (`/stock`)

**GET /stock/{ticker}** — Full deep-dive on a ticker

This is the richest endpoint. Full response shape:
```json
{
  "ticker": str,
  "name": str,
  "sector": str,
  "industry": str,
  "profile": {
    "sector": str,
    "industry": str,
    "businessSummary": str,         // LLM-USABLE: Full business description
    "website": str,
    "employees": int,
    "city": str,
    "country": str,
    "beta": float | null,
    "dividendYield": float | null,
    "trailingPE": float | null,
    "forwardPE": float | null,
    "priceToBook": float | null,
    "priceToSales": float | null,
    "fiftyTwoWeekHigh": float | null,
    "fiftyTwoWeekLow": float | null,
    "averageVolume": int | null,
    "analystTarget": float | null,   // Wall Street consensus target price
    "analystRecommendation": str | null,  // e.g. "buy", "hold", "underperform"
    "analystCount": int | null
  } | null,
  "fundamentals": {
    "ticker": str,
    "fetched_at": str,
    "market_cap": float,
    "operating_income": float,
    "revenue": float,
    "net_income": float,
    "total_debt": float,
    "cash": float,
    "shares_outstanding": float,
    "price": float,
    "earnings_yield": float | null,
    "roic": float | null,
    "enterprise_value": float
  } | null,
  "quantGate": {
    "combinedRank": int,
    "eyRank": int,
    "roicRank": int,
    "piotroskiScore": int,           // 0-9 Piotroski F-Score
    "altmanZScore": float | null,
    "altmanZone": str | null,        // "safe", "grey", "distress"
    "compositeScore": float | null
  } | null,
  "competence": {
    "passed": bool,
    "confidence": float | null,
    "reasoning": str,               // LLM prose: competence assessment
    "in_circle": bool | null,
    "sector_familiarity": str | null,
    "moat": str | null
  } | null,
  "verdict": {                      // Latest verdict (same as verdictHistory[0])
    "recommendation": str,          // STRONG_BUY|BUY|ACCUMULATE|HOLD|WATCHLIST|REDUCE|SELL|AVOID|DISCARD
    "confidence": float | null,
    "consensusScore": float | null, // -1.0 to +1.0
    "reasoning": str,               // LLM-GENERATED prose verdict reasoning
    "agentStances": [{              // Per-agent stances
      "name": str,                  // agent name
      "sentiment": float,           // -1.0 to +1.0
      "confidence": float,
      "key_signals": [str],         // Top 3 signal tags
      "summary": str                // LLM PROSE: agent's reasoning summary
    }],
    "riskFlags": [str],             // e.g. ["LEVERAGE_HIGH: detail"]
    "auditorOverride": bool,
    "mungerOverride": bool,
    "advisoryOpinions": [{          // 8 advisory board members' opinions
      "advisor_name": str,          // "dalio", "lynch", "munger", etc.
      "display_name": str,          // "Ray Dalio", etc.
      "vote": str,                  // APPROVE|ADJUST_UP|ADJUST_DOWN|VETO
      "confidence": float,
      "assessment": str,            // LLM PROSE: 1-sentence headline
      "key_concern": str | null,    // LLM PROSE: specific risk or null
      "key_endorsement": str | null,// LLM PROSE: specific positive or null
      "reasoning": str,             // LLM PROSE: 2-3 sentence analysis from advisor's lens
      "model": str,
      "latency_ms": int
    }] | null,
    "boardNarrative": {             // CIO synthesis (if generated)
      "headline": str,              // LLM PROSE: short headline
      "narrative": str,             // LLM PROSE: 3-4 paragraph analysis
      "risk_summary": str,          // LLM PROSE: what would make us wrong
      "pre_mortem": str,            // LLM PROSE: if this goes badly...
      "conflict_resolution": str,   // LLM PROSE: how competing views reconciled
      "verdict_adjustment": int,    // -1, 0, or +1
      "adjusted_verdict": str | null,
      "advisor_consensus": dict,    // vote count breakdown
      "model": str,
      "latency_ms": int
    } | null,
    "boardAdjustedVerdict": str | null,
    "createdAt": str
  } | null,
  "verdictHistory": [               // Last 20 verdicts (same structure as verdict)
    { ...same as verdict above... }
  ],
  "position": {                     // If held
    "id": int,
    "shares": float,
    "entryPrice": float,
    "currentPrice": float,
    "positionType": str,
    "weight": float | null,
    "stopLoss": float | null,
    "fairValue": float | null,
    "pnl": float,
    "pnlPct": float,
    "entryDate": str | null,
    "thesis": str | null            // Original buy thesis text
  } | null,
  "briefing": {                     // Plain-English position-aware synthesis
    "headline": str,                // e.g. "Keep holding — the thesis is intact"
    "situation": str,               // Portfolio position summary sentence
    "action": str,                  // What to do
    "rationale": str                // Why (agents, quant scores, analyst target)
  } | null,
  "signals": [{                     // All historical agent signals
    "agentName": str,
    "model": str,
    "signals": {                    // Raw signal JSON {signals: [...]}
      "signals": [{"tag": str, "strength": str, "detail": str}]
    },
    "confidence": float | null,
    "reasoning": str,               // LLM PROSE: agent's summary text
    "createdAt": str
  }],
  "decisions": [{                   // Decision log
    "id": str,
    "decisionType": str,
    "layer": str,
    "confidence": float | null,
    "reasoning": str,               // LLM PROSE: decision reasoning
    "createdAt": str
  }],
  "watchlist": {
    "state": str,
    "notes": str | null,
    "updated_at": str | null
  } | null,
  "buzz": {
    "buzzScore": float,             // 0-100 news/social buzz score
    "buzzLabel": str,               // "LOW", "MEDIUM", "HIGH", "VERY_HIGH"
    "headlineSentiment": float | null,  // -1.0 to +1.0 aggregate sentiment
    "articleCount": int,
    "contrarianFlag": bool          // True if low buzz + positive sentiment
  } | null,
  "earningsMomentum": {
    "score": float,
    "label": str,                   // "STRONG_UPWARD", "UPWARD", "NEUTRAL", "DECLINING", "STRONG_DECLINING"
    "upwardRevisions": int,
    "downwardRevisions": int,
    "beatStreak": int
  } | null,
  "stabilityScore": float,          // 0.33, 0.67, or 1.0
  "stabilityLabel": str,            // "STABLE", "MODERATE", "UNSTABLE", "UNKNOWN"
  "consensusTier": str | null       // "HIGH_CONVICTION", "MIXED", "CONTRARIAN"
}
```

**GET /stock/{ticker}/news** — Recent articles from yfinance
```json
{"ticker": str, "articles": [{"headline": str, "datetime": str, ...}]}
```

**GET /stock/{ticker}/signals** — Agent signals with token usage and latency
```json
{
  "ticker": str,
  "signals": [{
    "id": int,
    "agent_name": str,
    "model": str,
    "signals": {signals JSONB},
    "confidence": float | null,
    "reasoning": str,              // LLM PROSE
    "token_usage": {input: int, output: int} | null,
    "latency_ms": int | null,
    "created_at": str
  }]
}
```

**GET /stock/{ticker}/decisions** — Full decision history with signals metadata
**GET /stock/{ticker}/chart** — OHLCV price data (1w/1mo/3mo/6mo/1y/ytd)

---

### 1.3 Recommendations (`/recommendations`)

**GET /recommendations** — Buy-ready stocks (STRONG_BUY, BUY, ACCUMULATE only)

Full response shape:
```json
{
  "items": [{
    "ticker": str,
    "name": str,
    "sector": str,
    "industry": str,
    "currentPrice": float,
    "marketCap": float,
    "watchlistState": str | null,
    "verdict": str,
    "confidence": float | null,
    "consensusScore": float | null,
    "consensusTier": str | null,    // "HIGH_CONVICTION", "MIXED", "CONTRARIAN"
    "reasoning": str,               // LLM PROSE: verdict reasoning
    "agentStances": [same as above],// Per-agent stance objects
    "riskFlags": [str],
    "auditorOverride": bool,
    "mungerOverride": bool,
    "advisoryOpinions": [...],      // 8 board member opinions (see above)
    "boardNarrative": {...},        // CIO synthesis
    "boardAdjustedVerdict": str | null,
    "analysisDate": str,
    "successProbability": float | null,  // 0.0-1.0 blended score
    "changePct": float,
    "priceHistory": [{"date": str, "verdict": str, "confidence": float}],
    "stabilityScore": float | null,
    "stabilityLabel": str | null,
    "portfolioFit": {
      "score": float,
      "reasoning": str,             // Why this fits/doesn't fit portfolio
      "diversificationScore": float,
      "balanceScore": float,
      "capacityScore": float,
      "alreadyHeld": bool
    } | null,
    "dividendYield": float | null,
    "annualDividend": float | null,
    "dividendFrequency": str | null,
    "buzzScore": float | null,
    "buzzLabel": str | null,
    "headlineSentiment": float | null,
    "contrarianFlag": bool | null,
    "earningsMomentum": {
      "score": float,
      "label": str,
      "upwardRevisions": int,
      "downwardRevisions": int,
      "beatStreak": int
    } | null,
    "suggestedType": str,           // "core", "tactical", "income", "contrarian"
    "suggestedLabel": str,          // "Strong Conviction", "Core Hold", "Momentum Play", etc.
    "heldPosition": {               // Only if already held
      "positionType": str,
      "daysHeld": int,
      "pnlPct": float,
      "entryPrice": float,
      "thesisHealth": str,          // "INTACT", "UNDER_REVIEW", "CHALLENGED", "BROKEN"
      "convictionTrend": float,     // -1.0 to +1.0
      "entryThesis": str,           // Original thesis (truncated to 200 chars)
      "reasoning": str              // Thesis health assessment reasoning
    } | null
  }],
  "groupedByVerdict": {
    "STRONG_BUY": [...],
    "BUY": [...],
    "ACCUMULATE": [...]
  },
  "totalCount": int
}
```

---

### 1.4 Watchlist (`/watchlist`)

**GET /watchlist** — Stocks tagged WATCHLIST (below buy threshold)

```json
{
  "items": [{
    "ticker": str,
    "name": str,
    "sector": str,
    "state": str,
    "addedAt": str,
    "lastAnalysis": str,
    "priceAtAdd": float,
    "currentPrice": float,
    "changePct": float,
    "marketCap": float,
    "verdict": {
      "recommendation": str,
      "confidence": float | null,
      "consensusScore": float | null,
      "reasoning": str,             // LLM PROSE
      "agentStances": [...],
      "riskFlags": [str],
      "verdictDate": str
    },
    "successProbability": float | null,
    "priceHistory": [...]
  }],
  "groupedByState": {sector: [...]}
}
```

---

### 1.5 Decisions (`/decisions`)

**GET /decisions?ticker=&type=&page=&pageSize=** — Paginated decision log

```json
{
  "decisions": [{
    "id": str,
    "ticker": str,
    "decisionType": str,    // SCREEN, COMPETENCE_PASS/FAIL, AGENT_ANALYSIS, BUY, SELL, etc.
    "confidence": float,
    "reasoning": str,       // LLM PROSE: full decision reasoning text
    "createdAt": str,
    "layer": str,           // which pipeline layer
    "outcome": null,        // not yet used
    "settledAt": null
  }],
  "total": int,
  "page": int,
  "pageSize": int
}
```

---

### 1.6 Quant Gate (`/quant-gate`)

**GET /quant-gate/latest** — Latest screener run results
**GET /quant-gate/delta** — Additions/removals vs prior run
**GET /quant-gate/status** — Background screener progress
**POST /quant-gate/run** — Trigger new screener run

Latest run response includes per-ticker:
- ticker, name, sector, marketCap
- roicRank, eyRank, combinedRank (Magic Formula ranks)
- roic (float), earningsYield (float)
- piotroskiScore (0-9), altmanZScore, altmanZone
- compositeScore (weighted formula)
- verdict, verdictConfidence, verdictDate (if analyzed)

---

### 1.7 Pipeline (`/pipeline`)

**GET /pipeline/status** — Active cycle status
**GET /pipeline/tickers** — Per-ticker progress
**GET /pipeline/ticker/{ticker}** — Detailed step breakdown with screener votes
**GET /pipeline/funnel** — Funnel visualization (data_fetch→pre_filter→screeners→gate→analysis counts)
**GET /pipeline/health** — Per-step error rates, avg/max timing, recent errors

---

### 1.8 Daily Briefing (`/daily`)

**GET /daily/briefing** — Full daily advisory briefing

```json
{
  "date": str,
  "marketOverview": {
    "pendulum": {
      "score": int,               // 0-100 fear/greed
      "label": str,               // "extreme_fear", "fear", "neutral", "greed", "extreme_greed"
      "sizing_multiplier": float, // e.g. 0.75 in greed
      "components": {
        "vix": int,               // component score
        "put_call_ratio": int,
        "spy_momentum": int,
        ...
      }
    },
    "macroSignals": [str]         // Human-readable regime observations
  },
  "portfolioSnapshot": {
    "positions": [...],           // Simplified position list
    "totalValue": float,
    "positionCount": int,
    "sectorExposure": {sector: pct},
    "riskCategoryExposure": {"growth": pct, "defensive": pct, "cyclical": pct, ...},
    "totalUnrealizedPnl": float
  },
  "newRecommendations": [{        // Recent (7-day) STRONG_BUY/BUY/ACCUMULATE
    "ticker": str,
    "name": str,
    "verdict": str,
    "confidence": float,
    "successProbability": float | null,
    "sector": str,
    "currentPrice": float,
    "reasoning": str              // LLM PROSE verdict reasoning
  }],
  "positionAlerts": [{
    "ticker": str,
    "severity": str,              // "critical", "high", "medium", "low"
    "type": str,                  // "stop_loss_breach", "drawdown", "above_fair_value", "large_gain"
    "message": str
  }],
  "riskSummary": {
    "overallRiskLevel": str,      // "low", "moderate", "elevated", "high"
    "concentrationWarnings": [str],
    "drawdownAlerts": [str],
    "sectorImbalances": [str]
  },
  "actionItems": [{
    "priority": int,
    "category": str,              // "buy", "sell", "review", "rebalance", "watch"
    "ticker": str | null,
    "action": str,
    "reasoning": str
  }],
  "learningSummary": {
    "pending_predictions": int,
    "settled_predictions": int,
    "calibration": {
      "total_settled": int,
      "ece": float,               // Expected Calibration Error
      "brier": float              // Brier score
    }
  },
  "performance": {
    "portfolioReturnPct": float,
    "spyReturnPct": float,
    "alphaPct": float,
    "sharpeRatio": float,
    "maxDrawdownPct": float,
    "dispositionRatio": float,
    "measurementDays": int
  } | null
}
```

**GET /daily/briefing/summary** — Condensed version (key metrics only)
**GET /daily/reanalysis** — Active trigger conditions and recent verdict changes

---

### 1.9 Learning/Calibration (`/learning`)

**GET /learning/calibration** — Calibration buckets, Brier score
**GET /learning/agents** — Per-agent signal count, avg confidence, avg latency
**POST /learning/settle** — Trigger prediction settlement
**GET /learning/attribution** — Full agent performance attribution report

Attribution includes:
- Per-agent: total calls, accuracy, bullish/bearish accuracy splits
- Recommended weight adjustments
- Top/worst signal tags (agent × tag × accuracy)
- Override outcome analysis (auditor/munger overrides — were they correct?)

**GET /learning/buzz/{ticker}** — Real-time buzz score for any ticker
**GET /learning/earnings/{ticker}** — Live earnings revision momentum
**GET /learning/pendulum** — Live pendulum reading

---

### 1.10 Other Routes

**GET /analyse/{ticker}** — On-demand SSE stream analysis
**POST /analyse/{ticker}** — Trigger analysis (SSE events)
**GET /system/health** — API health check
**GET /system/config** — Pipeline config
**GET /backtesting/...** — Backtesting results
**GET /pipeline/...** — Pipeline status (see 1.7)

---

## 2. LLM Agent Output Schema

### 2.1 Standard Agent Output (All 8 Investment Agents)

All primary agents (Warren, Auditor, Klarman, Soros, Druckenmiller, Dalio, Simons, Lynch) use `_STANDARD_OUTPUT`:

```json
{
  "signals": [
    {"tag": "TAG_NAME", "strength": "strong|moderate|weak", "detail": "Explanation of why this signal was emitted"}
  ],
  "confidence": 0.65,
  "target_price": 145.50,
  "summary": "2-4 sentence prose assessment of the investment thesis"
}
```

**Fields:**
- `signals[].tag` — One of ~102 `SignalTag` enum values (see Section 4)
- `signals[].strength` — `"strong"`, `"moderate"`, or `"weak"`
- `signals[].detail` — **LLM PROSE**: Explanation text (stored in DB, returned in API)
- `confidence` — Float 0.0-1.0 (Simons capped at 0.15 without technical data)
- `target_price` — Fair value estimate (float or null)
- `summary` — **LLM PROSE**: The agent's overall summary reasoning

### 2.2 Data Analyst (Validator) Output

```json
{
  "status": "VALIDATED|SUSPICIOUS|REJECTED",
  "issues": [
    {"field": "revenue", "detail": "Revenue returned as $0 for established company"}
  ],
  "confidence": 0.85,
  "summary": "Brief explanation of validation result"
}
```

### 2.3 Advisory Board Member Output (8 members, per pair call)

Each of 8 board members (Dalio, Lynch, Druckenmiller, Klarman, Munger, Williams, Soros, Simons) produces:

```json
{
  "vote": "APPROVE|ADJUST_UP|ADJUST_DOWN|VETO",
  "confidence": 0.75,
  "assessment": "One sentence headline assessment",          // LLM PROSE
  "key_concern": "Specific risk identified or null",         // LLM PROSE
  "key_endorsement": "Specific positive factor or null",     // LLM PROSE
  "reasoning": "2-3 sentence analysis from this advisor's unique investment philosophy lens"  // LLM PROSE
}
```

These are stored in `invest.verdicts.advisory_opinions` as JSONB.

### 2.4 CIO Narrative (BoardNarrative)

Currently not always populated (depends on implementation path). Schema:
```json
{
  "headline": str,              // LLM PROSE: short buy/sell headline
  "narrative": str,             // LLM PROSE: 3-4 paragraphs
  "risk_summary": str,          // LLM PROSE: bear case
  "pre_mortem": str,            // LLM PROSE: failure scenario
  "conflict_resolution": str,   // LLM PROSE: how disagreements resolved
  "verdict_adjustment": int,    // -1, 0, +1
  "adjusted_verdict": str | null
}
```

Stored in `invest.verdicts.board_narrative` as JSONB.

### 2.5 Adversarial (Munger Orchestrator) Output

Not directly stored per-se, but its verdict influences the final verdict:

```python
AdversarialResult:
  verdict: MungerVerdict  # PROCEED | CAUTION | VETO
  bias_flags: [BiasResult]  # 20 cognitive biases checked via keyword matching
  kill_scenarios: [KillScenario]  # LLM: 5 realistic failure scenarios
  premortem: PreMortemResult | None  # LLM: failure narrative + key risks
  reasoning: str  # summary text
```

**KillScenario fields (LLM-generated):**
- `scenario`: str — specific failure description
- `likelihood`: "low" | "medium" | "high"
- `impact`: "moderate" | "severe" | "fatal"
- `timeframe`: "1-2 years" | "3-5 years" | "5+ years"

**PreMortemResult fields (LLM-generated):**
- `narrative`: str — "It's 2028, we lost 50% on AAPL because..."
- `key_risks`: [str] — 3-5 specific risks that led to the loss
- `probability_estimate`: "unlikely" | "possible" | "plausible" | "likely"
- `base_rates`: str — Historical sector success rates used as context

### 2.6 Debate Agent Output

When agents disagree (<75% consensus), a debate round fires using the standard agent output schema. The debate agent is routed through the `remote-debate-claude` provider.

---

## 3. Data Flow — What's Produced at Each Layer

### Layer 1: Quant Gate (Greenblatt Magic Formula)
- **Computed, not LLM**: ROIC rank, Earnings Yield rank, Combined rank, Piotroski F-Score, Altman Z-Score
- Stored in: `invest.quant_gate_results`

### Layer 1.5: Pre-filter
- Binary rule-based pass/fail with named rule failures
- Stored in: `invest.pipeline_data_cache` as `pre_filter_result`

### Layer 2: Competence Filter
- **LLM-generated**: In-circle assessment, sector familiarity, moat text
- Stored in: `invest.decisions` (type=COMPETENCE_PASS/FAIL) with signals JSONB

### Layer 3: Multi-Agent Analysis (9 agents)
- **LLM-generated per agent**: signals[], confidence, target_price, summary
- Stored in: `invest.agent_signals` (one row per agent per ticker per cycle)
- Convergence check: `should_debate()` checks if <75% same sentiment

### Layer 4: Adversarial (Munger)
- **LLM-generated**: kill scenarios, pre-mortem narrative, bias flags
- **NOT stored separately** — its verdict (PROCEED/CAUTION/VETO) influences final verdict only
- munger_override flag stored in `invest.verdicts`

### Layer 5: Timing & Sizing (Pendulum)
- **Not LLM**: Mathematical pendulum score from VIX + market data
- sizing_multiplier affects position sizing recommendations

### Layer 5.5: Advisory Board (8 members)
- **LLM-generated per member**: vote, assessment, key_concern, key_endorsement, reasoning
- Stored in: `invest.verdicts.advisory_opinions` (JSONB array of 8 opinions)
- Board narrative: `invest.verdicts.board_narrative`
- Board-adjusted verdict: `invest.verdicts.board_adjusted_verdict`

### Layer 6: Verdict Synthesizer (Python, deterministic)
- Computed from agent stances: weighted_sentiment, weighted_confidence
- AgentStance distilled: name, sentiment (-1.0 to +1.0), confidence, key_signals (top 3), summary (prose)
- Stored in: `invest.verdicts`

---

## 4. Signal Tag Taxonomy

102 signal tags across 6 categories:

**Fundamental (24 tags):** UNDERVALUED, OVERVALUED, FAIRLY_VALUED, DEEP_VALUE, MOAT_WIDENING, MOAT_STABLE, MOAT_NARROWING, NO_MOAT, EARNINGS_QUALITY_HIGH/LOW, REVENUE_ACCELERATING/DECELERATING, MARGIN_EXPANDING/COMPRESSING, BALANCE_SHEET_STRONG/WEAK, DIVIDEND_GROWING, BUYBACK_ACTIVE, MANAGEMENT_ALIGNED/MISALIGNED, ROIC_IMPROVING/DECLINING, CAPITAL_ALLOCATION_EXCELLENT/POOR

**Macro/Cycle (26 tags):** REGIME_BULL/BEAR/NEUTRAL/TRANSITION, SECTOR_ROTATION_INTO/OUT, CREDIT_TIGHTENING/EASING, RATE_RISING/FALLING, INFLATION_HIGH/LOW, DOLLAR_STRONG/WEAK, GEOPOLITICAL_RISK, SUPPLY_CHAIN_DISRUPTION, FISCAL_STIMULUS/CONTRACTION, LIQUIDITY_ABUNDANT/TIGHT, REFLEXIVITY_DETECTED, REGIME_TRANSITION_UP/DOWN, REGIME_CHOPPY, CYCLE_EARLY/MID/LATE/CONTRACTION, RATES_STABLE, MACRO_CATALYST

**Technical/Timing (22 tags):** TREND_UPTREND/DOWNTREND/SIDEWAYS, MOMENTUM_STRONG/WEAK/DIVERGENCE, BREAKOUT/BREAKDOWN_CONFIRMED, SUPPORT/RESISTANCE_NEAR, VOLUME_SURGE/DRY/CLIMAX, RSI_OVERSOLD/OVERBOUGHT, GOLDEN/DEATH_CROSS, RELATIVE_STRENGTH_HIGH/LOW, TREND_REVERSAL_BULLISH/BEARISH, PATTERN_BULL_FLAG/BASE_FORMING

**Risk/Portfolio (19 tags):** CONCENTRATION, CORRELATION_HIGH/LOW, LIQUIDITY_LOW/OK, DRAWDOWN_RISK, ACCOUNTING_RED_FLAG, GOVERNANCE_CONCERN, LEVERAGE_HIGH/OK, VOLATILITY_HIGH/LOW, SECTOR_OVERWEIGHT/UNDERWEIGHT, RISK_LITIGATION/KEY_PERSON/CUSTOMER_CONCENTRATION, PORTFOLIO_OVER_EXPOSED/UNDERWEIGHT_CASH

**Special Situation (17 tags):** SPINOFF_ANNOUNCED/SELLING_PEAK, MERGER_TARGET, INSIDER_CLUSTER_BUY/SELL, ACTIVIST_INVOLVED, MANAGEMENT_CHANGE, REGULATORY_CHANGE, PATENT_CATALYST, EARNINGS_SURPRISE, GUIDANCE_RAISED/LOWERED, POST_BANKRUPTCY, RIGHTS_OFFERING, INDEX_ADD/DROP, CONGRESSIONAL_TRADE

**Decision/Action (23 tags):** BUY_NEW, BUY_ADD, TRIM, SELL_FULL/PARTIAL, HOLD/HOLD_STRONG, WATCHLIST_ADD/REMOVE/PROMOTE, REJECT/REJECT_HARD, CONFLICT_FLAG, REVIEW_REQUIRED, MUNGER_PROCEED/CAUTION/VETO, NO_ACTION, MISSED, REASON_THESIS_BROKEN/STOP_LOSS/TARGET_REACHED/OPPORTUNITY_COST/REGIME_SHIFT/REBALANCE/TAX_LOSS/POSITION_LIMIT, FORCED_SELLING_OVERRIDE

---

## 5. Database Schema — Key Tables

### invest.verdicts
```sql
id, ticker, verdict, confidence, consensus_score,
reasoning TEXT,                  -- LLM PROSE (synthesized from agent summaries)
agent_stances JSONB,             -- [{name, sentiment, confidence, key_signals, summary}]
risk_flags JSONB,                -- [str]
auditor_override BOOLEAN,
munger_override BOOLEAN,
advisory_opinions JSONB,         -- [{advisor_name, display_name, vote, confidence, assessment, key_concern, key_endorsement, reasoning}]
board_narrative JSONB,           -- {headline, narrative, risk_summary, pre_mortem, conflict_resolution}
board_adjusted_verdict TEXT,
-- From migration 009:
market_snapshot_id INT,
position_type TEXT,
thesis_health TEXT,
was_gated BOOLEAN,
gating_reason TEXT,
created_at TIMESTAMPTZ
```

### invest.agent_signals
```sql
id, ticker, agent_name, model,
signals JSONB,                   -- {signals: [{tag, strength, detail}]}
confidence NUMERIC(4,3),
reasoning TEXT,                  -- LLM PROSE (= summary field from LLM JSON)
token_usage JSONB,               -- {input: int, output: int}
latency_ms INTEGER,
run_id INTEGER,
created_at TIMESTAMPTZ
```

### invest.decisions
```sql
id, ticker, decision_type (enum), layer_source,
confidence NUMERIC(4,3),
reasoning TEXT,                  -- LLM PROSE
signals JSONB,                   -- competence signals, adversarial result, etc.
metadata JSONB,
created_at TIMESTAMPTZ
```

### invest.portfolio_positions
```sql
id, ticker, entry_date, entry_price, current_price, shares, position_type,
weight, stop_loss, fair_value_estimate,
thesis TEXT,                     -- User-entered or LLM-generated buy thesis
entry_thesis TEXT,               -- Immutable copy of thesis at entry
thesis_jsonb JSONB,              -- Structured thesis
thesis_type TEXT,                -- "growth", "income", "value", "momentum"
investment_horizon TEXT,
thesis_health TEXT,              -- "INTACT", "UNDER_REVIEW", "CHALLENGED", "BROKEN"
thesis_state TEXT,
is_closed BOOLEAN
```

### invest.thesis_events
```sql
id, ticker, event_type,          -- ENTRY, REAFFIRM, CHALLENGE, BREAK, CLOSE, UPDATE
thesis_text TEXT,                -- LLM PROSE: thesis narrative
verdict_at_time TEXT, confidence_at_time, price_at_time,
market_regime TEXT,
agent_stances JSONB,             -- Per-agent snapshot at this event
created_at TIMESTAMPTZ
```

---

## 6. LLM Prose Fields — Complete Inventory

These are all text fields in the system that contain **LLM-generated prose** (not computed or rule-based):

| Field | Location | Content |
|-------|----------|---------|
| `agent_signals.reasoning` | DB / API signals[] | Agent's summary assessment (2-4 sentences) |
| `agent_signals.signals[].detail` | DB / API signals[] | Per-signal explanation for each tag |
| `verdicts.reasoning` | DB / API verdict.reasoning | Synthesized verdict narrative |
| `verdicts.agent_stances[].summary` | DB / API agentStances[].summary | Per-agent stance summary |
| `verdicts.advisory_opinions[].assessment` | DB / API advisoryOpinions[].assessment | 1-sentence board member headline |
| `verdicts.advisory_opinions[].key_concern` | DB / API advisoryOpinions[].key_concern | Specific risk text |
| `verdicts.advisory_opinions[].key_endorsement` | DB / API advisoryOpinions[].key_endorsement | Specific positive text |
| `verdicts.advisory_opinions[].reasoning` | DB / API advisoryOpinions[].reasoning | 2-3 sentence advisor analysis |
| `verdicts.board_narrative.headline` | DB / API boardNarrative.headline | CIO synthesis headline |
| `verdicts.board_narrative.narrative` | DB / API boardNarrative.narrative | 3-4 paragraph investment thesis |
| `verdicts.board_narrative.risk_summary` | DB / API boardNarrative.risk_summary | Bear case prose |
| `verdicts.board_narrative.pre_mortem` | DB / API boardNarrative.pre_mortem | Failure scenario prose |
| `verdicts.board_narrative.conflict_resolution` | DB / API boardNarrative.conflict_resolution | How advisors disagreed |
| `decisions.reasoning` | DB / API decisions[].reasoning | Per-layer decision text |
| `thesis_events.thesis_text` | DB / thesis API | Thesis narrative text |
| `premortem.narrative` | Adversarial (ephemeral) | "It's 2028, we lost 50%..." |
| `premortem.key_risks[]` | Adversarial (ephemeral) | Risk list from pre-mortem |
| `kill_scenarios[].scenario` | Adversarial (ephemeral) | Failure description |
| `portfolio_positions.thesis` | DB / stock API position.thesis | Buy thesis text |

---

## 7. Data Available at Backend But Potentially Underutilized in PWA

### 7.1 High-Value LLM Content Not Prominently Displayed

1. **Advisory Board Opinions (8 members)** — `advisoryOpinions[]`
   - Each has: `assessment` (1-sentence headline), `key_concern`, `key_endorsement`, `reasoning` (2-3 sentences)
   - 8 distinct investor philosophies (Dalio, Lynch, Druckenmiller, Klarman, Munger, Williams, Soros, Simons)
   - The board also includes vote counts (APPROVE/ADJUST_UP/ADJUST_DOWN/VETO)
   - Vote outcome: was the verdict board-adjusted? (`boardAdjustedVerdict`)

2. **BoardNarrative (CIO Synthesis)** — `boardNarrative`
   - Contains: `headline`, `narrative` (3-4 paragraphs), `risk_summary` (bear case), `pre_mortem`, `conflict_resolution`
   - These are the richest LLM-generated insights in the entire system

3. **Per-Agent Signal Details** — `signals[].detail`
   - Every signal has a prose explanation. Currently signals are often shown as just tag names and strengths
   - The `detail` field on each signal is the agent's actual reasoning for that specific signal

4. **Adversarial Analysis** — Only the final verdict flags are surfaced
   - `kill_scenarios` (5 failure scenarios with likelihood/impact/timeframe) are NOT stored persistently
   - `premortem.narrative` (full failure narrative) is NOT stored persistently
   - Only `mungerOverride: bool` makes it to the API — the content is lost

5. **Agent Target Prices** — `target_price` from agent output
   - Each agent optionally provides a fair value estimate
   - These individual estimates are NOT returned via the API, only aggregated
   - Only `position.fairValue` (manually set) is shown

6. **Token Usage and Latency** — `signals.token_usage`, `signals.latency_ms`
   - Available in `/stock/{ticker}/signals` endpoint
   - Useful for pipeline health/cost visibility

7. **Calibration and Attribution Data**
   - `/learning/attribution` returns per-agent accuracy, bullish/bearish splits, recommended weight adjustments
   - This is substantive content that could build user trust

### 7.2 Numerical Scores Produced but Possibly Underused

1. **successProbability** — Blended 0.0-1.0 score (35% confidence + 25% consensus + 20% alignment + 20% risk-adjusted)
2. **stabilityScore** — Verdict flip rate (1.0=STABLE, 0.67=MODERATE, 0.33=UNSTABLE)
3. **consensusTier** — HIGH_CONVICTION / MIXED / CONTRARIAN categorization
4. **convictionTrend** — Numeric trend in agent conviction over time
5. **buzzscore** — 0-100 news/social attention score
6. **headlineSentiment** — -1.0 to +1.0 aggregate news sentiment
7. **earningsMomentum.score** — Numeric earnings revision momentum score
8. **portfolioFit.score** — How well the stock fits current portfolio (diversification, balance, capacity)
9. **pendulum.sizing_multiplier** — Concrete sizing adjustment factor (e.g. 0.75 in greed)
10. **performance.dispositionRatio** — Winner-to-loser hold time ratio (>1.5 = disposition effect)

### 7.3 Structured Data Available But Potentially Not Shown

1. **priceHistory[]** on recommendations/watchlist — 10-point verdict history for sparklines
2. **verdictHistory[]** on stock detail — Last 20 verdicts with full data
3. **verdict_diffs** in thesis API — When/why the verdict changed, gating events
4. **competence.in_circle / sector_familiarity / moat** — L2 competence detail
5. **pnl_pct on positions** — Day-over-day tracking (from fundamentals cache)
6. **portfolio risk snapshot** — sector_concentration, avg_thesis_health_score, risk_level
7. **Dividend data detail** — `div_growth_5y`, `last_div_amount`, `last_div_date`, `payout_ratio`
8. **Quant gate delta** — Which stocks entered/left the universe between runs
9. **agent_disagreements table** — Not surfaced via API at all
10. **pipeline_data_cache** — Pre-filter rejection reasons, screener vote detail
11. **market_snapshots table** — Historical SPY/VIX/yield data stored but no dedicated API route

---

## 8. Per-Agent Data Details

| Agent | Role | Weight | Key Output Fields | What It Uniquely Produces |
|-------|------|--------|-------------------|---------------------------|
| **Warren** (Claude) | Primary 0.18 | summary, signals (fundamental tags), target_price | Intrinsic value, moat quality, earnings quality |
| **Auditor** (Claude) | Primary 0.14 | summary, signals (risk tags), target_price | Risk flags, portfolio fit, governance concerns |
| **Klarman** (Claude) | Primary 0.14 | summary, signals (value+risk), target_price | Margin of safety, downside scenarios |
| **Soros** (Gemini) | Primary 0.14 | summary, signals (macro tags), target_price | Reflexivity, regime analysis, credit cycles |
| **Druckenmiller** (Gemini) | Primary 0.12 | summary, signals (technical+macro), target_price | Risk/reward asymmetry, catalysts, sizing |
| **Dalio** (Gemini) | Primary 0.12 | summary, signals (macro tags), target_price | All-weather analysis, debt cycles |
| **Simons** (Groq) | Scout 0.08 | summary, signals (technical tags), target_price | Technical indicators, momentum (conf capped 0.15 without tech data) |
| **Lynch** (DeepSeek) | Scout 0.08 | summary, signals (fundamental+growth), target_price | PEG ratio, company category classification |
| **Data Analyst** (Gemini) | Validator 0.0 | status (VALIDATED/SUSPICIOUS/REJECTED), issues[], summary | Data quality gate, not investment signal |

**Screener agents** (FINANCIAL_HEALTH, VALUATION, GROWTH_MOMENTUM, QUALITY_POSITION) — run in Phase 1 gate:
- Produce pass/reject signals with details
- Visible in `/pipeline/ticker/{ticker}/screeners`

---

## 9. Adversarial Layer Detail

The Munger adversarial check is the most content-rich layer that is **not persistently stored**:

**What it produces:**
1. **20 cognitive bias checks** (keyword-based) on agent reasoning — each with `is_flagged`, `detail`
2. **5 Kill Scenarios** (LLM, DeepSeek) — scenario text, likelihood, impact, timeframe
3. **1 Pre-Mortem** (LLM, DeepSeek) — narrative (full failure story), key_risks[], probability_estimate
4. **Overall verdict** — PROCEED, CAUTION, or VETO

**What gets stored:**
- Only `munger_override: bool` in `invest.verdicts`
- The full adversarial content (kill scenarios, pre-mortem narrative, bias flags) is **ephemeral**
- The verdict `reasoning` field includes a truncated summary like "3 total kill scenarios; Pre-mortem: plausible"

**Implication**: The richest adversarial content (failure narratives, kill scenarios with timeframes) is produced but not stored or shown in the PWA. This is a significant gap.

---

## 10. Summary of Key Gaps

1. **Advisory board opinions are rich but buried** — 8 advisors produce assessment/key_concern/key_endorsement/reasoning, plus board narrative with pre-mortem, but the PWA may not display all this content prominently

2. **Adversarial content is ephemeral** — kill_scenarios and premortem narrative are not stored persistently; only the boolean override flag survives

3. **Individual agent target prices not returned** — The API doesn't aggregate or return individual agent fair value estimates (only `position.fairValue` which is manually set)

4. **Signal details (prose)** — The `detail` field on each signal contains the agent's specific reasoning for that tag, but UIs often only show the tag name

5. **Agent stance summaries** — Each `agentStances[].summary` is the agent's prose reasoning; this is separate from the synthesized verdict.reasoning and contains richer per-agent perspective

6. **Dividend growth 5-year** — Computed (`div_growth_5y`) but may not be displayed

7. **Earnings momentum components** — `upwardRevisions`, `downwardRevisions`, `beatStreak` are useful for timing

8. **Pipeline health/cost** — `token_usage` per agent call and `latency_ms` are stored but likely not shown in PWA

9. **Attribution/learning data** — Per-agent accuracy, weight recommendations, signal performance available at `/learning/attribution` but likely not a visible PWA screen
