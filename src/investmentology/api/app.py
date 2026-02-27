"""FastAPI application factory with CORS, auth middleware, and lifespan management."""

from __future__ import annotations

import asyncio

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from investmentology.api.auth import verify_token

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
            logger.debug("Daily settlement task failed")
        await asyncio.sleep(86400)  # 24 hours


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage startup/shutdown of DB, gateway, and dependent services."""
    config = load_config()

    # Database
    db = Database(config.db_dsn)
    db.connect()
    registry = Registry(db)

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
    logger.info("API started — DB, gateway, and background tasks ready")
    yield

    # Cancel background tasks
    for task in _bg_tasks:
        task.cancel()

    # Shutdown
    await gateway.close()
    db.close()
    logger.info("API shutdown complete")


# Paths that don't require authentication
PUBLIC_PATHS = {
    "/api/invest/auth/login",
    "/api/invest/auth/logout",
    "/api/invest/auth/check",
    "/api/invest/system/health",
}


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

        # Skip auth entirely if no secret key is configured (dev mode)
        config = app_state.config
        if not config or not config.auth_secret_key:
            return await call_next(request)

        # Internal token bypass (for trusted proxies like Tamar)
        internal_token = request.headers.get("x-internal-token")
        if internal_token and config.internal_api_token and internal_token == config.internal_api_token:
            return await call_next(request)

        # Validate session cookie
        token = request.cookies.get("session")
        if not token or not verify_token(token, config.auth_secret_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        return await call_next(request)


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

    # Auth middleware — must be added before routes
    app.add_middleware(AuthMiddleware)

    # Import and mount route modules
    from investmentology.api.routes import (
        analyse,
        auth,
        backtest,
        decisions,
        learning,
        portfolio,
        quant_gate,
        recommendations,
        stocks,
        system,
        daily,
        watchlist,
    )
    from investmentology.api import ws

    prefix = "/api/invest"
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
    app.include_router(ws.router, prefix=prefix, tags=["websocket"])

    return app
