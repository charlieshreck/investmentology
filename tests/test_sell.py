from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal


from investmentology.models.position import PortfolioPosition
from investmentology.models.stock import FundamentalsSnapshot
from investmentology.sell.core import check_core_rules
from investmentology.sell.engine import SellEngine
from investmentology.sell.permanent import check_permanent_rules
from investmentology.sell.rules import SellReason, SellUrgency
from investmentology.sell.tactical import (
    check_greenblatt_rotation,
    check_tactical_rules,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pos(
    ticker: str = "AAPL",
    entry_date: date = date(2025, 1, 1),
    entry_price: str = "100",
    current_price: str = "100",
    position_type: str = "core",
    shares: str = "10",
    weight: str = "0.05",
) -> PortfolioPosition:
    return PortfolioPosition(
        ticker=ticker,
        entry_date=entry_date,
        entry_price=Decimal(entry_price),
        current_price=Decimal(current_price),
        shares=Decimal(shares),
        position_type=position_type,
        weight=Decimal(weight),
    )


def _snap(
    ticker: str = "AAPL",
    revenue: str = "100",
    operating_income: str = "20",
    total_debt: str = "50",
    fetched_at: datetime | None = None,
    **overrides: str,
) -> FundamentalsSnapshot:
    defaults = dict(
        ticker=ticker,
        fetched_at=fetched_at or datetime(2025, 1, 1),
        operating_income=Decimal(operating_income),
        market_cap=Decimal("1000"),
        total_debt=Decimal(total_debt),
        cash=Decimal("50"),
        current_assets=Decimal("200"),
        current_liabilities=Decimal("100"),
        net_ppe=Decimal("300"),
        revenue=Decimal(revenue),
        net_income=Decimal("15"),
        total_assets=Decimal("800"),
        total_liabilities=Decimal("400"),
        shares_outstanding=100,
        price=Decimal("100"),
    )
    for k, v in overrides.items():
        defaults[k] = Decimal(v)
    return FundamentalsSnapshot(**defaults)


# ===========================================================================
# Permanent rules
# ===========================================================================

class TestPermanentRules:
    def test_revenue_decline_flags(self) -> None:
        """Revenue decline >15% for 2+ consecutive periods triggers FLAG."""
        pos = _pos(position_type="permanent")
        # 3 snapshots: 100 -> 80 (-20%) -> 60 (-25%)
        snaps = [
            _snap(revenue="100"),
            _snap(revenue="80"),
            _snap(revenue="60"),
        ]
        signals = check_permanent_rules(pos, snaps)
        revenue_signals = [s for s in signals if "Revenue declined" in s.detail]
        assert len(revenue_signals) == 1
        assert revenue_signals[0].urgency == SellUrgency.FLAG
        assert revenue_signals[0].reason == SellReason.THESIS_BREAK

    def test_margin_compression_flags(self) -> None:
        """Margin compression >500 bps triggers FLAG."""
        pos = _pos(position_type="permanent")
        # Early margin: 20/100 = 20%, Late margin: 10/100 = 10% -> 1000 bps drop
        snaps = [
            _snap(revenue="100", operating_income="20"),
            _snap(revenue="100", operating_income="10"),
        ]
        signals = check_permanent_rules(pos, snaps)
        margin_signals = [s for s in signals if "margin compressed" in s.detail]
        assert len(margin_signals) == 1
        assert margin_signals[0].urgency == SellUrgency.FLAG

    def test_no_flag_within_bounds(self) -> None:
        """No signals when metrics are within acceptable bounds."""
        pos = _pos(position_type="permanent")
        # Revenue decline only 5% (within 15%), margin stable
        snaps = [
            _snap(revenue="100", operating_income="20"),
            _snap(revenue="95", operating_income="19"),
            _snap(revenue="91", operating_income="18"),
        ]
        signals = check_permanent_rules(pos, snaps)
        assert signals == []

    def test_single_snapshot_no_signal(self) -> None:
        """Single snapshot is insufficient for analysis."""
        pos = _pos(position_type="permanent")
        signals = check_permanent_rules(pos, [_snap()])
        assert signals == []


# ===========================================================================
# Core rules
# ===========================================================================

class TestCoreRules:
    def test_trailing_stop_at_20_pct(self) -> None:
        """Trailing stop fires when price is 20%+ below peak."""
        pos = _pos(current_price="78")
        signals = check_core_rules(
            pos, [], highest_price_since_entry=Decimal("100"),
        )
        trail_signals = [s for s in signals if s.reason == SellReason.TRAILING_STOP]
        assert len(trail_signals) == 1
        assert trail_signals[0].urgency == SellUrgency.SIGNAL
        assert trail_signals[0].trigger_price == Decimal("80")

    def test_trailing_stop_not_triggered(self) -> None:
        """No trailing stop when price is within 20% of peak."""
        pos = _pos(current_price="85")
        signals = check_core_rules(
            pos, [], highest_price_since_entry=Decimal("100"),
        )
        trail_signals = [s for s in signals if s.reason == SellReason.TRAILING_STOP]
        assert trail_signals == []

    def test_roic_declining_triggers(self) -> None:
        """ROIC declining 3 consecutive quarters triggers SIGNAL."""
        pos = _pos()
        # ROIC: invested_capital = (current_assets - current_liabilities) + net_ppe
        # For defaults: (200-100)+300 = 400
        # ROIC = operating_income / 400
        snaps = [
            _snap(operating_income="120"),  # 30%
            _snap(operating_income="80"),   # 20%
            _snap(operating_income="40"),   # 10%
        ]
        signals = check_core_rules(pos, snaps)
        roic_signals = [s for s in signals if "ROIC declining" in s.detail]
        assert len(roic_signals) == 1
        assert roic_signals[0].urgency == SellUrgency.SIGNAL

    def test_debt_ebitda_over_3x(self) -> None:
        """Debt/EBITDA > 3x triggers SIGNAL."""
        pos = _pos()
        snaps = [_snap(total_debt="400", operating_income="100")]  # 4x
        signals = check_core_rules(pos, snaps)
        debt_signals = [s for s in signals if "Debt/EBITDA" in s.detail]
        assert len(debt_signals) == 1

    def test_take_profit_150_pct(self) -> None:
        """Full exit signal at 150% of fair value."""
        pos = _pos(current_price="150")
        signals = check_core_rules(pos, [], fair_value=Decimal("100"))
        ov_signals = [s for s in signals if s.reason == SellReason.OVERVALUED]
        assert len(ov_signals) == 1
        assert "full exit" in ov_signals[0].detail

    def test_take_profit_120_pct(self) -> None:
        """Trim 1/3 signal at 120% of fair value."""
        pos = _pos(current_price="125")
        signals = check_core_rules(pos, [], fair_value=Decimal("100"))
        ov_signals = [s for s in signals if s.reason == SellReason.OVERVALUED]
        assert len(ov_signals) == 1
        assert "trim 1/3" in ov_signals[0].detail

    def test_no_take_profit_below_threshold(self) -> None:
        """No overvalued signal when price is under 120% of fair value."""
        pos = _pos(current_price="115")
        signals = check_core_rules(pos, [], fair_value=Decimal("100"))
        ov_signals = [s for s in signals if s.reason == SellReason.OVERVALUED]
        assert ov_signals == []


# ===========================================================================
# Tactical rules
# ===========================================================================

class TestTacticalRules:
    def test_hard_stop_at_15_pct(self) -> None:
        """Hard stop fires when price is 15%+ below entry."""
        pos = _pos(position_type="tactical", entry_price="100", current_price="84")
        signals = check_tactical_rules(pos, today=date(2025, 2, 1))
        stop_signals = [s for s in signals if s.reason == SellReason.STOP_LOSS]
        assert len(stop_signals) == 1
        assert stop_signals[0].urgency == SellUrgency.EXECUTE

    def test_hard_stop_not_triggered(self) -> None:
        """No hard stop when price is within 15%."""
        pos = _pos(position_type="tactical", entry_price="100", current_price="90")
        signals = check_tactical_rules(pos, today=date(2025, 2, 1))
        stop_signals = [s for s in signals if s.reason == SellReason.STOP_LOSS]
        assert stop_signals == []

    def test_time_stop_6_months(self) -> None:
        """Time stop at 6 months triggers trim 50% SIGNAL."""
        pos = _pos(
            position_type="tactical",
            entry_date=date(2025, 1, 1),
            current_price="100",
        )
        today = date(2025, 7, 5)  # 185 days
        signals = check_tactical_rules(pos, today=today)
        time_signals = [s for s in signals if s.reason == SellReason.TIME_STOP]
        assert len(time_signals) == 1
        assert time_signals[0].urgency == SellUrgency.SIGNAL
        assert "trim 50%" in time_signals[0].detail

    def test_time_stop_12_months(self) -> None:
        """Time stop at 12 months triggers full exit EXECUTE."""
        pos = _pos(
            position_type="tactical",
            entry_date=date(2025, 1, 1),
            current_price="100",
        )
        today = date(2026, 1, 5)  # 370 days
        signals = check_tactical_rules(pos, today=today)
        time_signals = [s for s in signals if s.reason == SellReason.TIME_STOP]
        assert len(time_signals) == 1
        assert time_signals[0].urgency == SellUrgency.EXECUTE
        assert "full exit" in time_signals[0].detail

    def test_greenblatt_winner_53_weeks(self) -> None:
        """Winner sold at 53 weeks (371 days) for LTCG."""
        pos = _pos(
            position_type="tactical",
            entry_date=date(2025, 1, 1),
            entry_price="100",
            current_price="120",  # winner
        )
        today = date(2026, 1, 7)  # 371 days
        signal = check_greenblatt_rotation(pos, today=today)
        assert signal is not None
        assert signal.reason == SellReason.GREENBLATT_ROTATION
        assert signal.urgency == SellUrgency.EXECUTE
        assert "long-term capital gains" in signal.detail

    def test_greenblatt_loser_51_weeks(self) -> None:
        """Loser sold at 51 weeks (357 days) for tax loss."""
        pos = _pos(
            position_type="tactical",
            entry_date=date(2025, 1, 1),
            entry_price="100",
            current_price="80",  # loser
        )
        today = date(2025, 12, 24)  # 357 days
        signal = check_greenblatt_rotation(pos, today=today)
        assert signal is not None
        assert signal.reason == SellReason.GREENBLATT_ROTATION
        assert "tax loss harvesting" in signal.detail

    def test_greenblatt_no_rotation_too_early(self) -> None:
        """No rotation before 51 weeks."""
        pos = _pos(
            position_type="tactical",
            entry_date=date(2025, 1, 1),
            entry_price="100",
            current_price="80",  # loser
        )
        today = date(2025, 11, 1)  # ~304 days
        signal = check_greenblatt_rotation(pos, today=today)
        assert signal is None


# ===========================================================================
# Engine
# ===========================================================================

class TestSellEngine:
    def test_routes_permanent(self) -> None:
        """Engine routes permanent positions to permanent rules."""
        engine = SellEngine()
        pos = _pos(position_type="permanent")
        snaps = [
            _snap(revenue="100", operating_income="20"),
            _snap(revenue="80", operating_income="10"),
            _snap(revenue="60", operating_income="5"),
        ]
        signals = engine.evaluate_position(pos, fundamentals=snaps)
        # Should get thesis break flags from permanent rules
        assert all(s.urgency == SellUrgency.FLAG for s in signals)

    def test_routes_core(self) -> None:
        """Engine routes core positions to core rules."""
        engine = SellEngine()
        pos = _pos(position_type="core", current_price="150")
        signals = engine.evaluate_position(pos, fair_value=Decimal("100"))
        reasons = {s.reason for s in signals}
        assert SellReason.OVERVALUED in reasons

    def test_routes_tactical(self) -> None:
        """Engine routes tactical positions to tactical rules."""
        engine = SellEngine()
        pos = _pos(
            position_type="tactical",
            entry_date=date(2025, 1, 1),
            entry_price="100",
            current_price="80",  # hits hard stop
        )
        signals = engine.evaluate_position(pos)
        reasons = {s.reason for s in signals}
        assert SellReason.STOP_LOSS in reasons

    def test_evaluate_portfolio(self) -> None:
        """Engine evaluates all positions in a portfolio."""
        engine = SellEngine()
        positions = [
            _pos(ticker="AAPL", position_type="tactical",
                 entry_price="100", current_price="80"),
            _pos(ticker="MSFT", position_type="core",
                 current_price="150"),
            _pos(ticker="BRK", position_type="permanent",
                 current_price="100"),
        ]
        results = engine.evaluate_portfolio(
            positions,
            fair_values={"MSFT": Decimal("100")},
        )
        assert "AAPL" in results  # hard stop
        assert "MSFT" in results  # overvalued
        # BRK has no fundamentals and metrics are fine, no signals
        assert "BRK" not in results

    def test_unknown_position_type(self) -> None:
        """Unknown position type returns empty signals."""
        engine = SellEngine()
        pos = _pos(position_type="speculative")
        signals = engine.evaluate_position(pos)
        assert signals == []

    def test_urgency_levels(self) -> None:
        """Verify correct urgency levels per rule type."""
        # Permanent -> FLAG
        engine = SellEngine()
        perm = _pos(position_type="permanent")
        perm_snaps = [
            _snap(revenue="100", operating_income="20"),
            _snap(revenue="80", operating_income="10"),
            _snap(revenue="60", operating_income="5"),
        ]
        perm_signals = engine.evaluate_position(perm, fundamentals=perm_snaps)
        for s in perm_signals:
            assert s.urgency == SellUrgency.FLAG

        # Core -> SIGNAL
        core = _pos(position_type="core", current_price="78")
        core_signals = engine.evaluate_position(
            core, highest_price_since_entry=Decimal("100"),
        )
        for s in core_signals:
            assert s.urgency == SellUrgency.SIGNAL

        # Tactical hard stop -> EXECUTE
        tact = _pos(
            position_type="tactical",
            entry_price="100",
            current_price="80",
        )
        tact_signals = check_tactical_rules(tact, today=date(2025, 2, 1))
        stop_signals = [s for s in tact_signals if s.reason == SellReason.STOP_LOSS]
        for s in stop_signals:
            assert s.urgency == SellUrgency.EXECUTE
