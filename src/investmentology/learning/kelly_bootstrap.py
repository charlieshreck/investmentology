"""Kelly criterion bootstrap — compute win rate and avg win/loss from portfolio history.

Queries closed positions in invest.portfolio_positions to derive the parameters
needed for the KellyCalculator. Only activates after KELLY_MIN_DECISIONS (50)
closed trades.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from investmentology.timing.sizing import KELLY_MIN_DECISIONS, KellyCalculator

logger = logging.getLogger(__name__)


def compute_kelly_params(registry) -> KellyCalculator | None:
    """Compute Kelly parameters from closed position history.

    Returns a KellyCalculator if enough data exists (>= 50 closed trades),
    otherwise None.

    Win/loss is determined by realized P&L on closed positions:
    - Win: exit_price > entry_price
    - Loss: exit_price <= entry_price
    - Win %: (exit_price - entry_price) / entry_price * 100
    - Loss %: (entry_price - exit_price) / entry_price * 100
    """
    try:
        rows = registry._db.execute(
            "SELECT entry_price, exit_price, shares "
            "FROM invest.portfolio_positions "
            "WHERE is_closed = TRUE AND exit_price IS NOT NULL "
            "AND entry_price > 0 AND exit_price > 0 "
            "ORDER BY closed_at DESC LIMIT 500"
        )
    except Exception:
        logger.debug("Failed to query closed positions for Kelly bootstrap")
        return None

    if len(rows) < KELLY_MIN_DECISIONS:
        logger.info(
            "Only %d closed trades, need %d for Kelly criterion",
            len(rows), KELLY_MIN_DECISIONS,
        )
        return None

    wins: list[float] = []
    losses: list[float] = []

    for r in rows:
        entry = float(r["entry_price"])
        exit_p = float(r["exit_price"])
        if entry <= 0:
            continue

        pnl_pct = (exit_p - entry) / entry * 100

        if pnl_pct > 0:
            wins.append(pnl_pct)
        else:
            losses.append(abs(pnl_pct))

    total = len(wins) + len(losses)
    if total == 0:
        return None

    win_rate = len(wins) / total
    avg_win_pct = sum(wins) / len(wins) if wins else 0.0
    avg_loss_pct = sum(losses) / len(losses) if losses else 0.0

    if avg_win_pct <= 0 or avg_loss_pct <= 0:
        return None

    logger.info(
        "Kelly bootstrap: %d trades, win_rate=%.2f, avg_win=%.1f%%, avg_loss=%.1f%%",
        total, win_rate, avg_win_pct, avg_loss_pct,
    )

    return KellyCalculator(
        win_rate=win_rate,
        avg_win_pct=avg_win_pct,
        avg_loss_pct=avg_loss_pct,
    )
