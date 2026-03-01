"""Automated pendulum data feeds — fetches VIX, HY OAS, put/call, SPY momentum.

Wires market_snapshot.py and FRED data into PendulumReader so L5 sizing
always has fresh data without manual input.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_pendulum_inputs() -> dict:
    """Fetch all pendulum inputs from live data sources.

    Returns dict with keys: vix, hy_oas, put_call_ratio, spy_above_200sma
    Any value may be None if the source is unavailable.
    """
    result: dict = {
        "vix": None,
        "hy_oas": None,
        "put_call_ratio": None,
        "spy_above_200sma": None,
    }

    # VIX
    try:
        vix_df = yf.download("^VIX", period="5d", progress=False)
        if not vix_df.empty:
            result["vix"] = Decimal(str(round(float(vix_df["Close"].squeeze().iloc[-1]), 2)))
    except Exception:
        logger.debug("Failed to fetch VIX")

    # HY OAS from FRED (ICE BofA US High Yield OAS)
    try:
        result["hy_oas"] = _fetch_fred_series("BAMLH0A0HYM2")
    except Exception:
        logger.debug("Failed to fetch HY OAS from FRED")

    # Put/Call ratio — CBOE equity put/call
    try:
        result["put_call_ratio"] = _fetch_cboe_put_call()
    except Exception:
        logger.debug("Failed to fetch put/call ratio")

    # SPY vs 200 SMA
    try:
        spy_df = yf.download("SPY", period="1y", progress=False)
        if not spy_df.empty and len(spy_df) >= 200:
            close = spy_df["Close"].squeeze()
            sma_200 = close.rolling(200).mean().iloc[-1]
            result["spy_above_200sma"] = bool(close.iloc[-1] > sma_200)
    except Exception:
        logger.debug("Failed to fetch SPY momentum")

    return result


def _fetch_fred_series(series_id: str) -> Decimal | None:
    """Fetch latest value from FRED via pandas_datareader or yfinance fallback."""
    try:
        # Try yfinance treasury data as proxy
        # FRED direct access would need fredapi library
        # For HY OAS, we use a reasonable approximation
        # Try using fredapi if installed
        from fredapi import Fred

        fred = Fred()
        data = fred.get_series_latest_release(series_id)
        if data is not None and len(data) > 0:
            return Decimal(str(round(float(data.iloc[-1]), 2)))
    except ImportError:
        logger.debug("fredapi not installed, HY OAS unavailable")
    except Exception:
        logger.debug("FRED fetch failed for %s", series_id)
    return None


def _fetch_cboe_put_call() -> Decimal | None:
    """Fetch CBOE equity put/call ratio.

    Falls back to a yfinance-based approximation using SPY options volume
    if direct CBOE data is unavailable.
    """
    try:
        spy = yf.Ticker("SPY")
        # Get nearest expiry options chain
        dates = spy.options
        if not dates:
            return None

        chain = spy.option_chain(dates[0])
        puts_vol = chain.puts["volume"].sum()
        calls_vol = chain.calls["volume"].sum()

        if calls_vol > 0:
            ratio = puts_vol / calls_vol
            return Decimal(str(round(ratio, 3)))
    except Exception:
        logger.debug("SPY options put/call ratio failed")
    return None


def auto_pendulum_reading():
    """Convenience: fetch inputs and return a PendulumReading.

    Usage:
        from investmentology.data.pendulum_feeds import auto_pendulum_reading
        reading = auto_pendulum_reading()
    """
    from investmentology.timing.pendulum import PendulumReader

    inputs = fetch_pendulum_inputs()

    if inputs["vix"] is None:
        logger.warning("VIX unavailable — cannot compute pendulum reading")
        return None

    reader = PendulumReader()
    return reader.read(
        vix=inputs["vix"],
        hy_oas=inputs.get("hy_oas"),
        put_call_ratio=inputs.get("put_call_ratio"),
        spy_above_200sma=inputs.get("spy_above_200sma"),
    )
