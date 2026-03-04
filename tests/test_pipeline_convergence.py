"""Tests for pipeline convergence logic (debate trigger + synthesis readiness)."""

from __future__ import annotations

from decimal import Decimal

from investmentology.models.signal import (
    AgentSignalSet,
    Signal,
    SignalSet,
    SignalTag,
)
from investmentology.pipeline.convergence import (
    CONSENSUS_THRESHOLD,
    classify_sentiment,
    should_debate,
    synthesis_ready,
)


def _make_signal_set(tags: list[SignalTag]) -> AgentSignalSet:
    """Helper to create an AgentSignalSet with given tags."""
    signals = SignalSet(signals=[Signal(tag=t, strength="strong") for t in tags])
    return AgentSignalSet(
        agent_name="test-agent",
        model="test",
        signals=signals,
        confidence=Decimal("0.80"),
        reasoning="test",
    )


class TestClassifySentiment:
    def test_bullish(self):
        ss = _make_signal_set([SignalTag.BUY_NEW, SignalTag.HOLD_STRONG])
        assert classify_sentiment(ss) == "bullish"

    def test_bearish(self):
        ss = _make_signal_set([SignalTag.SELL_FULL, SignalTag.REJECT])
        assert classify_sentiment(ss) == "bearish"

    def test_neutral(self):
        ss = _make_signal_set([SignalTag.HOLD, SignalTag.NO_ACTION])
        assert classify_sentiment(ss) == "neutral"

    def test_mixed_defaults_neutral(self):
        ss = _make_signal_set([SignalTag.BUY_NEW, SignalTag.SELL_FULL, SignalTag.HOLD])
        # Equal bullish/bearish/neutral → neutral (tie-break)
        result = classify_sentiment(ss)
        assert result in ("bullish", "bearish", "neutral")

    def test_empty_signals_neutral(self):
        ss = _make_signal_set([])
        assert classify_sentiment(ss) == "neutral"


class TestShouldDebate:
    def test_empty_signals_no_debate(self):
        assert should_debate([]) is False

    def test_full_agreement_no_debate(self):
        agents = [
            _make_signal_set([SignalTag.BUY_NEW]),
            _make_signal_set([SignalTag.BUY_ADD]),
            _make_signal_set([SignalTag.HOLD_STRONG]),
            _make_signal_set([SignalTag.BUY_NEW]),
        ]
        # 4/4 bullish = 100% agreement, no debate
        assert should_debate(agents) is False

    def test_strong_majority_no_debate(self):
        agents = [
            _make_signal_set([SignalTag.BUY_NEW]),
            _make_signal_set([SignalTag.BUY_ADD]),
            _make_signal_set([SignalTag.BUY_NEW]),
            _make_signal_set([SignalTag.SELL_FULL]),
        ]
        # 3/4 bullish = 75%, exactly at threshold, no debate
        assert should_debate(agents) is False

    def test_disagreement_triggers_debate(self):
        agents = [
            _make_signal_set([SignalTag.BUY_NEW]),
            _make_signal_set([SignalTag.BUY_ADD]),
            _make_signal_set([SignalTag.SELL_FULL]),
            _make_signal_set([SignalTag.SELL_PARTIAL]),
        ]
        # 2/4 bullish = 50%, below threshold, debate needed
        assert should_debate(agents) is True

    def test_single_agent_no_debate(self):
        agents = [_make_signal_set([SignalTag.BUY_NEW])]
        # 1/1 = 100% agreement
        assert should_debate(agents) is False

    def test_threshold_value(self):
        assert CONSENSUS_THRESHOLD == 0.75


class TestSynthesisReady:
    def test_all_complete_no_debate(self):
        assert synthesis_ready(
            primary_completed=6, total_primary=6,
            debate_completed=False, debate_required=False,
        ) is True

    def test_all_complete_debate_done(self):
        assert synthesis_ready(
            primary_completed=6, total_primary=6,
            debate_completed=True, debate_required=True,
        ) is True

    def test_debate_required_not_done(self):
        assert synthesis_ready(
            primary_completed=6, total_primary=6,
            debate_completed=False, debate_required=True,
        ) is False

    def test_two_failures_allowed(self):
        # 6 primary, 4 completed = 2 failures allowed
        assert synthesis_ready(
            primary_completed=4, total_primary=6,
            debate_completed=False, debate_required=False,
        ) is True

    def test_three_failures_blocked(self):
        # 6 primary, 3 completed = 3 failures, blocked
        assert synthesis_ready(
            primary_completed=3, total_primary=6,
            debate_completed=False, debate_required=False,
        ) is False

    def test_minimum_one_agent(self):
        # Even with total=1, need at least 1
        assert synthesis_ready(
            primary_completed=1, total_primary=1,
            debate_completed=False, debate_required=False,
        ) is True
        assert synthesis_ready(
            primary_completed=0, total_primary=1,
            debate_completed=False, debate_required=False,
        ) is False
