"""Learning/calibration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_calibration_engine, get_registry
from investmentology.learning.calibration import CalibrationEngine
from investmentology.learning.predictions import PredictionManager
from investmentology.registry.queries import Registry

router = APIRouter()


@router.get("/learning/calibration")
def get_calibration(
    registry: Registry = Depends(get_registry),
    engine: CalibrationEngine = Depends(get_calibration_engine),
) -> dict:
    """Calibration data.

    Response shape matches PWA CalibrationResponse:
    {buckets: CalibrationBucket[], brierScore, totalPredictions}
    """
    pm = PredictionManager(registry)
    data = pm.get_calibration_data()

    return {
        "buckets": [
            {
                "midpoint": (b["low"] + b["high"]) / 2,
                "accuracy": b["accuracy"],
                "count": b["count"],
            }
            for b in data.get("buckets", [])
        ],
        "brierScore": data.get("brier", 0.0),
        "totalPredictions": data.get("total_settled", 0),
    }


@router.get("/learning/agents")
def get_agent_performance(registry: Registry = Depends(get_registry)) -> dict:
    """Per-agent performance summary."""
    rows = registry._db.execute(
        "SELECT agent_name, "
        "COUNT(*) as total_signals, "
        "AVG(confidence) as avg_confidence, "
        "AVG(latency_ms) as avg_latency_ms "
        "FROM invest.agent_signals "
        "GROUP BY agent_name "
        "ORDER BY agent_name"
    )
    return {
        "agents": [
            {
                "agent_name": r["agent_name"],
                "total_signals": r["total_signals"],
                "avg_confidence": float(r["avg_confidence"]) if r["avg_confidence"] else None,
                "avg_latency_ms": float(r["avg_latency_ms"]) if r["avg_latency_ms"] else None,
            }
            for r in rows
        ],
    }

@router.post("/learning/settle")
def trigger_settlement(registry: Registry = Depends(get_registry)) -> dict:
    """Trigger settlement of all due predictions.

    Looks up actual prices via yfinance for predictions where
    settlement_date <= today, and records the actual values.
    """
    pm = PredictionManager(registry)
    settled = pm.settle_due_predictions()
    return {
        "settled_count": len(settled),
        "settlements": [
            {"prediction_id": pid, "actual_value": float(val)}
            for pid, val in settled
        ],
    }


@router.get("/learning/attribution")
def get_attribution(registry: Registry = Depends(get_registry)) -> dict:
    """Agent performance attribution report.

    Computes per-agent accuracy, bullish/bearish splits, signal tag
    performance, and recommended weight adjustments.
    """
    from investmentology.learning.attribution import AgentAttributionEngine

    engine = AgentAttributionEngine(registry)
    report = engine.compute_attribution()

    if report is None:
        return {
            "status": "insufficient_data",
            "message": "Need at least 20 settled decisions for attribution",
            "agents": {},
            "recommended_weights": {},
            "top_signals": [],
            "worst_signals": [],
            "recommendations": [],
        }

    return {
        "status": "ok",
        "agents": {
            name: {
                "total_calls": attr.total_calls,
                "accuracy": round(attr.accuracy, 3),
                "bullish_accuracy": round(attr.bullish_accuracy, 3),
                "bearish_accuracy": round(attr.bearish_accuracy, 3),
                "bullish_total": attr.bullish_total,
                "bearish_total": attr.bearish_total,
            }
            for name, attr in report.agents.items()
        },
        "recommended_weights": report.recommended_weights,
        "top_signals": [
            {"agent": agent, "signal": tag, "accuracy": round(acc, 3)}
            for agent, tag, acc in report.top_signals
        ],
        "worst_signals": [
            {"agent": agent, "signal": tag, "accuracy": round(acc, 3)}
            for agent, tag, acc in report.worst_signals
        ],
        "recommendations": report.recommendations,
        "overrideOutcomes": [
            {
                "type": o.override_type,
                "totalOverrides": o.total_overrides,
                "totalSettled": o.total_settled,
                "correct": o.override_correct,
                "wrong": o.override_wrong,
                "valueAddedPct": o.value_added_pct,
            }
            for o in (report.override_outcomes or [])
        ],
    }


@router.get("/learning/buzz/{ticker}")
def get_ticker_buzz(ticker: str) -> dict:
    """Buzz score for a single ticker (SearXNG + Finnhub news)."""
    import os
    from investmentology.data.buzz_scorer import BuzzScorer
    from investmentology.data.finnhub_provider import FinnhubProvider

    fh_key = os.environ.get("FINNHUB_API_KEY", "")
    finnhub = FinnhubProvider(fh_key) if fh_key else None
    scorer = BuzzScorer(finnhub_provider=finnhub)
    result = scorer.score_ticker(ticker.upper())
    return {"status": "ok", "ticker": ticker.upper(), **result}


@router.get("/learning/earnings/{ticker}")
def get_ticker_earnings(
    ticker: str,
    registry: Registry = Depends(get_registry),
) -> dict:
    """Earnings revision momentum for a single ticker."""
    import os
    from investmentology.data.earnings_tracker import EarningsTracker
    from investmentology.data.finnhub_provider import FinnhubProvider

    fh_key = os.environ.get("FINNHUB_API_KEY", "")
    if not fh_key:
        return {"status": "unavailable", "message": "FINNHUB_API_KEY not set"}

    finnhub = FinnhubProvider(fh_key)
    tracker = EarningsTracker(finnhub, registry)

    # Capture latest snapshot
    snapshot = tracker.capture_snapshot(ticker.upper())
    momentum = tracker.compute_momentum(ticker.upper())

    return {
        "status": "ok",
        "ticker": ticker.upper(),
        "snapshot": snapshot,
        "momentum": momentum,
    }


@router.get("/learning/pendulum")
def get_pendulum_reading() -> dict:
    """Live pendulum (fear/greed) reading from market data."""
    from investmentology.data.pendulum_feeds import auto_pendulum_reading

    reading = auto_pendulum_reading()
    if reading is None:
        return {
            "status": "unavailable",
            "message": "VIX data unavailable — cannot compute pendulum",
        }

    return {
        "status": "ok",
        "score": reading.score,
        "label": reading.label,
        "sizing_multiplier": float(reading.sizing_multiplier),
        "components": reading.components,
    }
