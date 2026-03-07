"""Stage 7: Calibration Engine — feedback loop for prediction accuracy.

Computes calibration metrics (ECE, Brier score) from settled predictions,
generates weekly calibration reports, and adjusts confidence thresholds
based on historical accuracy.

Also includes:
- CalibrationTracker: Records every verdict with price snapshot for settlement.
- AgentCalibrator: Per-agent isotonic calibration (when sufficient data exists).
"""

from __future__ import annotations

import json
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


MIN_BUCKET_COUNT = 10  # Minimum samples per bucket for statistical significance


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
        if ece > 0.12:
            recs.append(
                f"High calibration error (ECE={ece:.3f}). "
                "Consider retraining confidence thresholds."
            )

        # Brier score threshold
        if brier > 0.25:
            recs.append(
                f"High Brier score ({brier:.3f}). "
                "Predictions are poorly calibrated overall."
            )

        # Check for overconfident buckets
        for bucket in buckets:
            if bucket.count >= MIN_BUCKET_COUNT and bucket.accuracy < bucket.midpoint - 0.15:
                recs.append(
                    f"Overconfident in {bucket.low:.0%}-{bucket.high:.0%} range: "
                    f"claimed {bucket.midpoint:.0%}, actual {bucket.accuracy:.0%}. "
                    f"Reduce confidence for predictions in this range."
                )

        # Check for underconfident buckets
        for bucket in buckets:
            if bucket.count >= MIN_BUCKET_COUNT and bucket.accuracy > bucket.midpoint + 0.15:
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
            if bucket.count < MIN_BUCKET_COUNT:
                continue
            gap = bucket.accuracy - bucket.midpoint
            # Only suggest adjustment if gap is significant
            if abs(gap) > 0.10:
                key = f"{bucket.low:.1f}-{bucket.high:.1f}"
                # Adjustment should move predicted confidence toward actual accuracy
                adjustments[key] = round(gap, 3)
        return adjustments


# ---------------------------------------------------------------------------
# Verdict correctness evaluation
# ---------------------------------------------------------------------------

# Verdicts that predict positive price movement
_POSITIVE_VERDICTS = {"STRONG_BUY", "BUY", "ACCUMULATE"}
# Verdicts that predict negative price movement
_NEGATIVE_VERDICTS = {"SELL", "AVOID", "REDUCE"}
# Neutral verdicts — correctness is ambiguous, but we evaluate as "no large move"
_NEUTRAL_VERDICTS = {"HOLD", "WATCHLIST"}


def _evaluate_verdict_correctness(
    verdict: str, actual_return: float,
) -> bool:
    """Determine if a verdict was correct given actual price return."""
    if verdict in _POSITIVE_VERDICTS:
        return actual_return > 0.0
    if verdict in _NEGATIVE_VERDICTS:
        return actual_return < 0.0
    # Neutral: correct if price didn't move more than 10% in either direction
    return abs(actual_return) < 0.10


# ---------------------------------------------------------------------------
# CalibrationTracker — records verdicts for later settlement
# ---------------------------------------------------------------------------

