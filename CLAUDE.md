# Investmentology

AI-powered institutional-grade investment advisory platform. A hedge fund analyst in a box.

## Deployment Architecture

**CRITICAL: This is a K8s application, NOT an LXC app.**

```
┌─────────────────────────────────────────────────────────┐
│  Agentic K8s Cluster (10.20.0.0/24)                     │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Pod: investmentology (namespace: investmentology) │  │
│  │  Image: ghcr.io/charlieshreck/investmentology-api  │  │
│  │  serve.py → FastAPI (API + Vite PWA on port 80)    │  │
│  │  NodePort: 30580                                   │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         ▲
         │ Caddy reverse proxy (10.10.0.1)
         │ haute-banque.kernow.io → 10.20.0.40:30580
         ▲
         │ AdGuard DNS rewrite
         │
      Browsers
```

### What runs WHERE

| Component | Where | Details |
|-----------|-------|---------|
| **PWA + API** | **Agentic K8s pod** | `serve.py` serves both FastAPI API and Vite PWA static files |
| **Database** | Agentic K8s (PostgreSQL) | Decision registry, predictions, portfolio |
| **CI/CD** | GitHub Actions → GHCR → ArgoCD | Push to main → build image → auto-deploy |
| **Claude CLI agent** | HB LXC (10.10.0.101) | CLI subscription analysis (NOT API) |
| **Gemini CLI agent** | HB LXC (10.10.0.101) | CLI subscription analysis (NOT API) |
| **Overnight pipeline** | HB LXC cron (02:00 UTC Tue-Sat) | `scripts/overnight-pipeline.sh` |

### DO NOT
- **NEVER** treat the LXC as the deployment target for the PWA or API
- **NEVER** point Caddy/DNS to the LXC for web traffic (10.10.0.101)
- **NEVER** create Express/nginx servers on the LXC to serve the PWA
- The LXC is for **CLI agents only** (Claude Code + Gemini CLI screens)

### Build & Deploy
1. Edit code in `/home/investmentology/pwa/` (frontend) or `src/` (backend)
2. `cd pwa && npx vite build` to verify locally
3. `git commit && git push` → GitHub Actions builds multi-stage Docker image
4. ArgoCD auto-syncs to agentic cluster (`k8s/argocd-app.yaml` → `10.20.0.40:6443`)
5. Restart deployment if needed: `kubectl rollout restart deployment/investmentology -n investmentology`

### Key Files
- `Dockerfile` — Multi-stage: builds PWA (node), then Python API + copies `pwa/dist`
- `serve.py` — FastAPI app that serves API routes AND PWA static files (SPA fallback)
- `k8s/base/deployment.yaml` — K8s deployment (image, env, probes)
- `k8s/base/controller-deployment.yaml` — K8s deployment for pipeline controller
- `k8s/base/service.yaml` — NodePort 30580
- `k8s/base/ingress.yaml` — Traefik ingress for `haute-banque.kernow.io`
- `k8s/argocd-app.yaml` — ArgoCD Application targeting agentic cluster
- `.github/workflows/ci.yml` — GitHub Actions CI/CD pipeline

---

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

### Layer 3: Multi-Agent Analysis (Agent-First Pipeline)

**Architecture**: Agent-first, event-driven pipeline with per-agent independence. Each agent runs across all its tickers independently (not per-ticker-all-agents). State tracked in `invest.pipeline_state` table with 24h staleness window.

#### Agent Skills Framework

9 investment agents + Data Analyst + conditional specialists defined as `AgentSkill` dataclass in `agents/skills.py`. A single `AgentRunner` class (`agents/runner.py`) replaces all individual agent classes.

| Agent | Role | Provider | Model | CLI Screen | Weight |
|-------|------|----------|-------|------------|--------|
| **Warren** | Primary | Claude CLI proxy | claude-opus-4-6 | claude | 0.18 |
| **Auditor** | Primary | Claude CLI proxy | claude-opus-4-6 | claude | 0.17 |
| **Klarman** | Primary | Claude CLI proxy | claude-opus-4-6 | claude | 0.12 |
| **Soros** | Primary | Gemini CLI proxy | gemini-3.1-pro-preview | gemini | 0.10 |
| **Druckenmiller** | Primary | Gemini CLI proxy | gemini-3.1-pro-preview | gemini | 0.11 |
| **Dalio** | Primary | Gemini CLI proxy | gemini-3.1-pro-preview | gemini | 0.12 |
| **Data Analyst** | Validator | Gemini CLI proxy | gemini-3.1-pro-preview | gemini | 0.0 |
| **Simons** | Scout | Groq API | llama-3.3-70b | None (API) | 0.07 |
| **Lynch** | Scout | DeepSeek API | deepseek-reasoner | None (API) | 0.07 |
| **Income Analyst** | Scout | DeepSeek API | deepseek-chat | None (API) | 0.06 |
| **Sector Specialist** | Conditional | DeepSeek API | deepseek-chat | None (API) | 0.05 |

