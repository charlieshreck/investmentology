# Technical Feasibility: Plan Validation Report

*Reviewer: Senior Software Engineer (Sonnet 4.6)*
*Date: 2026-03-09*
*Source: Code audit of 8 files + test suite + GitHub data for external libraries*

---

## Summary Verdict

Phase 0 bug fixes are real, all five are confirmed in the code. Four of the five are trivially correct one-line changes; one (Altman Z'') requires new infrastructure and careful test migration. Phase 1 items range from trivially simple (sell-side asymmetry, Simons redesign) to genuinely complex (Howard Marks agent + overnight pipeline time budget). The edgartools and OctagonAI dependencies are real and production-ready. The effort estimates in the roadmap are optimistic but not wildly wrong. Deployment can be staged cleanly.

---

## 1. Phase 0 Bug Fixes — Code Audit

### Bug #1 — Greenblatt ordinal rank (`screener.py:313–314`)

**Confirmed.** The code at lines 313–314 passes `gr.combined_rank` directly:

```python
# screener.py:313 — CURRENT (wrong)
score = composite_score(
    greenblatt_rank=gr.combined_rank,   # combined_rank = ey_rank + roic_rank (range: 2 to 2N)
    total_ranked=total_ranked,
```

`combined_rank` is defined in `greenblatt.py:22` as `ey_rank + roic_rank`. For N=500 stocks, the worst stock has `combined_rank=1000`. The `composite_score()` function in `composite.py:57–61` computes:

```python
greenblatt_pct = Decimal(total_ranked - greenblatt_rank) / Decimal(total_ranked - 1)
greenblatt_pct = max(Decimal("0"), min(Decimal("1"), greenblatt_pct))
```

For N=500, rank=501: `(500-501)/(500-1) = -1/499` → clamped to 0.0. Any stock with `combined_rank > total_ranked` (roughly half the universe) scores 0.0 on the 40%-weighted Greenblatt component. **The bug is exactly as described.**

**Fix is correct and safe:**
```python
for ordinal, gr in enumerate(top_ranked, start=1):
```

**Downstream risk:** The test at `test_quant_gate.py:764–771` (`test_best_possible_score`) currently passes `greenblatt_rank=1` which works. After the fix, if tests call `screener.run()` via the mocked pipeline, ordinal will always be 1..N and pass. No test breakage expected. The `run_delta()` method at `screener.py:415–455` reads `combined_rank` from DB for display purposes only — it does not re-call `composite_score()` — so no issue there.

**DB migration needed:** No. The `composite_score` value stored in `quant_gate_results` will change, but the column is computed-on-write and there is no constraint on its value.

---

### Bug #2 — Altman Z'': Manufacturing formula for all sectors (`altman.py`)

**Confirmed.** `altman.py` uses a single formula with coefficients hardcoded at module level:
```python
COEFF_A = Decimal("1.2")
COEFF_B = Decimal("1.4")
COEFF_C = Decimal("3.3")
COEFF_D = Decimal("0.6")
COEFF_E = Decimal("1.0")   # X5 = Revenue/Assets — absent from Z'' formula
```

No sector parameter is accepted: `calculate_altman(snapshot: FundamentalsSnapshot)` — there is no `sector` argument.

**The proposed fix is architecturally correct.** However there are implementation complications:

1. `calculate_altman` is called in `screener.py:310` without sector information. The `snap_by_ticker` dict contains `FundamentalsSnapshot` objects which have no `sector` field — sector lives in the `sectors` dict built from universe data at `screener.py:193`. The fix requires threading sector into the call: `calculate_altman(snap, sector=sectors.get(gr.ticker, ""))`.

2. **Test migration required:** `test_quant_gate.py:356–462` tests Altman extensively. The manual formula verification test at line 425–454 (`test_z_score_formula_manual`) hard-codes the original manufacturing formula. This test will need a sector parameter or it will fail after the fix.

3. The `_classify_zone()` function uses a single set of thresholds (2.99/1.81). After the fix, `_compute_z_double_prime()` must use different thresholds (2.6/1.1). The `AltmanResult.zone` field must remain consistent — a "safe" zone means different things under each formula variant.

