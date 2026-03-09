"""Tests for macro regime pre-classifier."""

from investmentology.data.macro_regime import MacroRegimeResult, classify_macro_regime


def _expansion_context() -> dict:
    return {
        "yield_curve_spread": 1.2,
        "high_yield_spread": 2.8,
        "vix": 14.0,
        "unemployment_rate": 3.7,
        "fed_funds_rate": 2.0,
        "real_yield_10y": 0.5,
    }


def _contraction_context() -> dict:
    return {
        "yield_curve_spread": -0.8,
        "high_yield_spread": 6.5,
        "vix": 35.0,
        "unemployment_rate": 7.0,
        "fed_funds_rate": 0.5,
        "real_yield_10y": -1.0,
    }


def _late_cycle_context() -> dict:
    return {
        "yield_curve_spread": 0.3,
        "high_yield_spread": 4.5,
        "vix": 22.0,
        "unemployment_rate": 3.5,
        "fed_funds_rate": 5.25,
        "real_yield_10y": 2.5,
    }


def _recovery_context() -> dict:
    return {
        "yield_curve_spread": 2.5,
        "high_yield_spread": 3.5,
        "vix": 18.0,
        "unemployment_rate": 6.5,
        "fed_funds_rate": 0.25,
        "real_yield_10y": -0.5,
    }


def test_expansion_regime():
    result = classify_macro_regime(_expansion_context())
    assert result.regime == "expansion"
    assert result.confidence > 0.3
    assert "yield_curve" in result.signals


def test_contraction_regime():
    result = classify_macro_regime(_contraction_context())
    assert result.regime == "contraction"
    assert result.confidence > 0.3


def test_late_cycle_regime():
    result = classify_macro_regime(_late_cycle_context())
    assert result.regime == "late_cycle"
    assert result.confidence > 0.2


def test_recovery_regime():
    result = classify_macro_regime(_recovery_context())
    assert result.regime == "recovery"
    assert result.confidence > 0.2


def test_empty_context_returns_unknown():
    result = classify_macro_regime({})
    assert result.regime == "unknown"
    assert result.confidence == 0.0


def test_partial_data_still_classifies():
    result = classify_macro_regime({"vix": 35.0, "yield_curve_spread": -1.0})
    assert result.regime in ("contraction", "late_cycle")
    assert len(result.signals) == 2


def test_result_has_summary():
    result = classify_macro_regime(_expansion_context())
    assert result.summary
    assert "Expansion" in result.summary


def test_derived_yield_curve_used():
    ctx = {"yield_curve_spread_derived": -0.3}
    result = classify_macro_regime(ctx)
    assert "yield_curve" in result.signals
    assert "inverted" in result.signals["yield_curve"]
