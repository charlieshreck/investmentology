from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class PositionType(StrEnum):
    """Classification of how a position is managed."""

    PERMANENT = "permanent"      # Decades-long compounders (Coca-Cola, Berkshire)
    CORE = "core"                # Multi-year competitive advantage (2-5 year horizon)
    TACTICAL = "tactical"        # Catalyst-driven, 3-12 month trades
    UNCLASSIFIED = "unclassified"  # New candidates not yet classified


# Implicit transaction cost: 10bps (0.10%) per round-trip trade.
# Penalizes excessive rotation in paper performance tracking.
TRANSACTION_COST_BPS = Decimal("0.0010")


@dataclass
class PortfolioPosition:
    ticker: str
    entry_date: date
    entry_price: Decimal
    current_price: Decimal
    shares: Decimal
    position_type: str  # PositionType value — kept as str for DB compat
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
    def pnl_pct_net(self) -> Decimal:
        """P&L after implicit transaction costs (10bps round-trip)."""
        raw = self.pnl_pct
        # Deduct round-trip cost: entry + exit = 2 legs
        return raw - TRANSACTION_COST_BPS

    @property
    def market_value(self) -> Decimal:
        return self.shares * self.current_price
