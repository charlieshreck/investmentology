from __future__ import annotations

from decimal import Decimal

from investmentology.models.stock import FundamentalsSnapshot
from investmentology.registry.db import Database


class FundamentalsRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def insert_fundamentals(self, snapshots: list[FundamentalsSnapshot]) -> int:
        query = """
            INSERT INTO invest.fundamentals_cache (
                ticker, fetched_at, operating_income, market_cap, total_debt, cash,
                current_assets, current_liabilities, net_ppe, revenue, net_income,
                total_assets, total_liabilities, shares_outstanding, price
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            (
                s.ticker, s.fetched_at, s.operating_income, s.market_cap, s.total_debt,
                s.cash, s.current_assets, s.current_liabilities, s.net_ppe, s.revenue,
                s.net_income, s.total_assets, s.total_liabilities, s.shares_outstanding,
                s.price,
            )
            for s in snapshots
        ]
        return self._db.execute_many(query, params)

    def get_latest_fundamentals(self, ticker: str) -> FundamentalsSnapshot | None:
        rows = self._db.execute(
            "SELECT * FROM invest.fundamentals_cache "
            "WHERE ticker = %s ORDER BY fetched_at DESC LIMIT 1",
            (ticker,),
        )
        if not rows:
            return None
        return self._row_to_fundamentals(rows[0])

    def get_all_latest_fundamentals(self) -> list[FundamentalsSnapshot]:
        rows = self._db.execute("""
            SELECT DISTINCT ON (ticker) *
            FROM invest.fundamentals_cache
            ORDER BY ticker, fetched_at DESC
        """)
        return [self._row_to_fundamentals(r) for r in rows]

    @staticmethod
    def _row_to_fundamentals(r: dict) -> FundamentalsSnapshot:
        return FundamentalsSnapshot(
            ticker=r["ticker"],
            fetched_at=r["fetched_at"],
            operating_income=Decimal(str(r["operating_income"])) if r["operating_income"] is not None else Decimal(0),
            market_cap=Decimal(str(r["market_cap"])) if r["market_cap"] is not None else Decimal(0),
            total_debt=Decimal(str(r["total_debt"])) if r["total_debt"] is not None else Decimal(0),
            cash=Decimal(str(r["cash"])) if r["cash"] is not None else Decimal(0),
            current_assets=Decimal(str(r["current_assets"])) if r["current_assets"] is not None else Decimal(0),
            current_liabilities=Decimal(str(r["current_liabilities"])) if r["current_liabilities"] is not None else Decimal(0),
            net_ppe=Decimal(str(r["net_ppe"])) if r["net_ppe"] is not None else Decimal(0),
            revenue=Decimal(str(r["revenue"])) if r["revenue"] is not None else Decimal(0),
            net_income=Decimal(str(r["net_income"])) if r["net_income"] is not None else Decimal(0),
            total_assets=Decimal(str(r["total_assets"])) if r["total_assets"] is not None else Decimal(0),
            total_liabilities=Decimal(str(r["total_liabilities"])) if r["total_liabilities"] is not None else Decimal(0),
            shares_outstanding=int(r["shares_outstanding"]) if r["shares_outstanding"] is not None else 0,
            price=Decimal(str(r["price"])) if r["price"] is not None else Decimal(0),
        )
