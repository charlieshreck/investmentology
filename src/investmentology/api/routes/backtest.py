"""Backtest API endpoints."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from investmentology.api.deps import get_registry
from investmentology.backtesting.runner import BacktestRunner
from investmentology.backtesting.tearsheet import generate_tearsheet
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

router = APIRouter()


class BacktestRequest(BaseModel):
    start_date: str
    end_date: str
    initial_capital: float = 100_000.0


@router.post("/backtest/run")
def run_backtest(
    body: BacktestRequest,
    registry: Registry = Depends(get_registry),
) -> dict:
    """Run a backtest for the given date range."""
    try:
        start = date.fromisoformat(body.start_date)
        end = date.fromisoformat(body.end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    if end <= start:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    if body.initial_capital <= 0:
        raise HTTPException(status_code=400, detail="initial_capital must be positive")

    runner = BacktestRunner(registry=registry)
    try:
        result = runner.run(start, end, body.initial_capital)
    except Exception:
        logger.exception("Backtest failed")
        raise HTTPException(status_code=500, detail="Backtest execution failed")

    tearsheet = generate_tearsheet(result)

    # Store result in DB
    try:
        registry._db.execute(
            """INSERT INTO invest.backtests
               (strategy_name, start_date, end_date, initial_capital,
                total_return, sharpe_ratio, max_drawdown, win_rate, total_trades, result_json)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
            (
                "pipeline_replay",
                start,
                end,
                body.initial_capital,
                result.total_return,
                result.sharpe_ratio,
                result.max_drawdown,
                result.win_rate,
                result.total_trades,
                __import__("json").dumps(tearsheet),
            ),
        )
    except Exception:
        logger.warning("Could not save backtest result to DB", exc_info=True)

    return tearsheet


@router.get("/backtest/history")
def get_backtest_history(registry: Registry = Depends(get_registry)) -> dict:
    """Return list of past backtest runs."""
    try:
        rows = registry._db.execute(
            """SELECT id, strategy_name, start_date, end_date, initial_capital,
                      total_return, sharpe_ratio, max_drawdown, win_rate, total_trades, created_at
               FROM invest.backtests
               ORDER BY created_at DESC
               LIMIT 20"""
        )
        return {
            "runs": [
                {
                    "id": r["id"],
                    "strategyName": r["strategy_name"],
                    "startDate": str(r["start_date"]),
                    "endDate": str(r["end_date"]),
                    "initialCapital": float(r["initial_capital"]),
                    "totalReturn": float(r["total_return"]),
                    "sharpeRatio": float(r["sharpe_ratio"]),
                    "maxDrawdown": float(r["max_drawdown"]),
                    "winRate": float(r["win_rate"]),
                    "totalTrades": r["total_trades"],
                    "createdAt": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
        }
    except Exception:
        logger.warning("Could not fetch backtest history", exc_info=True)
        return {"runs": []}
