# Investmentology Code Architecture Audit

**Date:** 2026-03-04
**Auditor:** Principal Software Architect (Claude Opus 4.6)
**Scope:** Full backend codebase, API layer, database, pipeline, CI/CD, security, testing
**Codebase:** ~31,200 lines Python across 134 source files + ~11,000 lines of tests across 30 test files

---

## 1. Executive Summary

**Overall Grade: B- (Solid Prototype / Early Production)**

Investmentology is an ambitious AI-powered investment platform with impressive domain modeling and a well-designed multi-agent pipeline. The codebase demonstrates strong domain knowledge and thoughtful architecture at the macro level. However, it carries significant technical debt characteristic of a project that evolved rapidly from prototype to production without a refactoring pass.

**Key Strengths:**
- Excellent domain modeling (signal taxonomy, agent skills framework, sell engine)
- Well-structured pipeline state machine with proper failure recovery
- Parameterized SQL throughout (no SQL injection risks)
- Good test coverage for a project of this stage (~11K lines of tests)
- Clean separation between API, pipeline, registry, and agent layers

**Critical Findings:**
1. Global mutable singleton for dependency injection (`app_state`) is fragile and test-hostile
2. Route handlers contain heavy business logic, violating separation of concerns (stocks.py: 645 lines, single endpoint builds briefings)
3. Registry is a 1,000+ line God class mixing 15+ distinct concerns
4. No request-scoped database transactions -- every query auto-commits
5. Connection pool uses default sizing with no configuration
6. Auth middleware has a dev-mode bypass that disables all auth if `AUTH_SECRET_KEY` is empty
7. Background tasks fire-and-forget with only `debug`-level logging on failure
8. Dependencies are not pinned to exact versions (only lower bounds)

---

## 2. Project Structure Assessment

### File Organization: B+

```
src/investmentology/
  api/           # FastAPI routes + auth
  agents/        # Agent framework (skills, runner, gateway, react)
  adversarial/   # Munger adversarial checks
  advisory/      # Briefings, CIO synthesis, board
  compatibility/ # Signal taxonomy compat layer
  data/          # yfinance client, enricher, validation
  learning/      # Calibration, predictions, decision registry
  memory/        # Semantic + graph memory
  models/        # Domain models (signal, position, decision, etc.)
  pipeline/      # Controller, scheduler, convergence, state
  quant_gate/    # Quantitative screening (Greenblatt, Piotroski, Altman)
  registry/      # Database + query layer
  sell/           # Position sell rules engine
  timing/        # Kelly criterion, position sizing
```

**Strengths:**
- Domain-driven package organization (not technical layers)
- Each domain concept has its own module
- Models separated from persistence

**Issues:**

1. **`registry/queries.py` is a God class** -- 1,000+ lines, ~40 methods spanning stocks, decisions, predictions, watchlist, positions, cron, snapshots, signals, verdicts, fundamentals, backtests, targets, buzz, earnings momentum, thesis lifecycle. This should be decomposed into domain-specific repositories.

2. **Orphaned files exist.** `=0.23.0` at the project root is a corrupted pip install artifact. The old individual agent classes (`agents/warren.py`, `agents/soros.py`, etc.) are still present despite being replaced by the skills framework -- the CLAUDE.md explicitly notes Phase 5 cleanup hasn't happened.

3. **`orchestrator.py`** is 800+ lines of legacy code that imports all old agent classes individually. It's the predecessor to the pipeline controller and should have been retired per the Phase 5 plan.

### Configuration: B

`config.py` uses a frozen dataclass which is good -- immutable config after load. However:

- **`load_config()` swallows missing env vars** by defaulting everything to empty strings. This means the app happily starts with no database URL configured (`db_dsn=""`), only to fail at runtime. Fail-fast on missing required config would be safer.
- **No config validation.** `quant_gate_top_n=int(os.environ.get("QUANT_GATE_TOP_N", "100"))` -- a non-numeric string crashes at startup with an unhelpful traceback.

```python
# config.py:59 -- dangerous silent default
db_dsn=os.environ.get("DATABASE_URL", ""),  # Empty = crash at runtime, not startup
```

