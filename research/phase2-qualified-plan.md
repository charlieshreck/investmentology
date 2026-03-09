# Haute-Banque Phase 2: Qualified Implementation Plan

*Author: Synthesis Agent (Claude Sonnet 4.6)*
*Date: 2026-03-09*
*Sources: Deep Review Synthesis + Devil's Advocate Challenge + Practitioner Validation + Technical Feasibility*

---

## Executive Summary

This plan charts the next 8–10 weeks of Investmentology development using a **fix, measure, then build** philosophy. Three validation teams challenged the original 30-item roadmap: a devil's advocate (challenging every assumption), a senior portfolio manager (applying practitioner judgment), and a senior engineer (verifying technical feasibility in the actual codebase). The result is a leaner, correctly-sequenced plan that aggressively cuts overengineered features while elevating the items that genuinely change decision quality. Phase 0 fixes five confirmed mathematical bugs that are degrading every pipeline run. Phase 1 establishes the measurement baseline and makes the analytical foundation trustworthy. Phase 2 builds the decision-support layer that a practitioner actually uses. Phase 3 holds only the items that survived rigorous validation. This is a sophisticated retail investor's decision-support tool — not a hedge fund — and the plan is scoped accordingly.

---

## Validation Summary

### What Was Challenged

The devil's advocate identified that "CRITICAL" labels on math bugs were asserted, not measured — no before/after comparison has been run to confirm that fixing the Greenblatt ordinal bug actually changes which stocks make the watchlist. The thesis monitoring priority was challenged: it is a human behavioral problem that software only partially solves, and it is premature before the paper portfolio has active positions. The six deep reviews were noted as suspiciously convergent — all produced by AI agents sharing training data — and the missing perspective was a practitioner who had watched real investment systems fail.

### What Survived Validation

- **Fix the math bugs first**: All three validators agree. Small effort, clear upside, no downside.
- **Sell-side verdict asymmetry**: 30-minute fix, confirmed in the code. Do it immediately.
- **Macro regime pre-classifier**: Reduces 9 redundant macro assessments, shares factual context (not opinions). Low risk, confirmed in the pipeline architecture.
- **Simons redesign**: All validators agree the current RSI/MACD persona is wrong and adds noise.
- **Thesis monitoring with forced entry**: Survived with one critical addition — criteria must be forced at buy time, not optional.
- **Earnings calendar with sizing guidance**: Elevated from Phase 2 to Phase 1 by the practitioner. The most common retail mistake (adding before earnings) is preventable.
- **Sector heatmap and correlation (core C3)**: Survived as the correct risk tool for a 10-20 position portfolio. Full C3 (Black-Litterman, optimization) cut.
- **Howard Marks as API agent**: Survived the challenge but with provider changed. Cannot be Claude CLI (pipeline timing risk). Must be API (DeepSeek or OpenRouter).
- **Beneish M-Score as binary exclusion filter**: Survived but blocked-by gross_profit data availability.
- **Monday morning briefing in narrative format**: Elevated from Phase 2 to high priority by the practitioner.

### What Was Cut

| Item | Reason |
|------|--------|
| Black-Litterman portfolio optimization | Overkill for 10–20 positions. Simple conviction weighting achieves the same outcome without false precision. |
| Company Knowledge Graph (Neo4j) | Requires institutional data maintenance. LLM extraction from 10-K is expensive and unreliable at this scale. |
| Congressional trading monitoring (Quiver Quantitative) | 20 calls/day free tier is insufficient for 100-stock pipeline. Signal already priced in by HFT. |
| VaR / CVaR | Wrong risk tool for a 10–20 position retail portfolio. Replace with sector limits + stress scenarios. |
| VectorBT backtesting | Survivorship bias + look-ahead bias in yfinance make backtesting misleading until point-in-time data is available. |
| empyrical + pyfolio tear sheets | No track record to analyze yet. Build after 6+ months of settled predictions. |
| Position lifecycle staging (Starter/Building/Full/Trimming) | Valuable but premature before calibration data exists. Move to Phase 3. |
| Industry lifecycle S-curve classification | Agents already implicitly assess this. Formalizing it creates documentation overhead without clear output improvement. |
| Benchmark-relative framing (full) | Partial version (vs. SPY in decision journal) retained. Full implementation deferred. |
| OctagonAI MCP (as Phase 1 priority) | Low star count (103), architectural mismatch (client-side MCP vs. server-side pipeline), unreliable availability. Deferred to Phase 3. |

