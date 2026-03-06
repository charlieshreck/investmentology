"""Data freshness detection — per-key staleness thresholds and auto-refresh logic.

Checks pipeline_data_cache timestamps against configurable thresholds to detect
stale or missing data before it flows to agents. Portfolio tickers get stricter
enforcement (any stale key triggers refresh) while watchlist tickers only refresh
on critical key staleness.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from investmentology.registry.db import Database

logger = logging.getLogger(__name__)

# Per-data-key staleness thresholds.
# Keys missing entirely are always treated as stale.
FRESHNESS_THRESHOLDS: dict[str, timedelta] = {
    "fundamentals": timedelta(hours=24),
    "technical_indicators": timedelta(hours=12),
    "macro_context": timedelta(hours=24),
    "news_context": timedelta(hours=6),
    "earnings_context": timedelta(hours=24),
    "insider_context": timedelta(hours=48),
    "filing_context": timedelta(hours=72),
    "institutional_context": timedelta(hours=72),
    "analyst_ratings": timedelta(hours=24),
    "short_interest": timedelta(hours=48),
    "social_sentiment": timedelta(hours=12),
    "research_briefing": timedelta(hours=24),
}

# Keys that directly impact agent quality — used to decide auto-refresh for
# watchlist tickers (portfolio tickers always refresh on any stale key).
CRITICAL_KEYS = frozenset({
    "fundamentals",
    "technical_indicators",
    "macro_context",
})


@dataclass
class FreshnessReport:
    """Result of checking data freshness for a single ticker."""

    ticker: str
    fresh_keys: dict[str, datetime] = field(default_factory=dict)
    stale_keys: dict[str, datetime | None] = field(default_factory=dict)
    missing_keys: list[str] = field(default_factory=list)

    @property
    def is_fresh(self) -> bool:
        return not self.stale_keys and not self.missing_keys

    @property
    def stale_key_names(self) -> list[str]:
        return list(self.stale_keys.keys()) + self.missing_keys

    @property
    def has_critical_staleness(self) -> bool:
        stale_set = set(self.stale_keys.keys()) | set(self.missing_keys)
        return bool(stale_set & CRITICAL_KEYS)


def check_freshness(
    db: Database,
    cycle_id: str,
    ticker: str,
) -> FreshnessReport:
    """Check all data keys for a ticker against staleness thresholds.

    Looks at pipeline_data_cache for the given cycle first, then falls back
    to the most recent entry across any cycle (cross-cycle).
    """
    now = datetime.now(timezone.utc)
    report = FreshnessReport(ticker=ticker)

    # Fetch timestamps for all cached keys (current cycle + cross-cycle latest)
    rows = db.execute(
        "SELECT DISTINCT ON (data_key) data_key, created_at "
        "FROM invest.pipeline_data_cache "
        "WHERE ticker = %s "
        "ORDER BY data_key, created_at DESC",
        (ticker,),
    )
    cached: dict[str, datetime] = {}
    for r in rows:
        ts = r["created_at"]
        if ts and not ts.tzinfo:
            ts = ts.replace(tzinfo=timezone.utc)
        cached[r["data_key"]] = ts

    for key, threshold in FRESHNESS_THRESHOLDS.items():
        ts = cached.get(key)
        if ts is None:
            report.missing_keys.append(key)
        elif (now - ts) > threshold:
            report.stale_keys[key] = ts
        else:
            report.fresh_keys[key] = ts

    return report


def get_stale_tickers(
    db: Database,
    cycle_id: str,
    tickers: list[str] | set[str],
) -> dict[str, list[str]]:
    """Batch check: returns {ticker: [stale_key_name, ...]} for tickers needing refresh."""
    result: dict[str, list[str]] = {}
    for ticker in tickers:
        report = check_freshness(db, cycle_id, ticker)
        stale = report.stale_key_names
        if stale:
            result[ticker] = stale
    return result


def should_auto_refresh(stale_keys: list[str], is_portfolio: bool) -> bool:
    """Decide whether stale keys warrant an automatic data refresh.

    Portfolio tickers: auto-refresh if ANY key is stale.
    Watchlist tickers: auto-refresh only if critical keys are stale.
    """
    if not stale_keys:
        return False
    if is_portfolio:
        return True
    return bool(set(stale_keys) & CRITICAL_KEYS)