**Risk: MEDIUM.** This is not a one-liner. Estimate: 3–4 hours including test updates, not 2 hours.

---

### Bug #3 — Piotroski F8: Operating margin instead of gross margin (`piotroski.py:106–110`)

**Confirmed exactly as described:**
```python
# piotroski.py:108 — CURRENT (wrong)
current_margin = current.operating_income / current.revenue   # operating margin
```

**Critical dependency:** `FundamentalsSnapshot` in `models/stock.py` has no `gross_profit` field. A search across the entire `src/` directory finds **zero occurrences of `gross_profit`**. This is a data layer change, not just a formula change.

The proposed fix requires:
1. Add `gross_profit: Decimal = Decimal(0)` to `FundamentalsSnapshot` (stock.py:37 area)
2. Populate it in `yfinance_client.py` from `info['grossProfits']`
3. Populate it in `edgar_client.py` from XBRL data (if using edgartools)
4. Update `piotroski.py:108` to use `current.gross_profit / current.revenue`

The `_dict_to_snapshot()` function in `screener.py:43–83` must also handle the new field or it will silently default to zero (which is already the default on the dataclass). The Piotroski test fixture `_make_snapshot()` at line 31 does not include `gross_profit`, so all existing tests will still pass with the default of 0 — but F8 will always score 0 unless `gross_profit` is populated. **A specific test for the fix is needed.**

**Risk: LOW-MEDIUM.** The code change is small but requires the data layer to actually provide `gross_profit`. Without the data, the fix is a no-op.

---

### Bug #4 — Momentum skip-month formula (`screener.py:118–122`)

**Confirmed exactly as described:**
```python
# screener.py:118 — CURRENT
if len(series) < 30:    # wrong threshold
    continue
ret_12m = (series.iloc[-1] / series.iloc[0]) - 1
ret_1m = (series.iloc[-1] / series.iloc[-22]) - 1 if len(series) > 22 else 0
momentum_raw[ticker] = float(ret_12m - ret_1m)   # wrong: subtraction ≠ J-T skip
```

The `period="1y"` fetch at `screener.py:107` retrieves ~252 trading days of data. The correct fix:
```python
if len(series) < 220:   # need 12 months minus 1 month = ~252-22 data points
    continue
momentum_raw[ticker] = float((series.iloc[-22] / series.iloc[-252]) - 1)
```

**Note on data availability:** `yf.download(period="1y")` may return fewer than 252 rows for tickers with recent IPOs or trading halts. The `series.iloc[-252]` access is safe only if `len(series) >= 252`. The threshold of 220 in the roadmap is slightly too permissive — any value between 220 and 252 would access a non-existent index when `252 > len(series) >= 220`. The correct guard is `len(series) < 252` (or use `series.iloc[0]` for the 12-month start when fewer than 252 rows are available but at least 220).

**Risk: LOW.** One-line fix. No downstream dependencies.

---

### Bug #5 — Piotroski without-prior normalization (`composite.py:25,64–65`)

**Confirmed:**
```python
# composite.py:25 — CURRENT
PIOTROSKI_MAX_WITHOUT_PRIOR = 3   # but the actual code on line 64 uses this as denominator
piotroski_max = PIOTROSKI_MAX_WITH_PRIOR if has_prior_year else PIOTROSKI_MAX_WITHOUT_PRIOR
piotroski_pct = Decimal(piotroski_score) / Decimal(piotroski_max)
```

