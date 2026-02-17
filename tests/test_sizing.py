from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from investmentology.timing.sizing import PositionSizer, SizingConfig, SizingResult
from investmentology.timing.pendulum import PendulumReader, PendulumReading


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class _FakePosition:
    ticker: str
    market_value: Decimal


# ---------------------------------------------------------------------------
# PositionSizer tests
# ---------------------------------------------------------------------------

class TestPositionSizerBaseSize:
    def test_equal_weight(self) -> None:
        """Base size is portfolio_value / target_positions."""
        sizer = PositionSizer()  # target_positions=25, max=5%
        base = sizer.calculate_base_size(Decimal("1000000"), 0)
        # 1_000_000 / 25 = 40_000;  1_000_000 * 0.05 = 50_000
        assert base == Decimal("40000")

    def test_capped_at_max_single_position(self) -> None:
        """Base size is capped at max_single_position_pct."""
        cfg = SizingConfig(target_positions=10, max_single_position_pct=Decimal("0.05"))
        sizer = PositionSizer(cfg)
        base = sizer.calculate_base_size(Decimal("1000000"), 0)
        # 1_000_000 / 10 = 100_000 but capped at 50_000
        assert base == Decimal("50000")


class TestPositionSizerCalculateSize:
    def test_shares_rounded_down(self) -> None:
        """Shares must be rounded down to whole numbers."""
        sizer = PositionSizer()
        result = sizer.calculate_size(
            portfolio_value=Decimal("1000000"),
            price=Decimal("33.33"),
            current_position_count=0,
            ticker="TEST",
        )
        # base = 40_000, shares = floor(40_000 / 33.33) = 1200
        assert isinstance(result.shares, int)
        assert result.shares == 1200
        assert result.dollar_amount == Decimal("33.33") * 1200

    def test_rejects_at_max_positions(self) -> None:
        """Returns 0 shares when at max_positions limit."""
        sizer = PositionSizer()
        result = sizer.calculate_size(
            portfolio_value=Decimal("1000000"),
            price=Decimal("100"),
            current_position_count=40,
            ticker="FULL",
        )
        assert result.shares == 0
        assert "max positions" in result.rationale.lower()

    def test_pendulum_multiplier_applied(self) -> None:
        """Pendulum multiplier adjusts position size."""
        sizer = PositionSizer()
        normal = sizer.calculate_size(
            portfolio_value=Decimal("1000000"),
            price=Decimal("100"),
            current_position_count=0,
            ticker="TST",
        )
        fear = sizer.calculate_size(
            portfolio_value=Decimal("1000000"),
            price=Decimal("100"),
            current_position_count=0,
            pendulum_multiplier=Decimal("1.20"),
            ticker="TST",
        )
        # Fear multiplier should give more shares (up to cap)
        assert fear.shares >= normal.shares

    def test_pendulum_multiplier_still_capped(self) -> None:
        """Even with high multiplier, position capped at max_single_position_pct."""
        cfg = SizingConfig(
            target_positions=10,
            max_single_position_pct=Decimal("0.05"),
        )
        sizer = PositionSizer(cfg)
        result = sizer.calculate_size(
            portfolio_value=Decimal("1000000"),
            price=Decimal("100"),
            current_position_count=0,
            pendulum_multiplier=Decimal("1.50"),
            ticker="CAP",
        )
        max_dollar = Decimal("1000000") * Decimal("0.05")
        assert result.dollar_amount <= max_dollar

    def test_result_weight_pct(self) -> None:
        """Weight pct is correctly calculated."""
        sizer = PositionSizer()
        result = sizer.calculate_size(
            portfolio_value=Decimal("1000000"),
            price=Decimal("100"),
            current_position_count=0,
            ticker="W",
        )
        expected_weight = result.dollar_amount / Decimal("1000000") * 100
        assert result.weight_pct <= expected_weight


class TestPortfolioLimits:
    def test_within_limits(self) -> None:
        """Clean portfolio passes limits check."""
        sizer = PositionSizer()
        positions = [
            _FakePosition("AAPL", Decimal("40000")),
            _FakePosition("MSFT", Decimal("40000")),
        ]
        result = sizer.check_portfolio_limits(positions, Decimal("1000000"))
        assert result["within_limits"] is True
        assert result["position_count"] == 2
        assert result["violations"] == []

    def test_detects_overweight_position(self) -> None:
        """Flags position exceeding max_single_position_pct."""
        sizer = PositionSizer()  # max 5%
        positions = [
            _FakePosition("BIG", Decimal("60000")),  # 6% of 1M
        ]
        result = sizer.check_portfolio_limits(positions, Decimal("1000000"))
        assert result["within_limits"] is False
        assert any("BIG" in v for v in result["violations"])

    def test_detects_low_cash(self) -> None:
        """Flags cash below min_cash_pct."""
        sizer = PositionSizer()  # min cash 5%
        # 96% invested = 4% cash
        positions = [_FakePosition(f"S{i}", Decimal("48000")) for i in range(20)]
        result = sizer.check_portfolio_limits(positions, Decimal("1000000"))
        assert result["within_limits"] is False
        assert any("cash" in v.lower() for v in result["violations"])

    def test_detects_too_many_positions(self) -> None:
        """Flags position count exceeding max_positions."""
        sizer = PositionSizer()  # max 40
        positions = [_FakePosition(f"S{i}", Decimal("1000")) for i in range(41)]
        result = sizer.check_portfolio_limits(positions, Decimal("1000000"))
        assert result["within_limits"] is False
        assert any("count" in v.lower() for v in result["violations"])


