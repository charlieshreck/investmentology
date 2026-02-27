"""Thesis health assessment and verdict gating.

Phase 2 of the Thesis Lifecycle Memory System:
- Assess thesis health based on verdict momentum and fundamentals
- Gate verdict changes based on position type (prevent flip-flops)
- Emergency bypass for STRONG_SELL signals with high confidence
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)


class ThesisHealth(StrEnum):
    """Current health status of an investment thesis."""
    INTACT = "INTACT"          # Thesis fundamentally sound
    UNDER_REVIEW = "UNDER_REVIEW"  # Mixed signals, monitoring
    CHALLENGED = "CHALLENGED"  # Significant counter-evidence
    BROKEN = "BROKEN"          # Thesis invalidated


class ThesisState(StrEnum):
    """State machine for thesis lifecycle."""
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    DRIFTING = "DRIFTING"
    BROKEN = "BROKEN"
    ARCHIVED = "ARCHIVED"


@dataclass
class ThesisAssessment:
    """Result of thesis health assessment."""
    health: ThesisHealth
    conviction_trend: float  # Rolling avg confidence (0-1)
    bearish_ratio: float  # Ratio of bearish verdicts in recent history
    consecutive_bearish: int  # Count of consecutive bearish verdicts
    reasoning: str
    fair_value_trend: str = "stable"  # rising, stable, declining


# Verdict gating thresholds per position type
# bearish_ratio_threshold: what ratio of recent verdicts must be bearish to allow downgrade
GATING_CONFIG = {
    "permanent": {
        "min_bearish_ratio": 0.6,    # 3+ of 5 must be bearish
        "min_consecutive": 3,
        "cooling_off_days": 30,
        "emergency_confidence": Decimal("0.85"),
    },
    "core": {
        "min_bearish_ratio": 0.4,    # 2+ of 5 must be bearish
        "min_consecutive": 2,
        "cooling_off_days": 7,
        "emergency_confidence": Decimal("0.85"),
    },
    "tactical": {
        "min_bearish_ratio": 0.0,    # No gating — flip immediately
        "min_consecutive": 0,
        "cooling_off_days": 2,
        "emergency_confidence": Decimal("0.0"),  # Always pass
    },
}


def assess_thesis_health(
    ticker: str,
    registry: Registry,
    position_type: str = "tactical",
) -> ThesisAssessment:
    """Assess the current health of a position's thesis.

    Uses verdict history, confidence trend, and fair value trajectory
    to determine thesis health.
    """
    verdicts = registry.get_verdict_history(ticker, limit=10)

    if not verdicts:
        return ThesisAssessment(
            health=ThesisHealth.INTACT,
            conviction_trend=0.5,
            bearish_ratio=0.0,
            consecutive_bearish=0,
            reasoning="No verdict history — thesis assumed intact.",
        )

    # Compute metrics from verdict history
    bearish_verdicts = {"SELL", "AVOID", "DISCARD", "REDUCE"}
    recent = verdicts[:5]  # Last 5 verdicts

    bearish_count = sum(1 for v in recent if v.get("verdict") in bearish_verdicts)
    bearish_ratio = bearish_count / len(recent) if recent else 0

    # Count consecutive bearish from most recent
    consecutive_bearish = 0
    for v in verdicts:
        if v.get("verdict") in bearish_verdicts:
            consecutive_bearish += 1
        else:
            break

    # Conviction trend — average confidence of last 5
    confidences = [
        float(v.get("confidence", 0.5))
        for v in recent
        if v.get("confidence") is not None
    ]
    conviction_trend = sum(confidences) / len(confidences) if confidences else 0.5

    # Fair value trajectory (from most recent verdicts' reasoning — heuristic)
    fv_trend = "stable"

    # Determine health
    if bearish_ratio >= 0.8 and consecutive_bearish >= 3:
        health = ThesisHealth.BROKEN
        reasoning = (
            f"Thesis appears broken: {bearish_count}/{len(recent)} recent verdicts bearish, "
            f"{consecutive_bearish} consecutive bearish. Conviction at {conviction_trend:.0%}."
        )
    elif bearish_ratio >= 0.4 or consecutive_bearish >= 2:
        health = ThesisHealth.CHALLENGED
        reasoning = (
            f"Thesis under challenge: {bearish_count}/{len(recent)} recent verdicts bearish, "
            f"{consecutive_bearish} consecutive bearish."
        )
    elif bearish_ratio >= 0.2 or conviction_trend < 0.5:
        health = ThesisHealth.UNDER_REVIEW
        reasoning = (
            f"Mixed signals: conviction trend {conviction_trend:.0%}, "
            f"{bearish_count}/{len(recent)} bearish."
        )
    else:
        health = ThesisHealth.INTACT
        reasoning = (
            f"Thesis intact: conviction {conviction_trend:.0%}, "
            f"{len(recent) - bearish_count}/{len(recent)} bullish/neutral."
        )

    return ThesisAssessment(
        health=health,
        conviction_trend=conviction_trend,
        bearish_ratio=bearish_ratio,
        consecutive_bearish=consecutive_bearish,
        reasoning=reasoning,
        fair_value_trend=fv_trend,
    )


@dataclass
class GatingResult:
    """Result of verdict gating decision."""
    allowed: bool  # True if verdict change is permitted
    original_verdict: str  # What the agents wanted
    gated_verdict: str | None  # What we clamped to (None if allowed)
    reason: str


def apply_verdict_gating(
    ticker: str,
    new_verdict: str,
    new_confidence: Decimal,
    position_type: str,
    registry: Registry,
) -> GatingResult:
    """Apply thesis-aware gating to a verdict.

    Core/permanent holdings require sustained bearish consensus before
    allowing downgrade. Tactical positions pass through immediately.
    Emergency bypass: SELL with confidence >= 0.85 always passes.

    Returns GatingResult with allowed=True if verdict should be used as-is,
    or allowed=False with gated_verdict showing what to use instead.
    """
    config = GATING_CONFIG.get(position_type, GATING_CONFIG["tactical"])

    bearish_verdicts = {"SELL", "AVOID", "DISCARD", "REDUCE"}

    # Only gate bearish verdicts on held positions
    if new_verdict not in bearish_verdicts:
        return GatingResult(
            allowed=True,
            original_verdict=new_verdict,
            gated_verdict=None,
            reason="Bullish/neutral verdict — no gating needed.",
        )

    # Tactical: no gating
    if position_type == "tactical":
        return GatingResult(
            allowed=True,
            original_verdict=new_verdict,
            gated_verdict=None,
            reason="Tactical position — immediate verdict changes allowed.",
        )

    # Emergency bypass: high-confidence SELL always passes
    if new_confidence >= config["emergency_confidence"]:
        return GatingResult(
            allowed=True,
            original_verdict=new_verdict,
            gated_verdict=None,
            reason=f"Emergency bypass: confidence {new_confidence:.0%} >= {config['emergency_confidence']:.0%} threshold.",
        )

    # Check thesis health
    assessment = assess_thesis_health(ticker, registry, position_type)

    # If thesis is BROKEN, allow the bearish verdict
    if assessment.health == ThesisHealth.BROKEN:
        return GatingResult(
            allowed=True,
            original_verdict=new_verdict,
            gated_verdict=None,
            reason=f"Thesis BROKEN — bearish verdict allowed. {assessment.reasoning}",
        )

    # Check ratio-based threshold
    if assessment.bearish_ratio >= config["min_bearish_ratio"]:
        return GatingResult(
            allowed=True,
            original_verdict=new_verdict,
            gated_verdict=None,
            reason=(
                f"Bearish ratio {assessment.bearish_ratio:.0%} >= "
                f"{config['min_bearish_ratio']:.0%} threshold for {position_type}."
            ),
        )

    # Check consecutive bearish threshold
    if assessment.consecutive_bearish >= config["min_consecutive"]:
        return GatingResult(
            allowed=True,
            original_verdict=new_verdict,
            gated_verdict=None,
            reason=(
                f"{assessment.consecutive_bearish} consecutive bearish >= "
                f"{config['min_consecutive']} threshold for {position_type}."
            ),
        )

    # GATED: Clamp to HOLD
    return GatingResult(
        allowed=False,
        original_verdict=new_verdict,
        gated_verdict="HOLD",
        reason=(
            f"Gated: {position_type} position requires bearish ratio >= "
            f"{config['min_bearish_ratio']:.0%} (got {assessment.bearish_ratio:.0%}) or "
            f"{config['min_consecutive']}+ consecutive bearish (got {assessment.consecutive_bearish}). "
            f"Thesis health: {assessment.health.value}."
        ),
    )