**Conditional agents**: Income Analyst activates for dividend yield > 1.5% or PERMANENT positions. Sector Specialist activates for Healthcare, Financial Services, Energy, Real Estate, Technology sectors.

#### Pipeline Flow

```
Controller (K8s, 60s poll) monitors invest.pipeline_state:
  data_fetch → data_validate (Data Analyst) → agent:{name} (9+ agents)
    → debate (if <75% consensus) → synthesis (CIO verdict)
```

- **CLI serialization**: Two async queues (claude/gemini). Warren runs all tickers, then Auditor, then Klarman. Similarly for Gemini screen.
- **API agents** (Simons, Lynch): Run in parallel via HTTP, bypass CLI queues entirely.
- **Hybrid debate**: Only triggers when primary agents disagree (<75% sentiment agreement).
- **Staleness**: All pipeline rows expire after 24h. Controller retries failed steps (max 2).

#### Key Files — Pipeline

| File | Purpose |
|------|---------|
| `agents/skills.py` | `AgentSkill` dataclass + `SKILLS` registry (9 skills) |
| `agents/runner.py` | Generic `AgentRunner` (prompt builder, response parser, provider resolution) |
| `pipeline/controller.py` | Main K8s controller loop (dispatches work every 60s) |
| `pipeline/scheduler.py` | `CLIScheduler` with claude/gemini async queue workers |
| `pipeline/convergence.py` | Debate trigger logic + synthesis readiness checks |
| `pipeline/state.py` | Pipeline state DB operations (CRUD, expiry, readiness queries) |
| `registry/migrations/012_pipeline_state.sql` | `pipeline_state` + `pipeline_cycles` tables |

#### HB Proxy (11 routes)

`scripts/hb-agent-proxy.py` on HB LXC:9100. Routes CLI calls to claude/gemini screens:

- **Claude screen**: warren, auditor, klarman, debate, synthesis, board-claude
- **Gemini screen**: soros, druckenmiller, dalio, data-analyst, board-gemini
- **Gemini slash commands**: 5 mapped agents use `/invest:{name}` commands defined in `scripts/gemini-commands/invest/*.toml`. Persona lives in .toml; ticker data staged to `.gemini-data/_prompt_{agent}.txt` via @file reference. Unmapped agents (researcher) fall back to concatenated prompt.
- Symlink: `~/.gemini/commands/invest` → `/home/investmentology/scripts/gemini-commands/invest/` on HB LXC
- All agent timeouts: 600s. Board timeouts: 360s.
- Provider preference: remote CLI proxy > local CLI > HTTP API fallback
- `HB_PROXY_URL` + `HB_PROXY_TOKEN` env vars on K8s pod
- **NEVER add ANTHROPIC_API_KEY or GROK_API_KEY to the K8s pod** — CLI subscriptions are the intended path

Source: `src/investmentology/agents/`, `src/investmentology/pipeline/`

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

## Data Quality Gate

**Source**: `src/investmentology/data/validation.py`

yfinance intermittently returns corrupted data (zeroed revenue, missing income) for
established companies. Without validation, this garbage flows through the pipeline and
produces nonsensical verdicts (e.g. labelling a $16B revenue defense contractor as a
"pre-revenue startup" because revenue came back as $0).

### How it works

1. **`validate_fundamentals()`** runs critical checks on fetched data:
   - Market cap > $100M but revenue is $0 → **REJECT** (corrupted source)
   - Both operating_income and net_income are $0 with real revenue → **REJECT**
   - Price is $0/missing for company with market cap → **REJECT**
   - Small pre-revenue companies (< $100M) are unaffected

2. **`yfinance_client.py`** validates BEFORE caching:
   - If validation fails, retries once (yfinance is flaky)
   - If retry also fails, attaches `_validation_errors` to the result dict
   - Bad data is NEVER cached — prevents 24-hour poison cache windows

3. **`orchestrator.py`** aborts analysis on bad data:
   - Checks `_validation_errors` on fresh yfinance data
   - Re-validates DB-cached fundamentals (may predate validation)
   - Sets `data_quality_error` on `CandidateAnalysis` with clear message
   - Emits `DataQualityError` SSE event for PWA progress display

4. **PWA** (`useAnalysisStream.ts`) shows error on Fundamentals step instead of proceeding

### Key principle
**Better to show "data unavailable, try later" than to produce a confident wrong verdict.**

---

## Current Phase: Pipeline Rearchitecture (Phase 1-4 complete)

### Completed
- [x] **Phase 1**: Skills framework — `AgentSkill` dataclass + generic `AgentRunner`
- [x] **Phase 2**: Pipeline state machine — DB migration, controller, scheduler, convergence
- [x] **Phase 3**: HB proxy (11 routes), gateway (11 providers), CLI entry point, K8s controller deployment, DB migration 012 applied live
- [x] **Phase 4**: Pipeline API routes (`/api/invest/pipeline/*`), agent panel uses skills registry

### Remaining
- [ ] **Phase 5**: Cleanup — retire old orchestrator + individual agent classes (after end-to-end validation with live traffic)

### Foundation (ongoing)
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
