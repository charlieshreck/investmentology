from __future__ import annotations

from decimal import Decimal

from investmentology.models.stock import Stock
from investmentology.registry.db import Database


class StockRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def upsert_stocks(self, stocks: list[Stock]) -> int:
        query = """
            INSERT INTO invest.stocks (ticker, name, sector, industry, market_cap, exchange, is_active, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (ticker) DO UPDATE SET
                name = EXCLUDED.name, sector = EXCLUDED.sector,
                industry = EXCLUDED.industry, market_cap = EXCLUDED.market_cap,
                exchange = EXCLUDED.exchange, is_active = EXCLUDED.is_active,
                updated_at = NOW()
        """
        params = [
            (s.ticker, s.name, s.sector, s.industry, s.market_cap, s.exchange, s.is_active)
            for s in stocks
        ]
        return self._db.execute_many(query, params)

    def get_active_stocks(self) -> list[Stock]:
        rows = self._db.execute(
            "SELECT ticker, name, sector, industry, market_cap, exchange, is_active "
            "FROM invest.stocks WHERE is_active = TRUE ORDER BY ticker"
        )
        return [
            Stock(
                ticker=r["ticker"], name=r["name"],
                sector=r["sector"] or "", industry=r["industry"] or "",
                market_cap=Decimal(str(r["market_cap"])) if r["market_cap"] else Decimal(0),
                exchange=r["exchange"] or "", is_active=r["is_active"],
            )
            for r in rows
        ]
