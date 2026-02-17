"""Stage 7: Calibration Engine — feedback loop for prediction accuracy.

Computes calibration metrics (ECE, Brier score) from settled predictions,
generates weekly calibration reports, and adjusts confidence thresholds
based on historical accuracy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from investmentology.learning.predictions import PredictionManager
from investmentology.learning.registry import DecisionLogger
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)


@dataclass
class CalibrationBucket:
    """A single calibration bin (e.g. 0.7–0.8 confidence range)."""

    low: float
    high: float
    count: int = 0
    correct: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.count if self.count > 0 else 0.0

    @property
    def midpoint(self) -> float:
        return (self.low + self.high) / 2

    @property
    def gap(self) -> float:
        """Calibration gap: |accuracy - midpoint|."""
        return abs(self.accuracy - self.midpoint)


@dataclass
class CalibrationReport:
    """Weekly calibration report output."""

    period_start: date
    period_end: date
    total_settled: int
    total_correct: int
    overall_accuracy: float
    buckets: list[CalibrationBucket]
    ece: float  # Expected Calibration Error
    brier: float  # Brier score
    agent_accuracy: dict[str, float] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


class CalibrationEngine:
    """Computes calibration metrics and generates adjustment recommendations."""

    BUCKET_RANGES = [
        (0.5, 0.6),
        (0.6, 0.7),
        (0.7, 0.8),
        (0.8, 0.9),
        (0.9, 1.0),
    ]

    def __init__(self, registry: Registry) -> None:
        self._registry = registry
        self._prediction_mgr = PredictionManager(registry)
        self._decision_logger = DecisionLogger(registry)

    def compute_calibration(
        self,
        settled_data: list[tuple[Decimal, bool]],
    ) -> tuple[list[CalibrationBucket], float, float]:
        """Compute calibration buckets, ECE, and Brier score.

        Args:
            settled_data: List of (confidence, was_correct) tuples.

        Returns:
            Tuple of (buckets, ece, brier_score).
        """
        buckets = [CalibrationBucket(low=lo, high=hi) for lo, hi in self.BUCKET_RANGES]

        for conf, correct in settled_data:
            conf_float = float(conf)
            for bucket in buckets:
                if bucket.low <= conf_float < bucket.high or (
                    bucket.high == 1.0 and conf_float == 1.0
                ):
                    bucket.count += 1
                    if correct:
                        bucket.correct += 1
                    break

        # Expected Calibration Error
        total = len(settled_data)
        ece = 0.0
        if total > 0:
            for bucket in buckets:
                if bucket.count > 0:
                    ece += (bucket.count / total) * bucket.gap

        # Brier score
        brier = 0.0
        if total > 0:
            for conf, correct in settled_data:
                outcome = 1.0 if correct else 0.0
                brier += (float(conf) - outcome) ** 2
            brier /= total

        return buckets, ece, brier

    def generate_report(
        self,
        settled_data: list[tuple[Decimal, bool]],
        agent_results: dict[str, list[tuple[Decimal, bool]]] | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> CalibrationReport:
        """Generate a full calibration report.

        Args:
            settled_data: Overall (confidence, was_correct) pairs.
            agent_results: Per-agent (confidence, was_correct) pairs.
            period_start: Report start date.
            period_end: Report end date.
        """
        end = period_end or date.today()
        start = period_start or (end - timedelta(days=90))

        buckets, ece, brier = self.compute_calibration(settled_data)

        total = len(settled_data)
        correct = sum(1 for _, c in settled_data if c)
        overall_accuracy = correct / total if total > 0 else 0.0

        # Per-agent accuracy
        agent_accuracy: dict[str, float] = {}
        if agent_results:
            for agent_name, results in agent_results.items():
                agent_total = len(results)
                agent_correct = sum(1 for _, c in results if c)
                agent_accuracy[agent_name] = (
                    agent_correct / agent_total if agent_total > 0 else 0.0
                )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            buckets, ece, brier, agent_accuracy,
        )

        return CalibrationReport(
            period_start=start,
            period_end=end,
            total_settled=total,
            total_correct=correct,
            overall_accuracy=overall_accuracy,
            buckets=buckets,
            ece=ece,
            brier=brier,
            agent_accuracy=agent_accuracy,
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        buckets: list[CalibrationBucket],
        ece: float,
        brier: float,
        agent_accuracy: dict[str, float],
    ) -> list[str]:
        """Generate actionable recommendations from calibration data."""
        recs: list[str] = []

        # ECE threshold
        if ece > 0.15:
            recs.append(
                f"High calibration error (ECE={ece:.3f}). "
                "Consider retraining confidence thresholds."
            )

        # Brier score threshold
        if brier > 0.30:
            recs.append(
                f"High Brier score ({brier:.3f}). "
                "Predictions are poorly calibrated overall."
            )

        # Check for overconfident buckets
        for bucket in buckets:
            if bucket.count >= 5 and bucket.accuracy < bucket.midpoint - 0.15:
                recs.append(
                    f"Overconfident in {bucket.low:.0%}-{bucket.high:.0%} range: "
                    f"claimed {bucket.midpoint:.0%}, actual {bucket.accuracy:.0%}. "
                    f"Reduce confidence for predictions in this range."
                )

        # Check for underconfident buckets
        for bucket in buckets:
            if bucket.count >= 5 and bucket.accuracy > bucket.midpoint + 0.15:
                recs.append(
                    f"Underconfident in {bucket.low:.0%}-{bucket.high:.0%} range: "
                    f"claimed {bucket.midpoint:.0%}, actual {bucket.accuracy:.0%}. "
                    f"Consider increasing confidence."
                )

        # Agent-specific recommendations
        for agent_name, accuracy in agent_accuracy.items():
            if accuracy < 0.45:
                recs.append(
                    f"Agent '{agent_name}' has low accuracy ({accuracy:.0%}). "
                    "Consider reducing its weight in the compatibility matrix."
                )

        if not recs:
            recs.append("Calibration looks healthy. No adjustments needed.")

        return recs

    def get_confidence_adjustment(
        self, buckets: list[CalibrationBucket],
    ) -> dict[str, float]:
        """Suggest confidence adjustments per bucket.

        Returns a dict like {"0.7-0.8": -0.05} meaning reduce confidence
        by 5% for predictions in the 0.7-0.8 range.
        """
        adjustments: dict[str, float] = {}
        for bucket in buckets:
            if bucket.count < 5:
                continue
            gap = bucket.accuracy - bucket.midpoint
            # Only suggest adjustment if gap is significant
            if abs(gap) > 0.10:
                key = f"{bucket.low:.1f}-{bucket.high:.1f}"
                # Adjustment should move predicted confidence toward actual accuracy
                adjustments[key] = round(gap, 3)
        return adjustments
