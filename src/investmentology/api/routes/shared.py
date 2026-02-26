"""Shared utilities for API route handlers."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# --- Dividend data cache (4-hour TTL) ---
_div_cache: dict[str, tuple[float, dict]] = {}
_DIV_CACHE_TTL = 14400  # 4 hours


def _fetch_one_dividend(ticker: str) -> tuple[str, dict]:
    """Fetch dividend data for a single ticker from yfinance."""
    import yfinance as yf

    result: dict = {
        "annual_div": 0.0,
        "div_yield": 0.0,
        "frequency": "none",
        "last_div_amount": 0.0,
        "last_div_date": None,
        "payout_ratio": 0.0,
        "ex_div_date": None,
        "div_growth_5y": None,
    }
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        divs = tk.dividends

        if len(divs) >= 4:
            result["annual_div"] = float(divs.tail(4).sum())
            result["last_div_amount"] = float(divs.iloc[-1])
            result["last_div_date"] = divs.index[-1].strftime("%Y-%m-%d")

            if len(divs) >= 2:
                spacing = (divs.index[-1] - divs.index[-2]).days
                if spacing < 45:
                    result["frequency"] = "monthly"
                elif spacing < 100:
                    result["frequency"] = "quarterly"
                elif spacing < 200:
                    result["frequency"] = "semi-annual"
                else:
                    result["frequency"] = "annual"

            if len(divs) >= 20:
                old_annual = float(divs.head(4).sum())
                if old_annual > 0:
                    years = (divs.index[-1] - divs.index[0]).days / 365.25
                    if years > 1:
                        result["div_growth_5y"] = (
                            (result["annual_div"] / old_annual)
                            ** (1 / min(years, 5))
                            - 1
                        ) * 100
        elif info.get("dividendRate"):
            result["annual_div"] = float(info["dividendRate"])
            result["frequency"] = "unknown"

        result["payout_ratio"] = float(info.get("payoutRatio") or 0) * 100

        ex_ts = info.get("exDividendDate")
        if ex_ts and isinstance(ex_ts, (int, float)):
            from datetime import datetime

            result["ex_div_date"] = datetime.fromtimestamp(ex_ts).strftime(
                "%Y-%m-%d"
            )
    except Exception:
        logger.debug("Failed to fetch dividend data for %s", ticker)

    return ticker, result


def get_dividend_data(tickers: list[str]) -> dict[str, dict]:
    """Fetch dividend data for multiple tickers using cache + parallel fetching.

    Returns {ticker: {annual_div, div_yield, frequency, ...}} for each ticker.
    """
    now = time.time()
    results: dict[str, dict] = {}
    to_fetch: list[str] = []

    for t in tickers:
        if t in _div_cache:
            ts, data = _div_cache[t]
            if now - ts < _DIV_CACHE_TTL:
                results[t] = data
                continue
        to_fetch.append(t)

    if to_fetch:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_fetch_one_dividend, t): t for t in to_fetch}
            for future in as_completed(futures):
                try:
                    ticker, data = future.result(timeout=15)
                    _div_cache[ticker] = (now, data)
                    results[ticker] = data
                except Exception:
                    ticker = futures[future]
                    results[ticker] = {"annual_div": 0.0, "frequency": "none"}

    return results


_BULLISH_VERDICTS = {"STRONG_BUY", "BUY", "ACCUMULATE"}
_BEARISH_VERDICTS = {"REDUCE", "SELL", "AVOID", "DISCARD"}
# HOLD, WATCHLIST = neutral


def verdict_stability(ticker: str, registry) -> tuple[float, str]:
    """Compute verdict stability from last 3 verdicts.

    Returns (score, label):
        1.0 / "STABLE" — all 3 same direction
        0.67 / "MODERATE" — 2 of 3 same direction
        0.33 / "UNSTABLE" — alternating directions
        None if fewer than 2 verdicts available.
    """
    try:
        rows = registry._db.execute(
            """SELECT verdict FROM invest.verdicts
               WHERE ticker = %s ORDER BY created_at DESC LIMIT 3""",
            (ticker,),
        )
    except Exception:
        return (1.0, "UNKNOWN")

    if not rows or len(rows) < 2:
        return (1.0, "UNKNOWN")

    directions = []
    for r in rows:
        v = r.get("verdict", "")
        if v in _BULLISH_VERDICTS:
            directions.append("bullish")
        elif v in _BEARISH_VERDICTS:
            directions.append("bearish")
        else:
            directions.append("neutral")

    if len(set(directions)) == 1:
        return (1.0, "STABLE")
    # Count most common direction
    from collections import Counter
    counts = Counter(directions)
    most_common_count = counts.most_common(1)[0][1]
    if most_common_count >= 2:
        return (0.67, "MODERATE")
    return (0.33, "UNSTABLE")


def consensus_tier(consensus_score: float | None) -> str | None:
    """Classify consensus score into actionable tiers.

    - > 0.3: HIGH_CONVICTION — agents aligned, full size
    - -0.2 to 0.3: MIXED — agents disagree, starter only
    - < -0.2: CONTRARIAN — positive verdict but agents bearish, flag for review
    """
    if consensus_score is None:
        return None
    if consensus_score > 0.3:
        return "HIGH_CONVICTION"
    if consensus_score < -0.2:
        return "CONTRARIAN"
    return "MIXED"


def success_probability(row: dict) -> float | None:
    """Blended success probability (0.0-1.0) from agent analysis signals.

    Components (weights renormalized when data is missing):
        35% verdict confidence
        25% consensus score (normalized -1..+1 to 0..1)
        20% agent alignment (fraction of agents with positive sentiment)
        20% risk-adjusted (penalized by risk flag count)
    """
    components: list[tuple[float, float]] = []

    vc = row.get("confidence")
    if vc is not None:
        components.append((float(vc), 0.35))

    cons = row.get("consensus_score")
    if cons is not None:
        components.append(((float(cons) + 1) / 2, 0.25))

    stances = row.get("agent_stances")
    if stances and isinstance(stances, list) and len(stances) > 0:
        pos_count = sum(
            1 for s in stances
            if isinstance(s, dict) and s.get("sentiment", 0) > 0
        )
        alignment = pos_count / len(stances)
        components.append((alignment, 0.20))

    # Risk-adjusted component: start at 1.0, deduct per risk flag
    risk_flags = row.get("risk_flags")
    risk_score = 1.0
    if risk_flags and isinstance(risk_flags, list):
        risk_score = max(0.0, 1.0 - len(risk_flags) * 0.15)
    components.append((risk_score, 0.20))

    if not components:
        return None

    total_weight = sum(w for _, w in components)
    return round(sum(v * w for v, w in components) / total_weight, 4)
