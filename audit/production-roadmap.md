# Investmentology — Unified Production Roadmap

**Date**: 2026-03-04
**Source**: Cross-disciplinary audit by Finance Analyst, Software Architect, and Frontend/UX Lead
**Purpose**: What the app and PWA need to reach production quality for public use

---

## Executive Summary

**Overall Maturity: B- (5.2/10) — Exceptional prototype, not production-ready**

Investmentology is a deeply impressive platform that punches well above its weight. The 6-layer investment pipeline mirrors institutional workflow. The 9-agent multi-model architecture is architecturally novel. The adversarial Munger layer, glossary auto-annotation, and thesis health tracking are genuine differentiators that don't exist in any consumer fintech product.

However, three systemic gaps prevent production deployment:

1. **Finance**: No portfolio-level risk management, quantitative formula errors, naive position sizing
2. **Backend**: Auth fails open, no DB transactions, God class registry, zero pipeline tests
3. **Frontend**: No React Query, no error boundaries, zero accessibility, no testing

The good news: none of these require architectural rewrites. The pipeline state machine, agent skills framework, and design system are solid foundations. The work ahead is hardening, not rebuilding.

---

## What's Genuinely Excellent (Preserve and Amplify)

These are the crown jewels — unique strengths that no competitor has:

| Feature | Source | Why It Matters |
|---------|--------|---------------|
| **Multi-agent consensus visualization** | PWA + Backend | 9 AI agents with distinct investment philosophies debating a stock — unprecedented in consumer fintech |
| **Adversarial Munger layer** | Backend | Trigger-based bias detection, Kill The Company exercise, pre-mortem with sector base rates — rare even in institutional funds |
| **Pipeline state machine** | Backend | DB-backed, crash-recoverable, staleness-aware — production-grade design |
| **Agent skills framework** | Backend | Single `AgentRunner` replacing 8 classes — elegant abstraction |
| **Daily Directive (Today view)** | PWA | "What do I need to do" prioritization with merged alerts + advisor actions — best-in-class UX |
| **Glossary auto-annotation** | PWA | Financial terms get inline plain-English definitions — genuine accessibility differentiator |
| **Thesis health tracking** | Backend + PWA | Monitoring *why* you bought, not just *what* — unique in the space |
| **12-theme design system** | PWA | Comprehensive CSS custom properties, cohesive dark glassmorphic aesthetic |
| **Real-time features** | PWA | WebSocket live prices, SSE analysis streaming, visibility-aware polling — technically excellent |

---

## Critical Findings by Domain

### Finance Methodology (4.5/10)

| Finding | Severity | Impact |
|---------|----------|--------|
| No portfolio-level VaR, correlation, or drawdown circuit breaker | CRITICAL | Cannot manage risk beyond individual positions |
| Altman Z-Score uses net_income as proxy for retained_earnings | CRITICAL | Materially wrong for mature companies — can flip zone classification |
| Piotroski uses operating_income as proxy for cash flow | CRITICAL | Makes accruals quality test tautological — defeats its purpose |
| No volatility-based position sizing | HIGH | Biotech gets same allocation as utility |
| Agent weights (0.08-0.18) have no empirical justification | HIGH | 29% difference between Warren and Soros with no evidence |
| Consensus is too coarse (bullish/bearish/neutral) | HIGH | Destroys confidence-level nuance |
| Calibration bucket minimum of 5 is statistically unreliable | HIGH | Need 20-30 for significance |
| 50-decision Kelly threshold needs ~380 for reliable win rate | MEDIUM | Current threshold is 7.6x too low |
| Bias detection is pure keyword matching | MEDIUM | Massive false positive rate |
| No momentum overlay on Greenblatt screen | MEDIUM | Academic literature shows value+momentum >> value alone |

### Code Architecture (5.5/10)

