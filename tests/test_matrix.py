"""Tests for the compatibility matrix engine and weights."""
from __future__ import annotations

from decimal import Decimal


from investmentology.compatibility.matrix import (
    CompatibilityEngine,
)
from investmentology.compatibility.patterns import (
    CONVICTION_BUY,
    HARD_REJECT,
)
from investmentology.compatibility.weights import (
    AgentWeights,
    RegimeAdjustedWeights,
    weighted_confidence,
)
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag


def _make_agent(
    name: str, tags: list[SignalTag], confidence: str = "0.75"
) -> AgentSignalSet:
    """Helper to build an AgentSignalSet."""
    return AgentSignalSet(
        agent_name=name,
        model="test-model",
        signals=SignalSet(signals=[Signal(tag=t, strength="strong") for t in tags]),
        confidence=Decimal(confidence),
        reasoning="test",
    )


class TestMergeSignals:
    def test_combines_tags_from_multiple_agents(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent("warren", [SignalTag.UNDERVALUED, SignalTag.MOAT_WIDENING]),
            _make_agent("simons", [SignalTag.TREND_UPTREND, SignalTag.MOMENTUM_STRONG]),
            _make_agent("auditor", [SignalTag.LEVERAGE_OK]),
        ]
        merged = engine.merge_signals(agents)
        assert merged == {
            SignalTag.UNDERVALUED,
            SignalTag.MOAT_WIDENING,
            SignalTag.TREND_UPTREND,
            SignalTag.MOMENTUM_STRONG,
            SignalTag.LEVERAGE_OK,
        }

    def test_deduplicates_shared_tags(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent("warren", [SignalTag.UNDERVALUED]),
            _make_agent("soros", [SignalTag.UNDERVALUED, SignalTag.REGIME_BULL]),
        ]
        merged = engine.merge_signals(agents)
        assert SignalTag.UNDERVALUED in merged
        assert SignalTag.REGIME_BULL in merged
        assert len(merged) == 2

    def test_empty_agents(self) -> None:
        engine = CompatibilityEngine()
        merged = engine.merge_signals([])
        assert merged == set()


class TestDetectDisagreements:
    def test_finds_dangerous_pairs(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent(
                "warren",
                [SignalTag.BALANCE_SHEET_STRONG],
                confidence="0.70",
            ),
            _make_agent(
                "auditor",
                [SignalTag.LEVERAGE_HIGH],
                confidence="0.70",
            ),
        ]
        disagreements = engine.detect_disagreements(agents)
        dangerous = [d for d in disagreements if d.is_dangerous and "balance sheet" in d.description.lower()]
        assert len(dangerous) >= 1
        assert dangerous[0].agent_a == "warren"
        assert dangerous[0].agent_b == "auditor"

    def test_finds_dangerous_pair_reverse_direction(self) -> None:
        engine = CompatibilityEngine()
        # Auditor listed first, Warren second -- should still detect
        agents = [
            _make_agent("auditor", [SignalTag.LEVERAGE_HIGH], confidence="0.70"),
            _make_agent("warren", [SignalTag.BALANCE_SHEET_STRONG], confidence="0.70"),
        ]
        disagreements = engine.detect_disagreements(agents)
        dangerous = [d for d in disagreements if d.is_dangerous and "balance sheet" in d.description.lower()]
        assert len(dangerous) >= 1

    def test_identifies_suspicious_unanimity(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent("warren", [SignalTag.UNDERVALUED], confidence="0.90"),
            _make_agent("soros", [SignalTag.REGIME_BULL], confidence="0.85"),
            _make_agent("simons", [SignalTag.TREND_UPTREND], confidence="0.88"),
            _make_agent("auditor", [SignalTag.LEVERAGE_OK], confidence="0.92"),
        ]
        disagreements = engine.detect_disagreements(agents)
        unanimity = [d for d in disagreements if "unanimity" in d.description.lower()]
        assert len(unanimity) == 1
        assert unanimity[0].is_dangerous

    def test_no_suspicious_unanimity_when_below_threshold(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent("warren", [SignalTag.UNDERVALUED], confidence="0.90"),
            _make_agent("soros", [SignalTag.REGIME_BULL], confidence="0.60"),
        ]
        disagreements = engine.detect_disagreements(agents)
        unanimity = [d for d in disagreements if "unanimity" in d.description.lower()]
        assert len(unanimity) == 0

    def test_no_disagreements_when_no_conflicts(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent("warren", [SignalTag.UNDERVALUED], confidence="0.70"),
            _make_agent("simons", [SignalTag.TREND_UPTREND], confidence="0.65"),
        ]
        disagreements = engine.detect_disagreements(agents)
        assert len(disagreements) == 0


