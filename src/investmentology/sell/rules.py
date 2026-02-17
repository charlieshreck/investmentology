from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class SellUrgency(StrEnum):
    FLAG = "FLAG"        # Flag for review, don't auto-sell
    SIGNAL = "SIGNAL"    # Sell signal, needs confirmation
    EXECUTE = "EXECUTE"  # Auto-execute (hard stops)


class SellReason(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    THESIS_BREAK = "THESIS_BREAK"
    OVERVALUED = "OVERVALUED"
    TIME_STOP = "TIME_STOP"
    GREENBLATT_ROTATION = "GREENBLATT_ROTATION"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"
    MANUAL = "MANUAL"


@dataclass
class SellSignal:
    ticker: str
    reason: SellReason
    urgency: SellUrgency
    detail: str
    current_price: Decimal | None = None
    trigger_price: Decimal | None = None


SELL_CHECKLIST = [
    "Would I buy this today at this price?",
    "Has the thesis changed, or just the price?",
    "What will I do with the proceeds?",
    "Am I acting on fear or analysis?",
    "Have I logged this decision?",
]


class SellChecklist:
    """Wrapper around the sell checklist for programmatic access."""

    items: list[str] = SELL_CHECKLIST

    @classmethod
    def as_text(cls) -> str:
        return "\n".join(f"  {i+1}. {q}" for i, q in enumerate(cls.items))
