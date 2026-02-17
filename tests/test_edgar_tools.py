"""Tests for EdgarToolsProvider."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from investmentology.data.edgar_tools import (
    EdgarToolsProvider,
    _extract_section,
    _truncate,
)


class TestTruncate:
    def test_short_text(self):
        assert _truncate("hello", 100) == "hello"

    def test_truncate_at_sentence(self):
        text = "First sentence. Second sentence. Third sentence."
        result = _truncate(text, 35)
        assert result.endswith(".")
        assert len(result) <= 35

    def test_truncate_no_sentence(self):
        text = "a" * 100
        result = _truncate(text, 50)
        assert result.endswith("...")


class TestExtractSection:
    def test_extract_risk_factors(self):
        text = (
            "Blah blah\nITEM 1A. RISK FACTORS\n"
            "We face significant risks including market volatility.\n"
            "ITEM 2. PROPERTIES\nOur headquarters..."
        )
        result = _extract_section(text, r"ITEM\s+1A\.?\s*[-—]?\s*RISK\s+FACTORS")
        assert result is not None
        assert "significant risks" in result

    def test_no_match(self):
        result = _extract_section("No sections here", r"ITEM\s+1A")
        assert result is None

    def test_empty_section(self):
        text = "ITEM 1A. RISK FACTORS\n\nITEM 2. PROPERTIES"
        result = _extract_section(text, r"ITEM\s+1A\.?\s*[-—]?\s*RISK\s+FACTORS")
        assert result is None


class TestEdgarToolsProvider:
    def test_cache_hit(self):
        provider = EdgarToolsProvider()
        cached = {"risk_factors": "test risk", "mda": "test mda", "filing_date": "2024-01-01", "filing_type": "10-K"}
        provider._cache["filing:AAPL:10-K"] = (datetime.now(), cached)
        result = provider.get_filing_text("AAPL")
        assert result == cached

    def test_cache_expired(self):
        provider = EdgarToolsProvider()
        old_time = datetime.now() - timedelta(hours=25)
        provider._cache["filing:AAPL:10-K"] = (old_time, {"old": True})
        assert provider._get_cached("filing:AAPL:10-K") is None

    def test_get_filing_text_success(self):
        provider = EdgarToolsProvider()
        mock_company = MagicMock()
        mock_filing = MagicMock()
        mock_filing.filing_date = "2024-03-15"
        mock_filing.markdown.return_value = (
            "Report content\nITEM 1A. RISK FACTORS\n"
            "Major risk factors include competition.\n"
            "ITEM 2. PROPERTIES\nWe have offices."
        )
        mock_company.latest_tenk = mock_filing

        mock_edgar = MagicMock()
        mock_edgar.Company.return_value = mock_company

        with patch.dict("sys.modules", {"edgar": mock_edgar}):
            provider._identity_set = True  # skip identity setup
            result = provider.get_filing_text("AAPL")

        assert result is not None
        assert "competition" in (result.get("risk_factors") or "")
        assert result["filing_type"] == "10-K"

    def test_get_filing_text_no_filing(self):
        provider = EdgarToolsProvider()
        mock_company = MagicMock()
        mock_company.latest_tenk = None

        mock_edgar = MagicMock()
        mock_edgar.Company.return_value = mock_company

        with patch.dict("sys.modules", {"edgar": mock_edgar}):
            provider._identity_set = True
            result = provider.get_filing_text("FAKE")

        assert result is None

    def test_get_filing_text_exception(self):
        provider = EdgarToolsProvider()
        mock_edgar = MagicMock()
        mock_edgar.Company.side_effect = Exception("API down")

        with patch.dict("sys.modules", {"edgar": mock_edgar}):
            provider._identity_set = True
            result = provider.get_filing_text("AAPL")

        assert result is None

    def test_holders_cache_hit(self):
        provider = EdgarToolsProvider()
        holders = [{"name": "Vanguard", "shares": 1000000, "value": 5000000}]
        provider._cache["holders:AAPL"] = (datetime.now(), holders)
        result = provider.get_institutional_holders("AAPL")
        assert result == holders

    def test_get_institutional_holders_no_filings(self):
        provider = EdgarToolsProvider()
        mock_company = MagicMock()
        mock_company.get_filings.return_value = []

        mock_edgar = MagicMock()
        mock_edgar.Company.return_value = mock_company

        with patch.dict("sys.modules", {"edgar": mock_edgar}):
            provider._identity_set = True
            result = provider.get_institutional_holders("FAKE")

        assert result is None

    def test_get_institutional_holders_exception(self):
        provider = EdgarToolsProvider()
        mock_edgar = MagicMock()
        mock_edgar.Company.side_effect = Exception("Boom")

        with patch.dict("sys.modules", {"edgar": mock_edgar}):
            provider._identity_set = True
            result = provider.get_institutional_holders("AAPL")

        assert result is None

    def test_insider_cache_hit(self):
        provider = EdgarToolsProvider()
        insider = {"total_filings": 5, "recent_count": 5, "recent_transactions": []}
        provider._cache["insider:AAPL"] = (datetime.now(), insider)
        result = provider.get_insider_summary("AAPL")
        assert result == insider

    def test_get_insider_summary_no_filings(self):
        provider = EdgarToolsProvider()
        mock_company = MagicMock()
        mock_company.get_filings.return_value = []

        mock_edgar = MagicMock()
        mock_edgar.Company.return_value = mock_company

        with patch.dict("sys.modules", {"edgar": mock_edgar}):
            provider._identity_set = True
            result = provider.get_insider_summary("FAKE")

        assert result is None

    def test_get_insider_summary_exception(self):
        provider = EdgarToolsProvider()
        mock_edgar = MagicMock()
        mock_edgar.Company.side_effect = Exception("Boom")

        with patch.dict("sys.modules", {"edgar": mock_edgar}):
            provider._identity_set = True
            result = provider.get_insider_summary("AAPL")

        assert result is None

    def test_identity_set_once(self):
        provider = EdgarToolsProvider()
        assert not provider._identity_set

        mock_edgar = MagicMock()
        with patch.dict("sys.modules", {"edgar": mock_edgar}):
            provider._ensure_identity()
            assert provider._identity_set
            mock_edgar.set_identity.assert_called_once()
            # Second call shouldn't call set_identity again
            provider._ensure_identity()
            mock_edgar.set_identity.assert_called_once()
