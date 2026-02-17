from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from investmentology.learning.calibration import (
    CalibrationBucket,
    CalibrationEngine,
    CalibrationReport,
)
from investmentology.registry.queries import Registry


# ---------------------------------------------------------------------------
# CalibrationBucket
# ---------------------------------------------------------------------------


class TestCalibrationBucket:
    def test_accuracy_zero_count(self) -> None:
        b = CalibrationBucket(low=0.7, high=0.8, count=0, correct=0)
        assert b.accuracy == 0.0

    def test_accuracy_calculated(self) -> None:
        b = CalibrationBucket(low=0.7, high=0.8, count=10, correct=7)
        assert b.accuracy == pytest.approx(0.7)

    def test_midpoint(self) -> None:
        b = CalibrationBucket(low=0.7, high=0.8)
        assert b.midpoint == pytest.approx(0.75)

    def test_gap_perfectly_calibrated(self) -> None:
        b = CalibrationBucket(low=0.7, high=0.8, count=100, correct=75)
        assert b.gap == pytest.approx(0.0)

    def test_gap_overconfident(self) -> None:
        b = CalibrationBucket(low=0.8, high=0.9, count=10, correct=6)
        # accuracy=0.6, midpoint=0.85, gap=0.25
        assert b.gap == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# CalibrationEngine.compute_calibration
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> CalibrationEngine:
    mock_registry = MagicMock(spec=Registry)
    return CalibrationEngine(mock_registry)


class TestComputeCalibration:
    def test_empty_data(self, engine: CalibrationEngine) -> None:
        buckets, ece, brier = engine.compute_calibration([])
        assert len(buckets) == 5
        assert ece == 0.0
        assert brier == 0.0
        assert all(b.count == 0 for b in buckets)

    def test_perfectly_calibrated(self, engine: CalibrationEngine) -> None:
        # All predictions at 0.7 confidence, 70% correct
        data = [(Decimal("0.7"), True)] * 7 + [(Decimal("0.7"), False)] * 3
        buckets, ece, brier = engine.compute_calibration(data)

        # All should land in 0.7-0.8 bucket
        bucket_07 = [b for b in buckets if b.low == 0.7][0]
        assert bucket_07.count == 10
        assert bucket_07.correct == 7
        assert bucket_07.accuracy == pytest.approx(0.7)

    def test_brier_score_perfect(self, engine: CalibrationEngine) -> None:
        # Perfect predictions: 1.0 confidence, all correct
        data = [(Decimal("0.95"), True)] * 10
        _, _, brier = engine.compute_calibration(data)
        # Brier = mean((0.95 - 1.0)^2) = 0.0025
        assert brier == pytest.approx(0.0025)

    def test_brier_score_terrible(self, engine: CalibrationEngine) -> None:
        # Terrible: 0.9 confidence, all wrong
        data = [(Decimal("0.9"), False)] * 10
        _, _, brier = engine.compute_calibration(data)
        # Brier = mean((0.9 - 0.0)^2) = 0.81
        assert brier == pytest.approx(0.81)

    def test_ece_overconfident(self, engine: CalibrationEngine) -> None:
        # 0.8-0.9 bucket: confidence ~0.85 but only 50% correct
        data = [(Decimal("0.85"), True)] * 5 + [(Decimal("0.85"), False)] * 5
        _, ece, _ = engine.compute_calibration(data)
        # ECE = |0.5 - 0.85| = 0.35 (all in one bucket, weight=1.0)
        assert ece == pytest.approx(0.35)

    def test_multiple_buckets(self, engine: CalibrationEngine) -> None:
        data = [
            (Decimal("0.55"), True),
            (Decimal("0.55"), False),
            (Decimal("0.75"), True),
            (Decimal("0.75"), True),
            (Decimal("0.95"), True),
        ]
        buckets, ece, brier = engine.compute_calibration(data)

        bucket_50 = [b for b in buckets if b.low == 0.5][0]
        assert bucket_50.count == 2
        assert bucket_50.correct == 1

        bucket_70 = [b for b in buckets if b.low == 0.7][0]
        assert bucket_70.count == 2
        assert bucket_70.correct == 2

        bucket_90 = [b for b in buckets if b.low == 0.9][0]
        assert bucket_90.count == 1
        assert bucket_90.correct == 1


