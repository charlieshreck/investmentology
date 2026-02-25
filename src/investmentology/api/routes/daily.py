"""Daily advisory briefing API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from investmentology.advisory.briefing import BriefingBuilder, briefing_to_dict
from investmentology.api.deps import get_registry
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache the latest briefing in memory (refreshed on each call)
_cached_briefing: dict | None = None


@router.get("/daily/briefing")
def get_daily_briefing(registry: Registry = Depends(get_registry)) -> dict:
    """Generate and return the daily advisory briefing.

    This endpoint builds a comprehensive financial review combining:
    - Market overview (pendulum, macro signals)
    - Portfolio snapshot (positions, P&L, sector exposure)
    - New recommendations from recent analysis runs
    - Position alerts (stop-loss, drawdown, fair value overshoot)
    - Risk summary (concentration, sector imbalances)
    - Prioritized action items

    The briefing is generated fresh on each call using current data.
    """
    global _cached_briefing

    builder = BriefingBuilder(registry)
    briefing = builder.build()
    result = briefing_to_dict(briefing)

    _cached_briefing = result
    return result


@router.get("/daily/briefing/summary")
def get_briefing_summary(registry: Registry = Depends(get_registry)) -> dict:
    """Return a condensed version of the daily briefing — just key metrics and action items."""
    builder = BriefingBuilder(registry)
    briefing = builder.build()

    return {
        "date": briefing.date,
        "pendulumScore": briefing.market_overview.pendulum.get("score"),
        "pendulumLabel": briefing.market_overview.pendulum.get("label"),
        "positionCount": briefing.portfolio_snapshot.position_count,
        "totalValue": round(briefing.portfolio_snapshot.total_value, 2),
        "totalUnrealizedPnl": round(briefing.portfolio_snapshot.total_unrealized_pnl, 2),
        "newRecommendationCount": len(briefing.new_recommendations),
        "alertCount": len(briefing.position_alerts),
        "criticalAlertCount": sum(1 for a in briefing.position_alerts if a.severity == "critical"),
        "overallRiskLevel": briefing.risk_summary.overall_risk_level,
        "topActions": [
            {"priority": a.priority, "category": a.category, "ticker": a.ticker, "action": a.action}
            for a in briefing.action_items[:5]
        ],
    }



@router.get("/daily/reanalysis")
def get_reanalysis_status(registry: Registry = Depends(get_registry)) -> dict:
    """Check current trigger conditions and recent re-analysis events.

    Returns which triggers would fire NOW and recent verdict changes.
    """
    from investmentology.advisory.triggers import ReanalysisTrigger

    trigger = ReanalysisTrigger(registry)
    events = trigger.check_triggers()

    # Get recent verdict changes from decisions
    recent_changes = []
    try:
        rows = registry._db.execute(
            """SELECT ticker, action, reasoning, confidence, signals, created_at
               FROM invest.decisions
               WHERE decision_type = 'verdict_change'
               ORDER BY created_at DESC
               LIMIT 20""",
        )
        for r in rows:
            recent_changes.append({
                "ticker": r["ticker"],
                "change": r.get("action"),
                "reasoning": r.get("reasoning"),
                "severity": r.get("signals", {}).get("severity") if isinstance(r.get("signals"), dict) else None,
                "date": str(r["created_at"])[:19] if r.get("created_at") else None,
            })
    except Exception:
        pass

    # Get recent trigger events
    recent_triggers = []
    try:
        rows = registry._db.execute(
            """SELECT ticker, action, reasoning, signals, created_at
               FROM invest.decisions
               WHERE decision_type = 'reanalysis_trigger'
               ORDER BY created_at DESC
               LIMIT 10""",
        )
        for r in rows:
            recent_triggers.append({
                "trigger_type": r.get("action"),
                "reason": r.get("reasoning"),
                "tickers": r.get("signals", {}).get("tickers") if isinstance(r.get("signals"), dict) else [],
                "severity": r.get("signals", {}).get("severity") if isinstance(r.get("signals"), dict) else None,
                "date": str(r["created_at"])[:19] if r.get("created_at") else None,
            })
    except Exception:
        pass

    return {
        "currentTriggers": [
            {
                "type": e.trigger_type,
                "severity": e.severity,
                "reason": e.reason,
                "tickers": e.tickers,
            }
            for e in events
        ],
        "activeTriggerCount": len(events),
        "recentVerdictChanges": recent_changes,
        "recentTriggers": recent_triggers,
    }
