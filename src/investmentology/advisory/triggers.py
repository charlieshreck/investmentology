"""Market condition triggers and automated re-analysis.

Monitors market conditions and portfolio state to trigger re-analysis:
  - Periodic: Re-analyze all held positions every N days
  - Pendulum shift: >20 point change in a week triggers portfolio review
  - VIX spike: VIX > 30 triggers emergency review
  - Position drawdown: >10% single-day drop triggers individual review

Designed to run as a background task in the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

# Configurable thresholds
REANALYSIS_INTERVAL_DAYS = 7
PENDULUM_SHIFT_THRESHOLD = 20  # points
VIX_EMERGENCY_THRESHOLD = 30
POSITION_DRAWDOWN_THRESHOLD = -10.0  # percent single-day
CHECK_INTERVAL_HOURS = 6  # how often to check conditions


@dataclass
class TriggerEvent:
    """A triggered re-analysis event."""
    trigger_type: str  # "periodic", "pendulum_shift", "vix_spike", "position_drawdown"
    tickers: list[str]
    reason: str
    severity: str  # "routine", "elevated", "emergency"
    triggered_at: datetime = field(default_factory=datetime.now)


@dataclass
class TriggerState:
    """Persistent state for trigger tracking."""
    last_full_reanalysis: date | None = None
    last_pendulum_score: int | None = None
    last_pendulum_date: date | None = None
    last_check: datetime | None = None


class ReanalysisTrigger:
    """Evaluates market conditions and decides when to trigger re-analysis."""

    def __init__(self, registry: Registry):
        self._registry = registry
        self._state = TriggerState()

    def check_triggers(self) -> list[TriggerEvent]:
        """Check all trigger conditions and return events that should fire."""
        events: list[TriggerEvent] = []

        # 1. Periodic re-analysis
        periodic = self._check_periodic()
        if periodic:
            events.append(periodic)

        # 2. Pendulum shift
        pendulum = self._check_pendulum_shift()
        if pendulum:
            events.append(pendulum)

        # 3. VIX spike
        vix = self._check_vix_spike()
        if vix:
            events.append(vix)

        # 4. Position drawdowns
        drawdowns = self._check_position_drawdowns()
        events.extend(drawdowns)

        self._state.last_check = datetime.now()
        return events

    def _check_periodic(self) -> TriggerEvent | None:
        """Check if it's time for routine portfolio re-analysis."""
        today = date.today()

        if self._state.last_full_reanalysis is None:
            # First run — check DB for last analysis dates
            try:
                positions = self._registry.get_open_positions()
                if not positions:
                    return None

                tickers = [p.ticker for p in positions]
                # Check when each was last analyzed
                stale_tickers = []
                for ticker in tickers:
                    verdict = self._registry.get_latest_verdict(ticker)
                    if verdict:
                        verdict_date = verdict.get("created_at")
                        if verdict_date:
                            if isinstance(verdict_date, str):
                                verdict_date = datetime.fromisoformat(verdict_date[:10]).date()
                            elif isinstance(verdict_date, datetime):
                                verdict_date = verdict_date.date()
                            if (today - verdict_date).days >= REANALYSIS_INTERVAL_DAYS:
                                stale_tickers.append(ticker)
                    else:
                        stale_tickers.append(ticker)

                self._state.last_full_reanalysis = today

                if stale_tickers:
                    return TriggerEvent(
                        trigger_type="periodic",
                        tickers=stale_tickers,
                        reason=f"{len(stale_tickers)} positions not analyzed in {REANALYSIS_INTERVAL_DAYS}+ days",
                        severity="routine",
                    )
            except Exception:
                logger.debug("Periodic trigger check failed")
                return None

        elif (today - self._state.last_full_reanalysis).days >= REANALYSIS_INTERVAL_DAYS:
            # Time for full re-analysis
            positions = self._registry.get_open_positions()
            if not positions:
                self._state.last_full_reanalysis = today
                return None

            tickers = [p.ticker for p in positions]
            self._state.last_full_reanalysis = today
            return TriggerEvent(
                trigger_type="periodic",
                tickers=tickers,
                reason=f"Scheduled {REANALYSIS_INTERVAL_DAYS}-day portfolio re-analysis",
                severity="routine",
            )

        return None

    def _check_pendulum_shift(self) -> TriggerEvent | None:
        """Check if the pendulum has shifted significantly."""
        try:
            from investmentology.data.pendulum_feeds import auto_pendulum_reading
            reading = auto_pendulum_reading()
            if not reading:
                return None

            current_score = int(reading.score)
            today = date.today()

            if self._state.last_pendulum_score is not None:
                shift = abs(current_score - self._state.last_pendulum_score)
                days_elapsed = (today - self._state.last_pendulum_date).days if self._state.last_pendulum_date else 999

                if shift >= PENDULUM_SHIFT_THRESHOLD and days_elapsed <= 7:
                    direction = "toward fear" if current_score < self._state.last_pendulum_score else "toward greed"
                    positions = self._registry.get_open_positions()
                    tickers = [p.ticker for p in positions] if positions else []

                    self._state.last_pendulum_score = current_score
                    self._state.last_pendulum_date = today

                    if tickers:
                        return TriggerEvent(
                            trigger_type="pendulum_shift",
                            tickers=tickers,
                            reason=f"Pendulum shifted {shift} points {direction} ({self._state.last_pendulum_score} -> {current_score})",
                            severity="elevated",
                        )

            self._state.last_pendulum_score = current_score
            self._state.last_pendulum_date = today

        except Exception:
            logger.debug("Pendulum shift check failed")

        return None

    def _check_vix_spike(self) -> TriggerEvent | None:
        """Check if VIX is above emergency threshold."""
        try:
            from investmentology.data.pendulum_feeds import fetch_pendulum_inputs
            inputs = fetch_pendulum_inputs()
            vix = inputs.get("vix")
            if vix is None:
                return None

            if float(vix) >= VIX_EMERGENCY_THRESHOLD:
                positions = self._registry.get_open_positions()
                tickers = [p.ticker for p in positions] if positions else []
                if tickers:
                    return TriggerEvent(
                        trigger_type="vix_spike",
                        tickers=tickers,
                        reason=f"VIX at {float(vix):.1f} (>= {VIX_EMERGENCY_THRESHOLD}) — emergency portfolio review",
                        severity="emergency",
                    )
        except Exception:
            logger.debug("VIX spike check failed")

        return None

    def _check_position_drawdowns(self) -> list[TriggerEvent]:
        """Check for positions with significant single-day drops via yfinance."""
        events = []
        try:
            positions = self._registry.get_open_positions()
            if not positions:
                return events

            import yfinance as yf
            tickers = [p.ticker for p in positions]
            # Batch fetch 2-day history for all positions
            data = yf.download(tickers, period="2d", progress=False, group_by="ticker")

            for p in positions:
                try:
                    if len(tickers) == 1:
                        hist = data
                    else:
                        hist = data[p.ticker] if p.ticker in data.columns.get_level_values(0) else None
                    if hist is None or len(hist) < 2:
                        continue
                    close = hist["Close"].squeeze()
                    prev_close = float(close.iloc[-2])
                    curr_close = float(close.iloc[-1])
                    if prev_close > 0:
                        day_pct = (curr_close - prev_close) / prev_close * 100
                        if day_pct <= POSITION_DRAWDOWN_THRESHOLD:
                            events.append(TriggerEvent(
                                trigger_type="position_drawdown",
                                tickers=[p.ticker],
                                reason=f"{p.ticker} dropped {day_pct:.1f}% today",
                                severity="elevated",
                            ))
                except Exception:
                    continue
        except Exception:
            logger.debug("Position drawdown check failed")

        return events


