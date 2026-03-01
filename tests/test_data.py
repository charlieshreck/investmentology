from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from investmentology.data.snapshots import (
    BENCHMARKS,
    SECTORS,
    fetch_market_snapshot,
    fetch_sector_performance,
)
from investmentology.data.universe import (
    _is_excluded,
    _parse_market_cap,
    load_full_universe,
)
from investmentology.data.validation import (
    detect_anomalies,
    detect_staleness,
    validate_fundamentals,
)
from investmentology.data.yfinance_client import (
    CircuitBreaker,
    YFinanceClient,
    _to_decimal,
)


# ---------------------------------------------------------------------------
# CircuitBreaker tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_starts_healthy(self) -> None:
        cb = CircuitBreaker()
        assert not cb.is_tripped
        assert cb.failure_rate == 0.0

    def test_does_not_trip_below_min_calls(self) -> None:
        cb = CircuitBreaker(min_calls=10, threshold=0.30)
        for _ in range(5):
            cb.record_failure()
        # 5 failures but below min_calls (10)
        assert not cb.is_tripped

    def test_trips_at_threshold(self) -> None:
        cb = CircuitBreaker(min_calls=10, threshold=0.30)
        for _ in range(7):
            cb.record_success()
        for _ in range(3):
            cb.record_failure()
        # 10 total, 30% failures -> exactly at threshold
        assert cb.is_tripped

    def test_stays_healthy_below_threshold(self) -> None:
        cb = CircuitBreaker(min_calls=10, threshold=0.30)
        for _ in range(8):
            cb.record_success()
        for _ in range(2):
            cb.record_failure()
        # 10 total, 20% failures -> below threshold
        assert not cb.is_tripped

    def test_failure_rate_calculation(self) -> None:
        cb = CircuitBreaker()
        cb.record_success()
        cb.record_failure()
        assert cb.failure_rate == pytest.approx(0.5)

    def test_recovers_after_window(self) -> None:
        cb = CircuitBreaker(
            min_calls=2, threshold=0.30, window_seconds=1
        )
        for _ in range(5):
            cb.record_failure()
        assert cb.is_tripped

        # Wait for window to expire
        time.sleep(1.1)
        assert not cb.is_tripped
        assert cb.failure_rate == 0.0

    def test_prune_removes_old_entries(self) -> None:
        cb = CircuitBreaker(window_seconds=1)
        cb.record_success()
        cb.record_failure()
        time.sleep(1.1)
        cb._prune()
        assert len(cb._successes) == 0
        assert len(cb._failures) == 0


# ---------------------------------------------------------------------------
# YFinanceClient tests
# ---------------------------------------------------------------------------


