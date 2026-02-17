"""FRED (Federal Reserve Economic Data) provider for macro context.

Fetches yield curves, VIX, credit spreads, inflation, and other
macro indicators that feed into Soros agent and L5 cycle detection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Key FRED series we care about
FRED_SERIES = {
    "DGS2": "treasury_2y",
    "DGS10": "treasury_10y",
    "DGS30": "treasury_30y",
    "FEDFUNDS": "fed_funds_rate",
    "CPIAUCSL": "cpi",
    "UNRATE": "unemployment_rate",
    "BAMLH0A0HYM2": "high_yield_spread",
    "DTWEXBGS": "usd_index",
    "T10Y2Y": "yield_curve_spread",
}


class FredProvider:
    """Fetches macro indicators from FRED."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._fred = None
        self._cache: dict[str, tuple[datetime, dict]] = {}
        self._cache_ttl = timedelta(hours=4)

    def _get_client(self):
        if self._fred is None:
            from fredapi import Fred
            self._fred = Fred(api_key=self._api_key)
        return self._fred

    def get_macro_context(self) -> dict:
        """Fetch current macro indicators. Returns a dict suitable for Soros agent."""
        cache_key = "macro"
        now = datetime.now()
        if cache_key in self._cache:
            cached_at, data = self._cache[cache_key]
            if now - cached_at < self._cache_ttl:
                return data

        context: dict = {}
        fred = self._get_client()

        for series_id, label in FRED_SERIES.items():
            try:
                data = fred.get_series(series_id, observation_start=(now - timedelta(days=90)).strftime("%Y-%m-%d"))
                if data is not None and len(data) > 0:
                    latest = data.dropna().iloc[-1]
                    context[label] = round(float(latest), 4)
            except Exception:
                logger.debug("Failed to fetch FRED series %s", series_id)

        # Derived indicators
        if "treasury_2y" in context and "treasury_10y" in context:
            spread = context["treasury_10y"] - context["treasury_2y"]
            context["yield_curve_spread_derived"] = round(spread, 4)
            context["yield_curve_inverted"] = spread < 0

        if "high_yield_spread" in context:
            hys = context["high_yield_spread"]
            if hys > 5.0:
                context["credit_stress"] = "high"
            elif hys > 3.5:
                context["credit_stress"] = "elevated"
            else:
                context["credit_stress"] = "normal"

        self._cache[cache_key] = (now, context)
        logger.info("FRED macro context: %d indicators loaded", len(context))
        return context