When `has_prior_year=False` and score=3, result is `3/3 = 1.0`. **However:** `piotroski.py:51` documents "If no previous snapshot, score only what we can (points 1, 2, 4)" — that is 3 points, not 4. The current constant is 3 (lines up with what's actually scoreable), but the normalization against 9 with a cap at 0.5 is the correct fix.

**Test impact:** `test_quant_gate.py:810–819` (`test_without_prior_year_normalizes_to_4`) currently passes a comment "max piotroski is 4" but the code uses 3 as the max. The test assertion `assert no_prior > Decimal("0.8")` passes because 3/3=1.0 and the math works out to ~0.925. After the fix (3/9=0.333, capped to 0.5), that test will **fail** — it asserts > 0.8 but will get ~0.695. The test needs updating to reflect the correct behavior.

**Risk: LOW except for one test that must be updated.**

---

## 2. Phase 1 Items — Effort and Risk Assessment

### Sell-Side Verdict Asymmetry Fix (`verdict.py:551–560`)

**Confirmed.** The code at lines 551–560 shows:
```python
if sent >= Decimal("-0.10"):
    return Verdict.HOLD, ...
if sent >= Decimal("-0.30"):
    return Verdict.REDUCE, ...    # no confidence gate
if sent >= Decimal("-0.50"):
    return Verdict.SELL, ...      # no confidence gate
```

vs. the buy side which has explicit `and confidence >= t["buy_confidence"]` checks. **The asymmetry is real.**

Fix is 2–3 lines. Estimated 30 minutes is accurate. **No DB migration. No pipeline disruption.** Only `test_verdict.py` needs coverage additions for the new confidence-gated REDUCE/SELL behavior.

**Risk: LOW.**

---

### OctagonAI MCP Integration

**GitHub confirms:** `OctagonAI/octagon-mcp-server` — 103 stars, 19 forks, JavaScript, active. Description matches ("earnings transcripts, financial metrics, SEC filings"). The low star count (103 vs. edgartools' 1,806) is a reliability concern. This is a young project.

**Architecture concern:** The existing pipeline fetches enrichment data server-side in the K8s pod via `enricher.py`. OctagonAI MCP would be a *client-side* MCP server that runs on the HB LXC and is accessed by Claude/Gemini agents as a tool during their analysis. This is architecturally different — agents would call OctagonAI tools *within* their analysis rather than having transcript data pre-fetched into the pipeline state cache.

**The roadmap classifies this as effort S.** That's accurate for the MCP config entry itself, but prompt modifications across 3+ agent skills (Klarman, Auditor, Warren) to explain when/how to use the OctagonAI tools adds 2–4 hours. Total: **S–M, 4–6 hours.**

**Risk: MEDIUM** — depends on OctagonAI service availability and API stability.

---

### pandas-ta for Simons Agent

`pandas-ta` is a standard library. The Simons skill definition in `skills.py` uses `provider_preference=["remote-simons", "groq-api", "deepseek"]` and `cli_screen=None`. There's already a `compute_technical_indicators` function being called in `controller.py:384–395`:

```python
from investmentology.data.technical_indicators import (
    compute_technical_indicators,
)
```

This module exists. Check what it currently provides vs. what Simons receives via `optional_data` and `required_data`. If `technical_data` is already cached in the pipeline state, pandas-ta may already be partially wired. **Actual effort may be less than S** — could be verification + prompt update only.

---

### Simons Persona Redesign

Pure prompt change in `skills.py`. The Simons skill methodology is defined at the dataclass level. No DB migration, no pipeline logic changes. 1–2 hours. **Risk: NONE.**

---

### Howard Marks Agent — Pipeline Time Budget Analysis

**This is the riskiest Phase 1 item.** The CLAUDE.md confirms the overnight pipeline runs at 02:00 UTC Tue–Sat. CLI agents serialize on two queues:

- **Claude queue** (via HB LXC): warren → auditor → klarman — all tickers processed sequentially per agent
- **Gemini queue**: soros → druckenmiller → dalio

Howard Marks is proposed as Claude Opus 4.6 via CLI. This adds a **4th agent to the claude queue**, each processing every ticker. With 30–50 tickers (post-competence filter), each agent averaging 3–5 minutes per ticker:

- Current claude queue: 3 agents × 40 tickers × 4 min = **480 minutes per cycle (8 hours)**
- After adding Marks: 4 agents × 40 tickers × 4 min = **640 minutes (10.7 hours)**

If the overnight pipeline must complete before market open (~13:30 UTC), there is limited headroom. The current 3-agent load may already be marginal. **Adding a 4th Claude CLI agent risks missing the morning completion window.**

**Recommendation from roadmap:** Use Gemini 2.5 Pro instead of Claude for Howard Marks. Gemini queue currently has 3 agents. Adding Marks to gemini: 4 agents × 40 tickers × 4 min = **640 min on gemini side**. Same problem, different queue. The scheduler runs both queues in parallel, so the bottleneck is whichever queue takes longer.

**Alternative:** Make Howard Marks an API agent (DeepSeek, Groq, or OpenRouter with Gemini) running in parallel with the scout tier. This reduces cycle time impact to near-zero.

**Risk: HIGH if implemented as Claude CLI. MEDIUM if Gemini CLI. LOW if API agent.**

---

### Macro Regime Pre-Classifier

**Architecture fit:** The pipeline state machine in `state.py` defines steps as string constants:
```python
STEP_DATA_FETCH = "data_fetch"
STEP_DATA_VALIDATE = "data_validate"
STEP_PRE_FILTER = "pre_filter"
...
STEP_AGENT_PREFIX = "agent:"
```

A new `macro_classify` step would be a **per-cycle step** (not per-ticker), which is architecturally novel. Currently all pipeline steps are per-ticker. The simplest implementation is a special singleton ticker (e.g., `"MACRO"`) with a `macro_classify` step, or better: run `macro_classify` once at cycle start in `_tick()` before iterating tickers, storing the result in a cycle-level cache key.

The result (`MacroRegimeResult`) would be stored in `invest.pipeline_data_cache` with `ticker="__cycle__"` and retrieved during each ticker's research/agent steps. **No new DB migration needed** — `pipeline_data_cache` already exists.

**Implementation path:**
1. New `data/macro_regime.py` (FRED API call + classification logic) — 2 hours
2. Modify `controller.py:_tick()` to run `macro_classify` once per cycle — 1 hour
3. Modify `pipeline/state.py` to add `STEP_MACRO_CLASSIFY = "macro_classify"` — 15 min
4. Modify agent prompt assembly in `runner.py` to inject `macro_regime` from cycle cache — 1 hour

**Total: 4–5 hours. Risk: LOW.**

---

### Beneish M-Score as Binary Exclusion Filter

**Requires the same data fields as Piotroski F8 fix.** Beneish needs:
- `gross_profit` (not in `FundamentalsSnapshot` yet)
- `receivables` (not in `FundamentalsSnapshot`)
- `depreciation` (not in `FundamentalsSnapshot`)
- `SGA` (Selling, General & Administrative) (not in `FundamentalsSnapshot`)

These are 4 new fields, all requiring data layer changes. The Beneish model also requires **two years** of data for most of its 8 variables (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA are all year-over-year ratios). This means prior-year snapshots must include `gross_profit`, `receivables`, `depreciation`, and `SGA` — the `get_prior_fundamentals_batch()` in the EDGAR client must be extended.

**The roadmap classifies this as effort M.** That's correct, but only if edgartools integration (which provides these fields) is done first. Without edgartools, the data doesn't exist. Beneish should be blocked-by edgartools integration.

**Risk: MEDIUM — data dependency is the gating factor.**

---

## 3. Data Dependencies

### edgartools (`dgunning/edgartools`)

**GitHub confirms:** 1,806 stars, 313 forks, Python, 18 open issues. Active library for SEC EDGAR XBRL data. **Production-ready.**

**Does it provide `gross_profit` and `retained_earnings`?** The library parses XBRL financial statements. These are standard GAAP line items that appear in SEC filings as `us-gaap:GrossProfit` and `us-gaap:RetainedEarningsAccumulatedDeficit`. edgartools exposes these as DataFrame columns from `company.get_financials()`. **Yes, both are available.**

**Integration path:** edgartools uses CIK lookups, not tickers. The existing `edgar_client.py` already handles the ticker→CIK mapping. Adding `gross_profit` extraction is an additive change to the existing client. `pip install edgartools` is the only dependency change.

**Concern:** edgartools rate-limits to SEC's EDGAR API limits (~10 requests/sec). The current EDGAR client already implements chunked fetching with 1s pauses (visible in `screener.py:213–238`). edgartools has its own rate limiter built in.

---

### OctagonAI MCP Server

**GitHub confirms:** 103 stars, JavaScript/Node.js, free. It provides earnings call transcripts, SEC filing data, and private market comparables. Active but young (low star count).

**Architecture mismatch:** This MCP server is designed to run locally alongside a Claude Desktop or CLI client. It requires Node.js runtime on the HB LXC. The server authenticates to OctagonAI's cloud service.

**Critical question:** Does OctagonAI require an API key or is it truly free? The README says "free" but the description says "MCP server" — the actual data comes from OctagonAI's backend. If OctagonAI becomes a paid service or rate-limits aggressively, the integration breaks silently. **Dependency risk: MEDIUM.**

---

## 4. Howard Marks Agent — Quantitative Pipeline Impact

As computed in Section 2:

| Configuration | Claude queue time | Gemini queue time | Total cycle time |
|--------------|------------------|------------------|-----------------|
| Current (6 agents) | ~480 min | ~480 min | ~480 min (parallel) |
| +Marks on Claude | ~640 min | ~480 min | ~640 min |
| +Marks on Gemini | ~480 min | ~640 min | ~640 min |
| +Marks as API agent | ~480 min | ~480 min | ~480 min |

The overnight pipeline at 02:00 UTC with a 13:30 UTC market open gives a 690-minute budget. Adding Marks as CLI consumes 640 of those minutes — only 50-minute margin for failures and retries. **This is dangerously tight.**

**Recommendation: Add Howard Marks as a DeepSeek API agent** (deepseek-chat or deepseek-reasoner). Cycle time impact is near-zero since API agents run in parallel with the scout tier. The tradeoff: DeepSeek is a significantly weaker model than Claude Opus for qualitative cycle analysis. Alternative: use OpenRouter with Gemini 2.5 Pro via API (not CLI), which provides the same model quality without adding to the CLI queue.

---

## 5. Macro Regime Pre-Classifier — Pipeline State Machine Integration

**Step naming:** Add `STEP_MACRO_CLASSIFY = "macro_classify"` to `state.py:22–31`.

**Ordering constraints:**
- Must run before `agent:*` steps — it provides context agents consume
- Must run after `data_fetch` (needs FRED data which is fetched in enrichment)
- Can run per-cycle (once), not per-ticker

**Current flow:** `data_fetch → data_validate → pre_filter → screener:* → gate_decision → research → agent:* → debate → adversarial → synthesis`

**New flow:** `[cycle-level] macro_classify → [per-ticker] data_fetch → data_validate → ...`

**Implementation:** The cleanest approach is to run `macro_classify` as the first action in `_tick()` at `controller.py:259`, before the per-ticker loop. Store result in a cycle-level cache. Each agent's `_build_analysis_request()` or equivalent retrieves it from cache. No new step type needed — just a synchronous method call at tick start with early exit if already done for this cycle.

---

## 6. Regression Risk Assessment

| Change | Risk | Why |
|--------|------|-----|
| Greenblatt ordinal fix | LOW | Logic fix; composite scores change (expected); no DB schema change |
| Momentum formula fix | LOW | Independent calculation; threshold increase means fewer tickers scored |
| Verdict sell-side fix | LOW | Behavioral change only; existing REDUCE/SELL tests need additions |
| Piotroski F8 fix | LOW-MEDIUM | Depends on gross_profit data availability; no-op if data absent |
| Altman Z'' routing | MEDIUM | Requires sector threading; breaks 1 existing test; new function needed |
| Piotroski normalization fix | LOW | Breaks 1 existing test (expected); fix is 2 lines |
| gross_profit data field | MEDIUM | New field on core dataclass; all `_make_snapshot()` test helpers need updating |
| Howard Marks as Claude CLI | HIGH | Overnight pipeline timing risk |
| Beneish M-Score | MEDIUM | Blocked by gross_profit + 3 other new fields |
| Macro pre-classifier | LOW | Additive, per-cycle, no existing steps touched |

---

## 7. Testing Strategy

**Existing test coverage is good.** There are 33 test files covering quant gate, agents, pipeline, verdict, calibration, and more. Key gaps after these changes:

1. **Greenblatt ordinal fix:** Add `test_composite_score_uses_ordinal_not_combined_rank()` — simulate 500 stocks where `combined_rank > total_ranked` and verify scores > 0.

2. **Altman Z'' routing:** Update `test_z_score_formula_manual` to accept a sector param. Add `test_z_double_prime_for_tech()` and `test_z_original_for_industrials()`.

3. **Piotroski F8 with gross_profit:** Add `test_f8_uses_gross_margin_not_operating_margin()` with a snapshot where gross margin improves but operating margin does not (SGA increase scenario).

4. **Verdict sell-side fix:** Add `test_reduce_requires_confidence_gate()` and `test_sell_requires_confidence_gate()`.

5. **Piotroski normalization:** Update `test_without_prior_year_normalizes_to_4` to assert the new behavior (capped at 0.5).

---

## 8. Deployment Sequence

### Can Phase 0 and Phase 1 ship together?

**No.** They should be staged:

**Commit 1 — Pure logic fixes (no data dependencies):**
- Greenblatt ordinal rank (`screener.py:313`)
- Momentum skip-month formula (`screener.py:118,121–122`)
- Piotroski without-prior normalization (`composite.py:25,64–65`)
- Verdict sell-side confidence gate (`verdict.py:551–560`)
- Altman Z'' formula routing (`altman.py`) — requires sector threading but no new data fields

**Commit 2 — Data layer + gross_profit:**
- Add `gross_profit` to `FundamentalsSnapshot` (`models/stock.py`)
- Populate from yfinance (`yfinance_client.py`)
- Populate from edgartools (`edgar_client.py`)
- Fix Piotroski F8 (`piotroski.py:108`)
- Add `retained_earnings` source from EDGAR (remove net_income fallback in `altman.py:71`)

**Commit 3 — Phase 1 quick wins (independent, can deploy together):**
- Simons persona redesign (`skills.py`)
- Macro regime pre-classifier (`data/macro_regime.py`, `pipeline/controller.py`)
- OctagonAI MCP config (HB LXC only — not K8s pod)
- Verdict weight adjustments

**Commit 4 — Howard Marks agent (after overnight timing analysis):**
- New AgentSkill in `skills.py`
- Gateway entry in `scripts/hb-agent-proxy.py`
- Weight reallocation (Dalio: 0.12→0.10, Soros: 0.10→0.08, Marks: 0.09)
- Only after confirming pipeline fits within overnight window

**Commit 5 — Beneish (after edgartools provides additional fields):**
- New `quant_gate/beneish.py`
- Extended `FundamentalsSnapshot` (receivables, depreciation, SGA)
- Pre-filter integration

**Rationale for staging:** Commits 1 and 3 deploy through CI/CD to the K8s pod cleanly. Commits 2 and 5 require data availability validation before they improve (vs. silently no-op on) scoring. Commit 4 requires overnight pipeline timing validation before deployment.

---

## 9. Effort Re-estimates (Corrected)

| Item | Roadmap estimate | Corrected estimate | Reason for difference |
|------|-----------------|-------------------|-----------------------|
| Greenblatt ordinal fix | 30 min | 1 hour | Test updates needed |
| Altman Z'' routing | 2 hours | 4 hours | Sector threading, 2 formulas, test migration |
| Altman retained_earnings | 30 min | 45 min | Minor |
| Piotroski F8 fix | 30 min | 30 min (accurate) | Conditional on edgartools |
| edgartools integration | 2 hours | 3–4 hours | Data mapping validation |
| ROIC NWC adjustment | 1 hour | 2 hours | Need `short_term_debt` field + test |
| Macro pre-classifier | S = ~2 hours | 4–5 hours | Per-cycle state machine integration |
| Howard Marks agent | M = ~4 hours | 4 hours + pipeline timing risk | Code is M; timing risk is separate |
| OctagonAI MCP | S = ~1 hour | 3–4 hours | MCP config + prompt changes for 3 agents |
| Beneish M-Score | M = ~4 hours | 6–8 hours | 4 new data fields required |

---

*Technical validation complete. Code references verified against actual source. External library data from GitHub API (edgartools: 1,806 stars — production-ready; OctagonAI: 103 stars — functional but young).*