class CalibrationTracker:
    """Records every verdict with a price snapshot for multi-horizon settlement.

    Called after every verdict synthesis. Stores the prediction for settlement
    at 30, 90, 180, and 365-day horizons.
    """

    # Settlement horizons in days
    HORIZONS = [30, 90, 180, 365]

    def __init__(self, registry: Registry) -> None:
        self._db = registry._db

    def record_verdict(
        self,
        ticker: str,
        verdict: str,
        sentiment: float | None,
        confidence: float | None,
        price_at_verdict: float,
        agent_contributions: list[dict] | None = None,
        position_type: str | None = None,
        regime_label: str | None = None,
    ) -> int | None:
        """Record a verdict prediction for later settlement.

        Returns the prediction ID, or None if recording failed.
        """
        try:
            rows = self._db.execute(
                """INSERT INTO invest.calibration_predictions
                   (ticker, verdict_date, verdict, sentiment, confidence,
                    price_at_verdict, agent_contributions, position_type,
                    regime_label)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    ticker, date.today(), verdict,
                    sentiment, confidence, price_at_verdict,
                    json.dumps(agent_contributions, default=str) if agent_contributions else None,
                    position_type, regime_label,
                ),
            )
            pred_id = rows[0]["id"] if rows else None
            logger.debug(
                "Recorded calibration prediction %s for %s: %s @ $%.2f",
                pred_id, ticker, verdict, price_at_verdict,
            )
            return pred_id
        except Exception:
            logger.debug("Could not record calibration prediction for %s", ticker)
            return None

    def record_agent_data(
        self,
        agent_name: str,
        ticker: str,
        raw_confidence: float,
        sentiment: float,
        price_at_verdict: float,
    ) -> None:
        """Record per-agent data for isotonic calibration training."""
        try:
            self._db.execute(
                """INSERT INTO invest.agent_calibration_data
                   (agent_name, ticker, verdict_date, raw_confidence,
                    sentiment, price_at_verdict)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (agent_name, ticker, date.today(), raw_confidence,
                 sentiment, price_at_verdict),
            )
        except Exception:
            logger.debug(
                "Could not record agent calibration data for %s/%s",
                agent_name, ticker,
            )

    def settle_predictions(self, lookback_days: int = 90) -> dict:
        """Settle predictions that have reached their horizon date.

        Run daily (e.g., from overnight pipeline). For each unsettled prediction,
        checks if enough time has passed and looks up the actual price.

        Returns summary dict with counts of settled predictions per horizon.
        """
        from investmentology.learning.auto_settle import lookup_price_on_date

        results = {h: 0 for h in self.HORIZONS}
        today = date.today()

        for horizon in self.HORIZONS:
            col_settled = f"settled_{horizon}d"
            col_price = f"price_{horizon}d"
            col_return = f"return_{horizon}d"
            col_correct = f"correct_{horizon}d"

            # Find unsettled predictions where the horizon date has passed
            try:
                rows = self._db.execute(
                    f"""SELECT id, ticker, verdict_date, verdict, price_at_verdict
                        FROM invest.calibration_predictions
                        WHERE {col_settled} = FALSE
                          AND verdict_date + INTERVAL '{horizon} days' <= %s
                        LIMIT 50""",
                    (today,),
                )
            except Exception:
                logger.debug("Could not query unsettled predictions for %dd", horizon)
                continue

            if not rows:
                continue

            for row in rows:
                ticker = row["ticker"]
                verdict_date = row["verdict_date"]
                if isinstance(verdict_date, str):
                    verdict_date = date.fromisoformat(verdict_date[:10])
                settlement_date = verdict_date + timedelta(days=horizon)
                price_at_verdict = float(row["price_at_verdict"])

                actual_price = lookup_price_on_date(ticker, settlement_date)
                if actual_price is None:
                    continue

                actual_return = (
                    (float(actual_price) - price_at_verdict) / price_at_verdict
                    if price_at_verdict > 0 else 0.0
                )
                was_correct = _evaluate_verdict_correctness(
                    row["verdict"], actual_return,
                )

                try:
                    self._db.execute(
                        f"""UPDATE invest.calibration_predictions
                            SET {col_settled} = TRUE,
                                {col_price} = %s,
                                {col_return} = %s,
                                {col_correct} = %s
                            WHERE id = %s""",
                        (float(actual_price), round(actual_return, 6),
                         was_correct, row["id"]),
                    )
                    results[horizon] += 1
                except Exception:
                    logger.debug(
                        "Failed to settle prediction %s for %s at %dd",
                        row["id"], ticker, horizon,
                    )

        # Also settle per-agent data (90-day horizon only)
        self._settle_agent_data(today)

        if any(v > 0 for v in results.values()):
            logger.info("Settled calibration predictions: %s", results)
        return results

    def _settle_agent_data(self, today: date) -> int:
        """Settle per-agent calibration data at 90-day horizon."""
        from investmentology.learning.auto_settle import lookup_price_on_date

        count = 0
        try:
            rows = self._db.execute(
                """SELECT id, ticker, verdict_date, price_at_verdict, sentiment
                   FROM invest.agent_calibration_data
                   WHERE settled = FALSE
                     AND verdict_date + INTERVAL '90 days' <= %s
                   LIMIT 100""",
                (today,),
            )
        except Exception:
            return 0

        if not rows:
            return 0

        for row in rows:
            ticker = row["ticker"]
            verdict_date = row["verdict_date"]
            if isinstance(verdict_date, str):
                verdict_date = date.fromisoformat(verdict_date[:10])
            settlement_date = verdict_date + timedelta(days=90)
            price_at_verdict = float(row["price_at_verdict"])

            actual_price = lookup_price_on_date(ticker, settlement_date)
            if actual_price is None:
                continue

            actual_return = (
                (float(actual_price) - price_at_verdict) / price_at_verdict
                if price_at_verdict > 0 else 0.0
            )
            # For per-agent: bullish sentiment -> correct if price up
            sentiment = float(row.get("sentiment") or 0)
            if sentiment > 0.1:
                was_correct = actual_return > 0.0
            elif sentiment < -0.1:
                was_correct = actual_return < 0.0
            else:
                was_correct = abs(actual_return) < 0.10

            try:
                self._db.execute(
                    """UPDATE invest.agent_calibration_data
                       SET settled = TRUE, actual_return_90d = %s,
                           was_correct = %s, settled_at = %s
                       WHERE id = %s""",
                    (round(actual_return, 6), was_correct, today, row["id"]),
                )
                count += 1
            except Exception:
                pass

        return count

    def get_calibration_summary(self) -> dict:
        """Get calibration summary for API/dashboard.

        Returns per-verdict and per-agent accuracy at multiple horizons.
        """
        summary: dict = {
            "by_verdict": {},
            "by_agent": {},
            "total_predictions": 0,
            "total_settled_90d": 0,
        }

        try:
            # Per-verdict accuracy at 90 days
            rows = self._db.execute(
                """SELECT verdict,
                          COUNT(*) AS total,
                          SUM(CASE WHEN correct_90d THEN 1 ELSE 0 END) AS correct,
                          AVG(return_90d) AS avg_return
                   FROM invest.calibration_predictions
                   WHERE settled_90d = TRUE
                   GROUP BY verdict
                   ORDER BY total DESC""",
            )
            for row in (rows or []):
                total = int(row["total"])
                correct = int(row["correct"])
                summary["by_verdict"][row["verdict"]] = {
                    "total": total,
                    "correct": correct,
                    "accuracy": round(correct / total, 3) if total > 0 else 0,
                    "avg_return": round(float(row["avg_return"]), 4) if row["avg_return"] else 0,
                }
                summary["total_settled_90d"] += total

            # Total predictions
            count_rows = self._db.execute(
                "SELECT COUNT(*) AS cnt FROM invest.calibration_predictions",
            )
            if count_rows:
                summary["total_predictions"] = int(count_rows[0]["cnt"])

            # Per-agent accuracy
            agent_rows = self._db.execute(
                """SELECT agent_name,
                          COUNT(*) AS total,
                          SUM(CASE WHEN was_correct THEN 1 ELSE 0 END) AS correct,
                          AVG(raw_confidence) AS avg_confidence
                   FROM invest.agent_calibration_data
                   WHERE settled = TRUE
                   GROUP BY agent_name
                   ORDER BY total DESC""",
            )
            for row in (agent_rows or []):
                total = int(row["total"])
                correct = int(row["correct"])
                summary["by_agent"][row["agent_name"]] = {
                    "total": total,
                    "correct": correct,
                    "accuracy": round(correct / total, 3) if total > 0 else 0,
                    "avg_confidence": round(float(row["avg_confidence"]), 3) if row["avg_confidence"] else 0,
                }

        except Exception:
            logger.debug("Could not generate calibration summary")

        return summary


