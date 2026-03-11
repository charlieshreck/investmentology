"""FastAPI application factory with CORS, auth middleware, and lifespan management."""

from __future__ import annotations

import asyncio
import hmac
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from investmentology.api.auth import get_user_id_from_token, verify_token

from investmentology.agents.gateway import LLMGateway
from investmentology.api.deps import app_state
from investmentology.config import load_config
from investmentology.data.enricher import build_enricher
from investmentology.learning.calibration import CalibrationEngine
from investmentology.learning.predictions import PredictionManager
from investmentology.learning.registry import DecisionLogger
from investmentology.orchestrator import AnalysisOrchestrator
from investmentology.registry.db import Database
from investmentology.registry.queries import Registry
from investmentology.timing.sizing import KellyCalculator, PositionSizer, KELLY_MIN_DECISIONS
from investmentology.advisory.triggers import reanalysis_loop

logger = logging.getLogger(__name__)


def _bootstrap_default_user(db: Database, config) -> None:
    """Create a default admin user if the users table is empty.

    Uses the existing AUTH_PASSWORD_HASH from config so the same password works.
    Also assigns all orphan data (user_id IS NULL) to the new user.
    """
    try:
        rows = db.execute("SELECT COUNT(*) AS cnt FROM invest.users")
        if rows and rows[0]["cnt"] > 0:
            return  # Users exist, nothing to do

        if not config or not config.auth_password_hash:
            logger.warning("No users and no AUTH_PASSWORD_HASH — cannot bootstrap default user")
            return

        # Take the first hash if comma-separated
        pw_hash = config.auth_password_hash.split(",")[0].strip()

        result = db.execute(
            "INSERT INTO invest.users (email, password_hash, display_name) "
            "VALUES (%s, %s, %s) RETURNING id",
            ("charlieshreck@gmail.com", pw_hash, "Charlie"),
        )
        if not result:
            return

        user_id = result[0]["id"]
        logger.info("Created default admin user (id=%s)", user_id)

        # Assign orphan data to the new user
        tables = [
            "invest.portfolio_positions",
            "invest.portfolio_budget",
            "invest.decisions",
            "invest.watchlist",
            "invest.predictions",
            "invest.push_subscriptions",
        ]
        for table in tables:
            try:
                db.execute(
                    f"UPDATE {table} SET user_id = %s WHERE user_id IS NULL",  # noqa: S608
                    (user_id,),
                )
            except Exception:
                logger.debug("Could not update %s — column may not exist", table)

        logger.info("Assigned orphan data to default user %s", user_id)
    except Exception:
        logger.warning("Default user bootstrap failed", exc_info=True)