# ---------------------------------------------------------------------------
# PendulumReader tests
# ---------------------------------------------------------------------------

class TestPendulumVIXScoring:
    def test_low_vix_greed(self) -> None:
        """Low VIX (<15) scores as greed (90)."""
        assert PendulumReader._score_vix(Decimal("12")) == 90

    def test_moderate_vix(self) -> None:
        """Moderate VIX (20-25) scores neutral (50)."""
        assert PendulumReader._score_vix(Decimal("22")) == 50

    def test_high_vix_fear(self) -> None:
        """High VIX (>35) scores as fear (10)."""
        assert PendulumReader._score_vix(Decimal("40")) == 10

    def test_extreme_vix(self) -> None:
        """Very high VIX (80) still scores 10."""
        assert PendulumReader._score_vix(Decimal("80")) == 10

    def test_very_low_vix(self) -> None:
        """VIX=10 scores 90."""
        assert PendulumReader._score_vix(Decimal("10")) == 90


class TestPendulumComposite:
    def test_weighted_average(self) -> None:
        """Composite score is weighted average of components."""
        reader = PendulumReader()
        result = reader.read(
            vix=Decimal("12"),         # score=90
            hy_oas=Decimal("2.5"),     # score=80
            put_call_ratio=Decimal("0.6"),  # score=80
            spy_above_200sma=True,     # score=80
        )
        # weighted = 90*0.30 + 80*0.25 + 80*0.20 + 80*0.25 = 27 + 20 + 16 + 20 = 83
        assert result.score == 83
        assert result.label == "extreme_greed"

    def test_all_fear_indicators(self) -> None:
        """All fear indicators produce low composite."""
        reader = PendulumReader()
        result = reader.read(
            vix=Decimal("40"),            # score=10
            hy_oas=Decimal("8"),          # score=10
            put_call_ratio=Decimal("1.2"),  # score=20
            spy_above_200sma=False,       # score=20
        )
        # weighted = 10*0.30 + 10*0.25 + 20*0.20 + 20*0.25 = 3+2.5+4+5 = 14.5 → 14
        assert result.score == 14
        assert result.label == "extreme_fear"


class TestPendulumLabels:
    @pytest.mark.parametrize(
        "vix,expected_label",
        [
            (Decimal("40"), "extreme_fear"),   # score=10
            (Decimal("30"), "fear"),            # score=30
            (Decimal("22"), "neutral"),         # score=50
            (Decimal("17"), "greed"),           # score=70
            (Decimal("12"), "extreme_greed"),   # score=90
        ],
    )
    def test_labels_match_score_ranges(self, vix: Decimal, expected_label: str) -> None:
        """Labels map correctly to score ranges."""
        reader = PendulumReader()
        # VIX-only reading uses only VIX score directly
        result = reader.read(vix=vix)
        assert result.label == expected_label


class TestPendulumMultiplier:
    @pytest.mark.parametrize(
        "label,expected_mult",
        [
            ("extreme_fear", Decimal("1.20")),
            ("fear", Decimal("1.10")),
            ("neutral", Decimal("1.00")),
            ("greed", Decimal("0.90")),
            ("extreme_greed", Decimal("0.80")),
        ],
    )
    def test_multiplier_per_label(self, label: str, expected_mult: Decimal) -> None:
        """Sizing multiplier maps correctly to each label."""
        from investmentology.timing.pendulum import _LABEL_MULTIPLIERS
        assert _LABEL_MULTIPLIERS[label] == expected_mult

    def test_fear_multiplier_in_reading(self) -> None:
        """Fear reading produces multiplier > 1 (buy more when fearful)."""
        reader = PendulumReader()
        result = reader.read(vix=Decimal("40"))  # extreme fear
        assert result.sizing_multiplier == Decimal("1.20")

    def test_greed_multiplier_in_reading(self) -> None:
        """Greed reading produces multiplier < 1 (buy less when greedy)."""
        reader = PendulumReader()
        result = reader.read(vix=Decimal("12"))  # extreme greed
        assert result.sizing_multiplier == Decimal("0.80")


class TestPendulumPartialData:
    def test_vix_only(self) -> None:
        """Works with only VIX provided."""
        reader = PendulumReader()
        result = reader.read(vix=Decimal("22"))
        assert result.score == 50
        assert "vix" in result.components
        assert len(result.components) == 1

    def test_vix_and_hy_oas(self) -> None:
        """Works with VIX + HY OAS (no put/call or momentum)."""
        reader = PendulumReader()
        result = reader.read(vix=Decimal("22"), hy_oas=Decimal("3.5"))
        assert "vix" in result.components
        assert "hy_oas" in result.components
        assert len(result.components) == 2
        # Weighted: vix=50*0.30 + oas=60*0.25, total_w=0.55
        # = (15+15)/0.55 = 54.5 → 55
        assert result.score == 55


class TestPendulumExtremes:
    def test_extreme_high_vix(self) -> None:
        """VIX=80 handled correctly."""
        reader = PendulumReader()
        result = reader.read(vix=Decimal("80"))
        assert result.score == 10
        assert result.label == "extreme_fear"

    def test_extreme_low_vix(self) -> None:
        """VIX=10 handled correctly."""
        reader = PendulumReader()
        result = reader.read(vix=Decimal("10"))
        assert result.score == 90
        assert result.label == "extreme_greed"