| Finding | Severity | Impact |
|---------|----------|--------|
| Auth middleware fails OPEN when `AUTH_SECRET_KEY` empty | CRITICAL | Silently disables all authentication |
| No request-scoped DB transactions | CRITICAL | Partial writes on crash (verdict without signals) |
| Internal token comparison not timing-safe | HIGH | Susceptible to timing attacks |
| Registry is a 1000+ line God class (40+ methods) | HIGH | Unmaintainable, untestable |
| Route handlers contain 300+ lines of business logic | HIGH | stocks.py `get_stock()` is 310 lines |
| Global mutable singleton for DI | HIGH | Fragile, test-hostile |
| Zero pipeline/scheduler tests | HIGH | Most complex component untested |
| No integration tests (all mock DB) | HIGH | SQL bugs reach production (proven: `do` alias) |
| Dependencies not pinned (only `>=` bounds) | MEDIUM | Non-reproducible builds |
| Sync DB in async context | MEDIUM | Thread pool exhaustion at ~50 concurrent users |
| Connection pool default (4 connections, no config) | MEDIUM | Exhaustion at ~100 concurrent |
| Background task failures logged at debug level | MEDIUM | Settlement failures silently swallowed |

### PWA Frontend (5.5/10)

| Finding | Severity | Impact |
|---------|----------|--------|
| No React Query / TanStack Query | CRITICAL | No request dedup, caching, retry, background refetch |
| No error boundaries | CRITICAL | JS error in one chart crashes entire app |
| Zero accessibility (WCAG) | CRITICAL | Legal liability, excludes disabled users |
| No code splitting | HIGH | All 14 views eagerly loaded — bloated initial bundle |
| No push notifications | HIGH | Alerts useless if user must open the app |
| No frontend tests | HIGH | Zero test files exist |
| Inline styles pervasive (~80 per view) | MEDIUM | No hover/focus CSS, no media queries, fragile maintenance |
| No centralized API client | MEDIUM | No interceptors, retry, timeout, logging |
| Sparkline duplicated 3 times | MEDIUM | Three separate implementations of the same thing |
| Portfolio fires 20+ concurrent sparkline API calls | MEDIUM | No batching or throttling |
| No onboarding flow | MEDIUM | New users have no guidance |
| Portfolio.tsx is 900+ lines with 6 inline components | MEDIUM | Needs extraction |

---

## The Roadmap

### Phase 0: Emergency Fixes (1-2 days)
*One-line and small fixes that address the most dangerous issues*

| # | Fix | Domain | Effort | Files |
|---|-----|--------|--------|-------|
| 0.1 | **Auth fails closed**: Require explicit `AUTH_DISABLED=true` env var | Backend | 30 min | `api/app.py:138-141` |
| 0.2 | **Timing-safe token comparison**: `hmac.compare_digest()` | Backend | 5 min | `api/app.py:145` |
| 0.3 | **Error logging**: Change `debug` to `exception` for background task failures | Backend | 5 min | `api/app.py:46` |
| 0.4 | **Pin dependencies**: Generate requirements.lock or use pip-compile | Backend | 30 min | `pyproject.toml` |
| 0.5 | **Delete retired code**: Remove old agent classes, orchestrator, `=0.23.0` | Backend | 1 hr | 10+ files |

### Phase 1: Foundation Hardening (1-2 weeks)
*Structural fixes that don't change behavior but make everything safer*

| # | Fix | Domain | Effort | Impact |
|---|-----|--------|--------|--------|
| 1.1 | **Add React Query**: Replace all manual fetch hooks | PWA | 2-3 days | Eliminates request duplication, adds caching, retry, background refetch |
| 1.2 | **Add error boundaries**: `<ViewErrorBoundary>` per route, `<PanelErrorBoundary>` per deep-dive panel | PWA | 0.5 day | Prevents total app crash |
| 1.3 | **Code splitting**: `React.lazy()` for all views except Today | PWA | 0.5 day | ~40% initial bundle reduction |
| 1.4 | **Request-scoped transactions**: Context manager in `Database` for atomic multi-step operations | Backend | 2 days | Prevents partial writes |
| 1.5 | **Fix Altman Z-Score**: Source actual retained_earnings from EDGAR or remove from composite | Finance | 1 day | Corrects materially wrong scoring |
| 1.6 | **Fix Piotroski OCF proxy**: Source actual operating cash flow or score only valid tests | Finance | 1 day | Fixes tautological test |
| 1.7 | **Decompose Registry**: Split into `stock_repo`, `decision_repo`, `position_repo`, `signal_repo`, `verdict_repo`, `watchlist_repo` | Backend | 3 days | Eliminates God class |
| 1.8 | **Extract route business logic**: Create service classes, routes < 30 lines | Backend | 3 days | Separation of concerns |
| 1.9 | **Configure connection pool**: `min_size=2, max_size=10` with timeout and lifetime | Backend | 1 hr | Prevents connection exhaustion |