class TestYFinanceClient:
    def _make_info(self, **overrides: object) -> dict:
        """Create a mock yfinance info dict."""
        base = {
            "quoteType": "EQUITY",
            "operatingIncome": 1000000,
            "marketCap": 50000000000,
            "totalDebt": 10000000000,
            "totalCash": 5000000000,
            "currentAssets": 20000000000,
            "currentLiabilities": 15000000000,
            "netTangibleAssets": 25000000000,
            "totalRevenue": 80000000000,
            "netIncome": 5000000000,
            "totalAssets": 100000000000,
            "sharesOutstanding": 1000000000,
            "currentPrice": 50.0,
            "sector": "Technology",
            "industry": "Software",
            "shortName": "Test Corp",
        }
        base.update(overrides)
        return base

    @patch("investmentology.data.yfinance_client.yf.Ticker")
    def test_get_fundamentals_success(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker = MagicMock()
        mock_ticker.info = self._make_info()
        mock_ticker_cls.return_value = mock_ticker

        client = YFinanceClient()
        result = client.get_fundamentals("AAPL")

        assert result is not None
        assert result["ticker"] == "AAPL"
        assert result["market_cap"] == Decimal("50000000000")
        assert result["sector"] == "Technology"
        assert result["name"] == "Test Corp"

    @patch("investmentology.data.yfinance_client.yf.Ticker")
    def test_get_fundamentals_returns_none_on_empty(
        self, mock_ticker_cls: MagicMock
    ) -> None:
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mock_ticker_cls.return_value = mock_ticker

        client = YFinanceClient()
        result = client.get_fundamentals("FAKE")
        assert result is None

    @patch("investmentology.data.yfinance_client.yf.Ticker")
    def test_get_fundamentals_returns_none_on_exception(
        self, mock_ticker_cls: MagicMock
    ) -> None:
        mock_ticker_cls.side_effect = Exception("network error")

        client = YFinanceClient()
        result = client.get_fundamentals("FAIL")
        assert result is None

    @patch("investmentology.data.yfinance_client.yf.Ticker")
    def test_cache_hit(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker = MagicMock()
        mock_ticker.info = self._make_info()
        mock_ticker_cls.return_value = mock_ticker

        client = YFinanceClient()
        result1 = client.get_fundamentals("AAPL")
        result2 = client.get_fundamentals("AAPL")

        assert result1 == result2
        # yf.Ticker should only be called once due to cache
        assert mock_ticker_cls.call_count == 1

    @patch("investmentology.data.yfinance_client.yf.Ticker")
    def test_cache_miss_after_clear(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker = MagicMock()
        mock_ticker.info = self._make_info()
        mock_ticker_cls.return_value = mock_ticker

        client = YFinanceClient()
        client.get_fundamentals("AAPL")
        client.clear_cache()
        client.get_fundamentals("AAPL")

        assert mock_ticker_cls.call_count == 2

    @patch("investmentology.data.yfinance_client.yf.Ticker")
    def test_circuit_breaker_blocks_after_threshold(
        self, mock_ticker_cls: MagicMock
    ) -> None:
        mock_ticker = MagicMock()
        mock_ticker.info = {}  # triggers failure
        mock_ticker_cls.return_value = mock_ticker

        client = YFinanceClient()
        client._circuit_breaker = CircuitBreaker(
            min_calls=3, threshold=0.30
        )

        # 3 failures, all above threshold
        for i in range(3):
            client.get_fundamentals(f"FAIL{i}")

        # Circuit breaker should now be tripped
        assert not client.is_healthy

        # Next call should be blocked without hitting yfinance
        call_count_before = mock_ticker_cls.call_count
        result = client.get_fundamentals("BLOCKED")
        assert result is None
        assert mock_ticker_cls.call_count == call_count_before

    @patch("investmentology.data.yfinance_client.yf.Ticker")
    def test_get_fundamentals_batch(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker = MagicMock()
        mock_ticker.info = self._make_info()
        mock_ticker_cls.return_value = mock_ticker

        client = YFinanceClient()
        results = client.get_fundamentals_batch(["AAPL", "MSFT", "GOOG"])
        assert len(results) == 3

    @patch("investmentology.data.yfinance_client.yf.Ticker")
    def test_get_price(self, mock_ticker_cls: MagicMock) -> None:
        mock_ticker = MagicMock()
        mock_ticker.info = {"currentPrice": 150.25}
        mock_ticker_cls.return_value = mock_ticker

        client = YFinanceClient()
        price = client.get_price("AAPL")
        assert price == Decimal("150.25")

    @patch("investmentology.data.yfinance_client.yf.download")
    def test_get_prices_batch(self, mock_download: MagicMock) -> None:
        # Simulate single row DataFrame
        mock_download.return_value = pd.DataFrame(
            {"Close": {"AAPL": [150.0], "MSFT": [300.0]}}
        ).T
        # For batch, yf.download returns MultiIndex columns
        idx = pd.MultiIndex.from_tuples(
            [("Close", "AAPL"), ("Close", "MSFT")]
        )
        mock_df = pd.DataFrame([[150.0, 300.0]], columns=idx)
        mock_download.return_value = mock_df

        client = YFinanceClient()
        prices = client.get_prices_batch(["AAPL", "MSFT"])
        assert prices["AAPL"] == Decimal("150.0")
        assert prices["MSFT"] == Decimal("300.0")

    def test_get_prices_batch_empty(self) -> None:
        client = YFinanceClient()
        assert client.get_prices_batch([]) == {}


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestValidation:
    def _make_data(self, **overrides: object) -> dict:
        base = {
            "ticker": "TEST",
            "fetched_at": datetime.now(UTC).isoformat(),
            "market_cap": Decimal("50000000000"),
            "operating_income": Decimal("10000000000"),
            "price": Decimal("150.0"),
            "shares_outstanding": Decimal("1000000000"),
            "revenue": Decimal("80000000000"),
            "total_debt": Decimal("20000000000"),
            "total_assets": Decimal("100000000000"),
        }
        base.update(overrides)
        return base

    def test_valid_data_passes(self) -> None:
        data = self._make_data()
        result = validate_fundamentals(data)
        assert result.is_valid
        assert result.errors == []

    def test_missing_required_field(self) -> None:
        data = self._make_data()
        del data["market_cap"]
        result = validate_fundamentals(data)
        assert not result.is_valid
        assert any("market_cap" in e for e in result.errors)

    def test_out_of_bounds_warns(self) -> None:
        data = self._make_data(market_cap=Decimal("100"))  # below $1M min
        result = validate_fundamentals(data)
        assert result.is_valid  # bounds are warnings, not errors
        assert any("market_cap" in w for w in result.warnings)

    def test_staleness_detection(self) -> None:
        old_date = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        data = self._make_data(fetched_at=old_date)
        result = validate_fundamentals(data)
        assert any("stale" in w.lower() for w in result.warnings)

    def test_staleness_not_detected_for_fresh_data(self) -> None:
        assert not detect_staleness(datetime.now(UTC))

    def test_staleness_detected_for_old_data(self) -> None:
        old = datetime.now(UTC) - timedelta(days=100)
        assert detect_staleness(old)

    def test_anomaly_operating_income_exceeds_revenue(self) -> None:
        data = self._make_data(
            operating_income=Decimal("100000000000"),
            revenue=Decimal("50000000000"),
        )
        anomalies = detect_anomalies(data)
        assert any("operating_income" in a for a in anomalies)

    def test_anomaly_negative_market_cap(self) -> None:
        data = self._make_data(market_cap=Decimal("-1000000"))
        anomalies = detect_anomalies(data)
        assert any("market_cap" in a.lower() for a in anomalies)

    def test_anomaly_negative_shares(self) -> None:
        data = self._make_data(shares_outstanding=Decimal("-100"))
        anomalies = detect_anomalies(data)
        assert any("shares_outstanding" in a for a in anomalies)

    def test_anomaly_extreme_debt_to_assets(self) -> None:
        data = self._make_data(
            total_debt=Decimal("2000000000000"),  # $2T
            total_assets=Decimal("100000000000"),  # $100B -> debt > 10x
        )
        anomalies = detect_anomalies(data)
        assert any("total_debt" in a for a in anomalies)

    def test_no_anomalies_on_clean_data(self) -> None:
        data = self._make_data()
        anomalies = detect_anomalies(data)
        assert anomalies == []


# ---------------------------------------------------------------------------
# Universe tests
# ---------------------------------------------------------------------------


class TestUniverse:
    def test_parse_market_cap_string(self) -> None:
        assert _parse_market_cap("1,234,567") == 1234567

    def test_parse_market_cap_with_dollar(self) -> None:
        assert _parse_market_cap("$1,234,567") == 1234567

    def test_parse_market_cap_int(self) -> None:
        assert _parse_market_cap(1234567) == 1234567

    def test_parse_market_cap_none(self) -> None:
        assert _parse_market_cap(None) == 0

    def test_parse_market_cap_empty_string(self) -> None:
        assert _parse_market_cap("") == 0

    def test_is_excluded_financial_sector(self) -> None:
        row = {
            "symbol": "JPM",
            "sector": "Financial Services",
            "marketCap": "400000000000",
            "lastsale": "$150.00",
            "volume": "5000000",
        }
        assert _is_excluded(row, 200_000_000, 5.0, 100_000)

    def test_is_excluded_utility_sector(self) -> None:
        row = {
            "symbol": "NEE",
            "sector": "Utilities",
            "marketCap": "100000000000",
            "lastsale": "$75.00",
            "volume": "3000000",
        }
        assert _is_excluded(row, 200_000_000, 5.0, 100_000)

    def test_is_excluded_low_market_cap(self) -> None:
        row = {
            "symbol": "TINY",
            "sector": "Technology",
            "marketCap": "50000000",  # $50M < $200M threshold
            "lastsale": "$10.00",
            "volume": "500000",
        }
        assert _is_excluded(row, 200_000_000, 5.0, 100_000)

    def test_is_excluded_low_price(self) -> None:
        row = {
            "symbol": "PENNY",
            "sector": "Technology",
            "marketCap": "500000000",
            "lastsale": "$2.00",  # below $5 threshold
            "volume": "500000",
        }
        assert _is_excluded(row, 200_000_000, 5.0, 100_000)

    def test_is_excluded_low_volume(self) -> None:
        row = {
            "symbol": "ILLIQ",
            "sector": "Technology",
            "marketCap": "500000000",
            "lastsale": "$50.00",
            "volume": "10000",  # below 100K threshold
        }
        assert _is_excluded(row, 200_000_000, 5.0, 100_000)

    def test_is_excluded_spac(self) -> None:
        row = {
            "symbol": "SPAC",
            "name": "Eagle Acquisition Corp",
            "sector": "Technology",
            "marketCap": "500000000",
            "lastsale": "$10.00",
            "volume": "500000",
        }
        assert _is_excluded(row, 200_000_000, 5.0, 100_000)

    def test_is_excluded_special_char_ticker(self) -> None:
        row = {
            "symbol": "BRK.A",
            "sector": "Technology",
            "marketCap": "500000000000",
            "lastsale": "$500000.00",
            "volume": "500000",
        }
        assert _is_excluded(row, 200_000_000, 5.0, 100_000)

    def test_not_excluded_valid_stock(self) -> None:
        row = {
            "symbol": "AAPL",
            "name": "Apple Inc",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "marketCap": "3000000000000",
            "lastsale": "$180.00",
            "volume": "50000000",
        }
        assert not _is_excluded(row, 200_000_000, 5.0, 100_000)

    @patch("investmentology.data.universe._fetch_nasdaq_traded_list")
    def test_load_full_universe(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            {
                "symbol": "AAPL",
                "name": "Apple Inc",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "marketCap": "3000000000000",
                "lastsale": "$180.00",
                "volume": "50000000",
                "exchange": "NASDAQ",
            },
            {
                "symbol": "JPM",
                "name": "JPMorgan Chase",
                "sector": "Financial Services",
                "industry": "Banks",
                "marketCap": "400000000000",
                "lastsale": "$150.00",
                "volume": "5000000",
                "exchange": "NYSE",
            },
            {
                "symbol": "TINY",
                "name": "Tiny Corp",
                "sector": "Technology",
                "industry": "Software",
                "marketCap": "50000000",
                "lastsale": "$3.00",
                "volume": "10000",
                "exchange": "NASDAQ",
            },
        ]

        result = load_full_universe()
        # Only AAPL should pass; JPM is Financial Services, TINY fails filters
        assert len(result) == 1
        assert result[0]["ticker"] == "AAPL"
        assert result[0]["market_cap"] == 3000000000000

    @patch("investmentology.data.universe._fetch_nasdaq_traded_list")
    def test_load_full_universe_empty(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = []
        result = load_full_universe()
        assert result == []


# ---------------------------------------------------------------------------
# Snapshots tests
# ---------------------------------------------------------------------------


class TestSnapshots:
    @patch("investmentology.data.snapshots.yf.download")
    def test_fetch_market_snapshot(self, mock_download: MagicMock) -> None:
        # Build mock DataFrame with MultiIndex columns
        all_tickers = BENCHMARKS + ["^VIX", "^TNX", "^IRX"] + SECTORS
        idx = pd.MultiIndex.from_tuples(
            [("Close", t) for t in all_tickers]
        )
        values = [
            450.0, 380.0, 200.0,  # SPY, QQQ, IWM
            15.0,  # VIX
            4.25, 5.10,  # TNX, IRX
        ] + [100.0 + i for i in range(len(SECTORS))]  # sector ETFs
        mock_df = pd.DataFrame([values], columns=idx)
        mock_download.return_value = mock_df

        result = fetch_market_snapshot()
        assert result["spy_price"] == Decimal("450.0")
        assert result["qqq_price"] == Decimal("380.0")
        assert result["iwm_price"] == Decimal("200.0")
        assert result["vix"] == Decimal("15.0")
        assert result["ten_year_yield"] == Decimal("4.25")
        assert result["sector_data"] is not None
        assert len(result["sector_data"]) == len(SECTORS)

    @patch("investmentology.data.snapshots.yf.download")
    def test_fetch_market_snapshot_empty(self, mock_download: MagicMock) -> None:
        mock_download.return_value = pd.DataFrame()
        result = fetch_market_snapshot()
        assert result["spy_price"] is None
        assert result["vix"] is None

    @patch("investmentology.data.snapshots.yf.download")
    def test_fetch_sector_performance(self, mock_download: MagicMock) -> None:
        # Build mock DataFrame with two rows (start and end)
        idx = pd.MultiIndex.from_tuples(
            [("Close", t) for t in SECTORS]
        )
        start_vals = [100.0] * len(SECTORS)
        end_vals = [110.0 + i for i in range(len(SECTORS))]
        mock_df = pd.DataFrame(
            [start_vals, end_vals], columns=idx
        )
        mock_download.return_value = mock_df

        result = fetch_sector_performance("1mo")
        assert len(result) == len(SECTORS)
        # First sector: (110 - 100) / 100 * 100 = 10%
        assert result["XLK"] == Decimal("10.0")

    @patch("investmentology.data.snapshots.yf.download")
    def test_fetch_sector_performance_empty(self, mock_download: MagicMock) -> None:
        mock_download.return_value = pd.DataFrame()
        result = fetch_sector_performance()
        assert result == {}


# ---------------------------------------------------------------------------
# _to_decimal helper tests
# ---------------------------------------------------------------------------


class TestToDecimal:
    def test_int(self) -> None:
        assert _to_decimal(42) == Decimal("42")

    def test_float(self) -> None:
        assert _to_decimal(3.14) == Decimal("3.14")

    def test_string_number(self) -> None:
        assert _to_decimal("99.99") == Decimal("99.99")

    def test_none(self) -> None:
        assert _to_decimal(None) is None

    def test_invalid(self) -> None:
        assert _to_decimal("not_a_number") is None
