"""Historical simulation Value at Risk (VaR).

Uses position-weighted portfolio returns over trailing 252 days
to compute VaR and Expected Shortfall (CVaR).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from investmentology.models.position import PortfolioPosition

logger = logging.getLogger(__name__)


@dataclass
class VaRResult:
    """VaR computation output."""

    var_95: float  # 1-day 95% VaR as % of portfolio
    var_99: float  # 1-day 99% VaR as %
    cvar_95: float  # Expected Shortfall at 95% as %
    dollar_var_95: float  # Dollar amount at risk
    horizon_days: int
    observation_count: int


class VaREngine:
    """Historical simulation VaR using position-weighted daily returns."""

    def compute_var(
        self,
        positions: list[PortfolioPosition],
        portfolio_value: float,
        horizon_days: int = 1,
    ) -> VaRResult | None:
        """Compute portfolio VaR from historical daily returns.

        Returns None if insufficient data.
        """
        if not positions or portfolio_value <= 0:
            return None

        tickers = sorted(set(p.ticker for p in positions))
        if not tickers:
            return None

        try:
            import yfinance as yf

            df = yf.download(tickers, period="1y", auto_adjust=True, progress=False)
            if df.empty:
                return None

            if len(tickers) == 1:
                closes = df[["Close"]].rename(columns={"Close": tickers[0]})
            else:
                closes = df["Close"]

            # Drop rows with any NaN
            closes = closes.dropna()
            if len(closes) < 60:  # Need at least 60 days
                return None

            # Compute daily log returns
            returns = np.log(closes / closes.shift(1)).dropna()
            if len(returns) < 30:
                return None

            # Position weights
            weights = {}
            for p in positions:
                mv = float(p.market_value)
                weights[p.ticker] = weights.get(p.ticker, 0.0) + mv
            total_mv = sum(weights.values())
            if total_mv <= 0:
                return None

            # Weighted portfolio returns
            portfolio_returns = np.zeros(len(returns))
            for ticker in tickers:
                if ticker in returns.columns and ticker in weights:
                    w = weights[ticker] / total_mv
                    portfolio_returns += returns[ticker].values * w

            # Scale to horizon
            scale = np.sqrt(horizon_days)

            # VaR = negative percentile of returns
            var_95 = -float(np.percentile(portfolio_returns, 5)) * scale
            var_99 = -float(np.percentile(portfolio_returns, 1)) * scale

            # CVaR (Expected Shortfall) = mean of returns below VaR threshold
            threshold_95 = np.percentile(portfolio_returns, 5)
            tail_returns = portfolio_returns[portfolio_returns <= threshold_95]
            cvar_95 = -float(np.mean(tail_returns)) * scale if len(tail_returns) > 0 else var_95

            dollar_var = var_95 * portfolio_value / 100

            return VaRResult(
                var_95=round(var_95 * 100, 3),  # Convert to percentage
                var_99=round(var_99 * 100, 3),
                cvar_95=round(cvar_95 * 100, 3),
                dollar_var_95=round(dollar_var, 2),
                horizon_days=horizon_days,
                observation_count=len(portfolio_returns),
            )

        except Exception:
            logger.exception("VaR computation failed")
            return None
