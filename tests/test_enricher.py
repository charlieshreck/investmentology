"""Tests for DataEnricher, FredProvider, and FinnhubProvider."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from investmentology.agents.base import AnalysisRequest
from investmentology.data.enricher import DataEnricher, build_enricher
from investmentology.data.finnhub_provider import FinnhubProvider
from investmentology.data.fred_provider import FredProvider, FRED_SERIES
from investmentology.models.stock import FundamentalsSnapshot


def _make_fundamentals() -> FundamentalsSnapshot:
    from datetime import datetime
    return FundamentalsSnapshot(
        ticker="AAPL",
        fetched_at=datetime.now(),
        price=Decimal("180"),
        market_cap=Decimal("2800000000000"),
        revenue=Decimal("380000000000"),
        net_income=Decimal("95000000000"),
        operating_income=Decimal("110000000000"),
        total_debt=Decimal("110000000000"),
        cash=Decimal("60000000000"),
        total_assets=Decimal("350000000000"),
        total_liabilities=Decimal("280000000000"),
        current_assets=Decimal("140000000000"),
        current_liabilities=Decimal("150000000000"),
        net_ppe=Decimal("40000000000"),
        shares_outstanding=15000000000,
    )


def _make_request() -> AnalysisRequest:
    return AnalysisRequest(
        ticker="AAPL",
        fundamentals=_make_fundamentals(),
        sector="Technology",
        industry="Consumer Electronics",
    )


# --- FredProvider ---

class TestFredProvider:
    def test_cache_hit(self):
        provider = FredProvider("test-key")
        # Pre-fill cache
        provider._cache["macro"] = (datetime.now(), {"fed_funds_rate": 5.25})
        result = provider.get_macro_context()
        assert result["fed_funds_rate"] == 5.25

    def test_cache_expired(self):
        provider = FredProvider("test-key")
        # Expired cache
        provider._cache["macro"] = (
            datetime.now() - timedelta(hours=5),
            {"fed_funds_rate": 5.0},
        )
        # Mock the FRED client
        mock_fred = MagicMock()
        provider._fred = mock_fred

        import pandas as pd
        mock_series = pd.Series([5.25], index=[datetime.now()])
        mock_fred.get_series.return_value = mock_series

        result = provider.get_macro_context()
        assert len(result) > 0

    def test_series_failure_skipped(self):
        provider = FredProvider("test-key")
        mock_fred = MagicMock()
        provider._fred = mock_fred
        mock_fred.get_series.side_effect = Exception("API error")

        result = provider.get_macro_context()
        assert result == {}

    def test_derived_yield_curve(self):
        provider = FredProvider("test-key")
        mock_fred = MagicMock()
        provider._fred = mock_fred

        import pandas as pd
        def mock_series(series_id, **kwargs):
            vals = {"DGS2": 4.5, "DGS10": 4.0}
            if series_id in vals:
                return pd.Series([vals[series_id]], index=[datetime.now()])
            return pd.Series(dtype=float)

        mock_fred.get_series.side_effect = mock_series

        result = provider.get_macro_context()
        assert result.get("yield_curve_inverted") is True
        assert result["yield_curve_spread_derived"] < 0


# --- FinnhubProvider ---

class TestFinnhubProvider:
    def test_get_news_cached(self):
        provider = FinnhubProvider("test-key")
        provider._cache["news:AAPL"] = (
            datetime.now(),
            [{"headline": "Apple launches new product"}],
        )
        result = provider.get_news("AAPL")
        assert len(result) == 1

    def test_get_news_api_call(self):
        provider = FinnhubProvider("test-key")
        mock_client = MagicMock()
        provider._client = mock_client
        mock_client.company_news.return_value = [
            {
                "headline": "Test headline",
                "summary": "Test summary",
                "source": "reuters",
                "datetime": int(datetime.now().timestamp()),
                "url": "https://example.com",
            }
        ]
        result = provider.get_news("AAPL")
        assert len(result) == 1
        assert result[0]["headline"] == "Test headline"

    def test_get_news_failure(self):
        provider = FinnhubProvider("test-key")
        mock_client = MagicMock()
        provider._client = mock_client
        mock_client.company_news.side_effect = Exception("API error")
        result = provider.get_news("AAPL")
        assert result == []

    def test_get_earnings(self):
        provider = FinnhubProvider("test-key")
        mock_client = MagicMock()
        provider._client = mock_client
        mock_client.earnings_calendar.return_value = {
            "earningsCalendar": [
                {"symbol": "AAPL", "date": "2025-07-24", "epsEstimate": 1.42}
            ]
        }
        mock_client.company_earnings.return_value = [
            {"period": "2025-Q1", "actual": 1.50, "estimate": 1.40, "surprisePercent": 7.1}
        ]
        result = provider.get_earnings("AAPL")
        assert result is not None
        assert result["upcoming"]["date"] == "2025-07-24"
        assert result["beat_count"] == 1

    def test_get_insider_transactions(self):
        provider = FinnhubProvider("test-key")
        mock_client = MagicMock()
        provider._client = mock_client
        mock_client.stock_insider_transactions.return_value = {
            "data": [
                {"name": "Tim Cook", "share": 100000, "change": -5000,
                 "filingDate": "2025-03-01", "transactionDate": "2025-02-28"}
            ]
        }
        result = provider.get_insider_transactions("AAPL")
        assert len(result) == 1
        assert result[0]["transaction_type"] == "sell"

    def test_get_social_sentiment(self):
        provider = FinnhubProvider("test-key")
        mock_client = MagicMock()
        provider._client = mock_client
        mock_client.stock_social_sentiment.return_value = {
            "reddit": [
                {"mention": 100, "positiveMention": 70, "negativeMention": 30, "score": 0.7}
            ],
            "twitter": [],
        }
        result = provider.get_social_sentiment("AAPL")
        assert result is not None
        assert "reddit" in result
        # 70 > 30*1.5=45, so bullish
        assert result["aggregate"]["bias"] == "bullish"

    def test_get_social_sentiment_empty(self):
        provider = FinnhubProvider("test-key")
        mock_client = MagicMock()
        provider._client = mock_client
        mock_client.stock_social_sentiment.return_value = {}
        result = provider.get_social_sentiment("AAPL")
        assert result is None


# --- DataEnricher ---

class TestDataEnricher:
    def test_enrich_no_providers(self):
        enricher = DataEnricher()
        request = _make_request()
        result = enricher.enrich(request)
        assert result.macro_context is None
        assert result.news_context is None

    def test_enrich_with_fred(self):
        mock_fred = MagicMock(spec=FredProvider)
        mock_fred.get_macro_context.return_value = {"fed_funds_rate": 5.25}

        enricher = DataEnricher(fred=mock_fred)
        request = _make_request()
        enricher.enrich(request)

        assert request.macro_context == {"fed_funds_rate": 5.25}

    def test_enrich_merges_existing_macro(self):
        mock_fred = MagicMock(spec=FredProvider)
        mock_fred.get_macro_context.return_value = {"fed_funds_rate": 5.25}

        enricher = DataEnricher(fred=mock_fred)
        request = _make_request()
        request.macro_context = {"custom_indicator": 42}
        enricher.enrich(request)

        assert request.macro_context["fed_funds_rate"] == 5.25
        assert request.macro_context["custom_indicator"] == 42

    def test_enrich_with_finnhub(self):
        mock_finnhub = MagicMock(spec=FinnhubProvider)
        mock_finnhub.get_news.return_value = [{"headline": "Test"}]
        mock_finnhub.get_earnings.return_value = {"upcoming": None, "recent_surprises": []}
        mock_finnhub.get_insider_transactions.return_value = []
        mock_finnhub.get_social_sentiment.return_value = {"aggregate": {"bias": "neutral"}}

        enricher = DataEnricher(finnhub=mock_finnhub)
        request = _make_request()
        enricher.enrich(request)

        assert request.news_context == [{"headline": "Test"}]
        assert request.earnings_context is not None
        assert request.insider_context == []
        assert request.social_sentiment is not None

    def test_enrich_skips_if_already_set(self):
        mock_finnhub = MagicMock(spec=FinnhubProvider)
        enricher = DataEnricher(finnhub=mock_finnhub)

        request = _make_request()
        request.news_context = [{"headline": "Existing"}]
        enricher.enrich(request)

        # Should not overwrite existing
        assert request.news_context == [{"headline": "Existing"}]
        mock_finnhub.get_news.assert_not_called()

    def test_enrich_fred_caches_across_calls(self):
        mock_fred = MagicMock(spec=FredProvider)
        mock_fred.get_macro_context.return_value = {"fed_funds_rate": 5.25}

        enricher = DataEnricher(fred=mock_fred)

        r1 = _make_request()
        r2 = _make_request()
        r2.ticker = "MSFT"

        enricher.enrich(r1)
        enricher.enrich(r2)

        # FRED should only be called once (cached in enricher)
        mock_fred.get_macro_context.assert_called_once()
        assert r1.macro_context == r2.macro_context

    def test_enrich_failure_doesnt_crash(self):
        mock_finnhub = MagicMock(spec=FinnhubProvider)
        mock_finnhub.get_news.side_effect = Exception("Boom")
        mock_finnhub.get_earnings.side_effect = Exception("Boom")
        mock_finnhub.get_insider_transactions.side_effect = Exception("Boom")
        mock_finnhub.get_social_sentiment.side_effect = Exception("Boom")

        enricher = DataEnricher(finnhub=mock_finnhub)
        request = _make_request()
        result = enricher.enrich(request)

        # Should not crash, fields stay None
        assert result.news_context is None
        assert result.earnings_context is None


# --- build_enricher ---

class TestBuildEnricher:
    def test_returns_enricher_without_keys(self):
        """EdgarTools needs no API key, so enricher is always created."""
        config = MagicMock()
        config.fred_api_key = ""
        config.finnhub_api_key = ""
        enricher = build_enricher(config)
        assert enricher is not None
        assert enricher._fred is None
        assert enricher._finnhub is None
        assert enricher._edgar is not None

    def test_returns_enricher_with_fred_only(self):
        config = MagicMock()
        config.fred_api_key = "test-key"
        config.finnhub_api_key = ""
        enricher = build_enricher(config)
        assert enricher is not None
        assert enricher._fred is not None
        assert enricher._finnhub is None
        assert enricher._edgar is not None

    def test_returns_enricher_with_both(self):
        config = MagicMock()
        config.fred_api_key = "fred-key"
        config.finnhub_api_key = "finnhub-key"
        enricher = build_enricher(config)
        assert enricher is not None
        assert enricher._fred is not None
        assert enricher._finnhub is not None
        assert enricher._edgar is not None
