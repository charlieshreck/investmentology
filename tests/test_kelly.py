"""Tests for KellyCalculator and Kelly-enhanced position sizing."""

from __future__ import annotations

from decimal import Decimal

import pytest

from investmentology.timing.sizing import (
    KellyCalculator,
    KELLY_MIN_DECISIONS,
    PositionSizer,
    SizingConfig,
    SizingResult,
)


class TestKellyCalculator:
    def test_positive_kelly(self):
        """60% win rate, 10% avg win, 5% avg loss → positive Kelly."""
        kelly = KellyCalculator(win_rate=0.6, avg_win_pct=10.0, avg_loss_pct=5.0)
        fraction = kelly.calculate()
        assert fraction > 0

    def test_half_kelly(self):
        """Half Kelly should be half of full Kelly."""
        kelly = KellyCalculator(win_rate=0.6, avg_win_pct=10.0, avg_loss_pct=5.0)
        full = kelly.calculate()
        half = kelly.half_kelly()
        assert half == pytest.approx(min(full / 2, 0.04), abs=0.001)

    def test_half_kelly_capped_at_4pct(self):
        """Half Kelly should never exceed 4% per position."""
        kelly = KellyCalculator(win_rate=0.9, avg_win_pct=50.0, avg_loss_pct=5.0)
        half = kelly.half_kelly()
        assert half <= 0.04

    def test_negative_edge(self):
        """30% win rate with poor ratio → Kelly should be 0."""
        kelly = KellyCalculator(win_rate=0.3, avg_win_pct=5.0, avg_loss_pct=10.0)
        assert kelly.calculate() == 0.0
        assert kelly.half_kelly() == 0.0

    def test_zero_win_pct(self):
        kelly = KellyCalculator(win_rate=0.5, avg_win_pct=0.0, avg_loss_pct=5.0)
        assert kelly.calculate() == 0.0

    def test_zero_loss_pct(self):
        kelly = KellyCalculator(win_rate=0.5, avg_win_pct=10.0, avg_loss_pct=0.0)
        # Division by zero case
        assert kelly.calculate() == 0.0

    def test_breakeven_edge(self):
        """50% win rate with equal win/loss → Kelly should be small or zero."""
        kelly = KellyCalculator(win_rate=0.5, avg_win_pct=10.0, avg_loss_pct=10.0)
        fraction = kelly.calculate()
        # At 50/50 with equal sizes, Kelly = 0
        assert fraction == pytest.approx(0.0, abs=0.01)

    def test_min_decisions_constant(self):
        """Verify the minimum decisions threshold is 50."""
        assert KELLY_MIN_DECISIONS == 50


class TestPositionSizerWithKelly:
    def test_kelly_sizing_method(self):
        """When Kelly is provided, sizing_method should be kelly_half."""
        kelly = KellyCalculator(win_rate=0.6, avg_win_pct=10.0, avg_loss_pct=5.0)
        sizer = PositionSizer(kelly=kelly)
        result = sizer.calculate_size(
            portfolio_value=Decimal("100000"),
            price=Decimal("50"),
            current_position_count=5,
            ticker="AAPL",
        )
        assert result.sizing_method == "kelly_half"
        assert result.shares > 0

    def test_no_kelly_uses_equal_weight(self):
        """Without Kelly, sizing_method should be equal_weight."""
        sizer = PositionSizer()
        result = sizer.calculate_size(
            portfolio_value=Decimal("100000"),
            price=Decimal("50"),
            current_position_count=5,
            ticker="AAPL",
        )
        assert result.sizing_method == "equal_weight"

    def test_kelly_capped_at_equal_weight(self):
        """Kelly base should never exceed equal weight base."""
        # Very aggressive Kelly
        kelly = KellyCalculator(win_rate=0.9, avg_win_pct=50.0, avg_loss_pct=2.0)
        sizer = PositionSizer(kelly=kelly)
        result_kelly = sizer.calculate_size(
            portfolio_value=Decimal("100000"),
            price=Decimal("50"),
            current_position_count=5,
            ticker="AAPL",
        )

        sizer_no_kelly = PositionSizer()
        result_equal = sizer_no_kelly.calculate_size(
            portfolio_value=Decimal("100000"),
            price=Decimal("50"),
            current_position_count=5,
            ticker="AAPL",
        )

        assert result_kelly.dollar_amount <= result_equal.dollar_amount

    def test_negative_kelly_falls_back(self):
        """Negative Kelly edge → should fall back to equal weight."""
        kelly = KellyCalculator(win_rate=0.3, avg_win_pct=5.0, avg_loss_pct=10.0)
        sizer = PositionSizer(kelly=kelly)
        result = sizer.calculate_size(
            portfolio_value=Decimal("100000"),
            price=Decimal("50"),
            current_position_count=5,
            ticker="AAPL",
        )
        assert result.sizing_method == "equal_weight"
        assert result.shares > 0
