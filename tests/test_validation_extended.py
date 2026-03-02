"""Tests for extended data validation checks.

Covers the new validation rules added to validation.py:
- P/E ratio sanity (negative P/E for profitable company)
- EPS sign vs net_income sign consistency
- Market cap vs shares_outstanding * price consistency
- Revenue growth rate sanity for large caps
- Extreme revenue growth critical error for mega-caps
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import importlib
import sys
from pathlib import Path

# Import validation.py directly to avoid data/__init__.py pulling in yfinance
_src = Path(__file__).resolve().parent.parent / "src" / "investmentology" / "data" / "validation.py"
_spec = importlib.util.spec_from_file_location("investmentology.data.validation", _src)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["investmentology.data.validation"] = _mod
_spec.loader.exec_module(_mod)

detect_anomalies = _mod.detect_anomalies
detect_critical_anomalies = _mod.detect_critical_anomalies
validate_fundamentals = _mod.validate_fundamentals


def _make_data(**overrides: object) -> dict:
    """Create a valid baseline data dict."""
    base = {
        "ticker": "TEST",
        "fetched_at": datetime.now(UTC).isoformat(),
        "market_cap": Decimal("50000000000"),  # $50B
        "operating_income": Decimal("10000000000"),
        "net_income": Decimal("8000000000"),
        "price": Decimal("150.0"),
        "shares_outstanding": Decimal("333333333"),  # ~$50B / $150
        "revenue": Decimal("80000000000"),
        "total_debt": Decimal("20000000000"),
        "total_assets": Decimal("100000000000"),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# P/E ratio sanity (critical error)
# ---------------------------------------------------------------------------


class TestPERatioSanity:
    def test_negative_pe_profitable_company_is_error(self):
        """Negative P/E with positive net_income = corrupted data."""
        data = _make_data(
            pe_ratio=Decimal("-25.0"),
            net_income=Decimal("8000000000"),
            price=Decimal("150.0"),
        )
        errors = detect_critical_anomalies(data)
        assert any("P/E ratio" in e for e in errors)

    def test_negative_pe_unprofitable_company_is_ok(self):
        """Negative P/E is expected when company is losing money."""
        data = _make_data(
            pe_ratio=Decimal("-15.0"),
            net_income=Decimal("-2000000000"),
            price=Decimal("50.0"),
            # Must also have revenue to avoid zeroed-financials error
            revenue=Decimal("10000000000"),
            operating_income=Decimal("-1000000000"),
        )
        errors = detect_critical_anomalies(data)
        assert not any("P/E ratio" in e for e in errors)

    def test_positive_pe_profitable_company_is_ok(self):
        """Normal case: positive P/E, positive income."""
        data = _make_data(pe_ratio=Decimal("25.0"))
        errors = detect_critical_anomalies(data)
        assert not any("P/E ratio" in e for e in errors)

    def test_no_pe_ratio_is_ok(self):
        """Missing P/E should not trigger an error."""
        data = _make_data()  # no pe_ratio
        errors = detect_critical_anomalies(data)
        assert not any("P/E ratio" in e for e in errors)

    def test_negative_pe_blocks_pipeline(self):
        """Full validation should mark as invalid."""
        data = _make_data(
            pe_ratio=Decimal("-25.0"),
            net_income=Decimal("8000000000"),
        )
        result = validate_fundamentals(data)
        assert not result.is_valid
        assert any("P/E ratio" in e for e in result.errors)


# ---------------------------------------------------------------------------
# EPS sign vs net_income sign (warning)
# ---------------------------------------------------------------------------


class TestEPSNetIncomeConsistency:
    def test_positive_income_negative_eps_warns(self):
        data = _make_data(
            eps=Decimal("-5.0"),
            net_income=Decimal("8000000000"),
        )
        anomalies = detect_anomalies(data)
        assert any("EPS" in a and "net_income" in a for a in anomalies)

    def test_negative_income_positive_eps_warns(self):
        data = _make_data(
            eps=Decimal("5.0"),
            net_income=Decimal("-2000000000"),
        )
        anomalies = detect_anomalies(data)
        assert any("EPS" in a and "net_income" in a for a in anomalies)

    def test_consistent_positive_is_ok(self):
        data = _make_data(
            eps=Decimal("24.0"),
            net_income=Decimal("8000000000"),
        )
        anomalies = detect_anomalies(data)
        assert not any("EPS" in a for a in anomalies)

    def test_consistent_negative_is_ok(self):
        data = _make_data(
            eps=Decimal("-5.0"),
            net_income=Decimal("-2000000000"),
        )
        anomalies = detect_anomalies(data)
        assert not any("EPS" in a for a in anomalies)

    def test_no_eps_is_ok(self):
        """Missing EPS should not trigger warning."""
        data = _make_data()  # no eps field
        anomalies = detect_anomalies(data)
        assert not any("EPS" in a for a in anomalies)

    def test_eps_warning_does_not_block_pipeline(self):
        """EPS mismatch is a warning, not an error."""
        data = _make_data(
            eps=Decimal("-5.0"),
            net_income=Decimal("8000000000"),
        )
        result = validate_fundamentals(data)
        assert result.is_valid  # warnings don't block
        assert any("EPS" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Market cap vs shares_outstanding * price consistency (warning)
# ---------------------------------------------------------------------------


class TestMarketCapConsistency:
    def test_wildly_inconsistent_warns(self):
        """Market cap 10x higher than implied = data error."""
        data = _make_data(
            market_cap=Decimal("500000000000"),  # $500B
            shares_outstanding=Decimal("1000000000"),
            price=Decimal("50.0"),  # implied = $50B
        )
        anomalies = detect_anomalies(data)
        assert any("market_cap" in a and "inconsistent" in a for a in anomalies)

    def test_within_tolerance_is_ok(self):
        """10% difference is within the 2x tolerance."""
        data = _make_data(
            market_cap=Decimal("55000000000"),  # $55B
            shares_outstanding=Decimal("1000000000"),
            price=Decimal("50.0"),  # implied = $50B, ratio=1.1
        )
        anomalies = detect_anomalies(data)
        assert not any("inconsistent" in a for a in anomalies)

    def test_exactly_matching_is_ok(self):
        data = _make_data(
            market_cap=Decimal("50000000000"),
            shares_outstanding=Decimal("1000000000"),
            price=Decimal("50.0"),
        )
        anomalies = detect_anomalies(data)
        assert not any("inconsistent" in a for a in anomalies)

    def test_missing_price_no_crash(self):
        data = _make_data(price=None)
        anomalies = detect_anomalies(data)
        # Should not crash, and should not warn about market cap consistency
        assert not any("inconsistent" in a for a in anomalies)

    def test_zero_shares_no_crash(self):
        data = _make_data(shares_outstanding=Decimal("0"))
        anomalies = detect_anomalies(data)
        assert not any("inconsistent" in a for a in anomalies)


# ---------------------------------------------------------------------------
# Revenue growth sanity (warning for large cap, error for mega cap)
# ---------------------------------------------------------------------------


class TestRevenueGrowthSanity:
    def test_extreme_growth_large_cap_warns(self):
        """1500% revenue growth for $20B company = suspicious."""
        data = _make_data(
            market_cap=Decimal("20000000000"),  # $20B
            revenue_growth=Decimal("15.0"),  # 1500%
        )
        anomalies = detect_anomalies(data)
        assert any("revenue_growth" in a for a in anomalies)

    def test_normal_growth_large_cap_ok(self):
        """20% revenue growth for large cap is normal."""
        data = _make_data(
            market_cap=Decimal("20000000000"),
            revenue_growth=Decimal("0.20"),  # 20%
        )
        anomalies = detect_anomalies(data)
        assert not any("revenue_growth" in a for a in anomalies)

    def test_high_growth_small_cap_ok(self):
        """High growth for small caps is plausible — shouldn't warn."""
        data = _make_data(
            market_cap=Decimal("500000000"),  # $500M
            revenue_growth=Decimal("15.0"),  # 1500%
        )
        anomalies = detect_anomalies(data)
        assert not any("revenue_growth" in a for a in anomalies)

    def test_impossible_growth_mega_cap_is_error(self):
        """5500% growth for $200B mega-cap = corrupted data (pipeline error)."""
        data = _make_data(
            market_cap=Decimal("200000000000"),  # $200B
            revenue_growth=Decimal("55.0"),  # 5500%
        )
        errors = detect_critical_anomalies(data)
        assert any("revenue_growth" in e and "Impossible" in e for e in errors)

    def test_impossible_negative_growth_mega_cap_is_error(self):
        """Extreme negative growth also triggers."""
        data = _make_data(
            market_cap=Decimal("200000000000"),
            revenue_growth=Decimal("-55.0"),  # -5500%
        )
        errors = detect_critical_anomalies(data)
        assert any("revenue_growth" in e for e in errors)

    def test_moderate_growth_mega_cap_is_ok(self):
        """15% growth for mega cap is fine."""
        data = _make_data(
            market_cap=Decimal("200000000000"),
            revenue_growth=Decimal("0.15"),
        )
        errors = detect_critical_anomalies(data)
        assert not any("revenue_growth" in e for e in errors)

    def test_no_revenue_growth_is_ok(self):
        """Missing revenue_growth should not trigger anything."""
        data = _make_data()
        anomalies = detect_anomalies(data)
        errors = detect_critical_anomalies(data)
        assert not any("revenue_growth" in a for a in anomalies)
        assert not any("revenue_growth" in e for e in errors)


# ---------------------------------------------------------------------------
# Existing checks still pass with new fields present
# ---------------------------------------------------------------------------


class TestExistingChecksUnbroken:
    def test_valid_data_with_new_fields_passes(self):
        """Clean data with all new fields should still validate OK."""
        data = _make_data(
            pe_ratio=Decimal("25.0"),
            eps=Decimal("24.0"),
            revenue_growth=Decimal("0.08"),
        )
        result = validate_fundamentals(data)
        assert result.is_valid
        assert result.errors == []

    def test_zeroed_revenue_still_errors(self):
        """Original zeroed-revenue check must still work."""
        data = _make_data(revenue=Decimal("0"))
        result = validate_fundamentals(data)
        assert not result.is_valid
        assert any("Zeroed revenue" in e for e in result.errors)

    def test_missing_price_still_errors(self):
        """Original zero-price check must still work."""
        data = _make_data(price=None)
        result = validate_fundamentals(data)
        assert not result.is_valid

    def test_operating_income_gt_revenue_still_warns(self):
        """Original anomaly check still works."""
        data = _make_data(
            operating_income=Decimal("100000000000"),
            revenue=Decimal("50000000000"),
        )
        anomalies = detect_anomalies(data)
        assert any("operating_income" in a for a in anomalies)
