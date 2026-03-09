"""Tests for the Beneish M-Score earnings manipulation detector."""

from datetime import datetime
from decimal import Decimal

from investmentology.models.stock import FundamentalsSnapshot
from investmentology.quant_gate.beneish import (
    MANIPULATION_THRESHOLD,
    BeneishResult,
    calculate_beneish,
)


def _make_snap(**overrides) -> FundamentalsSnapshot:
    """Helper to build a FundamentalsSnapshot with sensible defaults."""
    defaults = {
        "ticker": "TEST",
        "fetched_at": datetime(2025, 1, 1),
        "operating_income": Decimal("1000"),
        "market_cap": Decimal("10000"),
        "total_debt": Decimal("2000"),
        "cash": Decimal("500"),
        "current_assets": Decimal("3000"),
        "current_liabilities": Decimal("1500"),
        "net_ppe": Decimal("4000"),
        "revenue": Decimal("8000"),
        "net_income": Decimal("800"),
        "total_assets": Decimal("10000"),
        "total_liabilities": Decimal("5000"),
        "shares_outstanding": 1000,
        "price": Decimal("10"),
        "retained_earnings": Decimal("2000"),
        "operating_cash_flow": Decimal("900"),
        "gross_profit": Decimal("4000"),
        "receivables": Decimal("1200"),
        "depreciation": Decimal("400"),
        "sga": Decimal("1500"),
    }
    defaults.update(overrides)
    return FundamentalsSnapshot(**defaults)


class TestBeneishCalculation:
    def test_returns_none_without_prior(self):
        snap = _make_snap()
        assert calculate_beneish(snap, None) is None

    def test_healthy_company_not_flagged(self):
        """A company with stable, consistent financials should not be flagged."""
        prior = _make_snap(
            revenue=Decimal("7500"),
            receivables=Decimal("1100"),
            gross_profit=Decimal("3750"),
            net_ppe=Decimal("3800"),
            depreciation=Decimal("380"),
            sga=Decimal("1400"),
            total_assets=Decimal("9500"),
            total_liabilities=Decimal("4800"),
            current_assets=Decimal("2800"),
            net_income=Decimal("750"),
            operating_cash_flow=Decimal("850"),
        )
        current = _make_snap()
        result = calculate_beneish(current, prior)
        assert result is not None
        assert result.data_sufficient is True
        assert result.is_manipulator is False
        assert result.m_score <= MANIPULATION_THRESHOLD

    def test_manipulator_flagged(self):
        """A company showing manipulation signals should be flagged.

        Manipulation signals: rapidly growing revenue with receivables growing faster,
        deteriorating gross margins, increasing accruals, rising leverage.
        """
        prior = _make_snap(
            revenue=Decimal("5000"),
            receivables=Decimal("500"),
            gross_profit=Decimal("3000"),
            net_ppe=Decimal("4000"),
            depreciation=Decimal("400"),
            sga=Decimal("1000"),
            total_assets=Decimal("9000"),
            total_liabilities=Decimal("4000"),
            current_assets=Decimal("2500"),
            net_income=Decimal("600"),
            operating_cash_flow=Decimal("700"),
        )
        # Aggressive revenue growth, receivables ballooning, margins deteriorating
        current = _make_snap(
            revenue=Decimal("10000"),
            receivables=Decimal("3000"),  # 6x vs prior 500, far outpacing revenue
            gross_profit=Decimal("4000"),  # GM drops from 60% to 40%
            net_ppe=Decimal("4000"),
            depreciation=Decimal("200"),  # Depreciation cut in half
            sga=Decimal("1000"),  # SGA flat while revenue doubles
            total_assets=Decimal("15000"),
            total_liabilities=Decimal("10000"),  # Leverage increasing
            current_assets=Decimal("5000"),
            net_income=Decimal("2000"),  # High NI but...
            operating_cash_flow=Decimal("200"),  # ...cash flow doesn't match
        )
        result = calculate_beneish(current, prior)
        assert result is not None
        assert result.data_sufficient is True
        assert result.is_manipulator is True
        assert result.m_score > MANIPULATION_THRESHOLD

    def test_zero_revenue_returns_none(self):
        prior = _make_snap(revenue=Decimal("0"))
        current = _make_snap()
        assert calculate_beneish(current, prior) is None

    def test_zero_total_assets_returns_none(self):
        prior = _make_snap()
        current = _make_snap(total_assets=Decimal("0"))
        assert calculate_beneish(current, prior) is None

    def test_insufficient_data_not_flagged(self):
        """With most data missing asymmetrically, result should show data_sufficient=False."""
        # Prior has data, current doesn't — creates asymmetric missing (counted as missing)
        prior = _make_snap(
            receivables=Decimal("1000"),
            gross_profit=Decimal("3000"),
            depreciation=Decimal("400"),
            sga=Decimal("1200"),
        )
        current = _make_snap(
            receivables=Decimal("0"),
            gross_profit=Decimal("0"),
            depreciation=Decimal("0"),
            sga=Decimal("0"),
            operating_cash_flow=Decimal("0"),
            net_income=Decimal("0"),
        )
        result = calculate_beneish(current, prior)
        assert result is not None
        assert result.data_sufficient is False
        assert result.is_manipulator is False

    def test_all_components_present(self):
        """All 8 components should be computed when data is available."""
        prior = _make_snap()
        current = _make_snap(revenue=Decimal("9000"))  # Slight growth
        result = calculate_beneish(current, prior)
        assert result is not None
        assert result.data_sufficient is True
        for key in ["dsri", "gmi", "aqi", "sgi", "depi", "sgai", "lvgi", "tata"]:
            assert key in result.components
            assert result.components[key] is not None, f"{key} should not be None"

    def test_sgi_component_correct(self):
        """SGI = Revenue_t / Revenue_t-1."""
        prior = _make_snap(revenue=Decimal("5000"))
        current = _make_snap(revenue=Decimal("7500"))
        result = calculate_beneish(current, prior)
        assert result is not None
        assert result.components["sgi"] == Decimal("1.5")

    def test_tata_component_correct(self):
        """TATA = (NI - OCF) / TA."""
        current = _make_snap(
            net_income=Decimal("1000"),
            operating_cash_flow=Decimal("600"),
            total_assets=Decimal("10000"),
        )
        prior = _make_snap()
        result = calculate_beneish(current, prior)
        assert result is not None
        # TATA = (1000 - 600) / 10000 = 0.04
        assert result.components["tata"] == Decimal("0.04")

    def test_threshold_boundary(self):
        """M-Score exactly at -1.78 should NOT be flagged (> not >=)."""
        # We can't easily construct an exact -1.78, but verify the comparison logic
        result = BeneishResult(
            ticker="TEST",
            m_score=Decimal("-1.78"),
            is_manipulator=Decimal("-1.78") > MANIPULATION_THRESHOLD,
            components={},
            data_sufficient=True,
        )
        assert result.is_manipulator is False

        result2 = BeneishResult(
            ticker="TEST",
            m_score=Decimal("-1.77"),
            is_manipulator=Decimal("-1.77") > MANIPULATION_THRESHOLD,
            components={},
            data_sufficient=True,
        )
        assert result2.is_manipulator is True
