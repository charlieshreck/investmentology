from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from investmentology.models import (
    Decision,
    DecisionType,
    FundamentalsSnapshot,
    PortfolioPosition,
    Prediction,
    Signal,
    SignalSet,
    SignalTag,
    WatchlistState,
    validate_transition,
)


# ---------------------------------------------------------------------------
# FundamentalsSnapshot computed properties
# ---------------------------------------------------------------------------


def _make_snapshot(**overrides) -> FundamentalsSnapshot:
    defaults = dict(
        ticker="AAPL",
        fetched_at=datetime(2025, 1, 15, 12, 0, 0),
        operating_income=Decimal("100000"),
        market_cap=Decimal("500000"),
        total_debt=Decimal("50000"),
        cash=Decimal("30000"),
        current_assets=Decimal("80000"),
        current_liabilities=Decimal("40000"),
        net_ppe=Decimal("60000"),
        revenue=Decimal("400000"),
        net_income=Decimal("80000"),
        total_assets=Decimal("300000"),
        total_liabilities=Decimal("150000"),
        shares_outstanding=1000,
        price=Decimal("500"),
    )
    defaults.update(overrides)
    return FundamentalsSnapshot(**defaults)


class TestFundamentalsSnapshot:
    def test_enterprise_value(self):
        snap = _make_snapshot()
        # EV = market_cap + total_debt - cash = 500000 + 50000 - 30000 = 520000
        assert snap.enterprise_value == Decimal("520000")

    def test_earnings_yield(self):
        snap = _make_snapshot()
        # EY = operating_income / EV = 100000 / 520000
        expected = Decimal("100000") / Decimal("520000")
        assert snap.earnings_yield == expected

    def test_earnings_yield_zero_ev(self):
        snap = _make_snapshot(market_cap=Decimal("0"), total_debt=Decimal("0"), cash=Decimal("100"))
        # EV = 0 + 0 - 100 = -100 (negative)
        assert snap.earnings_yield is None

    def test_net_working_capital(self):
        snap = _make_snapshot()
        # NWC = current_assets - current_liabilities = 80000 - 40000 = 40000
        assert snap.net_working_capital == Decimal("40000")

    def test_invested_capital(self):
        snap = _make_snapshot()
        # IC = NWC + net_ppe = 40000 + 60000 = 100000
        assert snap.invested_capital == Decimal("100000")

    def test_roic(self):
        snap = _make_snapshot()
        # ROIC = operating_income / IC = 100000 / 100000 = 1
        assert snap.roic == Decimal("1")

    def test_roic_zero_ic(self):
        snap = _make_snapshot(
            current_assets=Decimal("10"),
            current_liabilities=Decimal("20"),
            net_ppe=Decimal("5"),
        )
        # IC = (10 - 20) + 5 = -5 (negative)
        assert snap.roic is None


# ---------------------------------------------------------------------------
# SignalTag enum count
# ---------------------------------------------------------------------------


class TestSignalTag:
    def test_signal_tag_count(self):
        # 19 fundamental + 21 macro + 19 technical + 14 risk + 11 special + 18 decision = 102
        assert len(SignalTag) == 102

    def test_signal_tag_values(self):
        assert SignalTag.UNDERVALUED == "UNDERVALUED"
        assert SignalTag.REFLEXIVITY_DETECTED == "REFLEXIVITY_DETECTED"
        assert SignalTag.NO_ACTION == "NO_ACTION"


# ---------------------------------------------------------------------------
# SignalSet
# ---------------------------------------------------------------------------


class TestSignalSet:
    def test_has_returns_true(self):
        ss = SignalSet(signals=[Signal(tag=SignalTag.DEEP_VALUE, strength="strong")])
        assert ss.has(SignalTag.DEEP_VALUE) is True

    def test_has_returns_false(self):
        ss = SignalSet(signals=[Signal(tag=SignalTag.DEEP_VALUE, strength="strong")])
        assert ss.has(SignalTag.OVERVALUED) is False

    def test_get_returns_signal(self):
        sig = Signal(tag=SignalTag.MOAT_WIDENING, strength="moderate", detail="growing margins")
        ss = SignalSet(signals=[sig])
        result = ss.get(SignalTag.MOAT_WIDENING)
        assert result is sig

    def test_get_returns_none(self):
        ss = SignalSet(signals=[])
        assert ss.get(SignalTag.MOAT_WIDENING) is None

    def test_tags_property(self):
        ss = SignalSet(
            signals=[
                Signal(tag=SignalTag.DEEP_VALUE, strength="strong"),
                Signal(tag=SignalTag.MOAT_STABLE, strength="moderate"),
            ]
        )
        assert ss.tags == {SignalTag.DEEP_VALUE, SignalTag.MOAT_STABLE}

    def test_empty_signal_set(self):
        ss = SignalSet()
        assert ss.tags == set()
        assert ss.has(SignalTag.HOLD) is False


