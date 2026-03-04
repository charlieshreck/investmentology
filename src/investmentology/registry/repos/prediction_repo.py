from __future__ import annotations

from datetime import date
from decimal import Decimal

from investmentology.models.prediction import Prediction
from investmentology.registry.db import Database


class PredictionRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def log_prediction(self, prediction: Prediction) -> int:
        rows = self._db.execute(
            "INSERT INTO invest.predictions "
            "(ticker, prediction_type, predicted_value, confidence, horizon_days, "
            "settlement_date, source) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                prediction.ticker, prediction.prediction_type,
                prediction.predicted_value, prediction.confidence,
                prediction.horizon_days, prediction.settlement_date,
                prediction.source,
            ),
        )
        return rows[0]["id"]

    def settle_prediction(self, prediction_id: int, actual_value: Decimal) -> None:
        self._db.execute(
            "UPDATE invest.predictions "
            "SET actual_value = %s, is_settled = TRUE, settled_at = NOW() "
            "WHERE id = %s",
            (actual_value, prediction_id),
        )

    def get_unsettled_predictions(self, as_of: date | None = None) -> list[Prediction]:
        target = as_of or date.today()
        rows = self._db.execute(
            "SELECT * FROM invest.predictions "
            "WHERE is_settled = FALSE AND settlement_date <= %s "
            "ORDER BY settlement_date",
            (target,),
        )
        return [self._row_to_prediction(r) for r in rows]

    @staticmethod
    def _row_to_prediction(r: dict) -> Prediction:
        return Prediction(
            id=r["id"],
            ticker=r["ticker"],
            prediction_type=r["prediction_type"],
            predicted_value=Decimal(str(r["predicted_value"])),
            confidence=Decimal(str(r["confidence"])) if r["confidence"] is not None else Decimal(0),
            horizon_days=r["horizon_days"],
            settlement_date=r["settlement_date"],
            source=r["source"] or "",
            actual_value=Decimal(str(r["actual_value"])) if r["actual_value"] is not None else None,
            is_settled=r["is_settled"],
            settled_at=r["settled_at"],
            created_at=r["created_at"],
            price_at_prediction=(
                Decimal(str(r["price_at_prediction"]))
                if r.get("price_at_prediction") is not None
                else None
            ),
        )
