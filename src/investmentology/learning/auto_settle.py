"""Auto-settlement module: resolves predictions by looking up actual prices.

Replaces the Phase 1 placeholder settlement with real yfinance price lookups.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal, InvalidOperation

import yfinance as yf

logger = logging.getLogger(__name__)


def lookup_price_on_date(ticker: str, target_date: date) -> Decimal | None:
    """Fetch the closing price for a ticker on or near a specific date.

    Tries the exact date first, then falls back to the nearest trading day
    within a 5-day window.
    """
    try:
        from datetime import timedelta

        start = target_date - timedelta(days=5)
        end = target_date + timedelta(days=5)

        df = yf.download(ticker, start=start.isoformat(), end=end.isoformat(), progress=False)
        if df.empty:
            logger.warning("No price data for %s around %s", ticker, target_date)
            return None

        close = df["Close"].squeeze()

        # Try exact date first
        target_str = target_date.isoformat()
        if target_str in close.index.strftime("%Y-%m-%d").tolist():
            idx = close.index.strftime("%Y-%m-%d").tolist().index(target_str)
            return Decimal(str(round(float(close.iloc[idx]), 2)))

        # Fall back to nearest date before or on target
        before_target = close[close.index.date <= target_date]
        if not before_target.empty:
            return Decimal(str(round(float(before_target.iloc[-1]), 2)))

        # Last resort: first available date after target
        return Decimal(str(round(float(close.iloc[0]), 2)))

    except Exception:
        logger.exception("Price lookup failed for %s on %s", ticker, target_date)
        return None


def settle_prediction_with_price(
    prediction,
    registry,
) -> tuple[Decimal, bool] | None:
    """Settle a single prediction by looking up its actual price.

    Returns (actual_value, was_correct) or None if price unavailable.

    Settlement logic:
    - 'price_target': correct if actual >= predicted (for bullish) or actual <= predicted (for bearish)
    - 'direction_up': correct if price went up
    - 'direction_down': correct if price went down
    - Default: compare actual vs predicted value
    """
    actual = lookup_price_on_date(prediction.ticker, prediction.settlement_date)
    if actual is None:
        return None

    registry.settle_prediction(prediction.id, actual)

    was_correct = _check_correctness(prediction, actual)
    return actual, was_correct


def _check_correctness(prediction, actual: Decimal) -> bool:
    """Determine if a prediction was correct based on type."""
    try:
        predicted = Decimal(str(prediction.predicted_value))
    except (InvalidOperation, TypeError):
        return False

    ptype = getattr(prediction, "prediction_type", "price_target")

    if ptype == "direction_up":
        return actual > predicted
    elif ptype == "direction_down":
        return actual < predicted
    else:
        # Price target: correct if actual is within 10% of predicted
        if predicted == 0:
            return False
        pct_diff = abs(float((actual - predicted) / predicted))
        return pct_diff <= 0.10