---

## 3. API Design Assessment

### Architecture: B

FastAPI is well-suited here. The application factory pattern (`create_app()`) is clean. Route separation into per-domain modules is good. The prefix convention (`/api/invest/`) is consistent.

### Anti-Patterns Found

#### 3.1 Route Handlers as Business Logic Containers

**Severity: HIGH**

`api/routes/stocks.py` is 645 lines with the `get_stock()` endpoint alone being ~310 lines. It contains business logic for building briefings, formatting profiles, computing P&L, enriching signals, and generating narratives. This should be in a service layer.

```python
# stocks.py:228 -- a 310-line endpoint that should be 10 lines calling a service
@router.get("/stock/{ticker}")
def get_stock(ticker: str, registry: Registry = Depends(get_registry)) -> dict:
    ticker = ticker.upper()
    # ... 310 lines of data assembly, formatting, enrichment ...
```

`api/routes/recommendations.py` is similarly bloated at 357 lines with complex scoring, enrichment, and position categorization logic embedded in the route handler.

#### 3.2 Direct `registry._db.execute()` Calls in Routes

**Severity: MEDIUM**

Multiple route handlers bypass the Registry abstraction and call `registry._db.execute()` directly with raw SQL. This defeats the purpose of having a query layer.

```python
# stocks.py:262 -- bypassing Registry, accessing private _db attribute
signal_rows = registry._db.execute(
    "SELECT agent_name, model, signals, confidence, reasoning, created_at "
    "FROM invest.agent_signals WHERE ticker = %s ORDER BY created_at DESC LIMIT 20",
    (ticker,),
)
```

This pattern appears in `stocks.py` (5 occurrences), `recommendations.py` (3 occurrences), `daily.py` (2 occurrences), `system.py` (3 occurrences), and `pipeline.py` (8 occurrences).

#### 3.3 Global Mutable Singleton DI

**Severity: HIGH**

```python
# deps.py:30 -- module-level singleton, mutated during lifespan
app_state = AppState()
```

The `AppState` singleton is mutated during lifespan startup and cleaned up manually in tests. This is fragile:
- No thread safety guarantees
- Test fixtures must manually clean up state
- No request scoping -- all requests share one state object
- Impossible to run parallel test suites

FastAPI's `Depends()` with `request.state` or lifespan state dict would be more idiomatic and safer.

#### 3.4 Synchronous Route Handlers with I/O

**Severity: MEDIUM**

Most route handlers are synchronous (`def`) despite performing database I/O. FastAPI runs sync handlers in a threadpool, which works but wastes threads:

```python
# stocks.py:228 -- sync handler doing multiple DB calls
@router.get("/stock/{ticker}")
def get_stock(ticker: str, registry: Registry = Depends(get_registry)) -> dict:
```

With `psycopg3` having full async support, these could be `async def` with async DB calls. The current sync-with-pool approach works at low concurrency but will bottleneck under load.

#### 3.5 No Response Models

**Severity: LOW**

No Pydantic response models are used. All endpoints return raw `dict` objects. This means:
- No automatic OpenAPI schema generation for responses
- No validation of outgoing data
- No compile-time catching of key typos
- Documentation consumers can't auto-generate clients

---

## 4. Database & Data Layer Assessment

### Database Connection Management: C+

#### 4.1 Connection Pool Configuration

```python
# db.py:31 -- default pool with no size configuration
self._pool = ConnectionPool(self._dsn, kwargs={"row_factory": dict_row})
```

`ConnectionPool` defaults to `min_size=4` and has no documented `max_size` default. For a production deployment handling API requests + background tasks + cronjobs, this needs explicit sizing. There's no connection timeout, no max connection lifetime, and no idle connection reclamation.

#### 4.2 No Transaction Boundaries

**Severity: HIGH**

Every `Database.execute()` call auto-commits immediately:

```python
# db.py:64 -- auto-commit after every query
cur.execute(query, params)
if cur.description is not None:
    rows = cur.fetchall()
    conn.commit()
    return [dict(row) for row in rows]
conn.commit()
```

