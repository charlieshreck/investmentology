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