### What Was Resequenced

- **Earnings calendar**: Phase 2 → Phase 1 (practitioner: prevents the most common retail mistake)
- **Sector heatmap / correlation**: Phase 3 → Phase 2 (the real portfolio risk tool at this scale)
- **Risk management**: Phase 3 → moved forward, but scoped to sector limits + stress scenarios, not VaR
- **Monday briefing**: Phase 2 → Phase 1 (practitioner: if nobody reads the output, the pipeline is wasted)
- **Howard Marks agent**: Phase 1 with corrected provider (API, not CLI)

---

## Success Metrics

Clear, measurable criteria for each phase. Without these, every improvement looks equally justified.

### Phase 0 Success Criteria
- All five bugs confirmed fixed by passing new regression tests (added as part of each fix)
- Test for Piotroski normalization (`test_without_prior_year_normalizes_to_4`) updated to reflect correct behavior (result capped at ~0.5, not inflated to 1.0)
- Altman Z'' sector routing confirmed: tech stocks produce Z'' scores, industrials produce Z-original scores

### Phase 1 Success Criteria
- Overnight pipeline completes within 690-minute window (02:00 UTC → 13:30 UTC) on ≥ 90% of runs
- Macro regime pre-classifier produces a `MacroRegimeResult` on every pipeline cycle
- Simons agent abstains (returns NEUTRAL/WATCHLIST) on ≥ 30% of stocks where momentum is statistically unclear (confirmation that it's no longer generating noise signals)
- Earnings calendar surfaces days-to-earnings for all held positions and watchlist stocks
- Monday briefing is in narrative format with thesis health leading

### Phase 2 Success Criteria
- Every new BUY decision has at least one quantifiable and one qualitative invalidation criterion recorded at entry (enforced by UI)
- Sector concentration dashboard shows sector weights for all portfolio holdings
- Pairwise correlation matrix displays for held positions
- Pipeline generates a thesis health alert within one cycle of an invalidation criterion being breached
- Howard Marks agent produces a verdict on ≥ 80% of analyzed stocks (confirming API reliability)

### Phase 1–2 Combined: 60-Day Measurement Baseline
After Phase 1 and Phase 2 are deployed, run the pipeline for 60 days and measure:
- Overnight success rate (target: ≥ 90%)
- Agent agreement rate (pairwise correlation across 50+ stock analyses — if Warren and Klarman correlate > 0.85, the ensemble is not independent)
- Top-100 quant gate stability (week-over-week composition overlap — target: 60–70% stable)
- Paper portfolio vs. SPY (6-month forward-looking — log this baseline now)

### Phase 3 Gate
Phase 3 work should not begin until the 60-day measurement baseline is complete and the pipeline is demonstrably stable. If the measurement reveals agent correlation > 0.85 or overnight failure rate > 15%, architectural changes take priority over Phase 3 features.

---

## Phase 0: Bug Fixes (Day 1–2)

All five bugs confirmed in the code by the technical reviewer. Fix these before any other work.

### Fix 1 — Greenblatt Ordinal Rank

**File**: `src/investmentology/quant_gate/screener.py:313–314`
**What's broken**: `gr.combined_rank` (range: 2 to 2N) is passed where an ordinal position (1 to N) is expected. Roughly 50% of the universe — all stocks with `combined_rank > total_ranked` — score 0.0 on the 40%-weighted Greenblatt component.
**The fix**:
```python
# Change the loop enumeration:
for ordinal, gr in enumerate(top_ranked, start=1):
    score = composite_score(
        greenblatt_rank=ordinal,   # 1 = best, N = worst
        total_ranked=len(top_ranked),
        ...
    )
```
**Risk**: LOW. No DB schema change. Composite scores will change (expected and correct).
**Test to add**: `test_composite_score_uses_ordinal_not_combined_rank()` — simulate 500 stocks where `combined_rank > total_ranked` and verify scores > 0.

---

### Fix 2 — Momentum Skip-Month Formula

**File**: `src/investmentology/quant_gate/screener.py:118–122`
**What's broken**: `ret_12m - ret_1m` is not mathematically equivalent to J-T skip-month return due to compounding. Minimum data guard (`< 30`) is far too permissive — IPOs with < 10 months data should not receive momentum scores.
**The fix**:
```python
if len(series) < 252:
    continue
momentum_raw[ticker] = float((series.iloc[-22] / series.iloc[-252]) - 1)
```
**Note from tech review**: The threshold should be `< 252` (not 220) to avoid `series.iloc[-252]` index errors when fewer than 252 rows are available.
**Risk**: LOW. Fewer tickers will receive momentum scores (those with < 1 year of data). This is the correct behavior.

---

### Fix 3 — Piotroski Without-Prior Normalization

**File**: `src/investmentology/quant_gate/composite.py:25,64–65`
**What's broken**: A company with 3/3 available points (no prior year) scores 1.0 on the Piotroski component — identical to a company with 9/9. Inflates scores for newly-listed or data-poor companies.
**The fix**:
```python
# Always normalize against 9; cap without-prior result at neutral
piotroski_raw = Decimal(piotroski_score) / Decimal(9)
if not has_prior_year:
    piotroski_pct = min(piotroski_raw, Decimal("0.5"))
else:
    piotroski_pct = piotroski_raw
```
**Risk**: LOW. One test (`test_without_prior_year_normalizes_to_4`) will fail and must be updated to assert the correct new behavior (result ≈ 0.5, not > 0.8).

---

### Fix 4 — Sell-Side Verdict Asymmetry

**File**: `src/investmentology/verdict.py:551–560`
**What's broken**: BUY requires `sentiment > 0.30 AND confidence > 0.50`, but REDUCE and SELL have no confidence requirement. Low-confidence bearish calls map to REDUCE, not WATCHLIST. Creates excessive sell signals when agents are uncertain.
**The fix**: Mirror the buy-side dual threshold on the sell side:
```python
# REDUCE requires confidence gate (like BUY requires confidence gate)
if sent <= Decimal("-0.30") and confidence < reduce_confidence_threshold:
    return Verdict.WATCHLIST, ...
if sent <= Decimal("-0.50") and confidence < sell_confidence_threshold:
    return Verdict.REDUCE, ...
```
**Risk**: LOW. 30-minute fix. Add `test_reduce_requires_confidence_gate()` and `test_sell_requires_confidence_gate()`.

---

### Fix 5 — Altman Z'' Formula Variant Routing

**File**: `src/investmentology/quant_gate/altman.py`
**What's broken**: The 1968 manufacturing formula is applied to all companies. Technology, services, and healthcare companies get inflated Z-scores (high Sales/Assets inflates the X5 coefficient that should not apply to them).
**The fix**:
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
**Threading requirement**: `screener.py:310` must pass `sector=sectors.get(gr.ticker, "")` to `calculate_altman()`. The `sectors` dict is already built at `screener.py:193`.
**Risk**: MEDIUM. Requires sector threading + new formula + test migration. Estimate: 3–4 hours, not 2. One existing test (`test_z_score_formula_manual`) will fail and must be updated.
**Tests to add**: `test_z_double_prime_for_tech()`, `test_z_original_for_industrials()`.

---

### Fix 5b — gross_profit Data Field (Unblocks Piotroski F8 + Beneish)

**Files**: `src/investmentology/models/stock.py`, `src/investmentology/data/yfinance_client.py`
**What's broken**: `FundamentalsSnapshot` has no `gross_profit` field. Zero occurrences in the entire codebase. This blocks both the Piotroski F8 fix and the Beneish M-Score.
**The fix**:
1. Add `gross_profit: Decimal = Decimal(0)` to `FundamentalsSnapshot`
2. Populate from `ticker.income_stmt` or `info['grossProfits']` in `yfinance_client.py`
3. Fix Piotroski F8 in `piotroski.py:108`: `current_margin = current.gross_profit / current.revenue`
**Risk**: MEDIUM. New field on core dataclass; all `_make_snapshot()` test helpers need the field added. Add `test_f8_uses_gross_margin_not_operating_margin()` with a scenario where gross margin improves but operating margin does not (rising SGA scenario).

---

### Commit Strategy (5 staged commits per tech reviewer)

| Commit | Contents | Risk |
|--------|----------|------|
| 1 | Greenblatt ordinal, momentum formula, Piotroski normalization, verdict asymmetry | LOW — pure logic, no data dependency |
| 2 | Altman Z'' routing + sector threading | MEDIUM — test migration required |
| 3 | gross_profit field + yfinance population + Piotroski F8 fix | MEDIUM — data availability validation needed |
| 4 | Phase 1 quick wins (Simons, macro, Howard Marks) | LOW–MEDIUM |
| 5 | Beneish M-Score (after gross_profit + additional fields available) | MEDIUM |

---

## Phase 1: Foundation + Measurement (Week 1–3)

These items establish the analytical and communication infrastructure. They are independent of each other and can be developed in parallel.

### 1.1 — Macro Regime Pre-Classifier

**What**: Add a `macro_classify` pipeline step running once per cycle, before all agents. Produces a `MacroRegimeResult` (expansion/late-cycle/contraction/recovery + confidence) using FRED data (yield curve, credit spreads, PMI, unemployment). All agents receive the pre-classified regime.

**Why**: Currently 9 agents independently interpret macro conditions — 9 redundant and potentially divergent assessments. Pre-classification shares factual context (not opinions), reducing variance without introducing information cascades.

**Implementation** (from tech review):
- New `data/macro_regime.py` — FRED API call + classification logic (2 hours)
- `controller.py:_tick()` — run `macro_classify` once at cycle start, store in `pipeline_data_cache` with `ticker="__cycle__"` (1 hour)
- `pipeline/state.py` — add `STEP_MACRO_CLASSIFY = "macro_classify"` (15 min)
- `runner.py` — inject `macro_regime` from cycle cache into agent prompt assembly (1 hour)

**Total estimate**: 4–5 hours. Risk: LOW.

---

### 1.2 — Simons Agent Redesign

**What**: Replace RSI/MACD/moving-average technical analyst persona with statistically rigorous pattern recognition. No narrative. If no statistical signal exists, abstain.

**Redesigned methodology**:
1. Momentum persistence check (12-1 month J-T, skip month)
2. Volatility regime classification (high-vol regime reduces momentum reliability)
3. Short-term reversal check (1-week return as weak predictor of next week's direction)
4. Hard rule: without ≥ 10 months of consistent price data, confidence capped at 0.20
5. Existing rule retained: confidence capped at 0.15 without `technical_data`

**Implementation**: Pure prompt change in `skills.py`. 1–2 hours. Risk: NONE.

**Why it matters**: The current Simons adds noise, not signal diversity. A correctly-implemented momentum signal adds genuine uncorrelated value to the value-heavy team. The Fama-French literature confirms 12-1 month momentum as one of the most replicated anomalies.

---

### 1.3 — Howard Marks Agent (API, not CLI)

**What**: Add Howard Marks as 7th primary agent with "second-level thinking" framework: not whether a company is good, but whether the market's consensus view about it is right.

**Critical implementation constraint** (from tech reviewer): Cannot be Claude CLI. Adding a 4th agent to the Claude queue extends overnight cycle time by ~160 minutes (480 → 640 min). With a 690-minute budget (02:00 UTC → 13:30 UTC), this leaves only 50 minutes of headroom — dangerously tight.

**Provider decision**: Use **OpenRouter with Gemini 2.5 Pro via API** (parallel, scout-tier execution). This adds near-zero cycle time while providing a capable model for credit cycle qualitative reasoning.

**Framework**:
- Second-level thinking: "What does the market believe about this company, and is the market right?"
- Market cycle position: early-cycle (aggressive) / mid-cycle (patient) / late-cycle (defensive) / peak (reduce exposure)
- Required context: `macro_context`, credit spreads, VIX term structure, investor sentiment
- Explicit abstention rule: if market cycle position is unclear, reduce confidence, do not fabricate certainty

**Weight reallocation**: Dalio: 0.12 → 0.10, Soros: 0.10 → 0.08, Marks: 0.09. Total unchanged.

**Implementation**: New `AgentSkill` in `skills.py` + gateway entry + weight updates. 4 hours. Risk: MEDIUM (API reliability dependency; test before adding to overnight pipeline).

---

### 1.4 — Earnings Calendar with Sizing Guidance

**What**: For every held position and watchlist stock, surface days-to-earnings prominently in the PWA and briefing. Add sizing guidance: standard position when > 30 days to earnings; defer entry or reduce to starter position when < 15 days.

**Why elevated to Phase 1** (from practitioner): This prevents the most common retail investment mistake — initiating or adding to a position immediately before a binary event where there is no informational edge.

**Implementation**: Earnings calendar API (yfinance `ticker.calendar`), surface in portfolio view and Monday briefing. Database: store expected earnings dates per position. 1–2 days.

---

### 1.5 — Monday Morning Briefing (Narrative Format)

**What**: Restructure the existing briefing from data tables to a narrative-first format. Lead with thesis health alerts, then actionable events (earnings, sector moves), then monitoring items.

**Why elevated to Phase 1** (from practitioner): "If the system produces brilliant analysis that nobody reads because it's formatted as a database dump, the entire pipeline is wasted."

**Format**:
1. **Immediate attention** (any position with thesis health = CHALLENGED or BROKEN)
2. **This week's events** (earnings in < 10 days, major macro data releases)
3. **Monitoring** (F-Score changes, quant gate rank movements)
4. **Watchlist** (BUY-rated stocks not yet in portfolio — the gap between verdict and action)

**Implementation**: Restructure `advisory/briefing.py` output. 1–2 days.

---

### 1.6 — 60-Day Measurement Baseline

**What**: After Phases 0 and 1 are deployed, run the pipeline for 60 days without adding Phase 2 features. Log and measure:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Overnight success rate | ≥ 90% of runs complete before market open | Pipeline logs in `pipeline_cycles` table |
| Agent agreement rate | Pairwise correlation < 0.75 | Compute across 50+ stock analyses |
| Quant gate stability | 60–70% week-over-week top-100 overlap | Compare successive `quant_gate_results` |
| Paper portfolio baseline | Record vs. SPY for forward-looking comparison | Alpaca paper account |

**Why this matters** (from devil's advocate): The biggest risk is building a sophisticated upper layer on an unvalidated foundation. If the measurement reveals agent correlation > 0.85 or overnight failure rate > 15%, that is more important to fix than any Phase 2 feature.

---

## Phase 2: Process Tools (Week 4–8)

These items transform the system from a screening tool into a decision-support instrument a practitioner would actually use.

### 2.1 — Thesis Monitoring with Forced Criteria at Entry

**What**: Structured invalidation criteria stored at buy time and automatically monitored on each pipeline cycle. Criteria breach generates a thesis health alert.

**Critical design requirement** (from practitioner): Forcing function at buy time. It must be mechanically impossible to record a BUY decision without entering at least one quantifiable criterion (e.g., ROIC floor ≥ 12%, F-Score ≥ 6) and one qualitative criterion (e.g., "thesis breaks if they lose the DOD contract"). Without this, the system becomes another note-taking tool that nobody acts on.

**Schema**:
```sql
-- invest.thesis_criteria
position_id          UUID references positions(id),
criteria_type        ENUM(roic_floor, fscore_floor, revenue_growth_floor,
                          debt_ceiling, dividend_cut, custom_llm),
threshold_value      DECIMAL,
qualitative_text     TEXT,    -- the custom narrative criterion
monitoring_active    BOOLEAN DEFAULT TRUE,
created_at           TIMESTAMPTZ DEFAULT NOW()
```

**Monitoring loop**: After each pipeline cycle for held positions, `ThesisMonitor` checks each criterion against latest fundamentals. Breaches emit `ThesisBreakEvent` to `thesis_events` table and appear in next Monday briefing.

**Note on stop-losses** (from practitioner): Hard price-based stop-losses are wrong for value investing. Stop-losses should be thesis-dependent, not price-only. For `PERMANENT` position type, a stop-loss only triggers if the thesis is also CHALLENGED or BROKEN. For `TACTICAL` type, a price-based stop is more appropriate.

**Implementation**: `advisory/thesis_health.py` extensions + DB migration + PWA entry screen. ~1 week.

---

### 2.2 — Sector Heatmap and Correlation (Core C3 Only)

**What**: Two specific tools from the Portfolio Analytics Dashboard:
1. Sector concentration by portfolio weight, with 30% warning threshold
2. Pairwise correlation matrix for held positions

**Why not full C3**: Black-Litterman optimization is cut (overkill for 10–20 positions). Full factor exposure analysis deferred until the portfolio has 15+ positions and a track record.

**Why this is the right risk tool** (from practitioner): "During a sector rotation out of tech, your '15-stock diversified portfolio' behaves like a 3-stock portfolio." VaR is the wrong tool for this scale — it assumes normal distributions and fails exactly when you need it. Sector limits and correlation visibility are the practical risk tools for a concentrated portfolio.

**Implementation**: `advisory/portfolio_fit.py` extensions + new PWA portfolio analytics view. 1–2 days.

---

### 2.3 — Beneish M-Score as Binary Exclusion Filter

**What**: The Beneish M-Score (8-variable earnings manipulation detector) runs in the pre-filter step. Companies flagged as likely manipulators (M > -1.78) are excluded before quant gate scoring. Binary, not composite.

**Blocked by**: `gross_profit` from Phase 0 (Fix 5b), plus 3 additional fields (`receivables`, `depreciation`, `SGA`) that must be added to `FundamentalsSnapshot` and populated via yfinance or edgartools.

**Implementation**: New `quant_gate/beneish.py` + extended `FundamentalsSnapshot` + pre-filter integration. 6–8 hours (per tech reviewer, not 4 hours — 4 new data fields required). Risk: MEDIUM.

**Note on edgartools**: Rather than a full yfinance→edgartools migration, use edgartools selectively for the subset of tickers where yfinance lacks `gross_profit`. The devil's advocate correctly notes that edgartools has its own reliability issues (XBRL tagging inconsistencies) and is a younger library. Additive use (yfinance first, edgartools fallback) is safer than a migration.

---

### 2.4 — Debate Direction-Lock Removal

**What**: The current debate hard-locks direction (cannot flip from bullish to bearish in debate). Allow direction changes with mandatory justification strings.

**Why**: The hard direction-lock preserves surface diversity while preventing genuine learning when new information surfaces during debate. Wisdom-of-crowds requires authentic updating, not locked positions.

**Implementation**: 2–3 hours in `pipeline/convergence.py`. Risk: LOW.

---

## Phase 3: Advanced (Month 3+)

Only items that survived validation, gated behind the Phase 1–2 measurement baseline.

### 3.1 — Position Lifecycle Management (Starter / Building / Full / Trimming)

Operational conviction weighting framework: starter (2–3%), core (5–7%), full (8–10%). The practitioner validates this is the correct approach for a concentrated portfolio — not Black-Litterman.

Gate: deploy only after thesis monitoring is working and calibration data begins accumulating.

### 3.2 — Temperature Scaling Calibration

Switch from isotonic regression (requires 300+ samples) to temperature scaling (viable at 50–100 samples). The literature recommendation, confirmed by the synthesis math reviewer.

### 3.3 — OctagonAI MCP (Earnings Transcripts)

After the pipeline is stable and calibration data exists. OctagonAI's low star count (103) and architectural mismatch (client-side MCP) make it premature for Phase 1. Revisit when service has demonstrable reliability.

### 3.4 — Lynch Reasoner Model Upgrade

Consider upgrading Lynch agent from `deepseek-chat` to `deepseek-reasoner`. The "two-minute story" qualitative judgment benefits from reasoner-class inference. Deferred until the 60-day baseline reveals whether Lynch's current signal quality is adequate.

### 3.5 — Agent Calibration Leaderboard

Per-agent accuracy tracking (Brier score, ECE, accuracy@70%confidence) after 100+ settled predictions per agent. The infrastructure for this already exists; it requires data accumulation, not building.

### 3.6 — Historical Stress Test

Simple historical scenario analysis: "In Q4 2022, this portfolio would have fallen X%." More useful than VaR for retail scale, and honest about crisis correlation behavior. Implement when the portfolio has 10+ positions.

### 3.7 — Benchmark Performance Tracking

Track paper portfolio returns vs. SPY in the decision journal. The practitioner identifies this as Tier 2 weekly monitoring. Add to decision journal enhancement (C4).

---

## Rejected Items

| Item | Validation That Justified Cutting |
|------|----------------------------------|
| **Black-Litterman optimization** | Practitioner: overkill for 10–20 positions. Devil's advocate: designed for 200+ stock institutional portfolios. Both agree simple conviction weighting achieves the same result. |
| **Company Knowledge Graph (Neo4j)** | Devil's advocate: requires institutional data maintenance; LLM extraction from 10-K is expensive and unreliable at this scale. Wait until there's evidence it would improve verdicts. |
| **Congressional trading monitoring** | Devil's advocate: already priced in by HFT; 20 calls/day free tier insufficient for 100-stock pipeline. Practitioner agrees: decorative, not systematic. |
| **VaR / CVaR** | Practitioner: wrong tool for retail scale. VaR assumes normal distributions and fails during fat-tail market crashes — exactly when it's needed. Replace with sector limits and stress scenarios. |
| **VectorBT backtesting** | Practitioner: survivorship bias + look-ahead bias in yfinance make backtests misleading until point-in-time data is available. |
| **empyrical + pyfolio tear sheets** | Devil's advocate: no track record exists yet. Build after 6+ months of settled predictions. |
| **OctagonAI MCP (Phase 1)** | Tech reviewer: 103 stars, client-side architectural mismatch, medium dependency risk. Deferred to Phase 3 after pipeline stability demonstrated. |
| **Industry lifecycle S-curve** | Devil's advocate: agents already implicitly assess this; formalizing it creates documentation overhead without clear output improvement. |
| **Tax-aware position indicators** | Devil's advocate: this is paper trading. Build only when transitioning to real capital. |
| **Activist 13D tracking** | Requires new parsing infrastructure; signal strength at this scale is unverified. |
| **Benchmark-relative framing (full)** | Partial version (paper portfolio vs. SPY in decision journal) retained. Full expected-return modeling framework deferred. |

---

## Architecture Decisions Record

### Decision 1: Agent Independence Retained

**Decision**: Keep agents independent for first-pass analysis. Do not route preliminary outputs between agents.

**Reasoning**: Wisdom-of-crowds (Surowiecki) requires diversity, independence, decentralization, and aggregation. Routing preliminary outputs risks information cascades. The devil's advocate correctly notes that LLMs trained on the same corpus have correlated underlying beliefs — but the practical defense of independence is that it prevents explicit anchoring, even if deep-level correlation exists.

**The one exception**: All agents receive a pre-computed `MacroRegimeResult` before running. This is factual context, not opinion-sharing.

**Open question**: The 60-day measurement baseline should compute pairwise agent correlation across 50+ analyses. If correlation > 0.85 between value agents, the ensemble design needs re-evaluation.

---

### Decision 2: Howard Marks as API Agent (OpenRouter / Gemini)

**Decision**: Howard Marks runs as an API agent (OpenRouter with Gemini 2.5 Pro), not Claude CLI.

**Reasoning**: Technical reviewer confirmed that adding a 4th Claude CLI agent extends overnight cycle time by ~160 minutes, leaving only 50 minutes of margin before market open. A single pipeline failure would cause the briefing to miss market hours. The practitioner confirms Marks's framework is the one genuinely missing perspective (second-level thinking, credit cycle). OpenRouter provides model quality without the timing risk.

**Tradeoff**: OpenRouter adds API cost. At 30–50 stocks per cycle, this is approximately 30–50 API calls per overnight run — manageable.

---

### Decision 3: Black-Litterman Cut, Conviction Weighting Adopted

**Decision**: Cut Black-Litterman entirely. Use simple conviction weighting for position sizing.

**Reasoning**: Both the practitioner and devil's advocate independently reached this conclusion. B-L was designed for institutional portfolios with 200+ stocks where Markowitz optimization produces extreme corner solutions. At 10–20 positions, the problem B-L solves does not exist.

**Retained framework** (from practitioner):
- Full position (8–10%): Maximum 3 at this weight
- Core position (5–7%): Standard allocation
- Starter position (2–3%): Initial entry or partially confirmed thesis
- Cash (15–30%): Not a failure; if < 4 high-conviction ideas exist, that is the correct answer

---

### Decision 4: Risk Management Scoped to Practical Tools

**Decision**: Drop VaR/CVaR. Implement sector concentration limits (30% threshold warning) and a simple historical stress test.

**Reasoning**: The practitioner's assessment is definitive — VaR assumes normal distributions and fails exactly during fat-tail crashes. For 10–20 positions, the actionable risk tools are: no single stock > 10%, no single sector > 30–35%, minimum 15% cash buffer, and a historical scenario analysis to show crisis correlation behavior.

---

### Decision 5: Sell Discipline Is Process, Not Just Software

**Decision**: Thesis monitoring must force criteria entry at buy time. The UI makes it impossible to record a BUY without at least one quantifiable and one qualitative invalidation criterion.

**Reasoning**: Practitioner validation is unambiguous. Thesis documents written retroactively — after a stock has already dropped 30% — are written to justify decisions already made (confirmation bias). The forcing function separates professional investment discipline from a note-taking tool.

The practitioner also clarified the correct software role: thesis monitoring surfaces that "a threshold has been crossed and requires review," not "sell this." The sell verdict is a human decision gate, not an automated action.

---

### Decision 6: edgartools as Selective Supplement, Not Migration

**Decision**: Use edgartools to populate `gross_profit` and other missing fields for the subset of tickers where yfinance fails, not as a wholesale replacement.

**Reasoning**: The devil's advocate correctly notes that edgartools (1,806 stars) is significantly smaller than yfinance (13,000+ stars) and has XBRL tagging inconsistencies of its own. The right approach: yfinance first, edgartools as fallback for missing fields. This is additive and lower-risk than a migration.

---

### Decision 7: No New Agents Without Performance Measurement

**Decision**: After adding Howard Marks, do not add further agents until the 60-day measurement baseline reveals whether the current ensemble is calibrated.

**Reasoning**: The devil's advocate's challenge is correct — the system has never been empirically validated. Nine agents on a poorly-calibrated system generate confident-sounding noise. After 100+ settled predictions per agent, empirical calibration (Brier score, ECE) should replace the current hand-tuned prior weights. Until that data exists, adding more agents amplifies the uncertainty rather than reducing it.

---

*Qualified plan complete. 30-item overengineered roadmap reduced to 18 items across 3 phases with clear gates, success metrics, and cut justifications from three independent validation teams.*

*Generated 2026-03-09 — Phase 2 Qualified Implementation Plan v1.0*
