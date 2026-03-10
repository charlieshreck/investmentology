"""Daily advisory briefing API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from investmentology.advisory.briefing import BriefingBuilder, DailyBriefing, briefing_to_dict
from investmentology.advisory.narrative_briefing import BriefingInputs, build_monday_briefing
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

    components = briefing.market_overview.pendulum.get("components", {})
    return {
        "date": briefing.date,
        "pendulumScore": briefing.market_overview.pendulum.get("score"),
        "pendulumLabel": briefing.market_overview.pendulum.get("label"),
        "pendulumComponents": {
            "vix": components.get("vix"),
            "creditSpread": components.get("hy_oas"),
            "putCall": components.get("put_call"),
            "momentum": components.get("momentum"),
        } if components else None,
        "sizingMultiplier": briefing.market_overview.pendulum.get("sizing_multiplier"),
        "macroSignals": briefing.market_overview.macro_signals,
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



def _briefing_to_narrative_inputs(
    briefing: DailyBriefing,
    registry: Registry,
) -> BriefingInputs:
    """Convert a DailyBriefing into narrative BriefingInputs, including earnings calendar."""
    from investmentology.advisory.earnings_calendar import (
        classify_earnings_proximity,
        format_earnings_alert,
    )

    # Section 1: critical alerts + thesis health
    critical = [a.message for a in briefing.position_alerts if a.severity == "critical"]
    thesis_challenges: list[str] = []
    for pos in briefing.portfolio_snapshot.positions:
        try:
            from investmentology.advisory.thesis_health import assess_thesis_health, ThesisHealth
            assessment = assess_thesis_health(pos.ticker, registry)
            if assessment.health in (ThesisHealth.CHALLENGED, ThesisHealth.BROKEN):
                thesis_challenges.append(f"{pos.ticker}: {assessment.reasoning}")
        except Exception:
            pass

    # Section 2: earnings proximity + macro
    earnings_alerts: list[str] = []
    tickers = (
        [p.ticker for p in briefing.portfolio_snapshot.positions]
        + [r.ticker for r in briefing.new_recommendations]
    )
    for ticker in dict.fromkeys(tickers):  # dedupe preserving order
        try:
            import yfinance as yf
            cal = yf.Ticker(ticker).calendar
            if cal is not None and isinstance(cal, dict):
                earnings_data = {"upcoming_earnings_date": cal.get("Earnings Date", [None])[0]}
            else:
                earnings_data = None
            proximity = classify_earnings_proximity(ticker, earnings_data)
            alert = format_earnings_alert(proximity)
            if alert:
                earnings_alerts.append(alert)
        except Exception:
            pass

    # Section 3: watchlist gap
    held = {p.ticker for p in briefing.portfolio_snapshot.positions}
    buy_not_held = [
        f"{r.ticker} — {r.verdict} (conf {r.confidence:.0%})"
        for r in briefing.new_recommendations
        if r.ticker not in held
    ]

    # Section 4: sell discipline
    sell_alerts = [
        a.message for a in briefing.position_alerts
        if a.alert_type in ("above_fair_value", "drawdown") and a.severity in ("high", "medium")
    ]

    # Section 5: posture
    sector_warnings = briefing.risk_summary.concentration_warnings + briefing.risk_summary.sector_imbalances

    # Cash regime guidance
    alloc_guidance = ""
    try:
        from investmentology.advisory.portfolio_fit import get_cash_regime_guidance
        # Fetch latest macro regime from pipeline data cache
        macro_rows = registry._db.execute(
            "SELECT data_value FROM invest.pipeline_data_cache "
            "WHERE ticker = '__cycle__' AND data_key = 'macro_regime' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        macro_regime = macro_rows[0]["data_value"] if macro_rows else None
        guidance = get_cash_regime_guidance(macro_regime)
        if guidance:
            alloc_guidance = (
                f"Macro regime: {guidance.regime} — {guidance.stance.value} "
                f"(equity {guidance.equity_min_pct}-{guidance.equity_max_pct}%)"
            )
    except Exception:
        pass

    perf_vs_spy = ""
    if briefing.performance and briefing.performance.get("alphaPct") is not None:
        alpha = briefing.performance["alphaPct"]
        perf_vs_spy = f"Portfolio alpha vs SPY: {alpha:+.1f}%"

    return BriefingInputs(
        critical_alerts=critical,
        thesis_challenges=thesis_challenges,
        earnings_alerts=earnings_alerts,
        macro_signals=briefing.market_overview.macro_signals,
        buy_rated_not_held=buy_not_held,
        sell_discipline_alerts=sell_alerts,
        monitoring_notes=[a.message for a in briefing.position_alerts if a.severity == "low"],
        position_count=briefing.portfolio_snapshot.position_count,
        total_value=briefing.portfolio_snapshot.total_value,
        cash_pct=briefing.portfolio_snapshot.cash_pct,
        sector_warnings=sector_warnings,
        allocation_guidance=alloc_guidance,
        performance_vs_spy=perf_vs_spy,
        overall_risk_level=briefing.risk_summary.overall_risk_level,
    )


@router.get("/daily/briefing/narrative")
def get_narrative_briefing(registry: Registry = Depends(get_registry)) -> dict:
    """Monday morning narrative briefing — prioritized, read-in-5-minutes format.

    Transforms the data-heavy daily briefing into a narrative:
      1. Immediate attention (thesis health, critical alerts)
      2. This week's events (earnings proximity, macro)
      3. Watchlist gap (BUY-rated not held)
      4. Monitoring (sell discipline, F-Score changes)
      5. Portfolio posture (cash, sectors, performance vs SPY)
    """
    builder = BriefingBuilder(registry)
    briefing = builder.build()
    inputs = _briefing_to_narrative_inputs(briefing, registry)
    narrative = build_monday_briefing(inputs)
    return narrative.to_dict()


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
