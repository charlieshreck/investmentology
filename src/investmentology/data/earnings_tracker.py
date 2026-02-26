"""Earnings revision tracker — monitors EPS estimate changes over time.

Captures Finnhub earnings data snapshots and computes revision momentum:
- Tracks EPS estimates per period
- Detects upward/downward revision trends
- Computes momentum score (-1.0 to 1.0)
- Flags stocks with strong positive revision momentum (3+ upward in 90d)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _momentum_label(score: float) -> str:
    if score >= 0.5:
        return "STRONG_UPWARD"
    if score >= 0.1:
        return "IMPROVING"
    if score <= -0.5:
        return "DECLINING"
    if score <= -0.1:
        return "WEAKENING"
    return "STABLE"


class EarningsTracker:
    """Track EPS estimate revisions and compute momentum."""

    def __init__(self, finnhub_provider, registry) -> None:
        self._finnhub = finnhub_provider
        self._registry = registry

    def capture_snapshot(self, ticker: str) -> dict | None:
        """Capture current earnings estimates for a ticker and store in DB.

        Returns the captured data or None if unavailable.
        """
        if not self._finnhub:
            return None

        earnings = self._finnhub.get_earnings(ticker)
        if not earnings:
            return None

        captured = []

        # Store upcoming estimate
        upcoming = earnings.get("upcoming")
        if upcoming and upcoming.get("date"):
            self._store_revision(
                ticker,
                period=upcoming["date"],
                eps_estimate=upcoming.get("eps_estimate"),
                revenue_estimate=upcoming.get("revenue_estimate"),
            )
            captured.append({"period": upcoming["date"], "eps_estimate": upcoming.get("eps_estimate")})

        # Store recent surprises (actuals)
        for s in earnings.get("recent_surprises", []):
            if s.get("period"):
                self._store_revision(
                    ticker,
                    period=s["period"],
                    eps_estimate=s.get("estimated_eps"),
                    actual_eps=s.get("actual_eps"),
                    surprise_pct=s.get("surprise_pct"),
                )
                captured.append({
                    "period": s["period"],
                    "actual_eps": s.get("actual_eps"),
                    "surprise_pct": s.get("surprise_pct"),
                })

        return {
            "ticker": ticker,
            "captured_count": len(captured),
            "data": captured,
            "beat_count": earnings.get("beat_count", 0),
            "miss_count": earnings.get("miss_count", 0),
        }

    def _store_revision(
        self,
        ticker: str,
        period: str,
        eps_estimate: float | None = None,
        revenue_estimate: float | None = None,
        actual_eps: float | None = None,
        surprise_pct: float | None = None,
    ) -> None:
        try:
            self._registry._db.execute(
                """INSERT INTO invest.earnings_revisions
                   (ticker, period, eps_estimate, revenue_estimate, actual_eps, surprise_pct)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (ticker, period, eps_estimate, revenue_estimate, actual_eps, surprise_pct),
            )
        except Exception:
            logger.debug("Failed to store earnings revision for %s/%s", ticker, period)

    def compute_momentum(self, ticker: str) -> dict:
        """Compute earnings revision momentum for a ticker.

        Looks at how EPS estimates have changed over the last 90 days
        by comparing snapshots of the same period.
        """
        cutoff = (datetime.now() - timedelta(days=90)).isoformat()
        try:
            rows = self._registry._db.execute(
                """SELECT period, eps_estimate, captured_at
                   FROM invest.earnings_revisions
                   WHERE ticker = %s
                     AND captured_at >= %s
                     AND eps_estimate IS NOT NULL
                   ORDER BY period, captured_at""",
                (ticker, cutoff),
            )
        except Exception:
            return self._empty_momentum()

        if not rows:
            return self._empty_momentum()

        # Group by period, detect revision direction
        periods: dict[str, list[float]] = {}
        for r in rows:
            period = r["period"]
            est = float(r["eps_estimate"])
            if period not in periods:
                periods[period] = []
            periods[period].append(est)

        upward = 0
        downward = 0
        for estimates in periods.values():
            if len(estimates) >= 2:
                # Compare first vs last estimate
                if estimates[-1] > estimates[0] * 1.01:  # >1% increase
                    upward += 1
                elif estimates[-1] < estimates[0] * 0.99:  # >1% decrease
                    downward += 1

        total_revisions = upward + downward
        if total_revisions == 0:
            momentum_score = 0.0
        else:
            momentum_score = (upward - downward) / total_revisions

        # Beat streak from actuals
        beat_streak = self._get_beat_streak(ticker)

        # Latest estimate
        latest_estimate = None
        if rows:
            latest_estimate = float(rows[-1]["eps_estimate"])

        result = {
            "revision_count_90d": total_revisions,
            "upward_revisions": upward,
            "downward_revisions": downward,
            "momentum_score": round(momentum_score, 3),
            "momentum_label": _momentum_label(momentum_score),
            "latest_eps_estimate": latest_estimate,
            "beat_streak": beat_streak,
        }

        # Persist momentum
        try:
            self._registry._db.execute(
                """INSERT INTO invest.earnings_momentum
                   (ticker, revision_count_90d, upward_revisions, downward_revisions,
                    momentum_score, momentum_label, latest_eps_estimate, beat_streak)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    ticker,
                    result["revision_count_90d"],
                    result["upward_revisions"],
                    result["downward_revisions"],
                    result["momentum_score"],
                    result["momentum_label"],
                    result["latest_eps_estimate"],
                    result["beat_streak"],
                ),
            )
        except Exception:
            logger.debug("Failed to persist earnings momentum for %s", ticker)

        return result

    def _get_beat_streak(self, ticker: str) -> int:
        """Count consecutive earnings beats (most recent first)."""
        try:
            rows = self._registry._db.execute(
                """SELECT surprise_pct FROM invest.earnings_revisions
                   WHERE ticker = %s AND surprise_pct IS NOT NULL
                   ORDER BY period DESC LIMIT 8""",
                (ticker,),
            )
            streak = 0
            for r in rows:
                if float(r["surprise_pct"]) > 0:
                    streak += 1
                else:
                    break
            return streak
        except Exception:
            return 0

    def _empty_momentum(self) -> dict:
        return {
            "revision_count_90d": 0,
            "upward_revisions": 0,
            "downward_revisions": 0,
            "momentum_score": 0.0,
            "momentum_label": "STABLE",
            "latest_eps_estimate": None,
            "beat_streak": 0,
        }
