from __future__ import annotations

import logging
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)


def _to_decimal(value: Any) -> Decimal | None:
    """Safely convert a value to Decimal."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


@dataclass
class CircuitBreaker:
    """Trips when failure rate exceeds threshold over a window."""

    threshold: float = 0.50  # 50% failure rate
    window_seconds: int = 300  # 5-minute window
    min_calls: int = 50
    _successes: deque[float] = field(default_factory=deque)
    _failures: deque[float] = field(default_factory=deque)

    def record_success(self) -> None:
        self._prune()
        self._successes.append(time.monotonic())

    def record_failure(self) -> None:
        self._prune()
        self._failures.append(time.monotonic())

    def _prune(self) -> None:
        """Remove entries outside the time window."""
        cutoff = time.monotonic() - self.window_seconds
        while self._successes and self._successes[0] < cutoff:
            self._successes.popleft()
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()

    @property
    def is_tripped(self) -> bool:
        self._prune()
        total = len(self._successes) + len(self._failures)
        if total < self.min_calls:
            return False
        return self.failure_rate >= self.threshold

    @property
    def failure_rate(self) -> float:
        self._prune()
        total = len(self._successes) + len(self._failures)
        if total == 0:
            return 0.0
        return len(self._failures) / total

    def reset(self) -> None:
        """Clear all recorded successes and failures."""
        self._successes.clear()
        self._failures.clear()


class YFinanceClient:
    """Client for fetching financial data from yfinance with caching and circuit breaking."""

    def __init__(self, cache_ttl_hours: int = 24) -> None:
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._circuit_breaker = CircuitBreaker()

    def get_fundamentals(self, ticker: str) -> dict | None:
        """Fetch fundamental data for a single ticker.

        Returns dict with standardized keys or None on failure.
        Validates data quality before caching — retries once if data
        appears corrupted (e.g. yfinance returning $0 revenue for
        established companies).
        """
        from investmentology.data.validation import validate_fundamentals

        cache_key = f"fundamentals:{ticker}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self._circuit_breaker.is_tripped:
            logger.warning(
                "Circuit breaker tripped (failure_rate=%.2f), skipping %s",
                self._circuit_breaker.failure_rate,
                ticker,
            )
            return None

        # Try up to 2 times — yfinance intermittently returns garbage
        for attempt in range(2):
            result = self._fetch_fundamentals_raw(ticker)
            if result is None:
                return None

            validation = validate_fundamentals(result)
            if validation.is_valid:
                if validation.warnings:
                    logger.warning(
                        "Data quality warnings for %s: %s",
                        ticker, validation.summary,
                    )
                self._circuit_breaker.record_success()
                self._set_cached(cache_key, result)
                return result

            # Data failed validation
            if attempt == 0:
                logger.warning(
                    "Data validation failed for %s (attempt 1), retrying: %s",
                    ticker, validation.summary,
                )
                # Don't cache — try fresh fetch
                continue

            # Second attempt also failed — return None with clear log
            logger.error(
                "Data validation failed for %s after retry: %s",
                ticker, validation.summary,
            )
            # Store the validation errors so the orchestrator can report them
            result["_validation_errors"] = validation.errors
            result["_validation_warnings"] = validation.warnings
            return result

        return None

    def _fetch_fundamentals_raw(self, ticker: str) -> dict | None:
        """Raw yfinance fetch without validation or caching."""
        try:
            info = yf.Ticker(ticker).info
            if not info or info.get("quoteType") is None:
                self._circuit_breaker.record_failure()
                logger.debug("No data returned for %s", ticker)
                return None

            # Estimate EBIT from operatingMargins * totalRevenue, fall back to ebitda
            revenue = info.get("totalRevenue")
            op_margins = info.get("operatingMargins")
            ebit_estimate = None
            if revenue and op_margins:
                ebit_estimate = _to_decimal(revenue * op_margins)
            if ebit_estimate is None:
                ebit_estimate = _to_decimal(info.get("ebitda"))

            # Estimate totalAssets from netIncomeToCommon / returnOnAssets
            roa = info.get("returnOnAssets")
            net_income_val = info.get("netIncomeToCommon")
            total_assets_est = None
            if roa and roa > 0 and net_income_val:
                total_assets_est = _to_decimal(net_income_val / roa)

            # Estimate current assets/liabilities from currentRatio and totalDebt
            current_ratio = info.get("currentRatio")
            total_debt = info.get("totalDebt") or 0
            current_liabilities_est = _to_decimal(total_debt * 0.3) if total_debt else None
            current_assets_est = None
            if current_ratio and current_liabilities_est:
                current_assets_est = _to_decimal(float(current_liabilities_est) * current_ratio)

            result: dict[str, Any] = {
                "ticker": ticker,
                "fetched_at": datetime.now(UTC).isoformat(),
                "operating_income": ebit_estimate,
                "market_cap": _to_decimal(info.get("marketCap")),
                "total_debt": _to_decimal(info.get("totalDebt")),
                "cash": _to_decimal(info.get("totalCash")),
                "current_assets": current_assets_est,
                "current_liabilities": current_liabilities_est,
                "net_tangible_assets": _to_decimal(
                    (info.get("bookValue") or 0) * (info.get("sharesOutstanding") or 0)
                ),
                "revenue": _to_decimal(revenue),
                "net_income": _to_decimal(net_income_val),
                "total_assets": total_assets_est,
                "total_liabilities": _to_decimal(info.get("totalDebt")),
                "shares_outstanding": _to_decimal(info.get("sharesOutstanding")),
                "price": _to_decimal(
                    info.get("currentPrice") or info.get("regularMarketPrice")
                ),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "name": info.get("shortName"),
                "enterprise_value": _to_decimal(info.get("enterpriseValue")),
            }
            return result

        except Exception:
            self._circuit_breaker.record_failure()
            logger.exception("Error fetching fundamentals for %s", ticker)
            return None

    def get_fundamentals_batch(
        self, tickers: list[str], chunk_size: int = 50, chunk_delay: float = 5.0
    ) -> list[dict]:
        """Fetch fundamentals for multiple tickers in throttled chunks.

        Processes tickers sequentially within each chunk (2 threads),
        then pauses between chunks to stay under Yahoo rate limits.
        """
        results: list[dict] = []
        total = len(tickers)

        for i in range(0, total, chunk_size):
            chunk = tickers[i : i + chunk_size]
            chunk_num = i // chunk_size + 1
            total_chunks = (total + chunk_size - 1) // chunk_size

            if self._circuit_breaker.is_tripped:
                logger.warning(
                    "Circuit breaker tripped at chunk %d/%d, pausing 60s...",
                    chunk_num, total_chunks,
                )
                time.sleep(60)
                # Reset breaker to retry
                self._circuit_breaker.reset()

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(self.get_fundamentals, t): t for t in chunk
                }
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result is not None:
                            results.append(result)
                    except Exception:
                        ticker = futures[future]
                        logger.warning("Thread failed for %s", ticker, exc_info=True)

            logger.info(
                "Chunk %d/%d done — %d/%d succeeded so far",
                chunk_num, total_chunks, len(results), i + len(chunk),
            )

            # Pause between chunks to avoid rate limiting
            if i + chunk_size < total:
                time.sleep(chunk_delay)

        return results

    def get_price(self, ticker: str) -> Decimal | None:
        """Get current price for a ticker."""
        cache_key = f"price:{ticker}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            info = yf.Ticker(ticker).info
            price = _to_decimal(
                info.get("currentPrice") or info.get("regularMarketPrice")
            )
            if price is not None:
                self._set_cached(cache_key, price)
            return price
        except Exception:
            logger.exception("Error fetching price for %s", ticker)
            return None

    def get_prices_batch(self, tickers: list[str]) -> dict[str, Decimal]:
        """Get current prices for multiple tickers. Uses yf.download for efficiency."""
        if not tickers:
            return {}

        try:
            df = yf.download(tickers, period="1d", progress=False)
            if df.empty:
                return {}

            prices: dict[str, Decimal] = {}
            # yf.download returns MultiIndex columns for multiple tickers
            if len(tickers) == 1:
                close = df["Close"].iloc[-1]
                val = _to_decimal(close)
                if val is not None:
                    prices[tickers[0]] = val
            else:
                close_row = df["Close"].iloc[-1]
                for t in tickers:
                    if t in close_row.index:
                        val = _to_decimal(close_row[t])
                        if val is not None:
                            prices[t] = val
            return prices
        except Exception:
            logger.exception("Error in batch price fetch")
            return {}

    @property
    def is_healthy(self) -> bool:
        return not self._circuit_breaker.is_tripped

    @property
    def failure_rate(self) -> float:
        return self._circuit_breaker.failure_rate

    def clear_cache(self) -> None:
        self._cache.clear()

    def _get_cached(self, key: str) -> Any | None:
        """Return cached value if still valid, else None."""
        if key in self._cache:
            value, cached_at = self._cache[key]
            if datetime.now(UTC) - cached_at < self._cache_ttl:
                return value
            del self._cache[key]
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        """Store a value in the cache."""
        self._cache[key] = (value, datetime.now(UTC))
