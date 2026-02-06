# Investmentology

AI-powered institutional-grade investment advisory platform. A hedge fund analyst in a box.

## Architecture: 6-Layer Sequential Pipeline

```
5000+ stocks → [L1: Quant Gate] → 100 → [L2: Competence] → 30-50
→ [L3: Multi-Agent] → scored → [L4: Adversarial] → vetted
→ [L5: Timing/Sizing] → executable → [L6: Learning] → feedback loop
```

### Layer 1: Quantitative Gate (Greenblatt Magic Formula)
- Pure math, no LLM. ROIC + Earnings Yield ranking.
- Source: `src/investmentology/quant_gate/`
- Data: yfinance for fundamentals

### Layer 2: Competence Filter (Buffett)
- LLM-assessed: Circle of Competence + Moat Analysis
- Source: `src/investmentology/competence/`

### Layer 3: Multi-Agent Analysis (Tri-Modal Consensus)
Four independent agents with weighted voting:
| Agent | Focus | Model |
|-------|-------|-------|
| Warren | Fundamentals, intrinsic value | DeepSeek R1 |
| Soros | Macro, cycles, geopolitics | Gemini |
| Simons | Technicals, momentum, timing | Groq Llama |
| Auditor | Risk, correlation, portfolio | DeepSeek V3 |
- Source: `src/investmentology/agents/`

### Layer 4: Adversarial Check (Munger)
- Bias checklist (25 cognitive biases)
- Kill The Company exercise
- Inversion + Pre-Mortem analysis
- Source: `src/investmentology/adversarial/`

### Layer 5: Timing & Sizing (Howard Marks)
- Cycle detection, pendulum reading
- Kelly Criterion sizing (after 50+ calibrated decisions)
- Source: `src/investmentology/timing/`

### Layer 6: Continuous Learning
- Decision Registry: ALL decisions (executed, rejected, missed)
- Prediction tracking with settlement dates
- Calibration feedback loop
- Source: `src/investmentology/learning/`

## Current Phase: Phase 1 (Foundation)

Build priority order:
1. **Decision Registry** - PostgreSQL schema for logging ALL decisions
2. **Quant Gate** - Greenblatt screener (pure Python, no LLM)
3. **Data Integration** - yfinance + Alpaca paper trading
4. **Weekly Review** - Automated portfolio review process

### Phase 1 "Done" Criteria
- [ ] Magic Formula runs on 5000+ stocks weekly
- [ ] Top 100 logged to Decision Registry
- [ ] Paper portfolio tracking operational
- [ ] 100+ decisions logged

## Outline Collection

All design docs live in Outline collection `4A1fLp8aqX` (Learning Investmentology).
Use knowledge MCP to read/update: `mcp__knowledge__read_document`, `mcp__knowledge__update_document`

## Data Sources

| Source | Use | Cost |
|--------|-----|------|
| yfinance | OHLCV, fundamentals | Free |
| Alpaca | Paper trading API | Free tier |
| SEC EDGAR | 10-K/10-Q filings | Free |
| sec-api.io | 13F holdings, Form 4 | Free tier |

## Coding Standards

- Python 3.13, type hints everywhere
- pytest for testing
- Structured logging (JSON)
- Every analysis MUST be logged to Decision Registry
- Every prediction MUST have a settlement date

## Collaboration Workflow

Use `scripts/collaborate.py` for Claude-Gemini planning sessions.
Target collection: `4A1fLp8aqX` (Learning Investmentology)

```bash
python3 scripts/collaborate.py start "Topic" --collection 4A1fLp8aqX --goal "Goal description"
```

## Critical Rules

1. **PAPER TRADING ONLY** - No real money trades without explicit human approval
2. **LOG EVERYTHING** - Every analysis, every decision, every prediction
3. **NEVER present stale data as current** - Always include data source + timestamp
4. **48-hour minimum hold** - This is NOT a day trading system
5. **Confidence calibration** - Track if 70% confidence calls are actually correct 70% of the time