### Phase 2: Risk & Reliability (2-3 weeks)
*Portfolio-level risk management + testing infrastructure*

| # | Fix | Domain | Effort | Impact |
|---|-----|--------|--------|--------|
| 2.1 | **Portfolio drawdown circuit breaker**: -10% from peak = halt new buying, trigger full review | Finance | 2 days | Core risk management |
| 2.2 | **Volatility-based position sizing**: size = base_weight * (target_vol / position_vol) | Finance | 2 days | Prevents equal-sizing biotech and utilities |
| 2.3 | **Return correlation matrix**: Rolling 60-day pairwise correlations, alert at avg > 0.5 | Finance | 3 days | Catches hidden concentration risk |
| 2.4 | **Portfolio VaR calculation**: Daily parametric VaR at 95% confidence | Finance | 2 days | Fundamental institutional risk metric |
| 2.5 | **Pipeline/scheduler tests**: Controller tick, scheduler worker lifecycle, state transitions | Backend | 3 days | Most critical untested component |
| 2.6 | **Integration tests**: testcontainers with real PostgreSQL | Backend | 3 days | Catches SQL bugs before production |
| 2.7 | **Accessibility pass**: Semantic HTML, ARIA roles, focus management, contrast audit, `prefers-reduced-motion` | PWA | 3-4 days | WCAG 2.1 AA compliance |
| 2.8 | **Increase calibration minimums**: Bucket min from 5 to 25, ECE threshold from 0.15 to 0.08 | Finance | 1 day | Statistical validity |
| 2.9 | **Add mypy to CI**: `mypy --strict` on existing type-hinted codebase | Backend | 1 day | Free bug catching |
| 2.10 | **Push notifications**: Service worker push for alerts and recommendations | PWA | 2-3 days | Alerts delivered without opening app |

### Phase 3: User Experience (2-3 weeks)
*Features needed for public-facing product*

| # | Feature | Domain | Effort | Impact |
|---|---------|--------|--------|--------|
| 3.1 | **Onboarding flow**: 3-screen product tour, empty-state CTAs, first-position guidance | PWA | 2 days | First-time user experience |
| 3.2 | **Portfolio performance chart**: Total return over time with S&P 500 benchmark overlay | PWA | 2-3 days | Table stakes for any portfolio app |
| 3.3 | **Batch sparkline API**: Single endpoint for N tickers, replace per-position fetching | Backend + PWA | 2 days | Eliminates 20-50 concurrent fetches |
| 3.4 | **Data export**: CSV download for positions, decisions, performance | Backend + PWA | 2 days | Trust-building, regulatory prep |
| 3.5 | **Centralized API client**: `src/api/client.ts` with retry, timeout, interceptors | PWA | 1 day | Consistent error handling |
| 3.6 | **Extract Portfolio inline components**: `PositionCard`, `ClosedTradeCard`, `ClosePositionModal` as separate files | PWA | 1 day | Maintainability |
| 3.7 | **Momentum overlay on Greenblatt screen**: 12-1 month price momentum filter | Finance | 2 days | Significantly improves risk-adjusted returns |
| 3.8 | **LLM-based bias detection**: Replace keyword matching with adversarial LLM pass | Finance | 2 days | Eliminates false positives |
| 3.9 | **Structured logging**: JSON-formatted with request IDs and correlation | Backend | 2 days | Production observability |
| 3.10 | **Pydantic response models**: Start with `/portfolio`, `/stock/{ticker}`, `/recommendations` | Backend | 2 days | API documentation, response validation |

