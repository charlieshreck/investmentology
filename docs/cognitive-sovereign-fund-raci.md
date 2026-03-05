# Cognitive Sovereign Fund: RACI & Operational Flow

## Operating Cycles (When Things Run)

```
WEEKLY (Sunday night)
  L0: Universe Scout     ── defines the 5,000+ stock universe
  L1: Quant Gate         ── screens to ~100 candidates (pure math)

OVERNIGHT (Tue-Sat 02:00 UTC, post-screen on Sunday)
  L2: Selection Desk     ── picks 10-30 for deep analysis
  L3: Data Desk          ── gathers all data each analyst needs
  L4: Analysis Desk      ── 7 strategy agents form independent views
  L5: Challenge Round    ── debate + adversarial review
  L6: Board Room         ── synthesis + final recommendation
  L7: Execution Desk     ── sizing + timing + allocation

DAILY (08:00 ET premarket, 16:15 ET post-close)
  M1: Price Monitor      ── update prices, check alerts, settle predictions
  M2: Position Review    ── re-analyze held positions (thesis health)
  M3: Sell Engine        ── check stop losses, circuit breakers
  M4: Daily Intel        ── compile briefing with actions

ON-DEMAND (user triggers from PWA)
  OD1: Single Analysis   ── full L3-L7 on one ticker
  OD2: Screener Run      ── custom screen with filters

CONTINUOUS (background)
  C1: Learning Engine    ── settle predictions, compute attribution
  C2: Memory Keeper      ── maintain Qdrant + Neo4j, generate embeddings
```

---

## Layer Map: What Happens at Each Stage

### L0: Universe Definition
**Current**: NASDAQ screener API → 5,000-7,000 US stocks (undocumented API)
**Gap**: No international stocks, no ETFs/bonds/gold, no pre-filtering by liquidity
**Future**: Universe agents that monitor new IPOs, delistings, emerging sectors

### L1: Quantitative Gate (Pure Math, No LLM)
**Current**: Greenblatt (ROIC + earnings yield) + Piotroski (9-point health) + Altman Z → composite score → top 100
**Gap**: Only one screening philosophy (value-oriented). Misses momentum, growth, or thematic plays.
**Future**: Multiple screening lenses that feed different strategy agents

### L2: Selection Desk (WHO DECIDES WHAT TO ANALYZE?)
**Current**: Mechanical — top N by composite score. Or user picks from PWA.
**Gap**: No intelligence in selection. A macro agent should say "credit is deteriorating, screen for defensive names." A momentum agent should say "tech breakout happening, screen for leaders."
**Future**: Strategy agents REQUEST analysis based on their worldview + market conditions

### L3: Data Desk (GATHERING)
**Current**: Enricher pre-fetches everything into a flat payload. All agents get the same data.
**Gap**: Agents can't request additional data. Forensic agent can't say "I need the last 3 10-Q filings" mid-analysis.
**Future**: Agents have tool access — each fetches what their role requires

### L4: Analysis Desk (HYPOTHESIS FORMATION)
**Current**: 4 agents run in parallel, each with a fixed prompt + pre-loaded data → JSON output
**Gap**: Agents are prompt-and-respond, not reason-and-act. No tool use, no memory query, no delegation.
**Future**: Each agent is a ReAct loop with domain-specific tools + memory access

