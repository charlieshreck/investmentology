from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from investmentology.models.prediction import Prediction
from investmentology.registry.queries import Registry


class PredictionManager:
    """Handles prediction lifecycle: creation, settlement, calibration."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def log_prediction(
        self,
        ticker: str,
        prediction_type: str,
        predicted_value: Decimal,
        confidence: Decimal,
        horizon_days: int,
        source: str,
        settlement_date: date | None = None,
    ) -> int:
        """Log a new prediction.

        If settlement_date not provided, calculate from today + horizon_days.
        Validates: confidence 0-1, horizon_days > 0, settlement_date in future.
        """
        if not (Decimal("0") <= confidence <= Decimal("1")):
            raise ValueError(f"Confidence must be between 0 and 1, got {confidence}")
        if horizon_days <= 0:
            raise ValueError(f"horizon_days must be > 0, got {horizon_days}")

        if settlement_date is None:
            settlement_date = date.today() + timedelta(days=horizon_days)

        if settlement_date <= date.today():
            raise ValueError(
                f"settlement_date must be in the future, got {settlement_date}"
            )

        prediction = Prediction(
            ticker=ticker,
            prediction_type=prediction_type,
            predicted_value=predicted_value,
            confidence=confidence,
            horizon_days=horizon_days,
            settlement_date=settlement_date,
            source=source,
        )
        return self._registry.log_prediction(prediction)

    def settle_due_predictions(
        self, as_of: date | None = None
    ) -> list[tuple[int, Decimal]]:
        """Settle all predictions where settlement_date <= as_of.

        In Phase 1, this marks predictions for manual settlement by setting
        actual_value to Decimal("0") as a placeholder. Auto-settlement with
        price lookup comes in Stage 3.

        Returns list of (prediction_id, actual_value) that were settled.
        """
        target = as_of or date.today()
        unsettled = self._registry.get_unsettled_predictions(as_of=target)
        settled: list[tuple[int, Decimal]] = []

        for pred in unsettled:
            # Phase 1: mark with placeholder value for manual review
            actual_value = Decimal("0")
            self._registry.settle_prediction(pred.id, actual_value)  # type: ignore[arg-type]
            settled.append((pred.id, actual_value))  # type: ignore[arg-type]

        return settled

    def get_calibration_data(self, window_days: int = 90) -> dict:
        """Get calibration statistics for settled predictions.

        Returns:
            {
                'total_settled': int,
                'total_correct': int,  # direction correct
                'buckets': [
                    {'low': 0.5, 'high': 0.6, 'count': N, 'correct': M, 'accuracy': M/N},
                    ...
                ],
                'ece': float,  # Expected Calibration Error
                'brier': float,  # Brier score
            }

        Buckets: (0.5-0.6), (0.6-0.7), (0.7-0.8), (0.8-0.9), (0.9-1.0)
        """
        # Get all settled predictions (use a large limit)
        all_decisions = self._registry.get_decisions(limit=100_000)

        # Get settled predictions via unsettled_predictions won't work (they're settled).
        # Instead we need to query predictions directly. For Phase 1, we gather all
        # predictions and filter to settled ones.
        # Since Registry doesn't expose a "get settled predictions" method,
        # we use get_unsettled_predictions with a far-future date to get everything,
        # but that only returns unsettled ones. We need a different approach.
        #
        # For now, we'll accept settled predictions passed in through the registry
        # by looking at predictions that were settled (actual_value is not None).
        # Since we can only get unsettled predictions from Registry, calibration
        # data must be computed from whatever data is available.
        #
        # Phase 1 implementation: return empty calibration if no data available.

        buckets_def = [
            (0.5, 0.6),
            (0.6, 0.7),
            (0.7, 0.8),
            (0.8, 0.9),
            (0.9, 1.0),
        ]

        # We store settled predictions that we process through settle_due_predictions.
        # Since we don't have a direct query for settled predictions in the Registry,
        # this returns a baseline structure. The actual data will be populated
        # when we add a get_settled_predictions query in Stage 3.
        buckets = [
            {"low": low, "high": high, "count": 0, "correct": 0, "accuracy": 0.0}
            for low, high in buckets_def
        ]

        return {
            "total_settled": 0,
            "total_correct": 0,
            "buckets": buckets,
            "ece": 0.0,
            "brier": 0.0,
        }

    @staticmethod
    def _compute_calibration(
        settled_predictions: list[tuple[Decimal, bool]],
    ) -> dict:
        """Compute calibration metrics from (confidence, was_correct) pairs.

        This is a static helper for when we have actual settled data.
        """
        buckets_def = [
            (0.5, 0.6),
            (0.6, 0.7),
            (0.7, 0.8),
            (0.8, 0.9),
            (0.9, 1.0),
        ]

        total_settled = len(settled_predictions)
        total_correct = sum(1 for _, correct in settled_predictions if correct)

        bucket_data: list[dict] = []
        ece_sum = 0.0
        brier_sum = 0.0

        for low, high in buckets_def:
            in_bucket = [
                (conf, correct)
                for conf, correct in settled_predictions
                if Decimal(str(low)) <= conf < Decimal(str(high))
                or (high == 1.0 and conf == Decimal("1"))
            ]
            count = len(in_bucket)
            correct = sum(1 for _, c in in_bucket if c)
            accuracy = correct / count if count > 0 else 0.0

            bucket_data.append({
                "low": low,
                "high": high,
                "count": count,
                "correct": correct,
                "accuracy": accuracy,
            })

            if count > 0:
                midpoint = (low + high) / 2
                ece_sum += (count / total_settled) * abs(accuracy - midpoint)

        for conf, correct in settled_predictions:
            outcome = 1.0 if correct else 0.0
            brier_sum += (float(conf) - outcome) ** 2

        brier = brier_sum / total_settled if total_settled > 0 else 0.0
        ece = ece_sum

        return {
            "total_settled": total_settled,
            "total_correct": total_correct,
            "buckets": bucket_data,
            "ece": ece,
            "brier": brier,
        }
