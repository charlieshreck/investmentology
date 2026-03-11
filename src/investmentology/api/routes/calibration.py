"""Calibration endpoints — verdict accuracy feedback and agent performance."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_registry
from investmentology.registry.queries import Registry

router = APIRouter()


@router.get("/calibration")
def get_calibration(registry: Registry = Depends(get_registry)) -> dict:
    """Calibration dashboard data: per-verdict and per-agent accuracy.

    Returns accuracy at multiple settlement horizons, reliability diagram
    data, and confidence calibration curves.
    """
    from investmentology.learning.calibration import (
        AgentCalibrator,
        CalibrationEngine,
        CalibrationTracker,
    )

    tracker = CalibrationTracker(registry)
    summary = tracker.get_calibration_summary()

    # Add calibration curves from isotonic models (if fitted)
    calibrator = AgentCalibrator(registry)
    try:
        calibrator.fit_all()
        summary["calibration_curves"] = calibrator.get_calibration_curves()
    except Exception:
        summary["calibration_curves"] = {}

    # Add overall calibration metrics (ECE, Brier) from settled 90d data
    try:
        rows = registry._db.execute(
            """SELECT confidence, correct_90d
               FROM invest.calibration_predictions
               WHERE settled_90d = TRUE AND confidence IS NOT NULL""",
        )
        if rows:
            from decimal import Decimal
            settled_data = [
                (Decimal(str(r["confidence"])), bool(r["correct_90d"]))
                for r in rows
            ]
            engine = CalibrationEngine(registry)
            buckets, ece, brier = engine.compute_calibration(settled_data)
            summary["overall_metrics"] = {
                "ece": round(ece, 4),
                "brier": round(brier, 4),
                "sample_count": len(settled_data),
            }
            summary["reliability_diagram"] = [
                {
                    "range": f"{b.low:.0%}-{b.high:.0%}",
                    "predicted": round(b.midpoint, 2),
                    "actual": round(b.accuracy, 3),
                    "count": b.count,
                }
                for b in buckets
                if b.count > 0
            ]
    except Exception:
        summary["overall_metrics"] = None
        summary["reliability_diagram"] = []

    # Multi-horizon accuracy
    try:
        horizon_rows = registry._db.execute(
            """SELECT
                 COUNT(*) FILTER (WHERE settled_30d) AS settled_30d,
                 SUM(CASE WHEN correct_30d THEN 1 ELSE 0 END) AS correct_30d,
                 COUNT(*) FILTER (WHERE settled_90d) AS settled_90d,
                 SUM(CASE WHEN correct_90d THEN 1 ELSE 0 END) AS correct_90d,
                 COUNT(*) FILTER (WHERE settled_180d) AS settled_180d,
                 SUM(CASE WHEN correct_180d THEN 1 ELSE 0 END) AS correct_180d,
                 COUNT(*) FILTER (WHERE settled_365d) AS settled_365d,
                 SUM(CASE WHEN correct_365d THEN 1 ELSE 0 END) AS correct_365d
               FROM invest.calibration_predictions""",
        )
        if horizon_rows:
            r = horizon_rows[0]
            summary["horizon_accuracy"] = {}
            for h in [30, 90, 180, 365]:
                settled = int(r.get(f"settled_{h}d") or 0)
                correct = int(r.get(f"correct_{h}d") or 0)
                summary["horizon_accuracy"][f"{h}d"] = {
                    "settled": settled,
                    "correct": correct,
                    "accuracy": round(correct / settled, 3) if settled > 0 else None,
                }
    except Exception:
        summary["horizon_accuracy"] = {}

    return summary


@router.get("/calibration/leaderboard")
def get_agent_leaderboard(registry: Registry = Depends(get_registry)) -> dict:
    """Agent calibration leaderboard — per-agent accuracy, Brier scores, and ranking.

    Returns agents sorted by accuracy (best first), with:
    - Total settled predictions
    - Accuracy (% correct)
    - Average confidence
    - Brier score (lower = better calibrated)
    - Overconfidence flag (avg confidence > accuracy)
    - Cross-agent correlation (if available)
    """
    agents: list[dict] = []

    try:
        rows = registry._db.execute(
            """SELECT
                 agent_name,
                 COUNT(*) AS total,
                 SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) AS correct,
                 AVG(raw_confidence) AS avg_confidence,
                 AVG(CASE WHEN was_correct THEN (1 - raw_confidence)^2
                          ELSE raw_confidence^2 END) AS brier_score
               FROM invest.agent_calibration_data
               WHERE settled = TRUE
               GROUP BY agent_name
               HAVING COUNT(*) >= 5
               ORDER BY SUM(CASE WHEN was_correct THEN 1 ELSE 0 END)::float / COUNT(*) DESC""",
        )
        for rank, row in enumerate(rows or [], 1):
            total = int(row["total"])
            correct = int(row["correct"])
            accuracy = correct / total if total > 0 else 0
            avg_conf = float(row["avg_confidence"]) if row["avg_confidence"] else 0
            brier = float(row["brier_score"]) if row["brier_score"] else 0

            agents.append({
                "rank": rank,
                "agent": row["agent_name"],
                "totalSettled": total,
                "correct": correct,
                "accuracy": round(accuracy, 3),
                "avgConfidence": round(avg_conf, 3),
                "brierScore": round(brier, 4),
                "overconfident": avg_conf > accuracy + 0.05,
                "readyForKelly": total >= 100,
            })
    except Exception:
        pass

    return {
        "agents": agents,
        "totalAgents": len(agents),
        "minForKelly": 100,
    }


@router.post("/calibration/settle")
def trigger_calibration_settlement(
    registry: Registry = Depends(get_registry),
) -> dict:
    """Settle calibration predictions that have reached their horizon date.

    Run daily from the overnight pipeline. Looks up actual prices for
    predictions that have matured at 30, 90, 180, and 365-day horizons.
    """
    from investmentology.learning.calibration import CalibrationTracker

    tracker = CalibrationTracker(registry)
    results = tracker.settle_predictions()
    total = sum(results.values())
    return {
        "settled": results,
        "total_settled": total,
    }


@router.post("/calibration/fit")
def trigger_calibration_fit(
    registry: Registry = Depends(get_registry),
) -> dict:
    """Refit isotonic calibration models for all agents with sufficient data.

    Run weekly from the overnight pipeline. Requires 100+ settled predictions
    per agent before activation.
    """
    from investmentology.learning.calibration import AgentCalibrator

    calibrator = AgentCalibrator(registry)
    fitted = calibrator.fit_all()
    return {
        "fitted_agents": fitted,
        "total_fitted": len(fitted),
    }


@router.get("/calibration/agent-accuracy")
def get_agent_accuracy(registry: Registry = Depends(get_registry)) -> dict:
    """Per-agent directional signal accuracy by regime.

    Returns accuracy at 30d and 90d horizons, broken down by market regime.
    Also returns dynamically adjusted weights based on historical accuracy.
    """
    from investmentology.learning.agent_accuracy import (
        get_agent_accuracy_stats,
        get_dynamic_weights,
    )

    stats = get_agent_accuracy_stats(registry._db)
    weights = get_dynamic_weights(registry._db)

    return {
        "stats": stats,
        "dynamicWeights": {k: round(v, 4) for k, v in weights.items()},
    }


@router.post("/calibration/settle-accuracy")
def trigger_accuracy_settlement(
    registry: Registry = Depends(get_registry),
) -> dict:
    """Settle agent accuracy records that have matured (30d and 90d)."""
    from investmentology.learning.agent_accuracy import settle_accuracy

    settled = settle_accuracy(registry._db)
    return {"settled": settled}
