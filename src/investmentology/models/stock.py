from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class Stock:
    ticker: str
    name: str
    sector: str
    industry: str
    market_cap: Decimal
    exchange: str
    is_active: bool = True


@dataclass
class FundamentalsSnapshot:
    ticker: str
    fetched_at: datetime
    operating_income: Decimal
    market_cap: Decimal
    total_debt: Decimal
    cash: Decimal
    current_assets: Decimal
    current_liabilities: Decimal
    net_ppe: Decimal
    revenue: Decimal
    net_income: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    shares_outstanding: int
    price: Decimal

    @property
    def enterprise_value(self) -> Decimal:
        return self.market_cap + self.total_debt - self.cash

    @property
    def earnings_yield(self) -> Decimal | None:
        ev = self.enterprise_value
        if ev <= 0:
            return None
        return self.operating_income / ev

    @property
    def net_working_capital(self) -> Decimal:
        return self.current_assets - self.current_liabilities

    @property
    def invested_capital(self) -> Decimal:
        return self.net_working_capital + self.net_ppe

    @property
    def roic(self) -> Decimal | None:
        ic = self.invested_capital
        if ic <= 0:
            return None
        return self.operating_income / ic