There is no mechanism for request-scoped transactions. Multi-step operations like "insert verdict + insert signals + update watchlist state" are not atomic. A failure partway through leaves the database in an inconsistent state.

Example: `Registry.insert_verdict()` + `Registry.insert_agent_signals()` are separate auto-committed operations. If the process crashes between them, you get a verdict with no associated signals.

#### 4.3 Raw SQL Approach

**Assessment: Appropriate for this project**

The Registry pattern with raw SQL using `psycopg3` parameterized queries is actually a reasonable choice for this domain. The queries are complex enough that an ORM would add friction (window functions, CTEs, JSONB operations, `ON CONFLICT` upserts). The parameterized approach eliminates SQL injection risks.

However, the queries should be extracted from the massive `Registry` class into domain-specific repositories (stocks, decisions, predictions, positions, signals, etc.).

#### 4.4 SQL Injection: Not a Risk

All queries use parameterized placeholders (`%s`). Even the dynamic queries in `state.py` and `recommendations.py` that build `IN` clauses use proper parameterization:

```python
# state.py:256 -- safe dynamic IN clause
placeholders = ", ".join(["%s"] * len(agent_names))
steps = [f"agent:{name}" for name in agent_names]
rows = db.execute(
    f"SELECT COUNT(*) AS cnt FROM invest.pipeline_state "
    f"WHERE cycle_id = %s AND ticker = %s "
    f"AND step IN ({placeholders}) AND status = 'completed'",
    (cycle_id, ticker, *steps),
)
```

The `f"agent:{name}"` construction takes `name` from the internal `SKILLS` registry, not from user input, so it's not injectable.

#### 4.5 Migration System

The migration system is simple but adequate:
- Sequential SQL files with a `_migrations` tracking table
- Applied at startup via `run_migrations()`
- 14 migrations spanning the full schema evolution

**Risk:** Migrations are not idempotent. Re-running a migration that partially applied (e.g., crash during a multi-statement migration) will fail. Each migration should wrap in a transaction or use `IF NOT EXISTS` guards.

### Data Layer (yfinance_client.py): B+

The `YFinanceClient` is well-designed with:
- In-memory cache with TTL
- Circuit breaker pattern (50% failure threshold, 5-minute window)
- Validation before caching (prevents poisoned cache)
- Retry on validation failure (yfinance is flaky)
- Batch processing with throttling and chunk delays

**Issue:** The in-memory cache lives in the process. When the pod restarts, all cached data is lost, triggering a thundering herd of yfinance API calls. Consider using the database cache (`pipeline_data_cache`) or Redis.

---

## 5. Pipeline Architecture Assessment

### Design: A-

The pipeline is the strongest piece of architecture in the codebase. The event-driven, database-backed state machine is well-designed:

```
data_fetch -> data_validate -> pre_filter -> screeners -> gate_decision
    -> research -> agents -> debate -> adversarial -> synthesis
```

**Strengths:**
- DB-backed state enables crash recovery (steps resume from last committed state)
- Per-agent queue workers enable parallelism across agents
- Staleness/expiry system handles abandoned work
- Re-entry blocks prevent re-analyzing recently rejected stocks
- Circuit breaker on yfinance prevents cascade failures

#### 5.1 Pipeline State Machine Robustness

The state transitions (`pending -> running -> completed/failed/expired`) are clean. Recovery from partial failures is handled:

```python
# state.py:180 -- recovers stuck steps
def reset_stale_running_steps(db: Database) -> int:
    """Reset steps stuck in 'running' for too long back to 'pending'."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=RUNNING_TIMEOUT_MINUTES)
```

**Issue:** There's no distributed locking. If two controller instances start (e.g., during a rolling deployment), they'll both process the same pending steps, potentially dispatching duplicate agent calls. The controller deployment uses `strategy: Recreate` which mitigates this, but it's not an application-level guarantee.

#### 5.2 CLI Proxy Pattern

**Severity: MEDIUM (Architectural Risk)**

The HB LXC proxy pattern is inherently fragile:

```
K8s Pod (10.20.0.0/24) -> HTTP -> HB LXC (10.10.0.101:9100) -> screen sessions -> CLI tools
```

