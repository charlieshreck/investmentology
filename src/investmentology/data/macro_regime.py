"""Macro regime pre-classifier using FRED data.

Classifies the current macro environment into one of four regimes:
  - expansion: growth accelerating, low credit stress, normal/steep yield curve
  - late_cycle: growth positive but decelerating, rising credit spreads, yield curve flattening
  - contraction: growth contracting, elevated credit stress, inverted yield curve
  - recovery: growth inflecting upward from trough, credit normalizing

Runs once per pipeline cycle. All agents receive the result as factual context
(not opinion) to avoid 9 redundant macro interpretations.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)


@dataclass
class MacroRegimeResult:
    """Output of macro regime classification."""

    regime: str  # expansion | late_cycle | contraction | recovery
    confidence: float  # 0.0–1.0
    signals: dict[str, str]  # indicator → reading (for agent context)
    summary: str  # One-line description


def classify_macro_regime(macro_context: dict) -> MacroRegimeResult:
    """Classify the macro regime from FRED indicators.

    Uses four primary signals:
    1. Yield curve (T10Y2Y or derived) — inversion = recession leading indicator
    2. High-yield credit spread — stress = late-cycle/contraction
    3. VIX — elevated = uncertainty/contraction
    4. Unemployment trend — rising = contraction, falling = expansion/recovery

    Args:
        macro_context: Dict from FredProvider.get_macro_context()

    Returns:
        MacroRegimeResult with regime classification
    """
    signals: dict[str, str] = {}
    scores: dict[str, int] = {
        "expansion": 0,
        "late_cycle": 0,
        "contraction": 0,
        "recovery": 0,
    }

    # 1. Yield curve
    yc_spread = macro_context.get(
        "yield_curve_spread",
        macro_context.get("yield_curve_spread_derived"),
    )
    if yc_spread is not None:
        yc = float(yc_spread)
        if yc < -0.5:
            signals["yield_curve"] = f"deeply inverted ({yc:+.2f}%)"
            scores["contraction"] += 3
        elif yc < 0:
            signals["yield_curve"] = f"inverted ({yc:+.2f}%)"
            scores["contraction"] += 2
            scores["late_cycle"] += 1
        elif yc < 0.5:
            signals["yield_curve"] = f"flat ({yc:+.2f}%)"
            scores["late_cycle"] += 2
        elif yc < 1.5:
            signals["yield_curve"] = f"normal ({yc:+.2f}%)"
            scores["expansion"] += 2
        else:
            signals["yield_curve"] = f"steep ({yc:+.2f}%)"
            scores["recovery"] += 2
            scores["expansion"] += 1

    # 2. High-yield credit spread
    hys = macro_context.get("high_yield_spread")
    if hys is not None:
        hys_val = float(hys)
        if hys_val > 6.0:
            signals["credit_spread"] = f"crisis ({hys_val:.0f} bps)"
            scores["contraction"] += 3
        elif hys_val > 5.0:
            signals["credit_spread"] = f"high stress ({hys_val:.0f} bps)"
            scores["contraction"] += 2
        elif hys_val > 4.0:
            signals["credit_spread"] = f"elevated ({hys_val:.0f} bps)"
            scores["late_cycle"] += 2
        elif hys_val > 3.0:
            signals["credit_spread"] = f"normal ({hys_val:.0f} bps)"
            scores["expansion"] += 1
        else:
            signals["credit_spread"] = f"tight ({hys_val:.0f} bps)"
            scores["expansion"] += 2

    # 3. VIX
    vix = macro_context.get("vix")
    if vix is not None:
        vix_val = float(vix)
        if vix_val > 30:
            signals["vix"] = f"fear ({vix_val:.1f})"
            scores["contraction"] += 2
        elif vix_val > 20:
            signals["vix"] = f"elevated ({vix_val:.1f})"
            scores["late_cycle"] += 1
            scores["contraction"] += 1
        elif vix_val > 15:
            signals["vix"] = f"normal ({vix_val:.1f})"
            scores["expansion"] += 1
        else:
            signals["vix"] = f"complacent ({vix_val:.1f})"
            scores["expansion"] += 1
            scores["late_cycle"] += 1  # extreme complacency is late-cycle

    # 4. Unemployment rate
    unemp = macro_context.get("unemployment_rate")
    if unemp is not None:
        u_val = float(unemp)
        if u_val > 6.0:
            signals["unemployment"] = f"high ({u_val:.1f}%)"
            scores["contraction"] += 2
            scores["recovery"] += 1  # could be trough
        elif u_val > 5.0:
            signals["unemployment"] = f"elevated ({u_val:.1f}%)"
            scores["late_cycle"] += 1
            scores["contraction"] += 1
        elif u_val > 4.0:
            signals["unemployment"] = f"moderate ({u_val:.1f}%)"
            scores["expansion"] += 1
        else:
            signals["unemployment"] = f"low ({u_val:.1f}%)"
            scores["expansion"] += 2
            scores["late_cycle"] += 1  # historically low unemp is late-cycle

    # 5. Fed funds rate (directional context)
    ff = macro_context.get("fed_funds_rate")
    if ff is not None:
        ff_val = float(ff)
        if ff_val > 5.0:
            signals["fed_funds"] = f"restrictive ({ff_val:.2f}%)"
            scores["late_cycle"] += 1
            scores["contraction"] += 1
        elif ff_val > 3.0:
            signals["fed_funds"] = f"neutral-tight ({ff_val:.2f}%)"
            scores["late_cycle"] += 1
        elif ff_val > 1.0:
            signals["fed_funds"] = f"accommodative ({ff_val:.2f}%)"
            scores["expansion"] += 1
        else:
            signals["fed_funds"] = f"emergency low ({ff_val:.2f}%)"
            scores["recovery"] += 2

    # 6. Real yield (inflation-adjusted)
    real_yield = macro_context.get("real_yield_10y")
    if real_yield is not None:
        ry = float(real_yield)
        if ry > 2.0:
            signals["real_yield"] = f"restrictive ({ry:+.2f}%)"
            scores["late_cycle"] += 1
        elif ry > 0:
            signals["real_yield"] = f"positive ({ry:+.2f}%)"
            scores["expansion"] += 1
        else:
            signals["real_yield"] = f"negative ({ry:+.2f}%)"
            scores["recovery"] += 1

    # Classify by highest score
    if not signals:
        return MacroRegimeResult(
            regime="unknown",
            confidence=0.0,
            signals={},
            summary="Insufficient FRED data for regime classification",
        )

    total_points = sum(scores.values())
    best_regime = max(scores, key=scores.get)
    best_score = scores[best_regime]

    # Confidence = proportion of points going to the winner
    confidence = best_score / total_points if total_points > 0 else 0.0

    # Second-best score for margin check
    sorted_scores = sorted(scores.values(), reverse=True)
    margin = (sorted_scores[0] - sorted_scores[1]) / total_points if total_points > 0 else 0.0

    # Low margin → reduce confidence (ambiguous regime)
    if margin < 0.1:
        confidence *= 0.7

    summary = _build_summary(best_regime, confidence, signals)

    return MacroRegimeResult(
        regime=best_regime,
        confidence=round(confidence, 2),
        signals=signals,
        summary=summary,
    )


def macro_regime_to_dict(result: MacroRegimeResult) -> dict:
    """Serialize MacroRegimeResult for pipeline cache storage."""
    return asdict(result)


def _build_summary(regime: str, confidence: float, signals: dict[str, str]) -> str:
    """Build a one-line summary for the briefing."""
    label = {
        "expansion": "Expansion",
        "late_cycle": "Late Cycle",
        "contraction": "Contraction",
        "recovery": "Recovery",
        "unknown": "Unknown",
    }.get(regime, regime.title())

    conf_label = "high" if confidence > 0.6 else "moderate" if confidence > 0.35 else "low"
    indicator_summary = ", ".join(f"{k}: {v}" for k, v in list(signals.items())[:4])

    return f"{label} ({conf_label} confidence). Key: {indicator_summary}"
