from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass
class Prediction:
    ticker: str
    prediction_type: str
    predicted_value: Decimal
    confidence: Decimal
    horizon_days: int
    settlement_date: date
    source: str
    actual_value: Decimal | None = None
    is_settled: bool = False
    settled_at: datetime | None = None
    id: int | None = None
    created_at: datetime | None = None
