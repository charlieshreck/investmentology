from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class MarketSnapshot:
    snapshot_date: date
    spy_price: Decimal
    qqq_price: Decimal
    iwm_price: Decimal
    vix: Decimal
    ten_year_yield: Decimal
    two_year_yield: Decimal
    hy_oas: Decimal | None
    put_call_ratio: Decimal | None
    sector_data: dict | None = None
    pendulum_score: int | None = None
    regime_score: Decimal | None = None
    id: int | None = None


@dataclass
class RegimeBlend:
    score: Decimal  # -1 (bear) to +1 (bull)
    label: str  # "bull", "bear", "neutral", "transition"
    indicators: dict | None = None
