"""Tests for verdict.py — the verdict synthesizer."""

from __future__ import annotations

from decimal import Decimal


from investmentology.adversarial.munger import AdversarialResult, MungerVerdict
from investmentology.compatibility.matrix import CompatibilityResult
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag
from investmentology.verdict import (
    AgentStance,
    Verdict,
    VerdictResult,
    _compute_sentiment,
    _distill_stance,
    _get_agent_weights,
    _score_to_verdict,
    synthesize,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal_set(
    agent_name: str,
    tags: list[tuple[SignalTag, str]],
    confidence: Decimal = Decimal("0.7"),
    reasoning: str = "test reasoning",
) -> AgentSignalSet:
    signals = [Signal(tag=t, strength=s, detail="") for t, s in tags]
    return AgentSignalSet(
        agent_name=agent_name,
        model="test-model",
        signals=SignalSet(signals=signals),
        confidence=confidence,
        reasoning=reasoning,
    )


def _bullish_warren() -> AgentSignalSet:
    return _make_signal_set("warren", [
        (SignalTag.UNDERVALUED, "strong"),
        (SignalTag.MOAT_WIDENING, "strong"),
        (SignalTag.EARNINGS_QUALITY_HIGH, "moderate"),
        (SignalTag.BUY_NEW, "strong"),
    ], Decimal("0.85"))


def _bullish_soros() -> AgentSignalSet:
    return _make_signal_set("soros", [
        (SignalTag.REGIME_BULL, "strong"),
        (SignalTag.SECTOR_ROTATION_INTO, "moderate"),
        (SignalTag.CREDIT_EASING, "moderate"),
    ], Decimal("0.75"))


def _bullish_simons() -> AgentSignalSet:
    return _make_signal_set("simons", [
        (SignalTag.TREND_UPTREND, "strong"),
        (SignalTag.MOMENTUM_STRONG, "strong"),
        (SignalTag.BREAKOUT_CONFIRMED, "moderate"),
        (SignalTag.GOLDEN_CROSS, "moderate"),
    ], Decimal("0.80"))


def _clean_auditor() -> AgentSignalSet:
    return _make_signal_set("auditor", [
        (SignalTag.LEVERAGE_OK, "moderate"),
        (SignalTag.LIQUIDITY_OK, "moderate"),
        (SignalTag.VOLATILITY_LOW, "moderate"),
        (SignalTag.CORRELATION_LOW, "moderate"),
    ], Decimal("0.80"))


def _bearish_auditor() -> AgentSignalSet:
    return _make_signal_set("auditor", [
        (SignalTag.LEVERAGE_HIGH, "strong"),
        (SignalTag.ACCOUNTING_RED_FLAG, "strong"),
        (SignalTag.GOVERNANCE_CONCERN, "strong"),
        (SignalTag.DRAWDOWN_RISK, "strong"),
    ], Decimal("0.85"))


def _bearish_warren() -> AgentSignalSet:
    return _make_signal_set("warren", [
        (SignalTag.OVERVALUED, "strong"),
        (SignalTag.NO_MOAT, "strong"),
        (SignalTag.EARNINGS_QUALITY_LOW, "moderate"),
        (SignalTag.REJECT, "strong"),
    ], Decimal("0.80"))


def _bearish_soros() -> AgentSignalSet:
    return _make_signal_set("soros", [
        (SignalTag.REGIME_BEAR, "strong"),
        (SignalTag.CREDIT_TIGHTENING, "strong"),
        (SignalTag.SECTOR_ROTATION_OUT, "moderate"),
    ], Decimal("0.75"))


def _bearish_simons() -> AgentSignalSet:
    return _make_signal_set("simons", [
        (SignalTag.TREND_DOWNTREND, "strong"),
        (SignalTag.MOMENTUM_WEAK, "strong"),
        (SignalTag.BREAKDOWN_CONFIRMED, "moderate"),
        (SignalTag.DEATH_CROSS, "strong"),
    ], Decimal("0.80"))


# ---------------------------------------------------------------------------
# TestVerdict enum
# ---------------------------------------------------------------------------

class TestVerdictEnum:
    def test_all_values_exist(self) -> None:
        expected = {
            "STRONG_BUY", "BUY", "ACCUMULATE", "HOLD", "WATCHLIST",
            "REDUCE", "SELL", "AVOID", "DISCARD",
        }
        assert {v.value for v in Verdict} == expected

    def test_is_str_enum(self) -> None:
        assert Verdict.BUY == "BUY"
        assert str(Verdict.SELL) == "SELL"


# ---------------------------------------------------------------------------
# TestAgentWeights
# ---------------------------------------------------------------------------

class TestAgentWeights:
    def test_weights_sum_to_one(self) -> None:
        weights = _get_agent_weights()
        total = sum(weights.values())
        assert total == Decimal("1.00")

    def test_all_active_agents_present(self) -> None:
        weights = _get_agent_weights()
        expected = {
            "warren", "auditor", "klarman", "soros",
            "druckenmiller", "dalio", "simons", "lynch",
            "marks", "income_analyst",
        }
        assert set(weights.keys()) == expected

    def test_auditor_has_significant_weight(self) -> None:
        weights = _get_agent_weights()
        assert weights["auditor"] >= Decimal("0.15")


# ---------------------------------------------------------------------------
# TestComputeSentiment
# ---------------------------------------------------------------------------

class TestComputeSentiment:
    def test_all_bullish(self) -> None:
        ss = _bullish_warren()
        result = _compute_sentiment(ss)
        assert result > 0.5

    def test_all_bearish(self) -> None:
        ss = _bearish_warren()
        result = _compute_sentiment(ss)
        assert result < -0.5

    def test_empty_signals(self) -> None:
        ss = _make_signal_set("warren", [], Decimal("0.5"))
        result = _compute_sentiment(ss)
        assert result == 0.0

    def test_neutral_signals(self) -> None:
        ss = _make_signal_set("warren", [
            (SignalTag.FAIRLY_VALUED, "moderate"),
        ], Decimal("0.5"))
        result = _compute_sentiment(ss)
        assert result == 0.0

    def test_strength_affects_sentiment(self) -> None:
        strong = _make_signal_set("warren", [
            (SignalTag.UNDERVALUED, "strong"),
            (SignalTag.OVERVALUED, "weak"),
        ], Decimal("0.5"))
        weak = _make_signal_set("warren", [
            (SignalTag.UNDERVALUED, "weak"),
            (SignalTag.OVERVALUED, "strong"),
        ], Decimal("0.5"))
        assert _compute_sentiment(strong) > 0
        assert _compute_sentiment(weak) < 0

    def test_range_bounded(self) -> None:
        for ss in [_bullish_warren(), _bearish_warren()]:
            result = _compute_sentiment(ss)
            assert -1.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# TestDistillStance
# ---------------------------------------------------------------------------

class TestDistillStance:
    def test_produces_stance(self) -> None:
        stance = _distill_stance(_bullish_warren())
        assert isinstance(stance, AgentStance)
        assert stance.name == "warren"
        assert stance.confidence == Decimal("0.85")
        assert stance.sentiment > 0

    def test_key_signals_limited_to_3(self) -> None:
        ss = _make_signal_set("test", [
            (SignalTag.UNDERVALUED, "strong"),
            (SignalTag.MOAT_WIDENING, "strong"),
            (SignalTag.EARNINGS_QUALITY_HIGH, "strong"),
            (SignalTag.REVENUE_ACCELERATING, "strong"),
            (SignalTag.MARGIN_EXPANDING, "strong"),
        ], Decimal("0.8"))
        stance = _distill_stance(ss)
        assert len(stance.key_signals) == 3

    def test_summary_is_reasoning(self) -> None:
        ss = _make_signal_set("warren", [(SignalTag.UNDERVALUED, "strong")],
                              reasoning="Great company")
        stance = _distill_stance(ss)
        assert stance.summary == "Great company"


# ---------------------------------------------------------------------------
# TestScoreToVerdict
# ---------------------------------------------------------------------------

class TestScoreToVerdict:
    def test_strong_buy(self) -> None:
        v, _m = _score_to_verdict(0.7, Decimal("0.8"), False, False, None)
        assert v == Verdict.STRONG_BUY

    def test_buy(self) -> None:
        v, _m = _score_to_verdict(0.4, Decimal("0.6"), False, False, None)
        assert v == Verdict.BUY

    def test_accumulate(self) -> None:
        v, _m = _score_to_verdict(0.2, Decimal("0.4"), False, False, None)
        assert v == Verdict.ACCUMULATE

    def test_hold(self) -> None:
        v, _m = _score_to_verdict(0.0, Decimal("0.5"), False, False, None)
        assert v == Verdict.HOLD

    def test_watchlist_positive_low_confidence(self) -> None:
        # WATCHLIST requires sentiment >= 0.10 AND confidence < 0.40
        v, _m = _score_to_verdict(0.12, Decimal("0.2"), False, False, None)
        assert v == Verdict.WATCHLIST

    def test_hold_neutral_sentiment(self) -> None:
        # Neutral sentiment (0.0) with low confidence falls to HOLD, not WATCHLIST
        v, _m = _score_to_verdict(0.0, Decimal("0.2"), False, False, None)
        assert v == Verdict.HOLD

    def test_reduce(self) -> None:
        v, _m = _score_to_verdict(-0.2, Decimal("0.5"), False, False, None)
        assert v == Verdict.REDUCE

    def test_sell(self) -> None:
        v, _m = _score_to_verdict(-0.4, Decimal("0.6"), False, False, None)
        assert v == Verdict.SELL

    def test_avoid(self) -> None:
        v, _m = _score_to_verdict(-0.6, Decimal("0.7"), False, False, None)
        assert v == Verdict.AVOID

    def test_munger_override_forces_avoid(self) -> None:
        v, _m = _score_to_verdict(0.8, Decimal("0.9"), False, True, None)
        assert v == Verdict.AVOID

    def test_auditor_override_caps_positive(self) -> None:
        v, _m = _score_to_verdict(0.5, Decimal("0.8"), True, False, None)
        assert v == Verdict.WATCHLIST

    def test_auditor_override_caps_neutral(self) -> None:
        v, _m = _score_to_verdict(0.0, Decimal("0.5"), True, False, None)
        assert v == Verdict.AVOID

    def test_dangerous_disagreements_force_watchlist(self) -> None:
        compat = CompatibilityResult(
            ticker="TEST", matched_pattern=None, pattern_score=0.0,
            merged_signals=set(), avg_confidence=Decimal("0.7"),
            disagreements=[], dangerous_disagreement_count=2,
            requires_munger=False, recommended_action="",
        )
        v, _m = _score_to_verdict(0.5, Decimal("0.8"), False, False, compat)
        assert v == Verdict.WATCHLIST

    def test_munger_beats_auditor(self) -> None:
        v, _m = _score_to_verdict(0.5, Decimal("0.8"), True, True, None)
        assert v == Verdict.AVOID  # Munger checked first

    def test_reduce_requires_confidence(self) -> None:
        # Low confidence negative → HOLD, not REDUCE
        v, _m = _score_to_verdict(-0.2, Decimal("0.3"), False, False, None)
        assert v == Verdict.HOLD

    def test_sell_requires_confidence(self) -> None:
        # Moderate confidence strongly negative → REDUCE, not SELL
        v, _m = _score_to_verdict(-0.4, Decimal("0.45"), False, False, None)
        assert v == Verdict.REDUCE

    def test_sell_low_confidence_falls_to_hold(self) -> None:
        # Low confidence strongly negative → HOLD
        v, _m = _score_to_verdict(-0.4, Decimal("0.3"), False, False, None)
        assert v == Verdict.HOLD

    def test_avoid_still_fires_high_confidence(self) -> None:
        # Very negative + high confidence → AVOID unchanged
        v, _m = _score_to_verdict(-0.6, Decimal("0.7"), False, False, None)
        assert v == Verdict.AVOID


# ---------------------------------------------------------------------------
# TestSynthesize — full integration
# ---------------------------------------------------------------------------

class TestSynthesize:
    def test_empty_signals_returns_discard(self) -> None:
        result = synthesize([])
        assert result.verdict == Verdict.DISCARD
        assert result.confidence == Decimal("0")
        assert "No agent signals" in result.reasoning

    def test_all_bullish_consensus(self) -> None:
        result = synthesize([
            _bullish_warren(), _bullish_soros(),
            _bullish_simons(), _clean_auditor(),
        ])
        assert result.verdict in {Verdict.STRONG_BUY, Verdict.BUY, Verdict.ACCUMULATE}
        assert result.consensus_score > 0.3
        # 4 provided + 5 imputed neutral = 9 total stances
        assert len(result.agent_stances) >= 4
        provided_names = {"warren", "soros", "simons", "auditor"}
        assert provided_names.issubset({s.name for s in result.agent_stances})
        assert not result.auditor_override
        assert not result.munger_override

    def test_all_bearish_consensus(self) -> None:
        result = synthesize([
            _bearish_warren(), _bearish_soros(),
            _bearish_simons(), _bearish_auditor(),
        ])
        assert result.verdict in {Verdict.SELL, Verdict.AVOID, Verdict.REDUCE}
        assert result.consensus_score < -0.3

    def test_auditor_veto_caps_verdict(self) -> None:
        result = synthesize([
            _bullish_warren(), _bullish_soros(),
            _bullish_simons(), _bearish_auditor(),
        ])
        assert result.auditor_override is True
        assert result.verdict in {Verdict.WATCHLIST, Verdict.AVOID}
        assert len(result.risk_flags) > 0

    def test_munger_veto_forces_avoid(self) -> None:
        adversarial = AdversarialResult(
            verdict=MungerVerdict.VETO,
            bias_flags=[],
            kill_scenarios=[],
            premortem=None,
            reasoning="Fatal flaw found in the thesis",
        )
        result = synthesize(
            [_bullish_warren(), _bullish_soros(), _bullish_simons(), _clean_auditor()],
            adversarial=adversarial,
        )
        assert result.verdict == Verdict.AVOID
        assert result.munger_override is True
        assert "vetoed" in result.reasoning.lower()

    def test_munger_caution_downgrades(self) -> None:
        adversarial = AdversarialResult(
            verdict=MungerVerdict.CAUTION,
            bias_flags=["anchoring_bias"],
            kill_scenarios=[],
            premortem=None,
            reasoning="Some concerns",
        )
        bullish_result = synthesize(
            [_bullish_warren(), _bullish_soros(), _bullish_simons(), _clean_auditor()],
        )
        cautious_result = synthesize(
            [_bullish_warren(), _bullish_soros(), _bullish_simons(), _clean_auditor()],
            adversarial=adversarial,
        )
        # Caution should produce a weaker verdict
        verdict_rank = {
            Verdict.STRONG_BUY: 8, Verdict.BUY: 7, Verdict.ACCUMULATE: 6,
            Verdict.HOLD: 5, Verdict.WATCHLIST: 4, Verdict.REDUCE: 3,
            Verdict.SELL: 2, Verdict.AVOID: 1, Verdict.DISCARD: 0,
        }
        assert verdict_rank[cautious_result.verdict] <= verdict_rank[bullish_result.verdict]

    def test_reasoning_mentions_agents(self) -> None:
        result = synthesize([
            _bullish_warren(), _bullish_soros(),
            _bullish_simons(), _clean_auditor(),
        ])
        assert "Warren" in result.reasoning
        assert "Soros" in result.reasoning

    def test_stances_contain_provided_agents(self) -> None:
        result = synthesize([
            _bullish_warren(), _bullish_soros(),
            _bullish_simons(), _clean_auditor(),
        ])
        names = {s.name for s in result.agent_stances}
        # Should include provided agents + imputed neutrals for missing agents
        assert {"warren", "soros", "simons", "auditor"}.issubset(names)

    def test_mixed_signals_moderate_verdict(self) -> None:
        # Warren and auditor bearish (combined 60% weight), soros and simons bullish (40%)
        result = synthesize([
            _bearish_warren(), _bullish_soros(),
            _bullish_simons(), _bearish_auditor(),
        ])
        # Mixed signals should not produce extreme buy verdict
        assert result.verdict not in {Verdict.STRONG_BUY, Verdict.BUY}

    def test_single_agent_still_works(self) -> None:
        result = synthesize([_bullish_warren()])
        assert result.verdict in {v for v in Verdict}
        assert len(result.agent_stances) >= 1

    def test_compatibility_with_dangerous_disagreements(self) -> None:
        compat = CompatibilityResult(
            ticker="TEST", matched_pattern=None, pattern_score=0.0,
            merged_signals=set(), avg_confidence=Decimal("0.7"),
            disagreements=[], dangerous_disagreement_count=3,
            requires_munger=False, recommended_action="",
        )
        result = synthesize(
            [_bullish_warren(), _bullish_soros(), _bullish_simons(), _clean_auditor()],
            compatibility=compat,
        )
        assert result.verdict == Verdict.WATCHLIST


# ---------------------------------------------------------------------------
# TestVerdictResult dataclass
# ---------------------------------------------------------------------------

class TestVerdictResult:
    def test_defaults(self) -> None:
        vr = VerdictResult(
            verdict=Verdict.HOLD,
            confidence=Decimal("0.5"),
            reasoning="test",
        )
        assert vr.agent_stances == []
        assert vr.consensus_score == 0.0
        assert vr.risk_flags == []
        assert vr.auditor_override is False
        assert vr.munger_override is False


# ---------------------------------------------------------------------------
# TestVerdictStabilityDampener
# ---------------------------------------------------------------------------

class TestVerdictStabilityDampener:
    """Tests for the verdict flip-prevention dampener.

    When previous verdict was positive, sentiment must drop well below -0.10
    (by the dampening band of 0.15) before REDUCE is allowed.
    """

    def test_no_previous_verdict_no_dampening(self) -> None:
        """Without previous verdict, normal thresholds apply."""
        verdict, _ = _score_to_verdict(-0.15, Decimal("0.6"), False, False, None)
        assert verdict == Verdict.REDUCE

    def test_previous_buy_prevents_reduce_on_small_drop(self) -> None:
        """Previous BUY + sentiment -0.15 → HOLD (within dampening band)."""
        verdict, _ = _score_to_verdict(
            -0.15, Decimal("0.6"), False, False, None,
            previous_verdict="BUY",
        )
        assert verdict == Verdict.HOLD

    def test_previous_strong_buy_prevents_reduce(self) -> None:
        """Previous STRONG_BUY + sentiment -0.20 → HOLD (within dampening band)."""
        verdict, _ = _score_to_verdict(
            -0.20, Decimal("0.6"), False, False, None,
            previous_verdict="STRONG_BUY",
        )
        assert verdict == Verdict.HOLD

    def test_previous_buy_allows_reduce_on_large_drop(self) -> None:
        """Previous BUY + sentiment -0.30 → REDUCE (exceeds dampening band)."""
        verdict, _ = _score_to_verdict(
            -0.30, Decimal("0.6"), False, False, None,
            previous_verdict="BUY",
        )
        assert verdict == Verdict.REDUCE

    def test_previous_accumulate_prevents_reduce(self) -> None:
        """Previous ACCUMULATE + sentiment -0.12 → HOLD."""
        verdict, _ = _score_to_verdict(
            -0.12, Decimal("0.6"), False, False, None,
            previous_verdict="ACCUMULATE",
        )
        assert verdict == Verdict.HOLD

    def test_previous_hold_no_dampening(self) -> None:
        """HOLD is neutral, no dampening applied."""
        verdict, _ = _score_to_verdict(
            -0.15, Decimal("0.6"), False, False, None,
            previous_verdict="HOLD",
        )
        assert verdict == Verdict.REDUCE

    def test_previous_reduce_no_dampening_on_sell_side(self) -> None:
        """Previous REDUCE → no dampening when already on sell side."""
        verdict, _ = _score_to_verdict(
            -0.35, Decimal("0.6"), False, False, None,
            previous_verdict="REDUCE",
        )
        # Sentiment -0.35 with confidence 0.6 → SELL (past -0.30, conf >= 0.50)
        assert verdict == Verdict.SELL

    def test_munger_override_bypasses_dampener(self) -> None:
        """Hard overrides still work even with previous positive verdict."""
        verdict, _ = _score_to_verdict(
            -0.15, Decimal("0.6"), False, True, None,
            previous_verdict="STRONG_BUY",
        )
        assert verdict == Verdict.AVOID

    def test_auditor_override_bypasses_dampener(self) -> None:
        """Auditor override still works even with previous positive verdict."""
        verdict, _ = _score_to_verdict(
            -0.15, Decimal("0.6"), True, False, None,
            previous_verdict="BUY",
        )
        assert verdict == Verdict.AVOID

    def test_positive_verdict_still_possible(self) -> None:
        """Even with previous AVOID, positive sentiment → BUY (no dampening needed)."""
        verdict, _ = _score_to_verdict(
            0.40, Decimal("0.6"), False, False, None,
            previous_verdict="AVOID",
        )
        assert verdict == Verdict.BUY

    def test_previous_verdict_as_string(self) -> None:
        """Previous verdict works as string (not just Verdict enum)."""
        verdict, _ = _score_to_verdict(
            -0.15, Decimal("0.6"), False, False, None,
            previous_verdict="STRONG_BUY",
        )
        assert verdict == Verdict.HOLD
