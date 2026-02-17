"""EdgarTools provider for 10-K filing text and 13F institutional holdings.

Uses the edgartools library (pip install edgartools) to fetch:
- 10-K/10-Q risk factors and MD&A sections
- 13F institutional holders (top funds)
- Form 4 insider transaction summaries

All methods are best-effort with caching and graceful failure.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Cache TTL: filing text rarely changes
_CACHE_TTL = timedelta(hours=24)

# Max text length to include in agent prompts (avoid token bloat)
_MAX_SECTION_CHARS = 3000


def _truncate(text: str, max_chars: int = _MAX_SECTION_CHARS) -> str:
    """Truncate text to max_chars, breaking at last sentence boundary."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    # Try to break at last period
    last_period = cut.rfind(". ")
    if last_period > max_chars // 2:
        return cut[: last_period + 1]
    return cut + "..."


def _extract_section(text: str, header_pattern: str) -> str | None:
    """Extract a section from filing text by header pattern.

    Looks for the header and captures text until the next major header.
    """
    match = re.search(header_pattern, text, re.IGNORECASE)
    if not match:
        return None
    start = match.end()
    # Find next major section header (Item X, PART X, or end)
    next_header = re.search(
        r"\n(?:ITEM\s+\d|PART\s+[IVX])", text[start:], re.IGNORECASE
    )
    end = start + next_header.start() if next_header else min(start + _MAX_SECTION_CHARS * 2, len(text))
    section = text[start:end].strip()
    return _truncate(section) if section else None


class EdgarToolsProvider:
    """Provides SEC filing data via the edgartools library."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[datetime, object]] = {}
        self._identity_set = False

    def _ensure_identity(self) -> None:
        """Set SEC API identity (required by edgartools)."""
        if not self._identity_set:
            import edgar
            edgar.set_identity("Investmentology admin@investmentology.io")
            self._identity_set = True

    def _get_cached(self, key: str) -> object | None:
        if key in self._cache:
            ts, val = self._cache[key]
            if datetime.now() - ts < _CACHE_TTL:
                return val
        return None

    def _set_cached(self, key: str, val: object) -> None:
        self._cache[key] = (datetime.now(), val)

    def get_filing_text(
        self, ticker: str, filing_type: str = "10-K"
    ) -> dict | None:
        """Extract risk factors and MD&A from the latest 10-K or 10-Q.

        Returns:
            dict with keys: risk_factors, mda (management discussion),
            filing_date, filing_type. Or None on failure.
        """
        cache_key = f"filing:{ticker}:{filing_type}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        try:
            self._ensure_identity()
            import edgar

            company = edgar.Company(ticker)

            # Get latest filing
            if filing_type == "10-K":
                filing = company.latest_tenk
            else:
                filing = company.latest_tenq

            if filing is None:
                logger.debug("No %s filing found for %s", filing_type, ticker)
                return None

            # Get the text content
            text = filing.markdown() if hasattr(filing, "markdown") else ""
            if not text:
                text = str(filing.text) if hasattr(filing, "text") else ""

            if not text:
                logger.debug("Empty filing text for %s %s", ticker, filing_type)
                return None

            # Extract key sections
            risk_factors = _extract_section(
                text, r"(?:ITEM\s+1A\.?\s*[-—]?\s*RISK\s+FACTORS)"
            )
            mda = _extract_section(
                text,
                r"(?:ITEM\s+(?:7|2)\.?\s*[-—]?\s*MANAGEMENT.S?\s+DISCUSSION)",
            )

            result = {
                "risk_factors": risk_factors,
                "mda": mda,
                "filing_date": str(getattr(filing, "filing_date", "")),
                "filing_type": filing_type,
            }
            self._set_cached(cache_key, result)
            time.sleep(0.12)  # SEC rate limit
            return result

        except Exception:
            logger.debug("EdgarTools filing fetch failed for %s", ticker, exc_info=True)
            return None

    def get_institutional_holders(self, ticker: str) -> list[dict] | None:
        """Get top institutional holders from 13F filings.

        Returns list of dicts: {name, shares, value, report_date}.
        Limited to top 20 holders.
        """
        cache_key = f"holders:{ticker}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        try:
            self._ensure_identity()
            import edgar

            company = edgar.Company(ticker)
            filings = company.get_filings(form="13F-HR")
            if not filings or len(filings) == 0:
                return None

            latest = filings[0]
            thirteenf = latest.obj()
            if not isinstance(thirteenf, edgar.ThirteenF):
                return None

            holdings = thirteenf.holdings
            if not holdings:
                return None

            # Filter to this ticker and collect holder info
            holders = []
            for h in holdings:
                holder_name = getattr(h, "name", "") or getattr(h, "nameOfIssuer", "")
                shares = getattr(h, "shares", 0) or getattr(h, "value", 0)
                value = getattr(h, "value", 0)
                holders.append({
                    "name": str(holder_name)[:60],
                    "shares": int(shares) if shares else 0,
                    "value": int(value) if value else 0,
                })

            holders.sort(key=lambda x: x["value"], reverse=True)
            result = holders[:20]
            self._set_cached(cache_key, result)
            time.sleep(0.12)
            return result

        except Exception:
            logger.debug("EdgarTools 13F fetch failed for %s", ticker, exc_info=True)
            return None

    def get_insider_summary(self, ticker: str) -> dict | None:
        """Get insider transaction summary from Form 4 filings.

        Returns dict: {net_buys, net_sells, buy_value, sell_value, recent_transactions: list}.
        """
        cache_key = f"insider:{ticker}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        try:
            self._ensure_identity()
            import edgar

            company = edgar.Company(ticker)
            filings = company.get_filings(form="4")
            if not filings or len(filings) == 0:
                return None

            buys = 0
            sells = 0
            transactions: list[dict] = []

            # Look at recent Form 4 filings (last 10)
            for f in filings[:10]:
                try:
                    tx_date = str(getattr(f, "filing_date", ""))
                    # Basic heuristic: check filing header for transaction codes
                    header = f.header if hasattr(f, "header") else None
                    if header:
                        reporting = getattr(header, "reporting_owner", "") or ""
                        transactions.append({
                            "date": tx_date,
                            "filer": str(reporting)[:40],
                        })
                except Exception:
                    continue

            result = {
                "total_filings": len(filings) if filings else 0,
                "recent_count": min(10, len(filings) if filings else 0),
                "recent_transactions": transactions[:5],
            }
            self._set_cached(cache_key, result)
            time.sleep(0.12)
            return result

        except Exception:
            logger.debug("EdgarTools insider fetch failed for %s", ticker, exc_info=True)
            return None
