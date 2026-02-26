"""Portfolio performance metrics — benchmark comparison and risk-adjusted returns.

Computes:
  - Total return vs SPY (alpha)
  - Sharpe ratio (annualized)
  - Sortino ratio (annualized)
  - Max drawdown
  - Win rate, avg win/loss, expectancy from closed trades
  - Disposition effect ratio (avg winner hold vs avg loser hold)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date

from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

# Annualized risk-free rate assumption (3-month T-bill ~4.5% as of early 2026)
RISK_FREE_ANNUAL = 0.045


@dataclass
class PerformanceMetrics:
    portfolio_return_pct: float
    spy_return_pct: float
    alpha_pct: float  # portfolio - SPY
    sharpe_ratio: float | None  # None if insufficient data
    sortino_ratio: float | None
    max_drawdown_pct: float
    win_rate: float | None
    avg_win_pct: float | None
    avg_loss_pct: float | None
    total_trades: int
    expectancy: float | None  # avg expected return per trade
    disposition_ratio: float | None  # avg loser hold / avg winner hold (>1 = bad)
    avg_winner_hold_days: float | None
    avg_loser_hold_days: float | None
    measurement_days: int


class PerformanceCalculator:
    """Compute portfolio performance metrics from registry data."""

    def __init__(self, registry: Registry):
        self._registry = registry

    def compute(self) -> PerformanceMetrics:
        """Compute all performance metrics."""
        spy_data = self._get_spy_returns()
        portfolio_return = self._get_portfolio_return()
        spy_return = self._get_spy_period_return(spy_data)
        trade_stats = self._registry.get_win_loss_stats()
        disposition = self._compute_disposition()
        max_dd = self._compute_max_drawdown(spy_data)
        sharpe, sortino = self._compute_risk_ratios()
        measurement_days = self._get_measurement_days()

        total_trades = trade_stats.get("total_settled", 0)
        win_rate = trade_stats.get("win_rate") if total_trades > 0 else None
        avg_win = trade_stats.get("avg_win_pct") if total_trades > 0 else None
        avg_loss = trade_stats.get("avg_loss_pct") if total_trades > 0 else None

        expectancy = None
        if win_rate is not None and avg_win is not None and avg_loss is not None and total_trades >= 2:
            expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        return PerformanceMetrics(
            portfolio_return_pct=round(portfolio_return, 2),
            spy_return_pct=round(spy_return, 2),
            alpha_pct=round(portfolio_return - spy_return, 2),
            sharpe_ratio=round(sharpe, 3) if sharpe is not None else None,
            sortino_ratio=round(sortino, 3) if sortino is not None else None,
            max_drawdown_pct=round(max_dd, 2),
            win_rate=round(win_rate, 3) if win_rate is not None else None,
            avg_win_pct=round(avg_win, 2) if avg_win is not None else None,
            avg_loss_pct=round(avg_loss, 2) if avg_loss is not None else None,
            total_trades=total_trades,
            expectancy=round(expectancy, 2) if expectancy is not None else None,
            disposition_ratio=disposition[0],
            avg_winner_hold_days=disposition[1],
            avg_loser_hold_days=disposition[2],
            measurement_days=measurement_days,
        )

    def _get_spy_returns(self) -> list[dict]:
        """Get SPY prices from market snapshots."""
        try:
            rows = self._registry._db.execute(
                """SELECT snapshot_date, spy_price
                   FROM invest.market_snapshots
                   WHERE spy_price IS NOT NULL AND spy_price != 'NaN'
                   ORDER BY snapshot_date"""
            )
            return [r for r in rows if r.get("spy_price") and not math.isnan(float(r["spy_price"]))]
        except Exception:
            logger.debug("Failed to get SPY data")
            return []

    def _get_spy_period_return(self, spy_data: list[dict]) -> float:
        """SPY return over the measurement period."""
        if len(spy_data) < 2:
            return 0.0
        first = float(spy_data[0]["spy_price"])
        last = float(spy_data[-1]["spy_price"])
        if first <= 0:
            return 0.0
        return (last - first) / first * 100

    def _get_portfolio_return(self) -> float:
        """Total portfolio return including realized + unrealized P&L."""
        try:
            # Unrealized from open positions
            open_rows = self._registry._db.execute(
                """SELECT
                    SUM(current_price * shares) AS total_value,
                    SUM(entry_price * shares) AS total_cost
                   FROM invest.portfolio_positions
                   WHERE is_closed = FALSE"""
            )
            total_value = float(open_rows[0]["total_value"] or 0) if open_rows else 0
            total_cost = float(open_rows[0]["total_cost"] or 0) if open_rows else 0

            # Realized from closed positions
            closed_rows = self._registry._db.execute(
                """SELECT COALESCE(SUM(realized_pnl), 0) AS realized
                   FROM invest.portfolio_positions
                   WHERE is_closed = TRUE"""
            )
            realized = float(closed_rows[0]["realized"] or 0) if closed_rows else 0

            # Total cost basis (open + closed original cost)
            all_cost_rows = self._registry._db.execute(
                """SELECT SUM(entry_price * shares) AS all_cost
                   FROM invest.portfolio_positions"""
            )
            all_cost = float(all_cost_rows[0]["all_cost"] or 0) if all_cost_rows else 0

            if all_cost <= 0:
                return 0.0

            total_pnl = (total_value - total_cost) + realized
            return total_pnl / all_cost * 100
        except Exception:
            logger.debug("Failed to compute portfolio return")
            return 0.0

    def _compute_max_drawdown(self, spy_data: list[dict]) -> float:
        """Max drawdown of portfolio (approximated from daily snapshots).

        Since we don't have daily portfolio NAV, use the worst position drawdown
        as a proxy. This is conservative (actual portfolio DD is usually less).
        """
        try:
            rows = self._registry._db.execute(
                """SELECT ticker, entry_price, current_price,
                          (current_price - entry_price) / entry_price * 100 AS pnl_pct
                   FROM invest.portfolio_positions
                   WHERE entry_price > 0"""
            )
            if not rows:
                return 0.0

            # Worst individual position drawdown
            worst = min(float(r["pnl_pct"]) for r in rows)
            return abs(min(0, worst))
        except Exception:
            return 0.0

    def _compute_risk_ratios(self) -> tuple[float | None, float | None]:
        """Compute Sharpe and Sortino ratios from closed trade returns.

        Needs 5+ trades to be meaningful.
        """
        try:
            rows = self._registry._db.execute(
                """SELECT (exit_price - entry_price) / entry_price * 100 AS return_pct
                   FROM invest.portfolio_positions
                   WHERE is_closed = TRUE AND entry_price > 0 AND exit_price IS NOT NULL"""
            )
            if len(rows) < 3:
                return None, None

            returns = [float(r["return_pct"]) for r in rows]
            avg_return = sum(returns) / len(returns)

            # Annualize based on average hold period
            hold_rows = self._registry._db.execute(
                """SELECT AVG(exit_date - entry_date) AS avg_hold
                   FROM invest.portfolio_positions
                   WHERE is_closed = TRUE AND exit_date IS NOT NULL"""
            )
            avg_hold_days = float(hold_rows[0]["avg_hold"].days) if hold_rows and hold_rows[0]["avg_hold"] else 30

            trades_per_year = 365.25 / max(avg_hold_days, 1)

            # Std dev of returns
            variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
            std_dev = math.sqrt(variance) if variance > 0 else 0

            # Downside deviation (for Sortino)
            downside_returns = [min(0, r) for r in returns]
            downside_var = sum(r ** 2 for r in downside_returns) / len(returns)
            downside_dev = math.sqrt(downside_var) if downside_var > 0 else 0

            # Risk-free per trade
            rf_per_trade = RISK_FREE_ANNUAL / trades_per_year * 100

            sharpe = None
            if std_dev > 0:
                sharpe = (avg_return - rf_per_trade) / std_dev * math.sqrt(trades_per_year)

            sortino = None
            if downside_dev > 0:
                sortino = (avg_return - rf_per_trade) / downside_dev * math.sqrt(trades_per_year)

            return sharpe, sortino
        except Exception:
            logger.debug("Failed to compute risk ratios")
            return None, None

    def _compute_disposition(self) -> tuple[float | None, float | None, float | None]:
        """Compute disposition effect: avg hold time for winners vs losers.

        Returns (ratio, avg_winner_days, avg_loser_days).
        Ratio > 1.0 means losers held longer than winners (bad).
        """
        try:
            rows = self._registry._db.execute(
                """SELECT
                    exit_price > entry_price AS is_winner,
                    (exit_date - entry_date) AS hold_days
                   FROM invest.portfolio_positions
                   WHERE is_closed = TRUE
                     AND exit_date IS NOT NULL
                     AND entry_date IS NOT NULL"""
            )
            if not rows:
                return None, None, None

            winner_days = [r["hold_days"].days for r in rows if r["is_winner"] and r["hold_days"]]
            loser_days = [r["hold_days"].days for r in rows if not r["is_winner"] and r["hold_days"]]

            avg_winner = sum(winner_days) / len(winner_days) if winner_days else None
            avg_loser = sum(loser_days) / len(loser_days) if loser_days else None

            ratio = None
            if avg_winner and avg_loser and avg_winner > 0:
                ratio = round(avg_loser / avg_winner, 2)

            return (
                ratio,
                round(avg_winner, 1) if avg_winner is not None else None,
                round(avg_loser, 1) if avg_loser is not None else None,
            )
        except Exception:
            logger.debug("Failed to compute disposition effect")
            return None, None, None

    def _get_measurement_days(self) -> int:
        """Days since first position was opened."""
        try:
            rows = self._registry._db.execute(
                "SELECT MIN(entry_date) AS first FROM invest.portfolio_positions"
            )
            if rows and rows[0]["first"]:
                return (date.today() - rows[0]["first"]).days
            return 0
        except Exception:
            return 0
