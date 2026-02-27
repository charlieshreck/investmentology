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
