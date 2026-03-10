"""Tests for pipeline freshness — material change detection."""

import pytest

from investmentology.pipeline.freshness import (
    MaterialChangeReport,
    check_material_change,
)


def _base_fundamentals() -> dict:
    """Base fundamentals dict for testing."""
    return {
        "total_revenue": 10_000_000_000,   # $10B
        "operating_income": 2_000_000_000,  # $2B
        "net_income": 1_500_000_000,        # $1.5B
        "total_debt": 3_000_000_000,        # $3B
        "total_equity": 8_000_000_000,      # $8B
        "eps": 5.50,
    }


class TestMaterialChange:
    def test_no_change(self):
        """Identical fundamentals → no material change."""
        fund = _base_fundamentals()
        report = check_material_change(fund, fund.copy(), "AAPL")
        assert not report.has_material_change
        assert report.changed_fields == {}

    def test_small_change_below_threshold(self):
        """<5% revenue change → no material change."""
        current = _base_fundamentals()
        previous = _base_fundamentals()
        previous["total_revenue"] = 10_400_000_000  # 4% change
        report = check_material_change(current, previous, "AAPL")
        assert not report.has_material_change

    def test_revenue_material_change(self):
        """6% revenue change → material change detected."""
        current = _base_fundamentals()
        previous = _base_fundamentals()
        current["total_revenue"] = 10_600_000_000  # 6% increase
        report = check_material_change(current, previous, "AAPL")
        assert report.has_material_change
        assert "total_revenue" in report.changed_fields

    def test_debt_material_change(self):
        """15% debt change → material change detected."""
        current = _base_fundamentals()
        previous = _base_fundamentals()
        current["total_debt"] = 3_450_000_000  # 15% increase
        report = check_material_change(current, previous, "AAPL")
        assert report.has_material_change
        assert "total_debt" in report.changed_fields

    def test_near_zero_values_ignored(self):
        """Both near-zero → comparison skipped (not misleading)."""
        current = _base_fundamentals()
        previous = _base_fundamentals()
        current["total_debt"] = 500_000   # $500K
        previous["total_debt"] = 100_000  # $100K (400% change but near zero)
        report = check_material_change(current, previous, "TINY")
        # total_debt should NOT be flagged since both below $1M floor
        assert "total_debt" not in report.changed_fields

    def test_missing_field_in_current(self):
        """Missing field in current → skip comparison, not flagged."""
        current = _base_fundamentals()
        previous = _base_fundamentals()
        del current["total_debt"]
        report = check_material_change(current, previous, "AAPL")
        assert "total_debt" not in report.changed_fields

    def test_missing_field_in_previous(self):
        """Missing field in previous → skip comparison, not flagged."""
        current = _base_fundamentals()
        previous = _base_fundamentals()
        del previous["operating_income"]
        report = check_material_change(current, previous, "AAPL")
        assert "operating_income" not in report.changed_fields

    def test_zero_previous_nonzero_current(self):
        """Previous was 0, current is nonzero → infinite change, flagged."""
        current = _base_fundamentals()
        previous = _base_fundamentals()
        previous["operating_income"] = 0
        report = check_material_change(current, previous, "AAPL")
        assert report.has_material_change
        assert "operating_income" in report.changed_fields

    def test_multiple_changes(self):
        """Multiple fields changing → all flagged."""
        current = _base_fundamentals()
        previous = _base_fundamentals()
        current["total_revenue"] = 12_000_000_000   # 20% up
        current["net_income"] = 2_000_000_000        # 33% up
        report = check_material_change(current, previous, "AAPL")
        assert report.has_material_change
        assert "total_revenue" in report.changed_fields
        assert "net_income" in report.changed_fields

    def test_reason_string_on_change(self):
        """Reason string contains changed field names."""
        current = _base_fundamentals()
        previous = _base_fundamentals()
        current["total_revenue"] = 12_000_000_000
        report = check_material_change(current, previous, "AAPL")
        assert "total_revenue" in report.reason
        assert "Material change" in report.reason

    def test_reason_string_no_change(self):
        """Reason string says no change."""
        fund = _base_fundamentals()
        report = check_material_change(fund, fund.copy(), "AAPL")
        assert "No material change" in report.reason

    def test_string_numeric_values(self):
        """Handles string-encoded numbers (from JSON/DB)."""
        current = _base_fundamentals()
        previous = {k: str(v) for k, v in _base_fundamentals().items()}
        current["total_revenue"] = 12_000_000_000  # 20% up
        report = check_material_change(current, previous, "AAPL")
        assert report.has_material_change

    def test_decimal_values(self):
        """Handles Decimal values from database."""
        from decimal import Decimal
        current = {k: Decimal(str(v)) for k, v in _base_fundamentals().items()}
        previous = _base_fundamentals()
        current["total_revenue"] = Decimal("12000000000")
        report = check_material_change(current, previous, "AAPL")
        assert report.has_material_change
