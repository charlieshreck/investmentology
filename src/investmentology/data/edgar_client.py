from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SEC_HEADERS = {"User-Agent": "Investmentology admin@investmentology.io"}
SEC_BASE = "https://data.sec.gov/api/xbrl/frames"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# XBRL concepts needed for the 18-key fundamentals dict.
# Each entry: (tag, unit, period_suffix) where period_suffix is appended to CY{year}.
# Duration items (income statement): "" -> CY2024
# Instant items (balance sheet): "Q4I" -> CY2024Q4I
FRAME_CONCEPTS: dict[str, list[tuple[str, str, str]]] = {
    "operating_income": [
        ("OperatingIncomeLoss", "USD", ""),
        ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", "USD", ""),
    ],
    "revenue": [
        ("RevenueFromContractWithCustomerExcludingAssessedTax", "USD", ""),
        ("Revenues", "USD", ""),
    ],
    "net_income": [
        ("NetIncomeLoss", "USD", ""),
    ],
    "total_assets": [
        ("Assets", "USD", "Q4I"),
    ],
    "current_assets": [
        ("AssetsCurrent", "USD", "Q4I"),
    ],
    "current_liabilities": [
        ("LiabilitiesCurrent", "USD", "Q4I"),
    ],
    "total_liabilities": [
        ("Liabilities", "USD", "Q4I"),
    ],
    "cash": [
        ("CashAndCashEquivalentsAtCarryingValue", "USD", "Q4I"),
    ],
    "total_debt": [
        ("LongTermDebt", "USD", "Q4I"),
        ("LongTermDebtNoncurrent", "USD", "Q4I"),
    ],
    "shares_outstanding": [
        ("CommonStockSharesOutstanding", "shares", "Q4I"),
    ],
    "net_ppe": [
        ("PropertyPlantAndEquipmentNet", "USD", "Q4I"),
    ],
    "stockholders_equity": [
        ("StockholdersEquity", "USD", "Q4I"),
    ],
}


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