# ---------------------------------------------------------------------------
# CalibrationEngine.generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_empty_report(self, engine: CalibrationEngine) -> None:
        report = engine.generate_report([])
        assert isinstance(report, CalibrationReport)
        assert report.total_settled == 0
        assert report.total_correct == 0
        assert report.overall_accuracy == 0.0
        assert report.ece == 0.0
        assert report.brier == 0.0

    def test_report_with_data(self, engine: CalibrationEngine) -> None:
        data = [(Decimal("0.8"), True)] * 8 + [(Decimal("0.8"), False)] * 2
        report = engine.generate_report(data)
        assert report.total_settled == 10
        assert report.total_correct == 8
        assert report.overall_accuracy == pytest.approx(0.8)

    def test_report_with_agent_accuracy(self, engine: CalibrationEngine) -> None:
        data = [(Decimal("0.7"), True)] * 7 + [(Decimal("0.7"), False)] * 3
        agent_results = {
            "warren": [(Decimal("0.8"), True)] * 8 + [(Decimal("0.8"), False)] * 2,
            "soros": [(Decimal("0.6"), True)] * 4 + [(Decimal("0.6"), False)] * 6,
        }
        report = engine.generate_report(data, agent_results=agent_results)
        assert report.agent_accuracy["warren"] == pytest.approx(0.8)
        assert report.agent_accuracy["soros"] == pytest.approx(0.4)

    def test_report_period(self, engine: CalibrationEngine) -> None:
        start = date(2026, 1, 1)
        end = date(2026, 2, 10)
        report = engine.generate_report(
            [], period_start=start, period_end=end,
        )
        assert report.period_start == start
        assert report.period_end == end


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


class TestRecommendations:
    def test_healthy_calibration(self, engine: CalibrationEngine) -> None:
        # Good calibration: low ECE, low Brier
        data = [(Decimal("0.7"), True)] * 7 + [(Decimal("0.7"), False)] * 3
        report = engine.generate_report(data)
        assert any("healthy" in r.lower() for r in report.recommendations)

    def test_high_ece_recommendation(self, engine: CalibrationEngine) -> None:
        # Very overconfident
        data = [(Decimal("0.9"), True)] * 3 + [(Decimal("0.9"), False)] * 7
        report = engine.generate_report(data)
        assert any("calibration error" in r.lower() for r in report.recommendations)

    def test_agent_low_accuracy_recommendation(self, engine: CalibrationEngine) -> None:
        data = [(Decimal("0.7"), True)] * 5 + [(Decimal("0.7"), False)] * 5
        agent_results = {
            "soros": [(Decimal("0.7"), True)] * 2 + [(Decimal("0.7"), False)] * 8,
        }
        report = engine.generate_report(data, agent_results=agent_results)
        assert any("soros" in r.lower() for r in report.recommendations)

    def test_overconfident_bucket_recommendation(self, engine: CalibrationEngine) -> None:
        # 0.8-0.9 bucket: 10 predictions, only 5 correct
        data = [(Decimal("0.85"), True)] * 5 + [(Decimal("0.85"), False)] * 5
        report = engine.generate_report(data)
        assert any("overconfident" in r.lower() for r in report.recommendations)


# ---------------------------------------------------------------------------
# Confidence adjustments
# ---------------------------------------------------------------------------


class TestConfidenceAdjustment:
    def test_no_adjustment_small_sample(self, engine: CalibrationEngine) -> None:
        buckets = [CalibrationBucket(low=0.7, high=0.8, count=3, correct=1)]
        adjustments = engine.get_confidence_adjustment(buckets)
        assert adjustments == {}

    def test_overconfident_adjustment(self, engine: CalibrationEngine) -> None:
        buckets = [CalibrationBucket(low=0.8, high=0.9, count=10, correct=5)]
        # accuracy=0.5, midpoint=0.85, gap=-0.35
        adjustments = engine.get_confidence_adjustment(buckets)
        assert "0.8-0.9" in adjustments
        assert adjustments["0.8-0.9"] < 0  # negative = reduce confidence

    def test_underconfident_adjustment(self, engine: CalibrationEngine) -> None:
        buckets = [CalibrationBucket(low=0.5, high=0.6, count=10, correct=9)]
        # accuracy=0.9, midpoint=0.55, gap=+0.35
        adjustments = engine.get_confidence_adjustment(buckets)
        assert "0.5-0.6" in adjustments
        assert adjustments["0.5-0.6"] > 0  # positive = increase confidence

    def test_well_calibrated_no_adjustment(self, engine: CalibrationEngine) -> None:
        buckets = [CalibrationBucket(low=0.7, high=0.8, count=20, correct=15)]
        # accuracy=0.75, midpoint=0.75, gap=0.0
        adjustments = engine.get_confidence_adjustment(buckets)
        assert adjustments == {}
