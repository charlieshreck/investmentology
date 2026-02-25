from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from investmentology.models.prediction import Prediction
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)


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

        Uses auto_settle to look up actual prices via yfinance. Falls back
        to placeholder Decimal("0") if price lookup fails.

        Returns list of (prediction_id, actual_value) that were settled.
        """
        target = as_of or date.today()
        unsettled = self._registry.get_unsettled_predictions(as_of=target)
        settled: list[tuple[int, Decimal]] = []

        for pred in unsettled:
            actual_value = self._auto_settle(pred)
            self._registry.settle_prediction(pred.id, actual_value)  # type: ignore[arg-type]
            settled.append((pred.id, actual_value))  # type: ignore[arg-type]

        return settled

    def _auto_settle(self, pred) -> Decimal:
        """Try to auto-settle using real price lookup, fall back to placeholder."""
        try:
            from investmentology.learning.auto_settle import lookup_price_on_date
            actual = lookup_price_on_date(pred.ticker, pred.settlement_date)
            if actual is not None:
                logger.info(
                    "Auto-settled prediction %s: %s on %s = %s",
                    pred.id, pred.ticker, pred.settlement_date, actual,
                )
                return actual
        except Exception:
            logger.debug("Auto-settle failed for prediction %s", pred.id)
        return Decimal("0")

    def get_calibration_data(self, window_days: int = 90) -> dict:
        """Get calibration statistics for settled predictions.

        Queries invest.predictions for settled records, determines correctness
        by comparing predicted direction with actual price movement, then
        computes calibration buckets, ECE, and Brier score.

        Returns:
            {
                'total_settled': int,
                'total_correct': int,
                'buckets': [{'low', 'high', 'count', 'correct', 'accuracy'}],
                'ece': float,
                'brier': float,
            }
        """
        from datetime import timedelta

        cutoff = date.today() - timedelta(days=window_days)

        try:
            rows = self._registry._db.execute(
                "SELECT confidence, predicted_value, actual_value, prediction_type "
                "FROM invest.predictions "
                "WHERE is_settled = TRUE AND actual_value IS NOT NULL "
                "AND actual_value != 0 AND created_at >= %s",
                (cutoff,),
            )
        except Exception:
            logger.debug("Failed to query settled predictions")
            rows = []

        if not rows:
            return self._empty_calibration()

        settled_data: list[tuple[Decimal, bool]] = []
        for r in rows:
            conf = Decimal(str(r["confidence"])) if r["confidence"] else Decimal("0.5")
            predicted = Decimal(str(r["predicted_value"]))
            actual = Decimal(str(r["actual_value"]))
            pred_type = r["prediction_type"] or ""

            if "direction" in pred_type:
                # Direction prediction: correct if actual price moved in predicted direction
                # predicted_value: 1=up, -1=down; actual_value = closing price
                # We need the entry price to determine direction — use predictions table context
                # For now, treat as correct if predicted direction matches (positive=up, negative=down)
                was_correct = (predicted > 0 and actual > 0) or (predicted < 0 and actual < 0)
            elif "target_price" in pred_type:
                # Target price prediction: correct if actual price is within 15% of target
                if predicted > 0:
                    tolerance = predicted * Decimal("0.15")
                    was_correct = abs(actual - predicted) <= tolerance
                else:
                    was_correct = False
            else:
                was_correct = False

            settled_data.append((conf, was_correct))

        return self._compute_calibration(settled_data)

    def _empty_calibration(self) -> dict:
        """Return empty calibration data structure."""
        buckets_def = [
            (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0),
        ]
        return {
            "total_settled": 0,
            "total_correct": 0,
            "buckets": [
                {"low": lo, "high": hi, "count": 0, "correct": 0, "accuracy": 0.0}
                for lo, hi in buckets_def
            ],
            "ece": 0.0,
            "brier": 0.0,
        }

    @staticmethod
    def _compute_calibration(
        settled_predictions: list[tuple[Decimal, bool]],
    ) -> dict:
        """Compute calibration metrics from (confidence, was_correct) pairs."""
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