class EdgarClient:
    """Fetches bulk financial data from SEC EDGAR frames API.

    Produces the same 18-key dict as YFinanceClient.get_fundamentals()
    so it's a drop-in replacement for the screener pipeline.
    """

    def __init__(self, fiscal_year: int | None = None) -> None:
        now = datetime.now(UTC)
        # Default to most recent complete fiscal year.
        # Most companies file 10-K within 60 days of fiscal year end,
        # so by March we usually have prior year data.
        self._fiscal_year = fiscal_year or (now.year - 1)
        self._http = httpx.Client(headers=SEC_HEADERS, timeout=30)
        self._cik_to_ticker: dict[int, str] = {}
        self._ticker_to_cik: dict[str, int] = {}
        self._ticker_to_name: dict[str, str] = {}
        # Multi-year data: year -> field -> {cik: value}
        self._data_by_year: dict[int, dict[str, dict[int, float]]] = {}

    @property
    def _bulk_data(self) -> dict[str, dict[int, float]]:
        """Primary year data (backward compat)."""
        return self._data_by_year.get(self._fiscal_year, {})

    def load_ticker_map(self) -> None:
        """Download CIK <-> ticker mapping from SEC."""
        resp = self._http.get(SEC_TICKERS_URL)
        resp.raise_for_status()
        data = resp.json()
        for entry in data.values():
            cik = int(entry["cik_str"])
            ticker = entry["ticker"]
            title = entry["title"]
            self._cik_to_ticker[cik] = ticker
            self._ticker_to_cik[ticker] = cik
            self._ticker_to_name[ticker] = title
        logger.info("Loaded %d CIK/ticker mappings", len(self._cik_to_ticker))

    def _fetch_frames_for_year(self, year: int) -> dict[str, dict[int, float]]:
        """Fetch all XBRL frame data for a given fiscal year.

        Makes ~15 HTTP requests total (one per concept) and returns
        a lookup of {field: {cik: value}}.
        """
        fetched = 0
        year_data: dict[str, dict[int, float]] = {}
        for field_name, alternatives in FRAME_CONCEPTS.items():
            merged: dict[int, float] = {}
            for tag, unit, suffix in alternatives:
                period = f"CY{year}{suffix}"
                url = f"{SEC_BASE}/us-gaap/{tag}/{unit}/{period}.json"
                try:
                    resp = self._http.get(url)
                    if resp.status_code == 404:
                        logger.debug("No data for %s/%s/%s", tag, unit, period)
                        continue
                    resp.raise_for_status()
                    frame = resp.json()
                    for entry in frame.get("data", []):
                        cik = int(entry["cik"])
                        if cik not in merged:
                            merged[cik] = entry["val"]
                    fetched += 1
                    logger.debug(
                        "Fetched %s: %d entries (%s/%s)",
                        field_name, len(frame.get("data", [])), tag, period,
                    )
                except Exception:
                    logger.exception("Error fetching frame %s/%s", tag, period)
                time.sleep(0.12)  # respect SEC 10 req/s limit

            year_data[field_name] = merged

        logger.info(
            "EDGAR bulk fetch complete: %d API calls, year=%d, fields=%d",
            fetched, year, len(year_data),
        )
        return year_data

    def fetch_bulk_frames(self) -> None:
        """Fetch XBRL frame data for the primary fiscal year."""
        self._data_by_year[self._fiscal_year] = self._fetch_frames_for_year(self._fiscal_year)

    def fetch_prior_year(self) -> None:
        """Fetch XBRL frame data for the year before the primary fiscal year.

        This enables Piotroski F-Score to use all 9 tests (YoY comparisons).
        """
        prior = self._fiscal_year - 1
        if prior in self._data_by_year:
            logger.info("Prior year %d already fetched", prior)
            return
        logger.info("Fetching prior year %d data for Piotroski YoY...", prior)
        self._data_by_year[prior] = self._fetch_frames_for_year(prior)

    def get_fundamentals(self, ticker: str, year: int | None = None) -> dict | None:
        """Get fundamentals for a single ticker from cached bulk data.

        Args:
            ticker: Stock ticker symbol.
            year: Fiscal year to look up. Defaults to primary fiscal year.

        Returns the same 18-key dict as YFinanceClient.get_fundamentals().
        """
        cik = self._ticker_to_cik.get(ticker)
        if cik is None:
            return None

        data = self._data_by_year.get(year or self._fiscal_year, {})

        def _get(field: str) -> Decimal | None:
            val = data.get(field, {}).get(cik)
            return _to_decimal(val)

        operating_income = _get("operating_income")
        total_assets = _get("total_assets")
        total_liabilities = _get("total_liabilities")
        equity = _get("stockholders_equity")

        # Compute net tangible assets: equity is a rough proxy
        # (actual NTA = total_assets - total_liabilities - intangibles,
        # but intangibles aren't reliably available via frames API)
        net_tangible_assets = equity

        return {
            "ticker": ticker,
            "fetched_at": datetime.now(UTC).isoformat(),
            "operating_income": operating_income,
            "market_cap": None,  # filled by price enrichment
            "total_debt": _get("total_debt"),
            "cash": _get("cash"),
            "current_assets": _get("current_assets"),
            "current_liabilities": _get("current_liabilities"),
            "net_tangible_assets": net_tangible_assets,
            "revenue": _get("revenue"),
            "net_income": _get("net_income"),
            "total_assets": total_assets,
            "total_liabilities": total_liabilities,
            "shares_outstanding": _get("shares_outstanding"),
            "price": None,  # filled by price enrichment
            "sector": None,  # filled from universe data
            "industry": None,  # filled from universe data
            "name": self._ticker_to_name.get(ticker),
            "enterprise_value": None,  # computed downstream from market_cap + debt - cash
            "net_ppe": _get("net_ppe"),
        }

    def get_fundamentals_batch(self, tickers: list[str]) -> list[dict]:
        """Get fundamentals for multiple tickers.

        Unlike YFinanceClient, this is nearly instant because
        all data was pre-fetched by fetch_bulk_frames().
        """
        results: list[dict] = []
        found = 0
        for ticker in tickers:
            result = self.get_fundamentals(ticker)
            if result is not None:
                results.append(result)
                found += 1

        logger.info(
            "EDGAR batch: %d/%d tickers matched (%.0f%%)",
            found, len(tickers), found / len(tickers) * 100 if tickers else 0,
        )
        return results

    def get_prior_fundamentals_batch(self, tickers: list[str]) -> list[dict]:
        """Get prior-year fundamentals for multiple tickers.

        Requires fetch_prior_year() to have been called first.
        """
        prior = self._fiscal_year - 1
        if prior not in self._data_by_year:
            logger.warning("Prior year %d not loaded — call fetch_prior_year() first", prior)
            return []
        results: list[dict] = []
        for ticker in tickers:
            result = self.get_fundamentals(ticker, year=prior)
            if result is not None:
                results.append(result)
        logger.info(
            "EDGAR prior-year batch: %d/%d tickers matched",
            len(results), len(tickers),
        )
        return results

    def enrich_with_prices(
        self, fundamentals: list[dict], prices: dict[str, Decimal]
    ) -> list[dict]:
        """Fill in market_cap and price from an external price source."""
        for f in fundamentals:
            ticker = f["ticker"]
            price = prices.get(ticker)
            if price is not None:
                f["price"] = price
                shares = f.get("shares_outstanding")
                if shares:
                    f["market_cap"] = price * shares
                # Compute enterprise value
                mc = f.get("market_cap")
                debt = f.get("total_debt") or Decimal(0)
                cash = f.get("cash") or Decimal(0)
                if mc:
                    f["enterprise_value"] = mc + debt - cash
        return fundamentals

    def enrich_with_sectors(
        self, fundamentals: list[dict], sectors: dict[str, str],
        industries: dict[str, str] | None = None,
    ) -> list[dict]:
        """Fill in sector/industry from universe data."""
        for f in fundamentals:
            ticker = f["ticker"]
            if sectors.get(ticker):
                f["sector"] = sectors[ticker]
            if industries and industries.get(ticker):
                f["industry"] = industries[ticker]
        return fundamentals

    @property
    def is_healthy(self) -> bool:
        return len(self._bulk_data) > 0

    @property
    def failure_rate(self) -> float:
        return 0.0

    def clear_cache(self) -> None:
        self._data_by_year.clear()

    @property
    def coverage(self) -> dict[str, int]:
        """Return count of companies per field in bulk data."""
        return {k: len(v) for k, v in self._bulk_data.items()}