async def reanalysis_loop(registry: Registry, orchestrator) -> None:
    """Background loop that checks triggers and runs re-analysis.

    Args:
        registry: Database registry for portfolio queries.
        orchestrator: AnalysisOrchestrator for running analysis.
    """
    trigger = ReanalysisTrigger(registry)

    # Wait a bit on startup to let other services initialize
    await asyncio.sleep(60)

    while True:
        try:
            events = trigger.check_triggers()

            for event in events:
                logger.info(
                    "Re-analysis trigger: %s (%s) — %s — %d tickers",
                    event.trigger_type, event.severity, event.reason, len(event.tickers),
                )

                # Log the trigger as a decision
                try:
                    from investmentology.learning.registry import DecisionLogger
                    dl = DecisionLogger(registry)
                    dl.log_decision(
                        ticker=event.tickers[0] if len(event.tickers) == 1 else "PORTFOLIO",
                        decision_type="reanalysis_trigger",
                        action=event.trigger_type,
                        reasoning=event.reason,
                        confidence=Decimal("1.0"),
                        signals={"tickers": event.tickers, "severity": event.severity},
                    )
                except Exception:
                    pass

                # Run re-analysis (only for routine and elevated — emergency just logs)
                if event.severity != "emergency" and event.tickers:
                    try:
                        # Build portfolio context so agents know stocks are held
                        from investmentology.api.routes.analyse import _build_portfolio_context
                        portfolio_context = _build_portfolio_context(registry)
                        result = await orchestrator.analyze_candidates(
                            event.tickers, portfolio_context=portfolio_context,
                        )
                        logger.info(
                            "Re-analysis complete: %d analyzed, %d conviction buys",
                            result.analyzed, result.conviction_buys,
                        )

                        # Check for verdict changes on held positions
                        _check_verdict_changes(registry, event.tickers)
                    except Exception:
                        logger.exception("Re-analysis failed for trigger %s", event.trigger_type)

                elif event.severity == "emergency":
                    # For emergency: just log alert, don't auto-analyze
                    # (VIX spike analysis would be unreliable during market panic)
                    logger.warning("EMERGENCY trigger: %s — logged but NOT auto-analyzing", event.reason)

        except Exception:
            logger.exception("Re-analysis loop iteration failed")

        # Sleep between checks
        await asyncio.sleep(CHECK_INTERVAL_HOURS * 3600)


