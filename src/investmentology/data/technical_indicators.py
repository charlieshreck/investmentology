"""Technical indicator computation for the Simons agent.

Computes RSI, MACD, Bollinger Bands, SMA crossovers, volume profile,
and ATR from yfinance price history. Feeds into
AnalysisRequest.technical_indicators.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_HISTORY_PERIOD = "1y"


def compute_technical_indicators(ticker: str) -> dict | None:
    """Compute a full technical indicator dict for a ticker.

    Returns None if price data is unavailable.
    """
    try:
        df = yf.download(ticker, period=_HISTORY_PERIOD, progress=False)
        if df.empty or len(df) < 50:
            logger.debug("Insufficient price data for %s", ticker)
            return None

        close = df["Close"].squeeze()
        high = df["High"].squeeze()
        low = df["Low"].squeeze()
        volume = df["Volume"].squeeze()

        result: dict = {}

        # RSI (14-period)
        rsi = _rsi(close, 14)
        result["rsi_14"] = _dec(rsi.iloc[-1])
        result["rsi_trend"] = "oversold" if rsi.iloc[-1] < 30 else "overbought" if rsi.iloc[-1] > 70 else "neutral"

        # MACD (12, 26, 9)
        macd_line, signal_line, histogram = _macd(close)
        result["macd_line"] = _dec(macd_line.iloc[-1])
        result["macd_signal"] = _dec(signal_line.iloc[-1])
        result["macd_histogram"] = _dec(histogram.iloc[-1])
        result["macd_crossover"] = "bullish" if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2] else "bearish" if macd_line.iloc[-1] < signal_line.iloc[-1] and macd_line.iloc[-2] >= signal_line.iloc[-2] else "none"

        # Bollinger Bands (20, 2)
        bb_upper, bb_middle, bb_lower = _bollinger(close, 20, 2)
        last_close = float(close.iloc[-1])
        result["bb_upper"] = _dec(bb_upper.iloc[-1])
        result["bb_middle"] = _dec(bb_middle.iloc[-1])
        result["bb_lower"] = _dec(bb_lower.iloc[-1])
        bb_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_middle.iloc[-1] if bb_middle.iloc[-1] != 0 else 0
        result["bb_width"] = _dec(bb_width)
        result["bb_position"] = "above" if last_close > bb_upper.iloc[-1] else "below" if last_close < bb_lower.iloc[-1] else "inside"

        # SMA crossovers
        sma_50 = close.rolling(50).mean()
        sma_200 = close.rolling(200).mean()
        result["sma_50"] = _dec(sma_50.iloc[-1])
        result["sma_200"] = _dec(sma_200.iloc[-1]) if len(close) >= 200 else None
        result["price_vs_sma50"] = "above" if last_close > sma_50.iloc[-1] else "below"
        if len(close) >= 200 and pd.notna(sma_200.iloc[-1]):
            result["price_vs_sma200"] = "above" if last_close > sma_200.iloc[-1] else "below"
            result["golden_cross"] = bool(sma_50.iloc[-1] > sma_200.iloc[-1] and sma_50.iloc[-2] <= sma_200.iloc[-2])
            result["death_cross"] = bool(sma_50.iloc[-1] < sma_200.iloc[-1] and sma_50.iloc[-2] >= sma_200.iloc[-2])
        else:
            result["price_vs_sma200"] = None
            result["golden_cross"] = False
            result["death_cross"] = False

        # Volume profile
        avg_vol_20 = volume.rolling(20).mean().iloc[-1]
        result["volume_last"] = int(volume.iloc[-1])
        result["volume_avg_20"] = int(avg_vol_20) if pd.notna(avg_vol_20) else None
        result["volume_ratio"] = _dec(volume.iloc[-1] / avg_vol_20) if pd.notna(avg_vol_20) and avg_vol_20 > 0 else None

        # ATR (14-period)
        atr = _atr(high, low, close, 14)
        result["atr_14"] = _dec(atr.iloc[-1])
        result["atr_pct"] = _dec((atr.iloc[-1] / last_close) * 100) if last_close > 0 else None

        # Momentum (Rate of Change)
        roc_20 = ((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20]) * 100 if len(close) >= 20 else None
        result["momentum_20d"] = _dec(roc_20) if roc_20 is not None else None

        # 52-week high/low
        if len(close) >= 252:
            high_52w = float(close.iloc[-252:].max())
            low_52w = float(close.iloc[-252:].min())
        else:
            high_52w = float(close.max())
            low_52w = float(close.min())
        result["high_52w"] = _dec(high_52w)
        result["low_52w"] = _dec(low_52w)
        result["pct_from_52w_high"] = _dec(((last_close - high_52w) / high_52w) * 100) if high_52w > 0 else None

        return result

    except Exception:
        logger.exception("Failed to compute technical indicators for %s", ticker)
        return None


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bollinger(
    close: pd.Series, period: int = 20, std_dev: int = 2
) -> tuple[pd.Series, pd.Series, pd.Series]:
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _dec(value) -> str | None:
    """Convert numeric to string for JSON serialization."""
    if value is None or (isinstance(value, float) and (pd.isna(value) or not pd.notna(value))):
        return None
    try:
        return str(round(float(value), 4))
    except (TypeError, ValueError):
        return None