- Single point of failure (one LXC handles all CLI agent calls)
- No health checking of the proxy from the controller
- 600-second timeouts mean a stuck CLI session blocks the queue worker for 10 minutes
- If the HB LXC reboots, all in-flight agent calls fail simultaneously

This is a known constraint documented in CLAUDE.md, and the gateway's fallback chain (`remote CLI -> local CLI -> HTTP API`) provides degradation. But the primary path has no redundancy.

#### 5.3 Scheduler Design

The `CLIScheduler` is clean and correct. Per-agent queues with configurable worker counts is the right pattern. The sentinel-based shutdown is proper.

**Minor issue:** `queue.put_nowait(job)` will raise `QueueFull` if the queue has a `maxsize`. Currently queues are unbounded (`asyncio.Queue()` with no `maxsize`), so this works but could be a problem if the controller submits faster than agents can process.

---

## 6. Security Assessment

### Overall: B-

#### 6.1 Authentication

**Design is sound but has a dangerous dev-mode bypass:**

```python
# app.py:138-141 -- auth silently disabled when no secret configured
if not config or not config.auth_secret_key:
    return await call_next(request)
```

If `AUTH_SECRET_KEY` is accidentally unset in production, ALL API endpoints become unauthenticated. This should fail closed (deny access) rather than fail open.

**JWT Implementation:**
- Uses `python-jose` with HS256 -- adequate for a single-service deployment
- Token contains only `exp` claim -- no user identity, no roles, no `jti` for revocation
- Cookie-based with `httponly`, `secure` (conditional), `samesite=lax` -- good

**Internal token bypass:**
```python
# app.py:144-145 -- simple string comparison for internal token
if internal_token and config.internal_api_token and internal_token == config.internal_api_token:
```
This is constant-time safe only if Python's `==` on strings is constant-time (it's not -- Python uses early exit). Use `hmac.compare_digest()` instead.

#### 6.2 Password Handling

```python
# auth.py:14-18 -- bcrypt with multi-hash support
def verify_password(plain: str, hashed: str) -> bool:
    for h in hashed.split(","):
        if h and _bcrypt.checkpw(plain_bytes, h.encode()):
            return True
```

The comma-split multi-hash support is unusual but functional. bcrypt is the right choice. No plaintext passwords in code.

#### 6.3 Input Validation

- Ticker inputs are `.upper()`-ified but not validated against a regex. A request to `/stock/../../etc/passwd` would just return null data (safe but could be cleaner).
- Pydantic models are used for POST bodies (`LoginRequest`, `CreatePositionRequest`) -- good.
- GET parameters use FastAPI `Query()` with regex validation where appropriate (e.g., chart periods).

#### 6.4 Secrets Management

Secrets come from Infisical via K8s `InfisicalSecret` CRD, injected as env vars via `envFrom: secretRef`. This is proper -- no secrets in code or manifests.

---

## 7. Testing & CI/CD Assessment

### Testing: B

**Coverage:** 30 test files, ~11,000 lines of test code. All major components have tests:

| Area | Test File | Lines |
|------|-----------|-------|
| API routes | test_api.py | 762 |
| Agents/Skills | test_agents.py, test_investment_agents.py | 1,485 |
| Quant Gate | test_quant_gate.py | 824 |
| Adversarial | test_adversarial.py | 624 |
| Advisory Board | test_advisory_board.py | 714 |
| Sell Engine | test_sell.py | 385 |
| Registry | test_registry.py | 294 |
| Database | test_db.py | 184 |
| Data/Validation | test_data.py, test_validation_extended.py | 889 |
| Orchestrator | test_orchestrator.py | 395 |

**Strengths:**
- All tests use mocked database (no external dependencies)
- API tests use FastAPI `TestClient`
- Tests cover both happy paths and edge cases
- Good use of `@pytest.fixture` for setup

**Gaps:**

1. **No integration tests.** Every test mocks the database. There are no tests that verify actual SQL queries against a real PostgreSQL instance. A query returning the wrong columns would pass all tests but fail in production.