class TestEvaluate:
    def test_conviction_buy_pattern(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent(
                "warren",
                [SignalTag.UNDERVALUED, SignalTag.MOAT_WIDENING, SignalTag.EARNINGS_QUALITY_HIGH],
                confidence="0.80",
            ),
            _make_agent(
                "simons",
                [SignalTag.TREND_UPTREND, SignalTag.MOMENTUM_STRONG],
                confidence="0.75",
            ),
            _make_agent(
                "auditor",
                [SignalTag.LEVERAGE_OK],
                confidence="0.70",
            ),
        ]
        result = engine.evaluate("AAPL", agents)
        assert result.ticker == "AAPL"
        assert result.matched_pattern is CONVICTION_BUY
        assert result.pattern_score > 0.0
        assert result.requires_munger  # CONVICTION_BUY always triggers Munger

    def test_hard_reject_on_accounting_red_flag(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent("warren", [SignalTag.UNDERVALUED], confidence="0.80"),
            _make_agent("auditor", [SignalTag.ACCOUNTING_RED_FLAG], confidence="0.90"),
        ]
        result = engine.evaluate("FRAUD", agents)
        assert result.matched_pattern is HARD_REJECT
        assert result.recommended_action == "Hard no — do not revisit without material change"

    def test_requires_munger_on_dangerous_disagreement(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent("warren", [SignalTag.EARNINGS_QUALITY_HIGH], confidence="0.70"),
            _make_agent("auditor", [SignalTag.ACCOUNTING_RED_FLAG], confidence="0.70"),
        ]
        result = engine.evaluate("SKETCHY", agents)
        assert result.dangerous_disagreement_count >= 1
        assert result.requires_munger

    def test_requires_munger_on_conviction_buy(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent(
                "warren",
                [SignalTag.UNDERVALUED, SignalTag.BALANCE_SHEET_STRONG],
                confidence="0.80",
            ),
            _make_agent(
                "simons",
                [SignalTag.TREND_UPTREND, SignalTag.MOMENTUM_STRONG],
                confidence="0.78",
            ),
            _make_agent("auditor", [SignalTag.LEVERAGE_OK], confidence="0.72"),
        ]
        result = engine.evaluate("GOOD", agents)
        assert result.matched_pattern is CONVICTION_BUY
        assert result.requires_munger

    def test_no_pattern_match(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent("warren", [SignalTag.HOLD], confidence="0.50"),
        ]
        result = engine.evaluate("MEH", agents)
        assert result.matched_pattern is None
        assert result.pattern_score == 0.0
        assert "manual review" in result.recommended_action.lower()

    def test_avg_confidence_calculated(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent("warren", [SignalTag.UNDERVALUED], confidence="0.80"),
            _make_agent("simons", [SignalTag.TREND_UPTREND], confidence="0.60"),
        ]
        result = engine.evaluate("TEST", agents)
        assert result.avg_confidence == Decimal("0.70")

    def test_merged_signals_in_result(self) -> None:
        engine = CompatibilityEngine()
        agents = [
            _make_agent("warren", [SignalTag.UNDERVALUED]),
            _make_agent("simons", [SignalTag.TREND_UPTREND]),
        ]
        result = engine.evaluate("TEST", agents)
        assert SignalTag.UNDERVALUED in result.merged_signals
        assert SignalTag.TREND_UPTREND in result.merged_signals


