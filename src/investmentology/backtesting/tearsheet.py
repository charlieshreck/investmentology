"""Generate formatted tearsheet data from backtest results."""

from __future__ import annotations

from investmentology.backtesting.runner import BacktestResult


def generate_tearsheet(result: BacktestResult) -> dict:
    """Format backtest result into a tearsheet for API/PWA consumption."""
    return {
        "summary": {
            "startDate": result.start_date.isoformat(),
            "endDate": result.end_date.isoformat(),
            "initialCapital": result.initial_capital,
            "finalValue": result.final_value,
            "totalReturn": result.total_return,
            "annualizedReturn": result.annualized_return,
            "sharpeRatio": result.sharpe_ratio,
            "maxDrawdown": result.max_drawdown,
            "maxDrawdownDate": result.max_drawdown_date.isoformat() if result.max_drawdown_date else None,
            "winRate": result.win_rate,
            "totalTrades": result.total_trades,
            "winningTrades": result.winning_trades,
            "losingTrades": result.losing_trades,
            "avgHoldingDays": result.avg_holding_days,
        },
        "equityCurve": result.equity_curve,
        "monthlyReturns": result.monthly_returns,
        "trades": [
            {
                "ticker": t.ticker,
                "entryDate": t.entry_date.isoformat(),
                "entryPrice": round(t.entry_price, 2),
                "exitDate": t.exit_date.isoformat() if t.exit_date else None,
                "exitPrice": round(t.exit_price, 2) if t.exit_price else None,
                "shares": t.shares,
                "pnl": round(t.pnl, 2),
                "pnlPct": round(t.pnl_pct, 2),
                "holdingDays": t.holding_days,
            }
            for t in result.trades
        ],
    }
