from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Exchange symbols for screening
EXCHANGES = ["NYSE", "NASDAQ", "AMEX"]

# Sector exclusions per Greenblatt
EXCLUDED_SECTORS = frozenset({"Financial Services", "Utilities"})

# Industry exclusions
EXCLUDED_INDUSTRIES = frozenset({
    "REIT",
    "Real Estate Investment Trusts",
    "Business Development Companies",
    "Shell Companies",
    "Blank Checks",
})

# Keywords in name that indicate exclusion
EXCLUDED_NAME_KEYWORDS = frozenset({
    "acquisition",
    "spac",
    "blank check",
    "merger",
})

_NASDAQ_SCREENER_URL = (
    "https://api.nasdaq.com/api/screener/stocks"
    "?tableType=earnings&limit=25000&country=united%20states"
)

_NASDAQ_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def load_full_universe(
    min_market_cap: int = 200_000_000,
    min_price: float = 5.0,
    min_avg_volume: int = 100_000,
) -> list[dict]:
    """Load the full US stock universe.

    Sources tickers from the NASDAQ screener API, then filters by
    market cap, price, volume. Excludes ADRs, SPACs, ETFs, REITs,
    BDCs, OTC, financials, and utilities.

    Returns list of dicts with keys:
        ticker, name, sector, industry, market_cap, exchange
    Expected: 5,000-7,000 tickers after filtering.
    """
    raw = _fetch_nasdaq_traded_list()
    if not raw:
        logger.error("Failed to fetch ticker universe — empty result")
        return []

    logger.info("Fetched %d raw tickers from NASDAQ screener", len(raw))

    filtered: list[dict] = []
    for row in raw:
        if _is_excluded(row, min_market_cap, min_price, min_avg_volume):
            continue
        filtered.append({
            "ticker": row.get("symbol", "").strip(),
            "name": row.get("name", ""),
            "sector": row.get("sector", ""),
            "industry": row.get("industry", ""),
            "market_cap": _parse_market_cap(row.get("marketCap")),
            "exchange": row.get("exchange", ""),
        })

    logger.info(
        "Universe filtered to %d tickers (from %d raw)",
        len(filtered),
        len(raw),
    )
    return filtered


def _fetch_nasdaq_traded_list() -> list[dict[str, Any]]:
    """Fetch ticker list from NASDAQ screener API."""
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(_NASDAQ_SCREENER_URL, headers=_NASDAQ_HEADERS)
            resp.raise_for_status()
            data = resp.json()

        rows = data.get("data", {}).get("rows", [])
        if not rows:
            # Try alternate path
            rows = data.get("data", {}).get("table", {}).get("rows", [])

        return rows if rows else []

    except httpx.HTTPError:
        logger.exception("HTTP error fetching NASDAQ screener")
        return []
    except Exception:
        logger.exception("Error fetching NASDAQ traded list")
        return []


def _parse_market_cap(value: Any) -> int:
    """Parse market cap from NASDAQ API format (e.g. '1,234,567' or 1234567)."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).replace(",", "").replace("$", "").strip()
    if not s:
        return 0
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def _is_excluded(
    row: dict,
    min_market_cap: int,
    min_price: float,
    min_avg_volume: int,
) -> bool:
    """Check if a ticker should be excluded based on type/sector/filters."""
    symbol = row.get("symbol", "")
    if not symbol:
        return True

    # Exclude tickers with special characters (warrants, units, etc.)
    if any(c in symbol for c in (".", "/", "^", " ")):
        return True

    # Exclude by sector
    sector = row.get("sector", "") or ""
    if sector in EXCLUDED_SECTORS:
        return True

    # Exclude by industry
    industry = row.get("industry", "") or ""
    for excl in EXCLUDED_INDUSTRIES:
        if excl.lower() in industry.lower():
            return True

    # Exclude by name keywords (SPACs, etc.)
    name = (row.get("name", "") or "").lower()
    for kw in EXCLUDED_NAME_KEYWORDS:
        if kw in name:
            return True

    # Market cap filter
    mcap = _parse_market_cap(row.get("marketCap"))
    if mcap < min_market_cap:
        return True

    # Price filter
    price_str = row.get("lastsale", "") or row.get("lastSale", "") or ""
    price_str = str(price_str).replace("$", "").replace(",", "").strip()
    try:
        price = float(price_str) if price_str else 0.0
    except (ValueError, TypeError):
        price = 0.0
    if price < min_price:
        return True

    # Volume filter (skip if not provided by the data source)
    volume_str = row.get("volume", "") or row.get("avgVolume", "") or ""
    volume_str = str(volume_str).replace(",", "").strip()
    try:
        volume = int(float(volume_str)) if volume_str else None
    except (ValueError, TypeError):
        volume = None
    if volume is not None and volume < min_avg_volume:
        return True

    return False