# ---------------------------------------------------------------------------
# Lifecycle state transitions
# ---------------------------------------------------------------------------


class TestLifecycleTransitions:
    def test_valid_universe_to_candidate(self):
        assert validate_transition(WatchlistState.UNIVERSE, WatchlistState.CANDIDATE) is True

    def test_invalid_universe_to_assessed(self):
        assert validate_transition(WatchlistState.UNIVERSE, WatchlistState.ASSESSED) is False

    def test_valid_assessed_to_conviction_buy(self):
        assert validate_transition(WatchlistState.ASSESSED, WatchlistState.CONVICTION_BUY) is True

    def test_valid_assessed_to_rejected(self):
        assert validate_transition(WatchlistState.ASSESSED, WatchlistState.REJECTED) is True

    def test_rejected_is_terminal(self):
        for state in WatchlistState:
            assert validate_transition(WatchlistState.REJECTED, state) is False

    def test_position_sell_is_terminal(self):
        for state in WatchlistState:
            assert validate_transition(WatchlistState.POSITION_SELL, state) is False

    def test_position_hold_to_trim(self):
        assert validate_transition(WatchlistState.POSITION_HOLD, WatchlistState.POSITION_TRIM) is True

    def test_position_hold_cannot_go_to_candidate(self):
        assert validate_transition(WatchlistState.POSITION_HOLD, WatchlistState.CANDIDATE) is False

    def test_conflict_review_to_assessed(self):
        assert validate_transition(WatchlistState.CONFLICT_REVIEW, WatchlistState.ASSESSED) is True


# ---------------------------------------------------------------------------
# PortfolioPosition
# ---------------------------------------------------------------------------


class TestPortfolioPosition:
    def test_pnl_pct_positive(self):
        pos = PortfolioPosition(
            ticker="AAPL",
            entry_date=date(2025, 1, 1),
            entry_price=Decimal("100"),
            current_price=Decimal("120"),
            shares=Decimal("10"),
            position_type="core",
            weight=Decimal("0.05"),
        )
        assert pos.pnl_pct == Decimal("0.2")

    def test_pnl_pct_negative(self):
        pos = PortfolioPosition(
            ticker="AAPL",
            entry_date=date(2025, 1, 1),
            entry_price=Decimal("100"),
            current_price=Decimal("80"),
            shares=Decimal("10"),
            position_type="core",
            weight=Decimal("0.05"),
        )
        assert pos.pnl_pct == Decimal("-0.2")

    def test_market_value(self):
        pos = PortfolioPosition(
            ticker="MSFT",
            entry_date=date(2025, 1, 1),
            entry_price=Decimal("200"),
            current_price=Decimal("250"),
            shares=Decimal("50"),
            position_type="permanent",
            weight=Decimal("0.10"),
        )
        assert pos.market_value == Decimal("12500")


# ---------------------------------------------------------------------------
# Prediction requires settlement_date
# ---------------------------------------------------------------------------


class TestPrediction:
    def test_prediction_has_settlement_date(self):
        pred = Prediction(
            ticker="GOOG",
            prediction_type="price_target",
            predicted_value=Decimal("200"),
            confidence=Decimal("0.75"),
            horizon_days=90,
            settlement_date=date(2025, 4, 15),
            source="warren_agent",
        )
        assert pred.settlement_date == date(2025, 4, 15)
        assert pred.is_settled is False

    def test_prediction_missing_settlement_date_raises(self):
        with pytest.raises(TypeError):
            Prediction(
                ticker="GOOG",
                prediction_type="price_target",
                predicted_value=Decimal("200"),
                confidence=Decimal("0.75"),
                horizon_days=90,
                # settlement_date omitted
                source="warren_agent",
            )


# ---------------------------------------------------------------------------
# Decision basic construction
# ---------------------------------------------------------------------------


class TestDecision:
    def test_decision_creation(self):
        d = Decision(
            ticker="NVDA",
            decision_type=DecisionType.SCREEN,
            layer_source="L1_quant_gate",
            confidence=Decimal("0.85"),
            reasoning="Top 100 by Magic Formula ranking",
        )
        assert d.ticker == "NVDA"
        assert d.decision_type == DecisionType.SCREEN
        assert d.id is None
        assert d.created_at is None
