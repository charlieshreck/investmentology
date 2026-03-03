"""Tests for the deterministic pre-filter.

Validates each hard cutoff rule, sector exemptions, and edge cases.
"""

from __future__ import annotations

import pytest

from investmentology.pipeline.pre_filter import (
    PreFilterResult,
    deterministic_pre_filter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_fundamentals(**overrides) -> dict:
    """Healthy baseline — passes all rules by default."""
    base = {
        "ticker": "TEST",
        "sector": "Technology",
        "operating_income": 500_000_000,
        "net_income": 300_000_000,
        "revenue_growth": 0.12,
        "pe_ratio": 22.0,
        "total_debt": 1_000_000_000,
        "total_assets": 5_000_000_000,
    }
    base.update(overrides)
    return base


def _base_quant(**overrides) -> dict:
    base = {
        "altman_z_score": 3.5,
        "piotroski_score": 7,
        "combined_rank": 10,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Healthy stock passes all rules
# ---------------------------------------------------------------------------


class TestHealthyStock:
    def test_passes_all_rules(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(), _base_quant(),
        )
        assert result.passed is True
        assert result.rules_failed == []
        assert result.rules_checked == 6

    def test_no_quant_data_still_passes(self) -> None:
        result = deterministic_pre_filter(_base_fundamentals(), None)
        assert result.passed is True

    def test_no_optional_data_still_passes(self) -> None:
        result = deterministic_pre_filter(_base_fundamentals(), None, None)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Rule 1: Altman extreme distress
# ---------------------------------------------------------------------------


class TestAltmanDistress:
    def test_below_1_rejects(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(),
            _base_quant(altman_z_score=0.8),
        )
        assert result.passed is False
        assert any("altman_z_distress" in r for r in result.rules_failed)

    def test_at_1_passes(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(),
            _base_quant(altman_z_score=1.0),
        )
        assert not any("altman_z_distress" in r for r in result.rules_failed)

    def test_financial_sector_exempt(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(sector="Financial Services"),
            _base_quant(altman_z_score=0.5),
        )
        assert not any("altman_z_distress" in r for r in result.rules_failed)

    def test_banking_sector_exempt(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(sector="Banking"),
            _base_quant(altman_z_score=0.3),
        )
        assert not any("altman_z_distress" in r for r in result.rules_failed)

    def test_none_altman_skips(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(),
            _base_quant(altman_z_score=None),
        )
        assert not any("altman_z_distress" in r for r in result.rules_failed)


# ---------------------------------------------------------------------------
# Rule 2: Piotroski catastrophic
# ---------------------------------------------------------------------------


class TestPiotroskiCatastrophic:
    def test_score_0_rejects(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(),
            _base_quant(piotroski_score=0),
        )
        assert result.passed is False
        assert any("piotroski_catastrophic" in r for r in result.rules_failed)

    def test_score_1_rejects(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(),
            _base_quant(piotroski_score=1),
        )
        assert result.passed is False
        assert any("piotroski_catastrophic" in r for r in result.rules_failed)

    def test_score_2_passes(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(),
            _base_quant(piotroski_score=2),
        )
        assert not any("piotroski_catastrophic" in r for r in result.rules_failed)

    def test_none_piotroski_skips(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(),
            _base_quant(piotroski_score=None),
        )
        assert not any("piotroski_catastrophic" in r for r in result.rules_failed)


# ---------------------------------------------------------------------------
# Rule 3: Triple negative
# ---------------------------------------------------------------------------


class TestTripleNegative:
    def test_all_three_negative_rejects(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(
                operating_income=-100_000,
                net_income=-200_000,
                revenue_growth=-0.15,
            ),
        )
        assert result.passed is False
        assert any("triple_negative" in r for r in result.rules_failed)

    def test_positive_oi_passes(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(
                operating_income=100_000,
                net_income=-200_000,
                revenue_growth=-0.15,
            ),
        )
        assert not any("triple_negative" in r for r in result.rules_failed)

    def test_mild_revenue_decline_passes(self) -> None:
        """Revenue declining but only -8% (above -10% threshold)."""
        result = deterministic_pre_filter(
            _base_fundamentals(
                operating_income=-100_000,
                net_income=-200_000,
                revenue_growth=-0.08,
            ),
        )
        assert not any("triple_negative" in r for r in result.rules_failed)

    def test_none_values_skip(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(
                operating_income=None,
                net_income=-200_000,
                revenue_growth=-0.15,
            ),
        )
        assert not any("triple_negative" in r for r in result.rules_failed)


# ---------------------------------------------------------------------------
# Rule 4: Extreme P/E with no growth
# ---------------------------------------------------------------------------


class TestExtremePENoGrowth:
    def test_high_pe_no_growth_rejects(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(pe_ratio=150, revenue_growth=0.02),
        )
        assert result.passed is False
        assert any("extreme_pe_no_growth" in r for r in result.rules_failed)

    def test_high_pe_with_growth_passes(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(pe_ratio=150, revenue_growth=0.30),
        )
        assert not any("extreme_pe_no_growth" in r for r in result.rules_failed)

    def test_moderate_pe_passes(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(pe_ratio=50, revenue_growth=0.02),
        )
        assert not any("extreme_pe_no_growth" in r for r in result.rules_failed)

    def test_none_growth_triggers(self) -> None:
        """None revenue_growth with high P/E should still reject."""
        result = deterministic_pre_filter(
            _base_fundamentals(pe_ratio=120, revenue_growth=None),
        )
        assert any("extreme_pe_no_growth" in r for r in result.rules_failed)


# ---------------------------------------------------------------------------
# Rule 5: Losing + shrinking
# ---------------------------------------------------------------------------


class TestLosingShrinking:
    def test_negative_pe_declining_revenue_rejects(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(pe_ratio=-15, revenue_growth=-0.08),
        )
        assert result.passed is False
        assert any("losing_and_shrinking" in r for r in result.rules_failed)

    def test_negative_pe_growing_revenue_passes(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(pe_ratio=-15, revenue_growth=0.10),
        )
        assert not any("losing_and_shrinking" in r for r in result.rules_failed)

    def test_positive_pe_declining_revenue_passes(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(pe_ratio=20, revenue_growth=-0.08),
        )
        assert not any("losing_and_shrinking" in r for r in result.rules_failed)

    def test_mild_decline_passes(self) -> None:
        """Revenue declining -3% (above -5% threshold)."""
        result = deterministic_pre_filter(
            _base_fundamentals(pe_ratio=-5, revenue_growth=-0.03),
        )
        assert not any("losing_and_shrinking" in r for r in result.rules_failed)


# ---------------------------------------------------------------------------
# Rule 6: Debt implosion
# ---------------------------------------------------------------------------


class TestDebtImplosion:
    def test_extreme_leverage_rejects(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(
                total_debt=980_000_000,
                total_assets=1_000_000_000,
            ),
        )
        assert result.passed is False
        assert any("debt_implosion" in r for r in result.rules_failed)

    def test_moderate_leverage_passes(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(
                total_debt=500_000_000,
                total_assets=1_000_000_000,
            ),
        )
        assert not any("debt_implosion" in r for r in result.rules_failed)

    def test_financial_sector_exempt(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(
                sector="Financial Services",
                total_debt=980_000_000,
                total_assets=1_000_000_000,
            ),
        )
        assert not any("debt_implosion" in r for r in result.rules_failed)

    def test_insurance_sector_exempt(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(
                sector="Insurance",
                total_debt=980_000_000,
                total_assets=1_000_000_000,
            ),
        )
        assert not any("debt_implosion" in r for r in result.rules_failed)

    def test_zero_assets_skips(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(total_assets=0),
        )
        assert not any("debt_implosion" in r for r in result.rules_failed)

    def test_none_debt_skips(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(total_debt=None),
        )
        assert not any("debt_implosion" in r for r in result.rules_failed)


# ---------------------------------------------------------------------------
# Multiple rule failures
# ---------------------------------------------------------------------------


class TestMultipleFailures:
    def test_multiple_rules_all_reported(self) -> None:
        """A truly terrible stock fails multiple rules."""
        result = deterministic_pre_filter(
            _base_fundamentals(
                operating_income=-100_000,
                net_income=-200_000,
                revenue_growth=-0.20,
                pe_ratio=-10,
                total_debt=980_000_000,
                total_assets=1_000_000_000,
            ),
            _base_quant(altman_z_score=0.5, piotroski_score=0),
        )
        assert result.passed is False
        # Should fail: altman, piotroski, triple_negative, losing_and_shrinking, debt_implosion
        assert len(result.rules_failed) >= 4
        assert result.rejection_reason is not None
        assert ";" in result.rejection_reason  # Multiple reasons joined

    def test_ticker_in_result(self) -> None:
        result = deterministic_pre_filter(
            _base_fundamentals(ticker="MSFT"),
        )
        assert result.ticker == "MSFT"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_string_values_handled(self) -> None:
        """Values that come as strings from JSON should be handled."""
        result = deterministic_pre_filter(
            _base_fundamentals(
                pe_ratio="25.5",
                revenue_growth="0.10",
                operating_income="500000",
            ),
        )
        assert result.passed is True

    def test_non_numeric_values_handled(self) -> None:
        """Non-numeric values should not crash."""
        result = deterministic_pre_filter(
            _base_fundamentals(
                pe_ratio="N/A",
                revenue_growth="N/A",
            ),
        )
        assert result.passed is True

    def test_empty_fundamentals(self) -> None:
        result = deterministic_pre_filter({})
        assert result.passed is True
        assert result.ticker == "???"

    def test_boundary_altman_0_99(self) -> None:
        """Just below 1.0 should reject."""
        result = deterministic_pre_filter(
            _base_fundamentals(),
            _base_quant(altman_z_score=0.99),
        )
        assert any("altman_z_distress" in r for r in result.rules_failed)

    def test_boundary_debt_ratio_0_95(self) -> None:
        """Exactly 0.95 should pass (> 0.95 required)."""
        result = deterministic_pre_filter(
            _base_fundamentals(
                total_debt=950_000_000,
                total_assets=1_000_000_000,
            ),
        )
        assert not any("debt_implosion" in r for r in result.rules_failed)

    def test_boundary_debt_ratio_0_951(self) -> None:
        """Just above 0.95 should reject."""
        result = deterministic_pre_filter(
            _base_fundamentals(
                total_debt=951_000_000,
                total_assets=1_000_000_000,
            ),
        )
        assert any("debt_implosion" in r for r in result.rules_failed)