def _check_verdict_changes(registry: Registry, tickers: list[str]) -> None:
    """Compare new verdicts with previous ones and log changes."""
    for ticker in tickers:
        try:
            # Get the two most recent verdicts
            rows = registry._db.execute(
                """SELECT verdict, confidence, created_at
                   FROM invest.verdicts
                   WHERE ticker = %s
                   ORDER BY created_at DESC
                   LIMIT 2""",
                (ticker,),
            )
            if len(rows) < 2:
                continue

            new_verdict = rows[0]["verdict"]
            old_verdict = rows[1]["verdict"]

            if new_verdict != old_verdict:
                # Classify the change
                positive = {"STRONG_BUY", "BUY", "ACCUMULATE"}
                negative = {"REDUCE", "SELL", "AVOID"}

                if old_verdict in positive and new_verdict in negative:
                    severity = "critical"
                elif old_verdict in negative and new_verdict in positive:
                    severity = "positive"
                else:
                    severity = "notable"

                logger.warning(
                    "Verdict change for %s: %s -> %s (severity: %s)",
                    ticker, old_verdict, new_verdict, severity,
                )

                # Log as alert-worthy decision
                from investmentology.learning.registry import DecisionLogger
                dl = DecisionLogger(registry)
                dl.log_decision(
                    ticker=ticker,
                    decision_type="verdict_change",
                    action=f"{old_verdict}_to_{new_verdict}",
                    reasoning=f"Re-analysis changed verdict from {old_verdict} to {new_verdict}",
                    confidence=Decimal(str(rows[0]["confidence"])) if rows[0].get("confidence") else Decimal("0.5"),
                    signals={
                        "old_verdict": old_verdict,
                        "new_verdict": new_verdict,
                        "severity": severity,
                    },
                )
        except Exception:
            logger.debug("Verdict change check failed for %s", ticker)