2. **No pipeline tests.** The most complex component (`pipeline/controller.py`, `pipeline/state.py`, `pipeline/scheduler.py`) has zero dedicated tests. `test_pre_filter.py` exists but tests only the pre-filter logic, not the controller or scheduler.

3. **No concurrency tests.** The scheduler processes jobs concurrently but is never tested under concurrent load.

4. **Test isolation concern.** The `app_state` singleton is mutated in test fixtures and must be manually cleaned up:
```python
# test_api.py:55-61 -- manual cleanup of global state
app_state.db = None
app_state.registry = None
# ...
```

### CI/CD: C+

```yaml
# ci.yml -- minimal pipeline
- run: pip install -e ".[dev]"
- run: ruff check src/
- run: pytest tests/ -x --tb=short
```

**Issues:**

1. **No test coverage reporting.** `pytest-cov` is a dev dependency but not used in CI. No coverage thresholds.
2. **`-x` flag** stops at first failure -- acceptable for fast feedback but risks masking multiple issues.
3. **No type checking.** `mypy` or `pyright` is not configured. Type hints are used extensively but never verified.
4. **No security scanning.** No `bandit`, `safety`, or `trivy` for dependency vulnerability scanning.
5. **Build-and-push has no `needs: test` dependency** in the workflow -- they're separate jobs that run in parallel. The image could be pushed even if tests fail (GitHub Actions `if: github.ref == 'refs/heads/main'` is checked but not `needs`).
6. **`:latest` tag only** (plus SHA tag). No semantic versioning. No way to roll back to a specific release.

---

## 8. Performance & Scalability Assessment

### Current Load Profile

Single-user platform with ~100 stocks analyzed per cycle. The architecture is appropriate for this scale.

### Bottlenecks Under Increased Load

#### 8.1 Synchronous Database Access in Async Context