# ---------------------------------------------------------------------------
# AgentCalibrator — per-agent isotonic calibration
# ---------------------------------------------------------------------------

# Minimum settled predictions per agent before isotonic calibration activates
_MIN_ISOTONIC_SAMPLES = 100


class AgentCalibrator:
    """Per-agent isotonic calibration using settled prediction data.

    Replaces the 1.3x sell-side bias correction with data-driven calibration
    once sufficient data exists (100+ settled predictions per agent).

    Uses isotonic regression to map raw confidence → calibrated confidence.
    """

    def __init__(self, registry: Registry) -> None:
        self._db = registry._db
        self._models: dict[str, object] = {}  # agent_name -> IsotonicRegression
        self._fitted_agents: set[str] = set()

    def fit_all(self) -> dict[str, int]:
        """Fit isotonic regression for all agents with sufficient data.

        Returns dict of {agent_name: sample_count} for successfully fitted agents.
        Run weekly from overnight pipeline.
        """
        fitted: dict[str, int] = {}

        try:
            # Get agents with enough settled data
            rows = self._db.execute(
                """SELECT agent_name, COUNT(*) AS cnt
                   FROM invest.agent_calibration_data
                   WHERE settled = TRUE
                   GROUP BY agent_name
                   HAVING COUNT(*) >= %s""",
                (_MIN_ISOTONIC_SAMPLES,),
            )
        except Exception:
            logger.debug("Could not query agent calibration data for fitting")
            return fitted

        if not rows:
            return fitted

        for row in rows:
            agent_name = row["agent_name"]
            count = int(row["cnt"])
            model = self._fit_agent(agent_name)
            if model is not None:
                self._models[agent_name] = model
                self._fitted_agents.add(agent_name)
                fitted[agent_name] = count
                logger.info(
                    "Isotonic calibration fitted for %s (%d samples)",
                    agent_name, count,
                )

        return fitted

    def _fit_agent(self, agent_name: str) -> object | None:
        """Fit isotonic regression for a single agent."""
        try:
            from sklearn.isotonic import IsotonicRegression
        except ImportError:
            logger.debug("sklearn not available, isotonic calibration disabled")
            return None

        try:
            rows = self._db.execute(
                """SELECT raw_confidence, was_correct
                   FROM invest.agent_calibration_data
                   WHERE agent_name = %s AND settled = TRUE
                   ORDER BY verdict_date""",
                (agent_name,),
            )
            if not rows or len(rows) < _MIN_ISOTONIC_SAMPLES:
                return None

            confidences = [float(r["raw_confidence"]) for r in rows]
            outcomes = [1.0 if r["was_correct"] else 0.0 for r in rows]

            ir = IsotonicRegression(out_of_bounds="clip")
            ir.fit(confidences, outcomes)
            return ir

        except Exception:
            logger.debug("Isotonic fit failed for %s", agent_name, exc_info=True)
            return None

    def calibrate(self, agent_name: str, raw_confidence: Decimal) -> Decimal:
        """Calibrate a raw confidence value using the fitted model.

        Falls back to the raw confidence if no model is available.
        """
        model = self._models.get(agent_name)
        if model is None:
            return raw_confidence

        try:
            calibrated = model.predict([float(raw_confidence)])[0]
            return Decimal(str(round(calibrated, 3)))
        except Exception:
            return raw_confidence

    def is_calibrated(self, agent_name: str) -> bool:
        """Check if an agent has a fitted calibration model."""
        return agent_name in self._fitted_agents

    def get_calibration_curves(self) -> dict[str, list[dict]]:
        """Get calibration curve data for all fitted agents (for PWA dashboard).

        Returns {agent_name: [{raw, calibrated}, ...]} for plotting.
        """
        curves: dict[str, list[dict]] = {}
        test_points = [i / 20.0 for i in range(1, 20)]  # 0.05, 0.10, ..., 0.95

        for agent_name, model in self._models.items():
            try:
                calibrated = model.predict(test_points)
                curves[agent_name] = [
                    {"raw": round(raw, 2), "calibrated": round(float(cal), 3)}
                    for raw, cal in zip(test_points, calibrated)
                ]
            except Exception:
                pass

        return curves