### Phase 4: Differentiation (4+ weeks)
*What would make this genuinely stand out*

| # | Feature | Domain | Effort | Impact |
|---|---------|--------|--------|--------|
| 4.1 | **Interactive stock charts**: Integrate lightweight-charts (TradingView OSS) | PWA | 1 week | Elevates from data display to analysis tool |
| 4.2 | **AI research reports**: Full-page formatted analysis combining all agent perspectives | Backend + PWA | 1 week | Leverages the unique multi-agent pipeline |
| 4.3 | **Multi-user support**: User accounts, individual portfolios, preferences | Backend + PWA | 2 weeks | Required for public launch |
| 4.4 | **Scenario analysis**: "What if I add this position" portfolio impact calculator | Finance + PWA | 1 week | Unique to AI-advisory context |
| 4.5 | **Sector-specialized agents**: Conditional agent activation by industry | Finance | 1 week | Biotech needs different analysis than utilities |
| 4.6 | **Full historical backtest**: Complete pipeline over 2015-2025 | Finance | 2 weeks | Strategy validation |
| 4.7 | **Prometheus metrics**: Pipeline latencies, agent success rates, API times, DB pool | Backend | 1 week | Production monitoring |
| 4.8 | **Async database**: psycopg3 AsyncConnectionPool + async route handlers | Backend | 1 week | Scale to 500+ concurrent users |

---

## Maturity Scorecard

| Dimension | Current | After Phase 1 | After Phase 2 | After Phase 4 |
|-----------|---------|---------------|---------------|---------------|
| Pipeline Design | 7/10 | 7/10 | 7/10 | 8/10 |
| Quant Screen Quality | 5/10 | 7/10 | 7/10 | 8/10 |
| Agent Framework | 7/10 | 7/10 | 7/10 | 8/10 |
| Risk Management | 2/10 | 2/10 | 6/10 | 7/10 |
| Position Sizing | 3/10 | 3/10 | 6/10 | 7/10 |
| Data Quality | 5/10 | 6/10 | 6/10 | 7/10 |
| Code Architecture | 5/10 | 7/10 | 8/10 | 8/10 |
| Security | 5/10 | 7/10 | 8/10 | 8/10 |
| Testing | 4/10 | 4/10 | 7/10 | 8/10 |
| PWA Architecture | 5/10 | 7/10 | 8/10 | 9/10 |
| UX/UI | 8/10 | 8/10 | 9/10 | 9/10 |
| Accessibility | 1/10 | 1/10 | 6/10 | 8/10 |
| Production Readiness | 4/10 | 6/10 | 7/10 | 9/10 |
| **Overall** | **5.2/10** | **6.2/10** | **7.2/10** | **8.3/10** |

---

## The Bottom Line

> "This platform has the design taste and domain insight of a $10M fintech product built by a full team. It has the engineering infrastructure of a rapid prototype. Close the gap."

**What makes this special**: The multi-agent consensus, adversarial analysis, thesis health tracking, and glossary auto-annotation don't exist in any consumer fintech product. These are the features to amplify.

**What's holding it back**: Portfolio-level risk management, code hardening (auth, transactions, testing), and frontend infrastructure (React Query, error boundaries, accessibility).

**The path**: Phase 0-1 (2 weeks) fixes the dangerous gaps. Phase 2 (3 weeks) adds institutional-grade risk management and testing. Phase 3 (3 weeks) makes it user-ready. Phase 4 (ongoing) differentiates it from everything else on the market.

**Total estimated effort to production-ready (through Phase 3): 8-10 weeks of focused development.**

---

*Synthesized from three independent audits:*
- *`audit/finance-methodology-audit.md` — Senior Quantitative Finance Analyst*
- *`audit/code-architecture-audit.md` — Principal Software Architect*
- *`audit/pwa-production-audit.md` — Senior Frontend Architect & UX Lead*
