"""Tests for the cash regime rule (macro → allocation guidance)."""

from investmentology.advisory.portfolio_fit import (
    AllocationStance,
    get_cash_regime_guidance,
)


class TestCashRegimeGuidance:
    def test_expansion_standard_allocation(self):
        regime = {"regime": "expansion", "confidence": 0.65, "summary": "Expansion (high confidence)"}
        result = get_cash_regime_guidance(regime)
        assert result.stance == AllocationStance.STANDARD
        assert result.equity_min_pct == 70
        assert result.equity_max_pct == 85
        assert result.cash_min_pct == 15

    def test_late_cycle_cautious(self):
        regime = {"regime": "late_cycle", "confidence": 0.55, "summary": "Late Cycle"}
        result = get_cash_regime_guidance(regime)
        assert result.stance == AllocationStance.CAUTIOUS
        assert result.equity_max_pct == 70
        assert result.cash_min_pct == 30
        assert "ALL SIGNALS ALIGNED" in result.entry_criteria

    def test_contraction_defensive(self):
        regime = {"regime": "contraction", "confidence": 0.70, "summary": "Contraction"}
        result = get_cash_regime_guidance(regime)
        assert result.stance == AllocationStance.DEFENSIVE
        assert result.equity_max_pct == 50
        assert result.cash_min_pct == 50
        assert "counter-cyclical" in result.entry_criteria

    def test_recovery_aggressive(self):
        regime = {"regime": "recovery", "confidence": 0.60, "summary": "Recovery"}
        result = get_cash_regime_guidance(regime)
        assert result.stance == AllocationStance.AGGRESSIVE
        assert result.equity_min_pct == 80
        assert result.cash_max_pct == 20

    def test_unknown_regime_defaults_to_standard(self):
        regime = {"regime": "unknown", "confidence": 0.0, "summary": "Unknown"}
        result = get_cash_regime_guidance(regime)
        assert result.stance == AllocationStance.STANDARD

    def test_none_macro_defaults_to_standard(self):
        result = get_cash_regime_guidance(None)
        assert result.stance == AllocationStance.STANDARD
        assert result.regime == "unknown"

    def test_low_confidence_softens_to_standard(self):
        """When confidence is low (<35%), soften to standard regardless of regime."""
        regime = {"regime": "contraction", "confidence": 0.20, "summary": "Contraction (low conf)"}
        result = get_cash_regime_guidance(regime)
        assert result.stance == AllocationStance.STANDARD
        assert "low confidence" in result.summary

    def test_high_confidence_uses_regime(self):
        regime = {"regime": "contraction", "confidence": 0.70, "summary": "Contraction"}
        result = get_cash_regime_guidance(regime)
        assert result.stance == AllocationStance.DEFENSIVE

    def test_summary_contains_regime_info(self):
        regime = {"regime": "expansion", "confidence": 0.65, "summary": "Expansion details here"}
        result = get_cash_regime_guidance(regime)
        assert "expansion" in result.summary
        assert "65%" in result.summary
        assert "Expansion details here" in result.summary
