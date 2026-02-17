"""Lightweight backtesting engine that replays historical decisions against price data."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    ticker: str
    entry_date: date
    entry_price: float
    exit_date: date | None = None
    exit_price: float | None = None
    shares: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0


@dataclass
class BacktestResult:
    start_date: date
    end_date: date
    initial_capital: float
    final_value: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_date: date | None
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_holding_days: float
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)
    monthly_returns: list[dict] = field(default_factory=list)


class BacktestRunner:
    """Replay historical decisions from the registry against real price data.

    Strategy: Buy on BUY decisions, sell after holding_days or on SELL decisions.
    Position size: equal weight (capital / max_positions).
    """

    def __init__(
        self,
        registry=None,
        max_positions: int = 25,
        default_hold_days: int = 90,
    ) -> None:
        self._registry = registry
        self._max_positions = max_positions
        self._default_hold_days = default_hold_days

    def run(
        self,
        start_date: date,
        end_date: date,
        initial_capital: float = 100_000.0,
    ) -> BacktestResult:
        """Run backtest for the given date range."""
        import yfinance as yf

        # Get historical decisions from registry
        decisions = self._get_decisions(start_date, end_date)

        if not decisions:
            return self._empty_result(start_date, end_date, initial_capital)

        # Get unique tickers and fetch price data
        tickers = list(set(d["ticker"] for d in decisions))
        price_data = self._fetch_prices(tickers, start_date, end_date)

        # Simulate
        cash = initial_capital
        positions: dict[str, dict] = {}  # ticker -> {entry_date, entry_price, shares}
        trades: list[Trade] = []
        equity_curve: list[dict] = []
        peak = initial_capital
        max_dd = 0.0
        max_dd_date = None

        # Generate trading days (skip weekends)
        current = start_date
        while current <= end_date:
            if current.weekday() >= 5:  # Saturday=5, Sunday=6
                current += timedelta(days=1)
                continue
            # Check for exits (holding period expired)
            to_close = []
            for ticker, pos in positions.items():
                hold_days = (current - pos["entry_date"]).days
                if hold_days >= self._default_hold_days:
                    to_close.append(ticker)

            for ticker in to_close:
                pos = positions.pop(ticker)
                exit_price = self._get_price(price_data, ticker, current)
                if exit_price:
                    pnl = (exit_price - pos["entry_price"]) * pos["shares"]
                    pnl_pct = (exit_price / pos["entry_price"] - 1) * 100
                    cash += exit_price * pos["shares"]
                    trades.append(Trade(
                        ticker=ticker,
                        entry_date=pos["entry_date"],
                        entry_price=pos["entry_price"],
                        exit_date=current,
                        exit_price=exit_price,
                        shares=pos["shares"],
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        holding_days=(current - pos["entry_date"]).days,
                    ))

            # Check for entries (BUY decisions on this date)
            for d in decisions:
                if d["date"] == current and d["type"] == "BUY":
                    ticker = d["ticker"]
                    if ticker in positions:
                        continue
                    if len(positions) >= self._max_positions:
                        continue

                    price = self._get_price(price_data, ticker, current)
                    if not price or price <= 0:
                        continue

                    position_size = cash / max(self._max_positions - len(positions), 1)
                    position_size = min(position_size, cash * 0.15)  # max 15% per position
                    shares = int(position_size / price)
                    if shares <= 0:
                        continue

                    cost = price * shares
                    if cost > cash:
                        continue

                    cash -= cost
                    positions[ticker] = {
                        "entry_date": current,
                        "entry_price": price,
                        "shares": shares,
                    }

            # Calculate portfolio value
            portfolio_value = cash
            for ticker, pos in positions.items():
                price = self._get_price(price_data, ticker, current)
                if price:
                    portfolio_value += price * pos["shares"]

            equity_curve.append({
                "date": current.isoformat(),
                "value": round(portfolio_value, 2),
            })

            # Track drawdown
            if portfolio_value > peak:
                peak = portfolio_value
            dd = (peak - portfolio_value) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_date = current

            current += timedelta(days=1)

        # Close remaining positions at end
        for ticker, pos in positions.items():
            exit_price = self._get_price(price_data, ticker, end_date)
            if exit_price:
                pnl = (exit_price - pos["entry_price"]) * pos["shares"]
                pnl_pct = (exit_price / pos["entry_price"] - 1) * 100
                trades.append(Trade(
                    ticker=ticker,
                    entry_date=pos["entry_date"],
                    entry_price=pos["entry_price"],
                    exit_date=end_date,
                    exit_price=exit_price,
                    shares=pos["shares"],
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    holding_days=(end_date - pos["entry_date"]).days,
                ))

        # Compute stats
        final_value = equity_curve[-1]["value"] if equity_curve else initial_capital
        total_return = (final_value / initial_capital - 1) * 100
        days = (end_date - start_date).days
        annualized = ((final_value / initial_capital) ** (365 / max(days, 1)) - 1) * 100 if days > 0 else 0

        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]
        win_rate = len(winning) / len(trades) * 100 if trades else 0
        avg_hold = sum(t.holding_days for t in trades) / len(trades) if trades else 0

        # Sharpe ratio (simplified: daily returns, 252 trading days)
        sharpe = self._calc_sharpe(equity_curve)

        # Monthly returns
        monthly = self._calc_monthly_returns(equity_curve)

        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            final_value=round(final_value, 2),
            total_return=round(total_return, 2),
            annualized_return=round(annualized, 2),
            sharpe_ratio=round(sharpe, 2),
            max_drawdown=round(max_dd * 100, 2),
            max_drawdown_date=max_dd_date,
            win_rate=round(win_rate, 1),
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            avg_holding_days=round(avg_hold, 1),
            trades=trades,
            equity_curve=equity_curve,
            monthly_returns=monthly,
        )

    def _get_decisions(self, start: date, end: date) -> list[dict]:
        """Fetch BUY/SELL decisions from the registry."""
        if not self._registry:
            return []
        try:
            rows = self._registry._db.execute(
                """SELECT ticker, decision_type, created_at::date AS dt
                   FROM invest.decisions
                   WHERE decision_type IN ('BUY', 'SELL')
                     AND created_at::date BETWEEN %s AND %s
                   ORDER BY created_at""",
                (start, end),
            )
            return [{"ticker": r["ticker"], "type": r["decision_type"], "date": r["dt"]} for r in rows]
        except Exception:
            logger.exception("Failed to fetch decisions for backtest")
            return []

    def _fetch_prices(self, tickers: list[str], start: date, end: date) -> dict:
        """Fetch historical close prices via yfinance."""
        import yfinance as yf

        # Add buffer for lookups
        fetch_start = start - timedelta(days=5)
        fetch_end = end + timedelta(days=5)

        result: dict[str, dict[date, float]] = {}
        try:
            data = yf.download(
                tickers,
                start=fetch_start.isoformat(),
                end=fetch_end.isoformat(),
                auto_adjust=True,
                progress=False,
            )
            if data.empty:
                return result

            closes = data["Close"] if len(tickers) > 1 else data[["Close"]].rename(columns={"Close": tickers[0]})

            for ticker in tickers:
                if ticker in closes.columns:
                    series = closes[ticker].dropna()
                    result[ticker] = {d.date(): float(v) for d, v in series.items()}
        except Exception:
            logger.exception("Failed to fetch price data")

        return result

    def _get_price(self, price_data: dict, ticker: str, dt: date) -> float | None:
        """Get price for ticker on or before the given date."""
        if ticker not in price_data:
            return None
        prices = price_data[ticker]
        if dt in prices:
            return prices[dt]
        # Look back up to 5 days
        for i in range(1, 6):
            prev = dt - timedelta(days=i)
            if prev in prices:
                return prices[prev]
        return None

    def _calc_sharpe(self, equity_curve: list[dict], risk_free_rate: float = 0.04) -> float:
        """Calculate annualized Sharpe ratio from equity curve."""
        if len(equity_curve) < 2:
            return 0.0

        values = [e["value"] for e in equity_curve]
        returns = [(values[i] / values[i - 1] - 1) for i in range(1, len(values)) if values[i - 1] > 0]

        if not returns:
            return 0.0

        avg = sum(returns) / len(returns)
        if len(returns) < 2:
            return 0.0

        var = sum((r - avg) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(var) if var > 0 else 0

        if std == 0:
            return 0.0

        daily_rf = risk_free_rate / 252
        sharpe = (avg - daily_rf) / std * math.sqrt(252)
        return sharpe

    def _calc_monthly_returns(self, equity_curve: list[dict]) -> list[dict]:
        """Calculate monthly returns from equity curve."""
        if not equity_curve:
            return []

        monthly: dict[str, dict] = {}
        prev_month_end = equity_curve[0]["value"]

        for entry in equity_curve:
            dt = date.fromisoformat(entry["date"])
            key = f"{dt.year}-{dt.month:02d}"
            monthly[key] = {"date": key, "value": entry["value"]}

        result = []
        prev_value = equity_curve[0]["value"]
        for key in sorted(monthly.keys()):
            value = monthly[key]["value"]
            ret = (value / prev_value - 1) * 100 if prev_value > 0 else 0
            result.append({"month": key, "return": round(ret, 2)})
            prev_value = value

        return result

    def _empty_result(self, start: date, end: date, capital: float) -> BacktestResult:
        return BacktestResult(
            start_date=start,
            end_date=end,
            initial_capital=capital,
            final_value=capital,
            total_return=0.0,
            annualized_return=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_date=None,
            win_rate=0.0,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            avg_holding_days=0.0,
        )