async def _daily_settlement_loop(registry):
    """Background task: settle due predictions once per day at startup and then every 24h."""
    from investmentology.learning.predictions import PredictionManager
    while True:
        try:
            pm = PredictionManager(registry)
            settled = pm.settle_due_predictions()
            if settled:
                logger.info("Daily settlement: settled %d predictions", len(settled))
        except Exception:
            logger.exception("Daily settlement task failed")
        await asyncio.sleep(86400)  # 24 hours


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup/shutdown of DB, gateway, and dependent services."""
    config = load_config()

    # Database (sync — used by existing routes and services)
    db = Database(config.db_dsn)
    db.connect()
    registry = Registry(db)

    # Bootstrap default user if users table is empty (single→multi-user migration)
    _bootstrap_default_user(db, config)

    # Async database (for gradual route migration to async)
    from investmentology.registry.db import AsyncDatabase

    async_db = AsyncDatabase(config.db_dsn)
    try:
        await async_db.connect()
    except Exception:
        logger.warning("AsyncDatabase init failed — async routes disabled", exc_info=True)
        async_db = None

    # LLM Gateway
    gateway = LLMGateway.from_config(config)
    await gateway.start()

    # Higher-level services
    decision_logger = DecisionLogger(registry)
    prediction_manager = PredictionManager(registry)
    calibration_engine = CalibrationEngine(registry)
    enricher = build_enricher(config)

    # L5: Position Sizer with Kelly criterion (if enough history)
    kelly: KellyCalculator | None = None
    stats = registry.get_win_loss_stats()
    if stats.get("total_settled", 0) >= KELLY_MIN_DECISIONS:
        kelly = KellyCalculator(
            win_rate=stats["win_rate"],
            avg_win_pct=stats["avg_win_pct"],
            avg_loss_pct=stats["avg_loss_pct"],
        )
        logger.info("Kelly criterion activated: %d settled decisions", stats["total_settled"])
    position_sizer = PositionSizer(kelly=kelly)

    orchestrator = AnalysisOrchestrator(
        registry, gateway, decision_logger,
        position_sizer=position_sizer,
        enricher=enricher,
        enable_debate=config.enable_debate,
    )

    # Populate shared state
    app_state.config = config
    app_state.db = db
    app_state.async_db = async_db
    app_state.registry = registry
    app_state.gateway = gateway
    app_state.decision_logger = decision_logger
    app_state.prediction_manager = prediction_manager
    app_state.calibration_engine = calibration_engine
    app_state.orchestrator = orchestrator

    # Start background tasks
    _bg_tasks = []
    _bg_tasks.append(asyncio.create_task(_daily_settlement_loop(registry)))
    _bg_tasks.append(asyncio.create_task(reanalysis_loop(registry, orchestrator)))
    _bg_tasks.append(asyncio.create_task(_metrics_update_loop(registry)))
    logger.info("API started — DB, gateway, and background tasks ready")
    yield

    # Cancel background tasks
    for task in _bg_tasks:
        task.cancel()

    # Shutdown
    await gateway.close()
    if async_db:
        await async_db.close()
    db.close()
    logger.info("API shutdown complete")


# Paths that don't require authentication
PUBLIC_PATHS = {
    "/api/invest/auth/login",
    "/api/invest/auth/logout",
    "/api/invest/auth/check",
    "/api/invest/auth/register",
    "/api/invest/system/health",
    "/metrics",
}


async def _metrics_update_loop(registry):
    """Background task: update Prometheus gauges every 60 seconds."""
    from investmentology.api.metrics import (
        build_info,
        db_pool_size,
        portfolio_value_usd,
        position_count,
    )

    build_info.info({"version": "0.1.0"})
    while True:
        try:
            positions = registry.get_open_positions()
            position_count.set(len(positions))
            total_val = sum(float(p.current_price * p.shares) for p in positions)
            portfolio_value_usd.set(total_val)

            # DB pool stats
            db = registry._db
            if db._pool is not None:
                stats = db._pool.get_stats()
                db_pool_size.labels(state="pool_size").set(stats.get("pool_size", 0))
                db_pool_size.labels(state="pool_available").set(stats.get("pool_available", 0))
        except Exception:
            logger.debug("Metrics update failed", exc_info=True)
        await asyncio.sleep(60)


class AuthMiddleware(BaseHTTPMiddleware):
    """Require a valid JWT session cookie for all API routes except public ones."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for non-API routes (PWA static files, index.html)
        if not path.startswith("/api/invest"):
            return await call_next(request)

        # Skip auth for whitelisted public endpoints
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Auth disabled explicitly via AUTH_DISABLED=true env var (dev mode only)
        config = app_state.config
        if config and config.auth_disabled:
            return await call_next(request)

        # If auth is enabled but secret key is missing, reject (fail closed)
        if not config or not config.auth_secret_key:
            return JSONResponse(
                status_code=503,
                content={"detail": "Authentication not configured"},
            )

        # Internal token bypass (for trusted proxies like Tamar)
        internal_token = request.headers.get("x-internal-token")
        if internal_token and config.internal_api_token and hmac.compare_digest(internal_token, config.internal_api_token):
            return await call_next(request)

        # Validate session cookie
        token = request.cookies.get("session")
        if not token or not verify_token(token, config.auth_secret_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        # Extract user_id from JWT and store in request state
        request.state.user_id = get_user_id_from_token(token, config.auth_secret_key)

        return await call_next(request)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to each request and response."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log API requests with method, path, status, and duration. Also records Prometheus metrics."""

    async def dispatch(self, request: Request, call_next):
        from investmentology.api.metrics import (
            api_request_duration,
            api_requests_total,
            template_path,
        )

        start = time.monotonic()
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/"):
            duration_s = time.monotonic() - start
            duration_ms = round(duration_s * 1000, 1)
            logger.info(
                "request",
                extra={
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "request_id": getattr(request.state, "request_id", ""),
                },
            )
            # Prometheus metrics
            tmpl = template_path(path)
            status = str(response.status_code)
            api_request_duration.labels(
                method=request.method, path_template=tmpl, status=status,
            ).observe(duration_s)
            api_requests_total.labels(
                method=request.method, path_template=tmpl, status=status,
            ).inc()
        return response


def create_app(*, use_lifespan: bool = True) -> FastAPI:
    """Build and return the FastAPI application.

    Args:
        use_lifespan: If False, skip the production lifespan (useful for testing
            where deps are injected via app_state directly).
    """
    app = FastAPI(
        title="Investmentology API",
        version="0.1.0",
        lifespan=lifespan if use_lifespan else None,
    )

    # CORSMiddleware: when allow_credentials=True, FastAPI reflects the
    # requesting origin instead of sending *.  We list known frontends
    # explicitly; unknown origins are still reflected by Starlette when
    # allow_origins=["*"] + allow_credentials=True, but listing them
    # makes intent clear.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://haute-banque.kernow.io",
            "https://tamar.kernow.io",
            "https://invest.kernow.cloud",
            "http://localhost:5173",
            "http://localhost:4173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware stack (executed outermost-first: RequestID → Logging → Auth)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Prometheus /metrics endpoint (no auth required)
    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics():
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
        from fastapi.responses import Response

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # Import and mount route modules
    from investmentology.api.routes import (
        analyse,
        assistant,
        auth,
        backtest,
        decisions,
        learning,
        calibration,
        pipeline,
        portfolio,
        push,
        quant_gate,
        recommendations,
        stocks,
        system,
        daily,
        thesis,
        watchlist,
    )
    from investmentology.api import ws

    prefix = "/api/invest"
    app.include_router(assistant.router, prefix=prefix, tags=["assistant"])
    app.include_router(auth.router, prefix=prefix, tags=["auth"])
    app.include_router(portfolio.router, prefix=prefix, tags=["portfolio"])
    app.include_router(quant_gate.router, prefix=prefix, tags=["quant-gate"])
    app.include_router(stocks.router, prefix=prefix, tags=["stocks"])
    app.include_router(watchlist.router, prefix=prefix, tags=["watchlist"])
    app.include_router(decisions.router, prefix=prefix, tags=["decisions"])
    app.include_router(learning.router, prefix=prefix, tags=["learning"])
    app.include_router(system.router, prefix=prefix, tags=["system"])
    app.include_router(analyse.router, prefix=prefix, tags=["analyse"])
    app.include_router(recommendations.router, prefix=prefix, tags=["recommendations"])
    app.include_router(backtest.router, prefix=prefix, tags=["backtest"])
    app.include_router(daily.router, prefix=prefix, tags=["daily"])
    app.include_router(thesis.router, prefix=prefix, tags=["thesis"])
    app.include_router(pipeline.router, prefix=prefix, tags=["pipeline"])
    app.include_router(push.router, prefix=prefix, tags=["push"])
    app.include_router(calibration.router, prefix=prefix, tags=["calibration"])
    app.include_router(ws.router, prefix=prefix, tags=["websocket"])

    return app
