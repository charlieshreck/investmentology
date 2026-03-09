"""Tests for the prediction card (stock outcome view)."""

from investmentology.advisory.prediction_card import (
    AgentTarget,
    ConvictionTier,
    PredictionCardInputs,
    build_prediction_card,
)


def _targets(*prices_weights: tuple[str, float, float]) -> list[AgentTarget]:
    return [AgentTarget(agent=name, target_price=p, weight=w) for name, p, w in prices_weights]


class TestBuildPredictionCard:
    def test_basic_card(self):
        inputs = PredictionCardInputs(
            ticker="AAPL",
            current_price=198.0,
            verdict="BUY",
            confidence=0.72,
            agent_targets=_targets(
                ("warren", 245.0, 0.17),
                ("klarman", 220.0, 0.12),
                ("druckenmiller", 260.0, 0.11),
            ),
            bear_case_price=165.0,
        )
        card = build_prediction_card(inputs)
        assert card.ticker == "AAPL"
        assert card.verdict == "BUY"
        assert card.composite_target is not None
        assert card.composite_target > 0
        assert card.target_range_low == 220.0
        assert card.target_range_high == 260.0
        assert card.bear_case == 165.0
        assert card.upside_pct > 0
        assert card.downside_pct > 0
        assert card.risk_reward_ratio > 0

    def test_weighted_average_target(self):
        inputs = PredictionCardInputs(
            ticker="MSFT",
            current_price=400.0,
            verdict="BUY",
            confidence=0.65,
            agent_targets=_targets(
                ("a", 500.0, 0.50),
                ("b", 400.0, 0.50),
            ),
        )
        card = build_prediction_card(inputs)
        assert card.composite_target == 450.0

    def test_equal_weight_when_zero_weights(self):
        inputs = PredictionCardInputs(
            ticker="TSLA",
            current_price=200.0,
            verdict="HOLD",
            confidence=0.50,
            agent_targets=_targets(
                ("a", 300.0, 0.0),
                ("b", 200.0, 0.0),
            ),
        )
        card = build_prediction_card(inputs)
        assert card.composite_target == 250.0

    def test_no_targets_gives_none(self):
        inputs = PredictionCardInputs(
            ticker="XYZ",
            current_price=100.0,
            verdict="HOLD",
            confidence=0.40,
        )
        card = build_prediction_card(inputs)
        assert card.composite_target is None
        assert card.target_range_low is None
        assert card.upside_pct is None
        assert card.risk_reward_ratio is None

    def test_bear_case_fallback_to_min_target(self):
        inputs = PredictionCardInputs(
            ticker="GOOG",
            current_price=170.0,
            verdict="BUY",
            confidence=0.60,
            agent_targets=_targets(
                ("a", 200.0, 0.50),
                ("b", 180.0, 0.50),
            ),
        )
        card = build_prediction_card(inputs)
        # No explicit bear_case → falls back to lowest agent target
        assert card.bear_case == 180.0

    def test_upside_downside_calculation(self):
        inputs = PredictionCardInputs(
            ticker="TEST",
            current_price=100.0,
            verdict="BUY",
            confidence=0.70,
            agent_targets=_targets(("a", 130.0, 1.0)),
            bear_case_price=80.0,
        )
        card = build_prediction_card(inputs)
        assert card.upside_pct == 30.0
        assert card.downside_pct == 20.0
        assert card.risk_reward_ratio == 1.5

    def test_negative_upside_for_sell(self):
        inputs = PredictionCardInputs(
            ticker="TEST",
            current_price=150.0,
            verdict="SELL",
            confidence=0.80,
            agent_targets=_targets(("a", 100.0, 1.0)),
            bear_case_price=80.0,
        )
        card = build_prediction_card(inputs)
        assert card.upside_pct < 0  # Target below current price


class TestConvictionTier:
    def test_all_signals_aligned(self):
        """All metrics at maximum → ALL_SIGNALS_ALIGNED."""
        inputs = PredictionCardInputs(
            ticker="AAPL",
            current_price=200.0,
            verdict="STRONG_BUY",
            confidence=0.85,
            agent_consensus_pct=90.0,
            quant_gate_rank=5,
            piotroski_score=9,
            altman_zone="safe",
            momentum_percentile=0.95,
        )
        card = build_prediction_card(inputs)
        # 6 checks: 2+2+2+2+2+1 = 11/12 = 0.917 >= 0.85
        assert card.conviction_tier == ConvictionTier.ALL_SIGNALS_ALIGNED

    def test_high_conviction(self):
        inputs = PredictionCardInputs(
            ticker="MSFT",
            current_price=400.0,
            verdict="BUY",
            confidence=0.75,
            agent_consensus_pct=75.0,
            piotroski_score=7,
        )
        card = build_prediction_card(inputs)
        assert card.conviction_tier == ConvictionTier.HIGH_CONVICTION

    def test_mixed_signals(self):
        inputs = PredictionCardInputs(
            ticker="TEST",
            current_price=100.0,
            verdict="HOLD",
            confidence=0.30,
            agent_consensus_pct=20.0,
            piotroski_score=3,
            quant_gate_rank=90,
        )
        card = build_prediction_card(inputs)
        assert card.conviction_tier in (
            ConvictionTier.MIXED_SIGNALS,
            ConvictionTier.LOW_CONVICTION,
        )

    def test_weak_metrics_gives_mixed_or_low(self):
        """Low confidence + low consensus → MIXED_SIGNALS or LOW_CONVICTION."""
        inputs = PredictionCardInputs(
            ticker="TEST",
            current_price=100.0,
            verdict="HOLD",
            confidence=0.40,
            agent_consensus_pct=40.0,
        )
        card = build_prediction_card(inputs)
        assert card.conviction_tier in (
            ConvictionTier.MIXED_SIGNALS,
            ConvictionTier.LOW_CONVICTION,
        )


class TestPredictionCardSerialization:
    def test_to_dict(self):
        inputs = PredictionCardInputs(
            ticker="AAPL",
            current_price=198.0,
            verdict="BUY",
            confidence=0.72,
            agent_targets=_targets(("warren", 245.0, 0.17)),
            bear_case_price=165.0,
            spy_price=512.0,
            earnings_warning="Earnings in 47d (safe to enter)",
        )
        card = build_prediction_card(inputs)
        d = card.to_dict()
        assert d["ticker"] == "AAPL"
        assert d["verdict"] == "BUY"
        assert d["compositeTarget"] == 245.0
        assert d["bearCase"] == 165.0
        assert d["settlementBenchmarkSpy"] == 512.0
        assert d["earningsWarning"] is not None
        assert len(d["agentTargets"]) == 1
        assert d["agentTargets"][0]["agent"] == "warren"

    def test_to_dict_with_none_values(self):
        inputs = PredictionCardInputs(
            ticker="XYZ",
            current_price=100.0,
            verdict="HOLD",
            confidence=0.40,
        )
        card = build_prediction_card(inputs)
        d = card.to_dict()
        assert d["compositeTarget"] is None
        assert d["bearCase"] is None
        assert d["riskRewardRatio"] is None
        assert d["agentTargets"] == []
