from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import yfinance as yf

logger = logging.getLogger(__name__)

# Market benchmark tickers
BENCHMARKS = ["SPY", "QQQ", "IWM"]
VOLATILITY = ["^VIX"]
YIELDS = ["^TNX", "^IRX"]  # 10-year, 3-month
SECTORS = [
    "XLK", "XLV", "XLF", "XLI", "XLC", "XLY",
    "XLP", "XLE", "XLU", "XLB", "XLRE",
]


def _to_decimal(value: float | int | None) -> Decimal | None:
    """Safely convert to Decimal."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def fetch_market_snapshot(snapshot_date: date | None = None) -> dict:
    """Fetch daily market snapshot: benchmarks, VIX, yields, sector ETFs.

    Returns dict with keys matching MarketSnapshot fields.
    """
    all_tickers = BENCHMARKS + VOLATILITY + YIELDS + SECTORS
    prices = _fetch_latest_prices(all_tickers)

    sector_data: dict[str, Decimal] = {}
    for etf in SECTORS:
        if etf in prices:
            sector_data[etf] = prices[etf]

    ten_year = prices.get("^TNX")
    three_month = prices.get("^IRX")
    yield_spread: Decimal | None = None
    if ten_year is not None and three_month is not None:
        yield_spread = ten_year - three_month

    return {
        "snapshot_date": snapshot_date or date.today(),
        "spy_price": prices.get("SPY"),
        "qqq_price": prices.get("QQQ"),
        "iwm_price": prices.get("IWM"),
        "vix": prices.get("^VIX"),
        "ten_year_yield": ten_year,
        "three_month_yield": three_month,
        "yield_spread": yield_spread,
        "sector_data": sector_data if sector_data else None,
    }


def fetch_sector_performance(period: str = "1mo") -> dict[str, Decimal]:
    """Fetch sector ETF performance over a period.

    Returns dict mapping sector ETF ticker to percentage change.
    """
    result: dict[str, Decimal] = {}

    try:
        df = yf.download(SECTORS, period=period, progress=False)
        if df.empty:
            return result

        close = df["Close"]
        for etf in SECTORS:
            try:
                if len(SECTORS) == 1:
                    series = close
                else:
                    series = close[etf]

                if len(series) < 2:
                    continue

                first = float(series.iloc[0])
                last = float(series.iloc[-1])
                if first > 0:
                    pct = ((last - first) / first) * 100
                    result[etf] = _to_decimal(round(pct, 2))
            except (KeyError, IndexError):
                logger.debug("No data for sector ETF %s", etf)
                continue

    except Exception:
        logger.exception("Error fetching sector performance")

    return result


def _fetch_latest_prices(tickers: list[str]) -> dict[str, Decimal]:
    """Fetch latest closing prices for a list of tickers."""
    prices: dict[str, Decimal] = {}

    if not tickers:
        return prices

    try:
        df = yf.download(tickers, period="5d", progress=False)
        if df.empty:
            return prices

        close = df["Close"]
        if len(tickers) == 1:
            val = _to_decimal(float(close.iloc[-1]))
            if val is not None:
                prices[tickers[0]] = val
        else:
            last_row = close.iloc[-1]
            for t in tickers:
                if t in last_row.index:
                    val = _to_decimal(float(last_row[t]))
                    if val is not None:
                        prices[t] = val

    except Exception:
        logger.exception("Error fetching latest prices")

    return prices
