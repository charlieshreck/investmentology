from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class DecisionType(StrEnum):
    SCREEN = "SCREEN"
    COMPETENCE_PASS = "COMPETENCE_PASS"
    COMPETENCE_FAIL = "COMPETENCE_FAIL"
    AGENT_ANALYSIS = "AGENT_ANALYSIS"
    PATTERN_MATCH = "PATTERN_MATCH"
    ADVERSARIAL_REVIEW = "ADVERSARIAL_REVIEW"
    BUY = "BUY"
    SELL = "SELL"
    TRIM = "TRIM"
    HOLD = "HOLD"
    REJECT = "REJECT"
    WATCHLIST = "WATCHLIST"


class DecisionOutcome(StrEnum):
    PENDING = "PENDING"
    CORRECT = "CORRECT"
    WRONG = "WRONG"
    PARTIAL = "PARTIAL"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


@dataclass
class Decision:
    ticker: str
    decision_type: DecisionType
    layer_source: str
    confidence: Decimal | None
    reasoning: str
    signals: dict | None = None
    metadata: dict | None = None
    id: int | None = None
    created_at: datetime | None = None
