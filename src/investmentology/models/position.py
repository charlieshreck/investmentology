from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class PortfolioPosition:
    ticker: str
    entry_date: date
    entry_price: Decimal
    current_price: Decimal
    shares: Decimal
    position_type: str  # "permanent", "core", "tactical"
    weight: Decimal
    stop_loss: Decimal | None = None
    fair_value_estimate: Decimal | None = None
    thesis: str = ""
    id: int | None = None
    exit_date: date | None = None
    exit_price: Decimal | None = None
    is_closed: bool = False
    realized_pnl: Decimal | None = None

    @property
    def pnl_pct(self) -> Decimal:
        if self.is_closed and self.exit_price:
            return (self.exit_price - self.entry_price) / self.entry_price
        return (self.current_price - self.entry_price) / self.entry_price

    @property
    def market_value(self) -> Decimal:
        return self.shares * self.current_price
