# Deep Review: Agent Orchestration — Team vs Individual, Data Flow, Pipeline Design

*Reviewer: Orchestration Architect Agent*
*Review date: 2026-03-08*
*Files reviewed: pipeline/controller.py, pipeline/scheduler.py, pipeline/selection.py, pipeline/freshness.py, pipeline/state.py*

---

## Executive Summary

The current pipeline is architecturally sound — event-driven, database-backed state machine, per-agent independent queues, conditional agents, and a debate/synthesis layer. It embodies the best practices of ensemble forecasting: independent agents with diverse perspectives, calibration-adjusted weights, and an adversarial counterweight.

However, six specific design choices warrant reconsideration: macro-context timing, debate architecture, inter-agent information flow, data asymmetry, ticker selection scoring, and pipeline triggers. These are not architectural flaws — they are the natural first version of a system that can be evolved toward better decision outcomes.

---

## Section 1: Team vs. Individual — Independence vs. Cross-Pollination

### Current design
All 9 agents (Warren, Auditor, Klarman, Soros, Druckenmiller, Dalio, Simons, Lynch, Income Analyst) run completely independently. They see the same cached data but produce their verdicts in isolation. No agent sees another's preliminary assessment before forming its own opinion. Cross-pollination only happens in debate (conditional on <75% consensus) and synthesis (aggregation).

### The Wisdom of Crowds argument FOR independence