### L5: Challenge Round
**Current**: L3.5 debate (all see each other's stances) + L4 Munger adversarial (bias checklist, kill the company)
**Gap**: Debate direction-lock is prompt-only. Munger is a single LLM call, not a structured red team.
**Future**: Structured adversarial with specific challenge patterns (value trap, accounting fraud, late cycle)

### L6: Board Room (SYNTHESIS)
**Current**: Mathematical weighted vote → deterministic score-to-verdict ladder. No narrative.
**Gap**: No CIO agent. No conflict resolution patterns. No "explain why" narrative.
**Future**: Board CIO reads all stances + adversarial + memory + allocation context → narrative recommendation

### L7: Execution Desk
**Current**: Kelly criterion sizing + pendulum multiplier. Paper trading only.
**Gap**: No allocation framework (100% equities). Pendulum only affects size, not asset class.
**Future**: Asset allocation by regime + per-pick sizing within equity allocation

---

## RACI Matrix

### Key
- **R** = Responsible (does the work)
- **A** = Accountable (owns the outcome, makes final call)
- **C** = Consulted (provides input before decision)
- **I** = Informed (notified after decision)

### Agents / Roles

| ID | Role | Type | Description |
|----|------|------|-------------|
| **SCOUT** | Universe Scout | Computation | Defines stock/asset universe |
| **SCREEN** | Quant Screener | Computation | Math-based filtering |
| **SELECT** | Selection Desk | LLM Agent | Decides what to analyze in depth |
| **MACRO** | Macro Strategist (Soros) | LLM Agent | Macro cycles, geopolitics, reflexivity |
| **VALUE** | Value Analyst (Warren) | LLM Agent | Intrinsic value, moats, quality compounding |
| **QUANT** | Quant Analyst (Simons) | LLM Agent | Technical patterns, momentum, statistical |
| **RISK** | Risk Controller (Auditor) | LLM Agent | Portfolio risk, correlation, concentration |
| **CREDIT** | Credit Analyst (Marks) | LLM Agent | Credit cycles, spreads, "where in cycle" |
| **FORENSIC** | Forensic Accountant | LLM Agent | Fraud detection, accounting quality, short thesis |
| **BENCH** | Benchmark Analyst (Bogle) | LLM Agent | Passive benchmark comparison, opportunity cost |
| **SENTI** | Sentiment Analyst | LLM Agent | News/social/insider flow, crowd behavior |
| **MUNGER** | Adversarial Reviewer | LLM Agent | Bias check, kill the company, devil's advocate |
| **CIO** | Board CIO | LLM Agent | Final synthesis, narrative, conflict resolution |
| **MEMORY** | Memory Keeper | Agent/System | Qdrant + Neo4j — historical patterns, similar situations |
| **LEARN** | Learning Engine | Computation | Attribution, prediction settlement, weight adjustment |
| **SIZE** | Position Sizer | Computation | Kelly criterion, VaR, allocation |
| **MONITOR** | Daily Monitor | Computation | Price tracking, alerts, sell engine |
| **BRIEF** | Briefing Builder | Computation | Daily intel compilation |

### RACI by Decision

| Decision | R | A | C | I |
|----------|---|---|---|---|
| **What universe to screen** | SCOUT | MACRO, SELECT | — | ALL |
| **Which screening criteria** | SCREEN | SELECT | MACRO, VALUE | QUANT |
| **Which tickers get deep analysis** | SELECT | CIO | MACRO, QUANT, MEMORY | ALL |
| **Gather fundamental data** | VALUE | VALUE | — | ALL |
| **Gather macro/cycle data** | MACRO | MACRO | CREDIT | ALL |
| **Gather technical data** | QUANT | QUANT | — | ALL |
| **Gather sentiment/news data** | SENTI | SENTI | — | ALL |
| **Gather SEC filings / accounting** | FORENSIC | FORENSIC | VALUE | ALL |
| **Gather credit/fixed income data** | CREDIT | CREDIT | MACRO | ALL |
| **Query historical memory** | MEMORY | MEMORY | ALL | ALL |
| **Form fundamental thesis** | VALUE | VALUE | MEMORY | ALL |
| **Form macro thesis** | MACRO | MACRO | CREDIT, MEMORY | ALL |
| **Form technical thesis** | QUANT | QUANT | MEMORY | ALL |
| **Form risk assessment** | RISK | RISK | ALL | ALL |
| **Detect accounting red flags** | FORENSIC | FORENSIC | VALUE, RISK | ALL |
| **Compare to passive benchmark** | BENCH | BENCH | QUANT | ALL |
| **Assess credit cycle impact** | CREDIT | CREDIT | MACRO, RISK | ALL |
| **Gauge market sentiment** | SENTI | SENTI | QUANT | ALL |
| **Challenge all theses (debate)** | ALL AGENTS | CIO | — | MEMORY |
| **Adversarial review** | MUNGER | MUNGER | ALL | CIO |
| **Veto on risk grounds** | RISK | RISK | CIO | ALL |
| **Veto on fraud grounds** | FORENSIC | FORENSIC | CIO | ALL |
| **Final verdict** | CIO | CIO | ALL | USER, MEMORY |
| **Position sizing** | SIZE | CIO | RISK | ALL |
| **Asset allocation** | SIZE | CIO | MACRO, CREDIT | ALL |
| **Monitor held positions** | MONITOR | RISK | BRIEF | USER |
| **Sell decision** | MONITOR | CIO | RISK, VALUE | USER |
| **Compile daily briefing** | BRIEF | BRIEF | ALL | USER |
| **Settle predictions** | LEARN | LEARN | — | ALL |
| **Adjust agent weights** | LEARN | LEARN | MEMORY | ALL |
| **Store analysis to memory** | MEMORY | MEMORY | — | LEARN |
| **Retrieve similar situations** | MEMORY | MEMORY | — | ALL |

---

## Operational Flow Diagram

```
                    ┌─────────────────────────────────────────┐
                    │           WEEKLY CYCLE                   │
                    │                                         │
                    │  SCOUT ─── define universe (5000+)      │
                    │    │                                    │
                    │    ▼                                    │
                    │  SCREEN ── quant gate (→ 100)           │
                    │    │                                    │
                    │    ▼                                    │
                    │  SELECT ── pick 10-30 for analysis      │
                    │    │       (informed by MACRO regime,    │
                    │    │        QUANT momentum signals,      │
                    │    │        MEMORY similar periods)      │
                    └────┼────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────────────────────────────┐
          │              ▼     ANALYSIS PIPELINE (per ticker)   │
          │                                                     │
          │  ┌─── MEMORY: "what happened last time?" ───────┐   │
          │  │    (Qdrant similar situations,                │   │
          │  │     Neo4j verdict chains,                     │   │
          │  │     prediction accuracy for this ticker)      │   │
          │  └──────────────────┬────────────────────────────┘   │
          │                     │ context injected               │
          │                     ▼                                │
          │  ┌──────────────────────────────────────────────┐    │
          │  │  PARALLEL ANALYSIS (7 strategy agents)       │    │
          │  │                                              │    │
          │  │  Each agent has:                             │    │
          │  │  - Domain-specific TOOLS (MCP, web, DB)      │    │
          │  │  - MEMORY context (similar past situations)   │    │
          │  │  - Own TRACK RECORD (accuracy by regime)      │    │
          │  │                                              │    │
          │  │  VALUE ──── fundamentals + SEC filings        │    │
          │  │  MACRO ──── FRED + news + Fed minutes         │    │
          │  │  QUANT ──── technicals + momentum             │    │
          │  │  CREDIT ─── yields + spreads + cycle          │    │
          │  │  FORENSIC ─ 10-K deep dive + accounting       │    │
          │  │  SENTI ──── Reddit + news + insider flow      │    │
          │  │  BENCH ──── SPY comparison + opportunity cost  │    │
          │  │                                              │    │
          │  │  Any agent can REQUEST more data mid-analysis │    │
          │  │  via tool calls (web search, SEC, Reddit...)  │    │
          │  └──────────────┬───────────────────────────────┘    │
          │                 │ 7 independent stances              │
          │                 ▼                                    │
          │  ┌──────────────────────────────────────────────┐    │
          │  │  CHALLENGE ROUND                             │    │
          │  │                                              │    │
          │  │  1. DEBATE: all 7 see each other's stances   │    │
          │  │     → can adjust confidence, NOT direction   │    │
          │  │                                              │    │
          │  │  2. MUNGER: adversarial review               │    │
          │  │     → bias check, kill-the-company, inversion│    │
          │  │     → can VETO (hard block) or CAUTION       │    │
          │  │                                              │    │
          │  │  3. RISK veto check                          │    │
          │  │     → concentration, liquidity, correlation   │    │
          │  │                                              │    │
          │  │  4. FORENSIC veto check                      │    │
          │  │     → accounting red flags = hard block       │    │
          │  └──────────────┬───────────────────────────────┘    │
          │                 │ vetted stances                     │
          │                 ▼                                    │
          │  ┌──────────────────────────────────────────────┐    │
          │  │  BOARD ROOM (CIO)                            │    │
          │  │                                              │    │
          │  │  Reads: all stances + vetoes + memory +      │    │
          │  │         allocation context + regime           │    │
          │  │                                              │    │
          │  │  Produces:                                   │    │
          │  │  - Narrative recommendation (plain English)   │    │
          │  │  - Verdict (STRONG_BUY → AVOID)              │    │
          │  │  - Conflict resolution explanation            │    │
          │  │  - "What would make us wrong" pre-mortem      │    │
          │  │  - Can adjust math verdict ±1 level           │    │
          │  └──────────────┬───────────────────────────────┘    │
          │                 │                                    │
          │                 ▼                                    │
          │  ┌──────────────────────────────────────────────┐    │
          │  │  EXECUTION                                   │    │
          │  │                                              │    │
          │  │  SIZE: Kelly + VaR + regime allocation        │    │
          │  │  RISK: final position limit / sector check    │    │
          │  │  MEMORY: store verdict + signals + regime     │    │
          │  │  LEARN: log predictions (30d, 90d)            │    │
          │  └──────────────────────────────────────────────┘    │
          └─────────────────────────────────────────────────────┘

          ┌─────────────────────────────────────────────────────┐
          │  DAILY CYCLE                                        │
          │                                                     │
          │  MONITOR ── price updates, alert checks             │
          │    │                                                │
          │    ├── sell engine (stops, circuit breakers)         │
          │    │     └── RISK consulted on position-level risk  │
          │    │                                                │
          │    ├── position review (thesis health check)        │
          │    │     └── VALUE + MACRO re-assess held positions │
          │    │                                                │
          │    └── prediction settlement                        │
          │          └── LEARN updates agent accuracy            │
          │                                                     │
          │  BRIEF ── compile daily intel                       │
          │    │       (actions, allocations, market context)    │
          │    │                                                │
          │    └── USER sees briefing in PWA                    │
          └─────────────────────────────────────────────────────┘

          ┌─────────────────────────────────────────────────────┐
          │  CONTINUOUS BACKGROUND                              │
          │                                                     │
          │  LEARN:                                             │
          │    - Settle 30d/90d predictions against actuals     │
          │    - Compute per-agent accuracy BY REGIME           │
          │    - Adjust weights: good agents in this regime ↑   │
          │    - Track signal accuracy (which tags predict?)    │
          │                                                     │
          │  MEMORY:                                            │
          │    - Generate embeddings for new analyses           │
          │    - Build verdict chains in Neo4j                  │
          │    - Index "similar situations" for retrieval       │
          │    - Decay stale knowledge (quarterly)              │
          │                                                     │
          │  MACRO (passive):                                   │
          │    - Monitor regime shifts (fear/greed transitions) │
          │    - Flag "regime change" → trigger re-analysis     │
          │      of all held positions                          │
          └─────────────────────────────────────────────────────┘
```

---

## Agent Tool Access Matrix

Each LLM agent needs specific tools. Not "all agents get all tools."

| Agent | Data Tools | Memory Tools | Action Tools |
|-------|-----------|--------------|-------------|
| **VALUE** | yfinance, SEC EDGAR (10-K, 10-Q), finnhub earnings | Qdrant (similar valuations), Neo4j (verdict history) | Request deeper SEC filing |
| **MACRO** | FRED, web search (Fed minutes), news search | Qdrant (similar macro regimes), Neo4j (regime→outcome) | Request economic calendar |
| **QUANT** | yfinance OHLCV, technical indicators | Qdrant (similar technical setups), Neo4j (pattern outcomes) | — |
| **CREDIT** | FRED (yields, spreads), web search (credit news) | Qdrant (similar credit conditions) | — |
| **FORENSIC** | SEC EDGAR (10-K, 10-Q, 8-K, DEF-14A), yfinance | Qdrant (past accounting flags) | Request specific SEC filing section |
| **SENTI** | Reddit MCP, web search, finnhub social, news | Qdrant (past sentiment extremes) | — |
| **BENCH** | yfinance (SPY, sector ETFs), FRED (risk-free rate) | Qdrant (past alpha vs index) | — |
| **RISK** | Portfolio DB, yfinance (correlations) | Neo4j (position relationships) | VETO power |
| **MUNGER** | All agent stances (read-only) | Qdrant (past bias patterns) | VETO power |
| **CIO** | All agent stances + all memory | Full Qdrant + Neo4j | Verdict adjustment ±1 |
| **SELECT** | Quant gate results, regime, watchlist | Qdrant (what worked in similar regimes) | Trigger analysis |
| **MEMORY** | PostgreSQL, Qdrant, Neo4j | — (IS the memory) | Embed, index, retrieve |
| **MONITOR** | yfinance prices, portfolio DB | — | Alert, sell signal |

---

## LLM Provider Assignment

Based on provider strengths and infrastructure constraints:

| Agent | Provider | Reasoning |
|-------|----------|-----------|
| **VALUE** | DeepSeek | Good at structured analysis, cheap ($0.01), handles long SEC filing context |
| **MACRO** | Gemini CLI (proxy) | Broad world knowledge, good at geopolitics, real-time web access built-in |
| **QUANT** | Groq (Llama 3.3) | Fast, free, good at pattern recognition in structured data |
| **CREDIT** | Groq | Fast, free, structured credit data analysis |
| **FORENSIC** | Claude CLI (proxy) | Best at nuanced reasoning, catching subtle inconsistencies in filings |
| **SENTI** | Groq | Fast, free, lightweight sentiment classification |
| **BENCH** | Groq | Fast, free, simple comparison math + narrative |
| **RISK** | Claude CLI (proxy) | Nuanced risk assessment needs strongest reasoning model |
| **MUNGER** | DeepSeek | Good at structured adversarial thinking, cheap |
| **CIO** | DeepSeek | Synthesis of all stances, cheap for long context |
| **SELECT** | Groq | Fast selection decisions based on structured data |

**HB LXC constraint**: Claude + Gemini CLI = 2 concurrent max.
Pipeline: MACRO (Gemini) + FORENSIC or RISK (Claude) run first in CLI pair.
Then: VALUE (DeepSeek) + QUANT + CREDIT + SENTI + BENCH (all Groq) run in parallel.
Then: RISK or FORENSIC (Claude, whichever didn't run) takes second CLI slot.

---

## What's Broken That Must Be Fixed First

Before building new agents, these bugs undermine the entire system:

| # | Bug | Impact | Fix Complexity |
|---|-----|--------|----------------|
| 1 | Qdrant stores `vector: None` | All semantic memory is broken | Medium (need embedding model) |
| 2 | Neo4j is write-only | Historical patterns never inform agents | Low (wire existing queries) |
| 3 | Attribution is circular | Agent weights adjust on consensus, not outcomes | Medium (use settled predictions) |
| 4 | Prediction settlement bug | Direction correctness always "true" | Low (compare price change, not absolute) |
| 5 | SPY drawdown always 0 | Circuit breaker never fires | Trivial |
| 6 | Sector map always empty | Concentration alerts never fire | Trivial |
| 7 | 13F fetches wrong filings | Institutional data is empty | Medium (different SEC API approach) |
| 8 | `total_liabilities = totalDebt` | Understates liabilities | Low (use yfinance field) |
| 9 | 15+ yfinance fields unused | FCF, P/E, short interest, analyst targets missing | Low |
| 10 | Sector ETF perf computed but unused | Agents miss sector rotation signals | Trivial |

---

## Open Questions for Collaboration

1. **Agent autonomy**: Full ReAct loop (agent calls tools mid-reasoning) vs. structured tool access (pre-fetch + prompt)? ReAct is more powerful but costs 3-5x more tokens per agent.

2. **Selection intelligence**: Should strategy agents REQUEST what to analyze, or should a dedicated Selection Desk agent decide based on all inputs?

3. **Memory architecture**: Fix current Qdrant+Neo4j or redesign? Current schema is okay but embeddings and read queries need real work.

4. **How many LLM calls per analysis?**: Current=~10. With 7 agents + debate + Munger + CIO = ~20. With ReAct tool use, could be 30-50. What's the cost/latency budget?

5. **Multi-asset**: When do we add bonds/gold/commodity analysis? Phase 1 or later?

6. **CLI bottleneck**: HB LXC can only run 2 CLI calls at once. Does the sequencing above (Gemini+Claude first, then Groq/DeepSeek parallel) work, or do we need a bigger LXC?

7. **What does "start over" mean?**: Rewrite the agent framework from scratch with ReAct + tools? Or fix the 10 bugs above and evolve incrementally?
