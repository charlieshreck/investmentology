"""Quant Gate endpoints."""

from __future__ import annotations

import asyncio
import logging
import threading

from fastapi import APIRouter, BackgroundTasks, Depends

from investmentology.api.deps import app_state, get_registry
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)
router = APIRouter()

# Screener run state (in-memory, single instance)
_screener_state: dict = {"running": False, "progress": {"stage": "", "detail": "", "pct": 0}}


@router.get("/quant-gate/latest")
def get_latest_run(registry: Registry = Depends(get_registry)) -> dict:
    """Get the latest quant gate run results.

    Response shape matches PWA QuantGateResponse:
    {latestRun: QuantGateRun | null}
    """
    rows = registry._db.execute(
        "SELECT id, run_date, universe_size, passed_count, config, data_quality "
        "FROM invest.quant_gate_runs ORDER BY id DESC LIMIT 1"
    )
    if not rows:
        return {"latestRun": None}

    run = rows[0]
    run_id = run["id"]

    results = registry._db.execute(
        "SELECT r.ticker, r.earnings_yield, r.roic, r.ey_rank, r.roic_rank, "
        "r.combined_rank, r.piotroski_score, r.altman_z_score, "
        "r.composite_score, r.altman_zone, "
        "s.name, s.sector, s.market_cap, "
        "v.verdict, v.confidence AS verdict_confidence, v.created_at AS verdict_date "
        "FROM invest.quant_gate_results r "
        "LEFT JOIN invest.stocks s ON s.ticker = r.ticker "
        "LEFT JOIN LATERAL ("
        "  SELECT verdict, confidence, created_at "
        "  FROM invest.verdicts vd WHERE vd.ticker = r.ticker "
        "  ORDER BY vd.created_at DESC LIMIT 1"
        ") v ON TRUE "
        "WHERE r.run_id = %s "
        "ORDER BY r.composite_score DESC NULLS LAST, r.combined_rank",
        (run_id,),
    )

    analyzed_count = sum(1 for r in results if r.get("verdict"))

    return {
        "latestRun": {
            "id": str(run["id"]),
            "runDate": str(run["run_date"]),
            "stocksScreened": run["universe_size"] or 0,
            "stocksPassed": run["passed_count"] or 0,
            "analyzedCount": analyzed_count,
            "results": [
                {
                    "ticker": r["ticker"],
                    "name": r["name"] or r["ticker"],
                    "roicRank": r["roic_rank"] or 0,
                    "eyRank": r["ey_rank"] or 0,
                    "combinedRank": r["combined_rank"] or 0,
                    "roic": float(r["roic"]) if r["roic"] else 0.0,
                    "earningsYield": float(r["earnings_yield"]) if r["earnings_yield"] else 0.0,
                    "piotroskiScore": r["piotroski_score"] or 0,
                    "altmanZScore": float(r["altman_z_score"]) if r["altman_z_score"] else None,
                    "altmanZone": r["altman_zone"] or None,
                    "compositeScore": float(r["composite_score"]) if r["composite_score"] else None,
                    "marketCap": float(r["market_cap"]) if r["market_cap"] else 0,
                    "sector": r["sector"] or "",
                    "verdict": r["verdict"] or None,
                    "verdictConfidence": float(r["verdict_confidence"]) if r["verdict_confidence"] else None,
                    "verdictDate": str(r["verdict_date"]) if r.get("verdict_date") else None,
                }
                for r in results
            ],
        },
    }


@router.get("/quant-gate/delta")
def get_run_delta(registry: Registry = Depends(get_registry)) -> dict:
    """Compare the two most recent quant gate runs to show additions/removals."""
    runs = registry._db.execute(
        "SELECT id, run_date FROM invest.quant_gate_runs ORDER BY id DESC LIMIT 2"
    )
    if len(runs) < 2:
        return {"delta": None, "message": "Need at least 2 runs for delta"}

    current_id = runs[0]["id"]
    previous_id = runs[1]["id"]

    current_tickers = {
        r["ticker"]
        for r in registry._db.execute(
            "SELECT ticker FROM invest.quant_gate_results WHERE run_id = %s",
            (current_id,),
        )
    }
    previous_tickers = {
        r["ticker"]
        for r in registry._db.execute(
            "SELECT ticker FROM invest.quant_gate_results WHERE run_id = %s",
            (previous_id,),
        )
    }

    return {
        "current_run_id": current_id,
        "previous_run_id": previous_id,
        "current_date": str(runs[0]["run_date"]),
        "previous_date": str(runs[1]["run_date"]),
        "added": sorted(current_tickers - previous_tickers),
        "removed": sorted(previous_tickers - current_tickers),
        "retained": sorted(current_tickers & previous_tickers),
    }


def _run_screener_background() -> None:
    """Run the quant gate screener in a background thread."""
    global _screener_state

    def _update_progress(stage: str, detail: str, pct: int) -> None:
        _screener_state["progress"] = {"stage": stage, "detail": detail, "pct": pct}

    try:
        _screener_state = {"running": True, "progress": {"stage": "starting", "detail": "Initializing...", "pct": 2}}

        from investmentology.data.edgar_client import EdgarClient
        from investmentology.data.yfinance_client import YFinanceClient
        from investmentology.quant_gate.screener import QuantGateScreener

        config = app_state.config
        registry = app_state.registry
        if not config or not registry:
            logger.error("Screener: app not initialized")
            _update_progress("error", "App not initialized", 0)
            return

        yf_client = YFinanceClient()
        edgar_client = EdgarClient() if config.use_edgar else None

        screener = QuantGateScreener(
            registry, yf_client, config,
            edgar_client=edgar_client,
            progress_callback=_update_progress,
        )
        result = screener.run()

        _update_progress(
            "complete",
            f"Done: {len(result.top_results)} stocks passed from {result.data_quality.universe_size} universe",
            100,
        )
        logger.info("Screener run complete: run_id=%d, passed=%d", result.run_id, len(result.top_results))
    except Exception:
        logger.exception("Screener background run failed")
        _screener_state["progress"] = {"stage": "error", "detail": "Screener run failed — check logs", "pct": 0}
    finally:
        _screener_state["running"] = False


@router.get("/quant-gate/status")
def get_screener_status() -> dict:
    """Check if a screener run is in progress."""
    return {"running": _screener_state["running"], "progress": _screener_state["progress"]}


@router.post("/quant-gate/run")
def trigger_screener_run(background_tasks: BackgroundTasks) -> dict:
    """Trigger a new quant gate screener run in the background."""
    if _screener_state["running"]:
        return {"status": "already_running", "message": "A screener run is already in progress"}

    _screener_state["running"] = True
    _screener_state["progress"] = {"stage": "starting", "detail": "Initializing...", "pct": 0}
    thread = threading.Thread(target=_run_screener_background, daemon=True)
    thread.start()
    return {"status": "started", "message": "Screener run started"}