The "wisdom of crowds" effect (Galton's "Vox Populi" 1907, formalized by Surowiecki 2004) requires **four conditions** for collective intelligence to outperform individual experts:
1. **Diversity of opinion** — each person has private information
2. **Independence** — each person's opinions are not determined by others'
3. **Decentralization** — local knowledge is used
4. **Aggregation** — a mechanism exists to turn individual judgments into collective decisions

The current system satisfies 1, 2, and 4. Condition 3 (decentralization) is partially satisfied via required_data/optional_data differentiation.

**Breaking condition 2 causes information cascades**: If agents see each other's preliminary outputs before forming their own, they may anchor to the first response. This is the Banerjee (1992) / Bikhchandani et al. (1992) "information cascade" problem — rational individuals discard their own private signals to follow what they observe others doing. In financial contexts, this is the primary mechanism behind analyst herding.

**Conclusion: Independence is correct for the first-pass analysis phase.** The current design is scientifically grounded.

### Where cross-pollination IS appropriate

However, independence does NOT require complete information isolation. Consider:

1. **Macro regime context**: Warren seeing the same FRED macro data as Dalio is not groupthink — it is shared factual input. The issue is when agents see each other's *interpretations*, not when they share *facts*.

2. **Post-debate cross-pollination (already implemented)**: The debate mechanism is exactly the right place for controlled information exchange. The current design correctly gates this on disagreement.

3. **Research briefing (recently added)**: The research step (Gemini synthesizing news/analyst data into a briefing) provides shared interpretive context. This slightly reduces independence but improves signal quality. The tradeoff is acceptable because the briefing is a factual summary, not an agent opinion.

### Recommendation: Preserve independence for first-pass analysis. Add one exception.

The only exception: agents should receive a **"consensus-blind summary"** of the macro regime *classification* (expansion/late-cycle/contraction/recovery) BEFORE they run, produced by a dedicated macro-classifier. This is different from sharing opinions — it is sharing context that all agents would independently assess similarly anyway, so providing it saves compute without creating information cascades.

---

## Section 2: Debate Effectiveness

### Current design
Debate triggers when `should_debate()` returns True — currently checking if primary agent consensus is below 75% (sentiment agreement across Warren/Auditor/Klarman/Soros/Druckenmiller/Dalio). Debate runs through `DebateOrchestrator` which allows agents to revise confidence but not direction (verdict). The debate uses primary agents only.

### What deliberation research says

The most relevant research is from **structured adversarial collaboration** (Mellers et al., Good Judgment Project, 2015) and **superforecasting** (Tetlock & Gardner, 2015):

- Groups that debate using **structured argument exchange** outperform groups that merely average individual forecasts
- The key is **reason giving**: participants must explain *why* they changed their estimate, not just change it
- **Devil's advocate techniques** (assigning one participant to argue the opposite) improve group calibration
- However, debate improves accuracy most when participants have genuinely different *information*, not just different prior beliefs

For LLM agents, debate format matters significantly:
- **Unstructured debate**: agents tend to converge toward the first response ("sycophancy cascade")
- **Structured debate**: assigning agents to explicitly argue a side produces better reasoning
- **Adversarial debate** (prosecution/defense format): produces the most robust stress-testing

### Issues with current debate design

**Issue 1: Agents can revise confidence but not direction.**

This is an intentional constraint, but it may be too conservative. If Agent A has genuinely new information in its debate response that would rationally cause Agent B to flip from HOLD to BUY, Agent B cannot do this. The constraint prevents "sycophancy cascade" but also prevents genuine learning.

**Better design**: Allow direction changes in debate, but require **written justification** for any direction flip. If an agent flips without justification matching its persona (e.g., Warren Buffett's voice saying "I was wrong because the growth rate is higher than I estimated"), that is genuine learning. If it flips without reasoning, that is cascade.

**Issue 2: Debate uses the same agents who already disagreed.**

Asking Warren (who said BUY) and Soros (who said SELL) to debate each other may not produce new insights — they may simply restate their positions more forcefully.

**Better design**: Add a **Moderator/Referee role** in debate — a designated agent (potentially the Data Analyst, already trained for neutral assessment) that identifies the specific factual points of disagreement and asks targeted questions. This is the "dialectical inquiry" approach (Mason & Mitroff, 1981), which produces better decisions than unstructured debate in group settings.

**Issue 3: The 75% threshold is reasonable but not data-driven.**

Without calibration history, there is no evidence that 75% is the right threshold. At 90+ decisions logged (per CLAUDE.md), a retrospective analysis of whether debates improved accuracy vs. non-debates would allow data-driven threshold setting.

**Issue 4: Only PRIMARY agents participate in debate.**

Simons and Lynch (API scouts) do not participate in debate. Given that Simons (quant) often has fundamentally different signal sources than the narrative-driven primaries, including scouts in debate would catch more genuine disagreements.

### Recommendation: Three structural changes to debate

1. **Allow direction changes with mandatory justification string** — track these in the DB for calibration
2. **Add Data Analyst as neutral moderator** identifying the top 2-3 factual points of contention
3. **Include scouts in debate** when their signal diverges significantly from primary consensus

---

## Section 3: Data Flow — Information Asymmetry

### Current design (from skills.py inferred from controller.py)

Each agent has `required_data` and `optional_data` lists. The `_build_request()` method in the controller loads cached data and passes it to agents. Agents see different subsets based on their role. For example:
- Warren (fundamental value) likely requires fundamentals, filing_context, insider_context
- Soros (macro/sentiment) likely requires macro_context, social_sentiment, analyst_ratings
- Simons (quant) likely requires technical_indicators, short_interest

### Is this optimal?

**The case for data asymmetry (current design)**:
Agents with specialized personas should focus on their domain data. Flooding Warren with social_sentiment data creates noise for a persona explicitly ignoring market sentiment.

**The case for shared data access**:
Modern ensemble methods (Breiman, 1996; Brown, 2010) show that **decorrelated errors** are more important than decorrelated inputs. Two agents that see different data may still reach similar conclusions, reducing ensemble value. Two agents that see the same data but reason differently (due to different value functions / personas) can still be decorrelated.

**The actual problem**: Currently there is no visibility into whether information asymmetry is causing agents to miss cross-domain signals. For example:
- Warren may not see that insider selling is occurring (insider_context) if it is in Lynch's optional_data
- Klarman may miss that Finnhub analyst consensus has shifted dramatically (analyst_ratings) if it is Soros's data

**Recommendation**:
- Keep asymmetry as the primary design (correct approach)
- Add one **shared baseline context** available to all agents: fundamentals, macro_context, news_context
- Make all other data **selectively optional** — agents request it if relevant to their analysis
- Log which data keys each agent actually used in each analysis (add to signal output) to empirically test whether asymmetry is benefiting or hurting

---

## Section 4: Macro Context Timing

### Current design
Macro context (`macro_context`) is fetched as part of `data_fetch` — the first pipeline step. It is cached and available to agents. However, it is fetched at the same time as company-specific data, with no pre-classification step.

### The issue
Agents receive raw macro data (FRED indicators, yield curve, etc.) and must independently interpret regime context. This means:
1. Each of 9 agents does its own macro regime assessment — 9 redundant interpretations
2. Agents that receive macro_context in their optional data may interpret it differently than those that don't
3. There is no authoritative regime signal that bounds the analysis

### What the research says
In ensemble forecasting, **pre-computation of shared context** reduces variance without increasing bias when:
- The contextual variable is factual/objective (yield curve inversion is a fact, not an opinion)
- All agents would interpret it similarly if they saw the same data

Macro regime classification (expansion/late-cycle/contraction/recovery) is more objective than individual stock analysis. A yield curve inverted for 12 months + rising unemployment + tightening credit spreads = late cycle. This is a near-deterministic classification.

### Recommendation: Add Macro Regime Pre-classifier

Add a new pipeline step `macro_classify` that runs BEFORE agent steps, after `data_fetch`. This step:
1. Loads FRED data (yield curve, credit spreads, PMI, unemployment)
2. Produces a `MacroRegimeResult` with: regime (expansion/late-cycle/contraction/recovery), confidence (high/medium/low), regime-specific risk factors
3. Caches the result as `macro_regime` in the pipeline data cache
4. All agents receive this pre-classified regime instead of raw FRED data

**Implementation cost**: Low — 1 new step, 1 new data class, minor prompt changes to include regime context.
**Expected benefit**: Reduces variance in macro interpretation, allows agents to focus on company-specific analysis within the appropriate macro context.

---

## Section 5: Freshness Management

### Current thresholds (from freshness.py)

| Key | Threshold | Portfolio behavior |
|-----|-----------|-------------------|
| fundamentals | 24 hours | Always refresh if stale |
| technical_indicators | 12 hours | Always refresh if stale |
| macro_context | 24 hours | Critical — refresh blocks |
| news_context | 6 hours | Critical — refresh blocks |
| earnings_context | 24 hours | Not critical |
| insider_context | 48 hours | Not critical |
| filing_context | 72 hours | Not critical |
| institutional_context | 72 hours | Not critical |
| analyst_ratings | 24 hours | Not critical |
| short_interest | 48 hours | Not critical |
| social_sentiment | 12 hours | Not critical |
| research_briefing | 24 hours | Not critical |

### Analysis

**Reasonable thresholds**: The core thresholds (fundamentals 24h, technical 12h, news 6h) are appropriate for overnight pipeline operation. These are not real-time trading thresholds — they match the overnight batch execution model.

**Potential issue: `news_context` is marked CRITICAL but `earnings_context` is not.**
An earnings release is the single highest-impact event for individual stock analysis. If an earnings release occurred 18 hours ago and `earnings_context` is stale (refreshes at 24h), but `news_context` has already captured it (refreshes at 6h), this is acceptable. But if the earnings release happened 7 hours ago and `news_context` just barely caught it, the `earnings_context` (with actual EPS/guidance numbers) won't be refreshed for another 17 hours. This creates a window where agents see earnings headlines in news but not the actual financials.

**Recommendation**:
1. Add `earnings_context` to `CRITICAL_KEYS` — earnings data is as critical as news
2. Reduce `earnings_context` threshold to 6 hours (matching news) during earnings season
3. Consider adding `earnings_window` detection: if an earnings date is within 48 hours, override thresholds and force a data refresh

**Portfolio tickers refreshing on ANY stale key**: This is correct design. Portfolio positions demand higher data quality — any stale key should trigger a full refresh.

---

## Section 6: Ticker Selection Scoring

### Current design (from selection.py)

The scoring system uses hardcoded point values:

| Signal | Points |
|--------|--------|
| Held position base | 25 |
| Thesis BROKEN | +50 |
| Thesis CHALLENGED | +35 |
| Thesis UNDER_REVIEW | +20 |
| Drawdown (type-aware threshold) | +40 |
| Minor drawdown (-10% to -5%) | +8–15 |
| Earnings proximity | 25 |
| Never analysed | 20 |
| Stale verdict (>14 days) | 15 |
| Stale verdict (7–14 days) | 10 |
| Aging verdict (3–7 days) | 5 |
| QG top-10 | 20 |
| QG top-25 | 12 |
| QG top-50 | 8 |

### What is well-designed

- **Position-type-aware drawdown thresholds** (tactical: -15%, core: -20%): Excellent design. A tactical position has a shorter rope than a core holding.
- **Portfolio-first guarantee** (portfolio tickers always selected regardless of score): Correct. Never let a watchlist candidate crowd out an existing position from analysis.
- **Thesis health as highest priority signal**: BROKEN thesis gets 50 points — the single highest value signal. This is the right priority ordering.

### What could be improved

**Issue 1: Points are additive with no interaction terms.**

A stock with earnings_soon AND thesis_BROKEN AND drawdown gets 25+25+50+40 = 140 points. A clean BUY candidate with QG rank #1 and never analysed gets 20+20 = 40 points. The first stock is correctly prioritized, but the interaction between signals matters:
- BROKEN thesis + major drawdown = consider selling immediately (different from analyse urgency)
- Never analysed + QG top-10 = screening priority, not portfolio urgency

The current system treats these as commensurable when they represent qualitatively different decisions.

**Issue 2: No urgency decay function.**

"Stale verdict (>14 days)" gets 15 points regardless of whether it has been 15 days or 60 days. A stock not analysed for 60 days with a 30-day-old QG rank should be prioritized differently than one that is 15 days old.

**Recommendation**:
1. Replace the linear stale bonus with an exponential decay: `min(15, 2 * ln(days_since))` for days_since > 7
2. Add a SELL_URGENCY flag alongside ANALYSE_URGENCY — when thesis is BROKEN with drawdown > threshold, this is a sell signal that should surface separately from the analysis queue
3. Log the top-5 selection reasons per cycle for retroactive analysis (partially done via `logger.debug`)

---

## Section 7: Pipeline Timing

### Current design
- Overnight only: cron at 02:00 UTC Tue–Sat
- 60-second controller poll interval (K8s)
- No intraday triggers
- No pre-market or post-earnings immediate analysis

### Issues and recommendations

**Issue 1: Earnings releases are not triggering immediate reanalysis.**

A company reports earnings at 7:00 PM after market close. The next pipeline run is at 02:00 AM. For 7 hours, portfolio positions with earnings releases have no fresh analysis. During this 7-hour window, the stock may move ±15% in after-hours trading.

**Recommendation**: Add an **earnings event trigger** that runs immediately when an earnings release is detected in `news_context` or `earnings_context`. Implementation: add a `trigger_type: earnings` flag to the cycle, run a streamlined pipeline (skip screeners, run primary agents only).

**Issue 2: Pre-market analysis window is underutilized.**

European markets open at 03:00 AM ET, US pre-market starts at 04:00 AM ET. Running the overnight pipeline at 02:00 UTC = 09:00 PM ET (evening, not pre-market). Consider shifting to 06:00 UTC = 01:00 AM ET to capture pre-market setup.

**Issue 3: No intraday portfolio monitoring.**

For existing positions, a lightweight "portfolio health check" (fundamentals + technical only, no full agent suite) could run intraday at 12:00 UTC and 16:00 UTC (market open + mid-day), flagging any dramatic changes for human review.

**Recommended cadence**:
- **02:00 UTC Tue–Sat**: Full overnight pipeline (current)
- **12:00 UTC weekdays**: Portfolio-only lightweight check (fundamentals + technicals, no agents — just freshness alerts)
- **Trigger-based**: Earnings releases detected in news → immediate streamlined reanalysis

---

## Section 8: Error Handling and Resilience

### Current design
- Max 2 retries per step
- 20-minute stuck timeout for `running` steps
- 24-hour cycle expiry
- Failed screeners count as PASS (fail-safe default)
- Adversarial and research failures marked `completed` (don't block synthesis)

### Analysis

**Max 2 retries**: Appropriate for a batch overnight system. Most failures are transient (rate limits, network). 2 retries catches transient failures without creating infinite loops. Third failure = permanent mark as failed.

**20-minute stuck timeout**: Appropriate for CLI agents (Claude/Gemini) which can take 5–10 minutes for complex analysis. 20 minutes gives 2× buffer. However, API agents (Simons via Groq, Lynch via DeepSeek) should not take 20 minutes — consider separate timeouts: 20 minutes for CLI agents, 3 minutes for API agents.

**24-hour cycle expiry**: Correct for overnight batch. A cycle that started at 02:00 UTC and is still "active" at 02:00 UTC the next day has almost certainly stalled — expire it and start fresh.

**Fail-open defaults for blocking steps (research, adversarial)**: Correct design. A pipeline that fails because one optional enrichment step is down is worse than proceeding with missing context. The agents can note data limitations in their reasoning.

**Issue: No dead-letter queue or alerting for repeated failures.**

If the same ticker fails data_fetch 3 consecutive cycles (6 days), there is no alerting mechanism. The ticker silently drops off the analysis rotation. A position being monitored could go weeks without analysis if its data fetch is consistently failing.

**Recommendation**: Add a `consecutive_cycle_failures` counter per ticker. If a ticker fails across 3 cycles, emit a Prometheus metric / log ERROR-level event for human review. The controller already tracks metrics via `pipeline_cycle_duration` and `pipeline_cycles_total` — extend this pattern.

---

## Section 9: Scaling

### Current constraints

- **Groq semaphore**: 2 concurrent (30 RPM free tier)
- **DeepSeek semaphore**: 15 concurrent (60 RPM)
- **Claude CLI**: 2 workers per agent = 2 concurrent tickers per CLI agent (6 total Claude slots)
- **Gemini CLI**: 2 workers per agent = 2 concurrent tickers per CLI agent (6 total Gemini slots)
- **Budget**: `MAX_WATCHLIST_TICKERS = 15` + all portfolio tickers

### Analysis for 100+ ticker scenario

At current settings: 15 watchlist + ~10 portfolio = ~25 tickers. Each ticker needs ~9 agent calls. That is 225 agent calls per cycle. With 2 parallel Claude workers (3 agents × 2) and 2 parallel Gemini workers (3 agents × 2), the theoretical throughput is:
- Claude wall time: `(25 tickers × 3 Claude agents × ~6 min/call) / 2 workers = 225 minutes`
- Gemini wall time: similar

This means **full analysis of 25 tickers takes ~3–4 hours** — acceptable for overnight. At 100 tickers, it would take ~12+ hours, which overruns the overnight window.

### Scaling recommendations

**Short-term (no architectural change needed)**:
1. Increase `workers_per_agent` from 2 to 3 for CLI agents — this requires validating that HB LXC can handle 3 concurrent Claude screens without hitting memory limits (6GB RAM on HB LXC, per MEMORY.md)
2. Reduce MAX_WATCHLIST_TICKERS progressively as portfolio grows — the current 15 cap is appropriate

**Medium-term (architectural change)**:
1. **Incremental analysis**: Track which data keys changed since last analysis. If fundamentals haven't changed significantly and technical indicators are the same, skip Warren (who focuses on fundamentals). Only run agents whose primary data sources have materially changed.
2. **Tier-based analysis depth**: Top-conviction portfolio positions get the full 9-agent suite. Watchlist candidates get 3-4 agents (screeners + Warren + one Gemini) unless they pass a deep-analysis gate.

**The key insight**: Not all tickers need all agents every cycle. A stock like a permanent Berkshire-style holding that hasn't changed fundamentals in 90 days should be re-analyzed with 3 agents (lighter touch), not 9. Reserve full analysis for: (a) post-earnings, (b) thesis health events, (c) new candidates.

---

## Section 10: Multi-Agent Architecture Patterns — Research Synthesis

### What the field knows (2024–2025)

Based on published research and production system patterns:

**CrewAI / AutoGen pattern (hierarchical with coordinator)**:
A "manager" agent decomposes tasks, assigns sub-agents, and aggregates results. The manager has full visibility into sub-agent outputs. This approach produces **better task decomposition** but suffers from **coordinator bias** — the manager's framing constrains sub-agent reasoning.

For investment decisions: a coordinator-agent telling Warren "analyze the growth prospects of AAPL" introduces framing that affects Warren's output. Not ideal.

**LangGraph / CAMEL pattern (graph-based with message passing)**:
Agents communicate via a shared message graph. Each node can read the outputs of preceding nodes. This enables **iterative refinement** but risks **information cascades** if run sequentially.

The investmentology pipeline uses a superior variant: **parallel independence with gated integration**. All agents run in parallel (independence preserved), integration happens only at debate/synthesis (gated by convergence check). This is architecturally closer to the "mixture of experts" (Shazeer et al., 2017) pattern than to agentic frameworks.

**Forecasting tournaments / Superforecasting insights (Tetlock, 2015)**:
- **Diversity beats expertise** for aggregate accuracy: 50 diverse moderate forecasters outperform 10 domain experts
- **Calibration matters more than individual accuracy**: the system needs to track P(correct | stated confidence)
- **Reason aggregation beats opinion aggregation**: preserve the *reasons* agents gave, not just their verdicts — this is partially implemented via `reasoning` field in agent_signals

**Recommendation: Implement "reason-aware synthesis"**
The current synthesis aggregates verdict votes with calibration-adjusted weights. A stronger approach: the synthesis step should also receive the top 3 reasons from the most confident agent on each side, and the CIO synthesizer should explicitly reference which arguments were most persuasive. This moves from "vote counting" to "argument evaluation."

---

## Summary: Priority Recommendations

Ordered by impact vs. implementation effort:

| # | Recommendation | Impact | Effort |
|---|---------------|--------|--------|
| 1 | **Macro regime pre-classifier** — run before agents, provide regime label as shared context | High | Low |
| 2 | **Earnings event trigger** — immediate streamlined reanalysis on earnings releases | High | Medium |
| 3 | **Debate: allow direction changes with justification** — remove hard constraint, require reason string | High | Low |
| 4 | **Add Data Analyst as debate moderator** — identify specific factual points of contention | Medium | Low |
| 5 | **Earn `earnings_context` CRITICAL status** — add to CRITICAL_KEYS, reduce threshold to 6h | Medium | Low |
| 6 | **Dead-letter alerting** — flag tickers with 3+ consecutive cycle failures | Medium | Low |
| 7 | **Scouts in debate** — include Simons/Lynch when their signal diverges from primary consensus | Medium | Medium |
| 8 | **Reason-aware synthesis** — pass top arguments to CIO, not just verdict counts | Medium | Medium |
| 9 | **Ticker selection: exponential staleness decay** — replace flat 15-point bonus with ln() decay | Low | Low |
| 10 | **Incremental analysis** — skip agents whose primary data sources haven't materially changed | High | High |
| 11 | **Intraday portfolio health check** — lightweight freshness run at 12:00 UTC weekdays | Medium | Medium |
| 12 | **Separate API vs. CLI stuck timeouts** — 3 min for API agents, 20 min for CLI agents | Low | Low |

---

## Architecture Assessment: What Is Working Well

Before closing, it is worth noting what the current pipeline does particularly well:

1. **The agent-first, event-driven architecture** replaces a brittle monolithic orchestrator with a resilient state machine. Any step can fail and be retried independently. This is production-grade design.

2. **Calibration-adjusted weights** (`_apply_calibration_weights` in controller) are the correct long-term path to improving ensemble accuracy. Once 100+ decisions are logged, the calibration loop becomes the most powerful accuracy improvement mechanism in the system.

3. **Conditional agents** (Income Analyst, Sector Specialist) add targeted expertise without burdening every analysis. This is the right architecture — avoid fat-tailed agent costs on generic analyses.

4. **The pre-filter → screener → gate → analysis two-phase design** is excellent. Running 4 API screeners (cheap, fast) before committing expensive CLI agent slots (slow, subscription) is economically sound. The supermajority gate (3/4 screeners must pass) is a principled quality threshold.

5. **The `research_briefing` step** (Gemini synthesizing news/analyst data before agents run) is a recent addition that improves signal quality without breaking independence. Agents receive synthesized facts, not each other's opinions.

6. **Debate fires conditionally** (not universally): Running debate for every ticker would double the analysis time and rarely improve accuracy for consensus verdicts. Conditional triggering on disagreement is the right design.

7. **The portfolio-first selection guarantee** ensures that active positions are never starved of analysis attention, regardless of their scoring rank.

---

*Sources: Galton (1907) "Vox Populi"; Surowiecki (2004) "The Wisdom of Crowds"; Banerjee (1992) "A Simple Model of Herd Behavior"; Bikhchandani et al. (1992) "A Theory of Fads, Fashion, Custom, and Cultural Change"; Tetlock & Gardner (2015) "Superforecasting"; Mason & Mitroff (1981) "Challenging Strategic Planning Assumptions"; Breiman (1996) "Bagging Predictors"; Shazeer et al. (2017) "Outrageously Large Neural Networks (MoE)"; Good Judgment Project open data (2013–2019). Multi-agent framework knowledge from public documentation of CrewAI, AutoGen, LangGraph, CAMEL.*