class TestRegimeAdjustedWeights:
    def test_bear_market_increases_warren_and_auditor(self) -> None:
        base = AgentWeights()
        adjusted = RegimeAdjustedWeights.from_regime(base, Decimal("-0.5"))
        assert adjusted.regime_label == "bear"
        assert adjusted.weights.warren > Decimal("0.25")
        assert adjusted.weights.auditor > Decimal("0.25")
        # Simons should decrease
        assert adjusted.weights.simons < Decimal("0.25")

    def test_bull_market_increases_simons(self) -> None:
        base = AgentWeights()
        adjusted = RegimeAdjustedWeights.from_regime(base, Decimal("0.5"))
        assert adjusted.regime_label == "bull"
        assert adjusted.weights.simons > Decimal("0.25")

    def test_neutral_market_preserves_base(self) -> None:
        base = AgentWeights()
        adjusted = RegimeAdjustedWeights.from_regime(base, Decimal("0.0"))
        assert adjusted.regime_label == "neutral"
        assert adjusted.weights.warren == Decimal("0.25")
        assert adjusted.weights.soros == Decimal("0.25")
        assert adjusted.weights.simons == Decimal("0.25")
        assert adjusted.weights.auditor == Decimal("0.25")

    def test_weights_sum_to_one(self) -> None:
        for score in [Decimal("-0.9"), Decimal("-0.3"), Decimal("0"), Decimal("0.3"), Decimal("0.9")]:
            base = AgentWeights()
            adjusted = RegimeAdjustedWeights.from_regime(base, score)
            w = adjusted.weights
            total = w.warren + w.soros + w.simons + w.auditor
            assert total == Decimal("1"), f"Weights sum to {total} for regime_score={score}"

    def test_min_weight_enforced(self) -> None:
        # Start with very skewed weights to test floor enforcement
        base = AgentWeights(
            warren=Decimal("0.10"),
            soros=Decimal("0.10"),
            simons=Decimal("0.10"),
            auditor=Decimal("0.70"),
        )
        adjusted = RegimeAdjustedWeights.from_regime(base, Decimal("0.5"))
        w = adjusted.weights
        assert w.warren >= Decimal("0.10")
        assert w.soros >= Decimal("0.10")
        assert w.simons >= Decimal("0.10")
        assert w.auditor >= Decimal("0.10")


class TestWeightedConfidence:
    def test_calculation_correct(self) -> None:
        agents = [
            _make_agent("warren", [SignalTag.UNDERVALUED], confidence="0.80"),
            _make_agent("soros", [SignalTag.REGIME_BULL], confidence="0.60"),
            _make_agent("simons", [SignalTag.TREND_UPTREND], confidence="0.70"),
            _make_agent("auditor", [SignalTag.LEVERAGE_OK], confidence="0.90"),
        ]
        weights = AgentWeights()  # equal 0.25 each
        result = weighted_confidence(agents, weights)
        # (0.80*0.25 + 0.60*0.25 + 0.70*0.25 + 0.90*0.25) / (0.25*4) = 0.75
        expected = Decimal("0.75")
        assert result == expected

    def test_unequal_weights(self) -> None:
        agents = [
            _make_agent("warren", [SignalTag.UNDERVALUED], confidence="1.00"),
            _make_agent("soros", [SignalTag.REGIME_BULL], confidence="0.00"),
        ]
        weights = AgentWeights(
            warren=Decimal("0.75"),
            soros=Decimal("0.25"),
            simons=Decimal("0"),
            auditor=Decimal("0"),
        )
        result = weighted_confidence(agents, weights)
        # (1.00*0.75 + 0.00*0.25) / (0.75 + 0.25) = 0.75
        assert result == Decimal("0.75")

    def test_no_matching_agents(self) -> None:
        agents = [
            _make_agent("unknown_agent", [SignalTag.UNDERVALUED], confidence="0.80"),
        ]
        weights = AgentWeights()
        result = weighted_confidence(agents, weights)
        assert result == Decimal("0")

    def test_empty_agents(self) -> None:
        weights = AgentWeights()
        result = weighted_confidence([], weights)
        assert result == Decimal("0")


class TestAgentWeightsDefaults:
    def test_defaults_sum_to_one(self) -> None:
        w = AgentWeights()
        total = w.warren + w.soros + w.simons + w.auditor
        assert total == Decimal("1")

    def test_as_dict(self) -> None:
        w = AgentWeights()
        d = w.as_dict()
        assert d == {
            "warren": Decimal("0.25"),
            "soros": Decimal("0.25"),
            "simons": Decimal("0.25"),
            "auditor": Decimal("0.25"),
        }