The `Database` class uses synchronous `psycopg3`. When called from async route handlers (via FastAPI's threadpool executor), each request consumes a thread. At 100 concurrent users, you'd exhaust the default threadpool.

#### 8.2 N+1 Query Patterns

`get_stock()` makes 10+ separate database queries for a single ticker (profile, fundamentals, signals, decisions, watchlist, quant gate, verdicts, competence, positions, buzz, earnings momentum, research briefing). These should be batched or joined.

Similarly, `get_recommendations()` makes 3 batch queries plus per-ticker queries for stability scoring.

#### 8.3 In-Memory Caching

```python
# daily.py:18 -- module-level cache with no eviction
_cached_briefing: dict | None = None
```

The daily briefing cache is global with no TTL. The yfinance client cache is in-process with no shared state across pods (irrelevant with 1 replica but worth noting).

#### 8.4 What Breaks at Scale

| Concurrent Users | Bottleneck |
|------------------|------------|
| 10 | None -- current architecture handles this fine |
| 50 | Thread pool exhaustion from sync DB calls in async handlers |
| 100 | Connection pool exhaustion (default 4 connections) |
| 500 | N+1 queries in stock detail endpoint cause latency spikes |
| 1000 | Need async DB, connection pool sizing, response caching, read replicas |

---

## 9. Production Readiness Gaps

### 9.1 Health Checks: B+

The `/api/invest/system/health` endpoint checks database connectivity, provider status, and decision count. Kubernetes liveness and readiness probes are configured.

**Gap:** The health check doesn't verify background task health. If `_daily_settlement_loop` or `reanalysis_loop` crashes, the health check still returns "healthy".

### 9.2 Graceful Shutdown: B

The lifespan handler cancels background tasks and closes the gateway/database. This is correct.

**Gap:** No draining of in-flight HTTP requests. Uvicorn handles this via `SIGTERM` → graceful shutdown, but the `serve.py` runs `uvicorn.run()` directly without configuring `timeout_graceful_shutdown`.

### 9.3 Logging & Observability: C+

- Standard Python `logging` module used throughout
- No structured logging (JSON format)
- Several critical paths use `logger.debug()` for errors that should be `logger.error()`:

```python
# app.py:46 -- settlement failure silently swallowed
except Exception:
    logger.debug("Daily settlement task failed")  # Should be logger.error()
```

- No metrics (Prometheus, StatsD, etc.)
- No distributed tracing
- No request ID propagation

### 9.4 Resource Limits: B

K8s deployment specifies resource requests and limits:
```yaml
resources:
  requests: {memory: "256Mi", cpu: "100m"}
  limits: {memory: "512Mi", cpu: "500m"}
```

These are reasonable for the current workload.

### 9.5 Dockerfile: B

Multi-stage build is correct. Non-root user is used. `pip install --no-cache-dir` keeps image lean.

**Issues:**
- `COPY src/ src/` before `pip install .` means every code change invalidates the pip install layer. Should copy `pyproject.toml` first, install deps, then copy source.
- Actually, the Dockerfile already does `COPY pyproject.toml .` then `RUN pip install --no-cache-dir .` then copies more files. But `COPY src/ src/` happens before the pip install, so the layer ordering is correct. However, `COPY src/investmentology/registry/migrations/ migrations/` after the install is redundant since migrations are already in the installed package.

---

## 10. Tech Debt Inventory

| # | Item | Severity | Effort | Location |
|---|------|----------|--------|----------|
| 1 | Registry God class (~1000 lines, 40+ methods) | HIGH | Medium | `registry/queries.py` |
| 2 | Unretired old agent classes (Phase 5 cleanup) | MEDIUM | Low | `agents/warren.py`, `soros.py`, etc. (8 files) |
| 3 | Unretired orchestrator (800+ lines, replaced by controller) | MEDIUM | Low | `orchestrator.py` |
| 4 | Route handlers contain business logic (stocks.py: 645 lines) | HIGH | Medium | `api/routes/stocks.py`, `recommendations.py` |
| 5 | Global mutable singleton DI | HIGH | Medium | `api/deps.py` |
| 6 | No request-scoped transactions | HIGH | Medium | `registry/db.py` |
| 7 | Sync DB in async context | MEDIUM | Medium | `registry/db.py`, all route handlers |
| 8 | No response models (Pydantic) | LOW | Medium | All route files |
| 9 | Dependencies not pinned | MEDIUM | Low | `pyproject.toml` |
| 10 | No type checking in CI | MEDIUM | Low | `.github/workflows/ci.yml` |
| 11 | No integration tests | HIGH | High | `tests/` |
| 12 | No pipeline/scheduler tests | HIGH | Medium | `tests/` |
| 13 | Auth fails open when unconfigured | HIGH | Low | `api/app.py:138-141` |
| 14 | Background task failures logged at debug level | MEDIUM | Low | `api/app.py:46` |
| 15 | Orphaned file `=0.23.0` in project root | LOW | Trivial | Root directory |
| 16 | Internal token comparison not timing-safe | MEDIUM | Trivial | `api/app.py:145` |
| 17 | No connection pool sizing configuration | MEDIUM | Low | `registry/db.py:31` |
| 18 | N+1 queries in stock detail endpoint | MEDIUM | Medium | `api/routes/stocks.py` |
| 19 | Module-level cache with no eviction | LOW | Low | `api/routes/daily.py:18` |
| 20 | No structured logging | MEDIUM | Medium | Throughout |

---

## 11. Prioritized Recommendations

### P0 -- Fix Before Scaling (Security & Data Integrity)

1. **Make auth fail closed.** Change the dev-mode bypass to require an explicit `AUTH_DISABLED=true` env var rather than silently opening when `AUTH_SECRET_KEY` is empty.

2. **Use `hmac.compare_digest()` for internal token comparison.** One-line fix in `app.py:145`.

3. **Add request-scoped transactions.** Create a context manager in `Database` that holds a connection for the duration of a request and commits/rolls back atomically. This prevents partial writes.

4. **Pin dependencies to exact versions.** Generate a `requirements.lock` or use `pip-compile`. Unpinned `>=` ranges mean a `pip install` at different times can produce different behavior.

5. **Fix background task error logging.** Change `logger.debug("Daily settlement task failed")` to `logger.exception("Daily settlement task failed")`.

### P1 -- Reduce Structural Debt (Next Sprint)

6. **Decompose Registry into domain repositories.** Split `queries.py` into `stock_repo.py`, `decision_repo.py`, `position_repo.py`, `signal_repo.py`, `verdict_repo.py`, `watchlist_repo.py`. Each with focused methods.

7. **Extract business logic from route handlers.** Create service classes (`StockDetailService`, `RecommendationService`, `BriefingService`) that route handlers delegate to. Routes should be <30 lines.

8. **Delete retired code.** Remove old agent classes, the orchestrator module, and `=0.23.0`. This eliminates confusion about what's active.

9. **Add pipeline/scheduler tests.** The most complex component has zero tests. Write integration-style tests using a mock database for the controller tick loop, scheduler worker lifecycle, and state transitions.

### P2 -- Production Hardening (Next Month)

10. **Replace `app_state` singleton with FastAPI lifespan state.** Use `app.state` populated during lifespan, accessed via `request.app.state` in dependencies. This is FastAPI-idiomatic and testable.

11. **Add Pydantic response models.** Start with the most-used endpoints (`/portfolio`, `/stock/{ticker}`, `/recommendations`). This improves API documentation and catches response shape drift.

12. **Configure connection pool.** Add `min_size`, `max_size`, `max_idle`, and `max_lifetime` parameters. A good starting point: `min_size=2, max_size=10`.

13. **Add mypy to CI.** The codebase already uses type hints extensively. Adding `mypy --strict` would catch bugs for free.

14. **Add integration tests with real PostgreSQL.** Use `testcontainers` or a CI-provisioned PostgreSQL service. Test actual SQL queries and migrations.

### P3 -- Scale When Needed (Future)

15. **Migrate to async database access.** Use `psycopg3`'s `AsyncConnectionPool` and `AsyncConnection`. Convert route handlers to `async def`.

16. **Add structured logging.** Switch to JSON-formatted logs with request IDs, latency, and correlation IDs.

17. **Add Prometheus metrics.** Instrument pipeline step latencies, agent success rates, API response times, and DB connection pool utilization.

18. **Optimize N+1 queries.** The stock detail endpoint should use CTEs or JOINs to fetch all data in 2-3 queries instead of 10+.

---

## 12. Overall Maturity Rating

**Rating: 5.5 / 10**

| Dimension | Score | Notes |
|-----------|-------|-------|
| Code Organization | 7/10 | Good domain-driven structure, but God classes and bloated routes |
| API Design | 6/10 | Functional but lacks response models, has business logic in routes |
| Database Layer | 5/10 | Safe SQL, but no transactions, no pool config, God class |
| Pipeline Architecture | 8/10 | Best part of the codebase -- proper state machine, recovery, scheduling |
| Security | 5/10 | Auth works but has dangerous fail-open mode and timing attack |
| Testing | 5/10 | Good unit coverage but no integration tests, no pipeline tests |
| CI/CD | 4/10 | Minimal -- no coverage, no type checking, no security scanning |
| Production Readiness | 5/10 | Health checks and probes exist, but poor observability and logging |
| Documentation | 7/10 | CLAUDE.md is thorough, but no API docs beyond FastAPI auto-gen |
| Scalability | 4/10 | Adequate for single user, significant bottlenecks at 50+ concurrent |

**Justification:**

This is a well-conceived platform with an impressive domain model built by engineers who understand both software architecture and investment finance. The pipeline state machine is production-grade. The agent skills framework is elegant.

However, the codebase shows classic signs of rapid iteration without refactoring: God classes, business logic in the wrong layers, no integration tests for the most critical components, and security shortcuts that were fine for development but need attention before wider deployment. The tech debt is concentrated in areas that are fixable (Registry decomposition, route extraction, auth hardening) without requiring an architectural rewrite.

The most impactful improvement would be items P0.1-P0.5 (security and data integrity fixes) followed by P1.6-P1.9 (structural debt reduction). These would move the rating to a solid 7/10 with moderate effort.

---

*Audit completed 2026-03-04. All findings reference specific files, line numbers, and code patterns in the `/home/investmentology/` codebase.*
