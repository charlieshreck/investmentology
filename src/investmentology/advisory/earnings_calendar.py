"""Earnings calendar utility with position sizing guidance.

Surfaces days-to-earnings for positions and watchlist stocks.
Provides sizing guidance based on proximity to earnings:
  - > 30 days: standard position sizing
  - 15-30 days: caution flag, reduce to starter position if entering
  - < 15 days: defer entry or reduce to starter position
  - < 7 days: defer entry entirely (uncompensated binary risk)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

logger = logging.getLogger(__name__)


class EarningsSizingGuidance(StrEnum):
    STANDARD = "standard"  # > 30 days — normal sizing
    CAUTION = "caution"  # 15-30 days — reduce or starter only
    DEFER = "defer"  # 7-15 days — defer new entry
    BLOCK = "block"  # < 7 days — do not enter new position


@dataclass
class EarningsProximity:
    ticker: str
    next_earnings_date: date | None
    days_to_earnings: int | None
    guidance: EarningsSizingGuidance
    eps_estimate: float | None = None
    revenue_estimate: float | None = None


def classify_earnings_proximity(
    ticker: str,
    earnings_data: dict | None,
    as_of: date | None = None,
) -> EarningsProximity:
    """Classify a stock's earnings proximity and return sizing guidance.

    Args:
        ticker: Stock ticker symbol.
        earnings_data: Dict from yfinance/finnhub with earnings info.
            Expected keys: 'upcoming_earnings_date' or 'date' (str YYYY-MM-DD),
            'eps_estimate', 'revenue_estimate'.
        as_of: Reference date (defaults to today).
    """
    if as_of is None:
        as_of = date.today()

    if not earnings_data:
        return EarningsProximity(
            ticker=ticker,
            next_earnings_date=None,
            days_to_earnings=None,
            guidance=EarningsSizingGuidance.STANDARD,
        )

    # Extract earnings date from various formats
    raw_date = (
        earnings_data.get("upcoming_earnings_date")
        or earnings_data.get("date")
        or earnings_data.get("earnings_date")
    )
    if not raw_date:
        return EarningsProximity(
            ticker=ticker,
            next_earnings_date=None,
            days_to_earnings=None,
            guidance=EarningsSizingGuidance.STANDARD,
        )

    try:
        if isinstance(raw_date, date):
            earnings_date = raw_date
        elif isinstance(raw_date, datetime):
            earnings_date = raw_date.date()
        else:
            earnings_date = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        logger.debug("Could not parse earnings date for %s: %s", ticker, raw_date)
        return EarningsProximity(
            ticker=ticker,
            next_earnings_date=None,
            days_to_earnings=None,
            guidance=EarningsSizingGuidance.STANDARD,
        )

    days = (earnings_date - as_of).days

    # Past earnings date — treat as standard (next date unknown)
    if days < 0:
        return EarningsProximity(
            ticker=ticker,
            next_earnings_date=earnings_date,
            days_to_earnings=days,
            guidance=EarningsSizingGuidance.STANDARD,
        )

    # Determine guidance based on proximity
    if days < 7:
        guidance = EarningsSizingGuidance.BLOCK
    elif days < 15:
        guidance = EarningsSizingGuidance.DEFER
    elif days <= 30:
        guidance = EarningsSizingGuidance.CAUTION
    else:
        guidance = EarningsSizingGuidance.STANDARD

    return EarningsProximity(
        ticker=ticker,
        next_earnings_date=earnings_date,
        days_to_earnings=days,
        guidance=guidance,
        eps_estimate=earnings_data.get("eps_estimate"),
        revenue_estimate=earnings_data.get("revenue_estimate"),
    )


def format_earnings_alert(proximity: EarningsProximity) -> str | None:
    """Format an earnings proximity alert for the briefing. Returns None if no alert needed."""
    if proximity.days_to_earnings is None or proximity.days_to_earnings < 0:
        return None

    if proximity.guidance == EarningsSizingGuidance.STANDARD:
        return None

    date_str = proximity.next_earnings_date.isoformat() if proximity.next_earnings_date else "unknown"

    if proximity.guidance == EarningsSizingGuidance.BLOCK:
        return (
            f"{proximity.ticker}: Earnings in {proximity.days_to_earnings}d ({date_str}) — "
            f"DEFER new entry. Uncompensated binary risk."
        )
    elif proximity.guidance == EarningsSizingGuidance.DEFER:
        return (
            f"{proximity.ticker}: Earnings in {proximity.days_to_earnings}d ({date_str}) — "
            f"Defer new entry or reduce to starter position only."
        )
    elif proximity.guidance == EarningsSizingGuidance.CAUTION:
        return (
            f"{proximity.ticker}: Earnings in {proximity.days_to_earnings}d ({date_str}) — "
            f"Caution: reduce to starter position if entering."
        )
    return None
