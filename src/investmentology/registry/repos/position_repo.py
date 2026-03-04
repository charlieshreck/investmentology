from __future__ import annotations

from datetime import date
from decimal import Decimal

from investmentology.models.position import PortfolioPosition
from investmentology.registry.db import Database


class PositionRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def upsert_position(self, position: PortfolioPosition) -> None:
        self._db.execute(
            "INSERT INTO invest.portfolio_positions "
            "(ticker, entry_date, entry_price, current_price, shares, position_type, "
            "weight, stop_loss, fair_value_estimate, thesis, is_closed, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, false, NOW()) "
            "ON CONFLICT (ticker) WHERE is_closed = false DO UPDATE SET "
            "current_price = EXCLUDED.current_price, "
            "shares = EXCLUDED.shares, "
            "weight = EXCLUDED.weight, "
            "stop_loss = EXCLUDED.stop_loss, "
            "fair_value_estimate = EXCLUDED.fair_value_estimate, "
            "thesis = EXCLUDED.thesis, "
            "updated_at = NOW()",
            (
                position.ticker, position.entry_date, position.entry_price,
                position.current_price, position.shares, position.position_type,
                position.weight, position.stop_loss, position.fair_value_estimate,
                position.thesis,
            ),
        )

    def get_open_positions(self) -> list[PortfolioPosition]:
        rows = self._db.execute(
            "SELECT * FROM invest.portfolio_positions "
            "WHERE is_closed = FALSE ORDER BY ticker"
        )
        return [self._row_to_position(r) for r in rows]

    def create_position(
        self, ticker: str, entry_date: date, entry_price: Decimal,
        shares: Decimal, position_type: str, weight: Decimal,
        stop_loss: Decimal | None = None, fair_value_estimate: Decimal | None = None,
        thesis: str = "",
    ) -> int:
        rows = self._db.execute(
            "INSERT INTO invest.portfolio_positions "
            "(ticker, entry_date, entry_price, current_price, shares, position_type, "
            "weight, stop_loss, fair_value_estimate, thesis, is_closed) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE) RETURNING id",
            (
                ticker, entry_date, entry_price, entry_price, shares,
                position_type, weight, stop_loss, fair_value_estimate, thesis,
            ),
        )
        return rows[0]["id"]

    def close_position(
        self, position_id: int, exit_price: Decimal, exit_date: date | None = None,
    ) -> None:
        actual_exit_date = exit_date or date.today()
        self._db.execute(
            "UPDATE invest.portfolio_positions SET "
            "exit_date = %s, exit_price = %s, is_closed = TRUE, "
            "realized_pnl = ((%s - entry_price) * shares), "
            "updated_at = NOW() "
            "WHERE id = %s AND is_closed = FALSE",
            (actual_exit_date, exit_price, exit_price, position_id),
        )

    def create_position_atomic(
        self, ticker: str, entry_date: date, entry_price: Decimal,
        shares: Decimal, position_type: str, weight: Decimal,
        purchase_cost: Decimal, stop_loss: Decimal | None = None,
        fair_value_estimate: Decimal | None = None, thesis: str = "",
    ) -> int:
        with self._db.transaction() as tx:
            rows = tx.execute(
                "INSERT INTO invest.portfolio_positions "
                "(ticker, entry_date, entry_price, current_price, shares, position_type, "
                "weight, stop_loss, fair_value_estimate, thesis, is_closed) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE) RETURNING id",
                (
                    ticker, entry_date, entry_price, entry_price, shares,
                    position_type, weight, stop_loss, fair_value_estimate, thesis,
                ),
            )
            tx.execute(
                "UPDATE invest.portfolio_budget SET cash_reserve = cash_reserve - %s",
                (purchase_cost,),
            )
            return rows[0]["id"]

    def close_position_atomic(
        self, position_id: int, exit_price: Decimal,
        proceeds: Decimal, exit_date: date | None = None,
    ) -> None:
        actual_exit_date = exit_date or date.today()
        with self._db.transaction() as tx:
            tx.execute(
                "UPDATE invest.portfolio_positions SET "
                "exit_date = %s, exit_price = %s, is_closed = TRUE, "
                "realized_pnl = ((%s - entry_price) * shares), "
                "updated_at = NOW() "
                "WHERE id = %s AND is_closed = FALSE",
                (actual_exit_date, exit_price, exit_price, position_id),
            )
            tx.execute(
                "UPDATE invest.portfolio_budget SET cash_reserve = cash_reserve + %s",
                (proceeds,),
            )

    def update_position_analysis(
        self, ticker: str, fair_value_estimate: Decimal | None = None,
        stop_loss: Decimal | None = None, thesis: str | None = None,
    ) -> bool:
        updates: list[str] = []
        params: list = []
        if fair_value_estimate is not None:
            updates.append("fair_value_estimate = %s")
            params.append(fair_value_estimate)
        if stop_loss is not None:
            updates.append("stop_loss = %s")
            params.append(stop_loss)
        if thesis is not None:
            updates.append("thesis = %s")
            params.append(thesis)
        if not updates:
            return False
        updates.append("updated_at = NOW()")
        params.append(ticker)
        rows = self._db.execute(
            f"UPDATE invest.portfolio_positions SET {', '.join(updates)} "
            "WHERE ticker = %s AND is_closed = false RETURNING id",
            tuple(params),
        )
        return bool(rows)

    def get_closed_positions(self) -> list[PortfolioPosition]:
        rows = self._db.execute(
            "SELECT * FROM invest.portfolio_positions "
            "WHERE is_closed = TRUE ORDER BY exit_date DESC"
        )
        return [self._row_to_position(r) for r in rows]

    def get_position_by_id(self, position_id: int) -> PortfolioPosition | None:
        rows = self._db.execute(
            "SELECT * FROM invest.portfolio_positions WHERE id = %s",
            (position_id,),
        )
        if not rows:
            return None
        return self._row_to_position(rows[0])

    @staticmethod
    def _row_to_position(r: dict) -> PortfolioPosition:
        return PortfolioPosition(
            ticker=r["ticker"],
            entry_date=r["entry_date"],
            entry_price=Decimal(str(r["entry_price"])),
            current_price=Decimal(str(r["current_price"])) if r["current_price"] else Decimal(0),
            shares=Decimal(str(r["shares"])),
            position_type=r["position_type"],
            weight=Decimal(str(r["weight"])) if r["weight"] else Decimal(0),
            stop_loss=Decimal(str(r["stop_loss"])) if r["stop_loss"] else None,
            fair_value_estimate=Decimal(str(r["fair_value_estimate"])) if r["fair_value_estimate"] else None,
            thesis=r["thesis"] or "",
            id=r["id"],
            exit_date=r.get("exit_date"),
            exit_price=Decimal(str(r["exit_price"])) if r.get("exit_price") else None,
            is_closed=r.get("is_closed", False),
            realized_pnl=Decimal(str(r["realized_pnl"])) if r.get("realized_pnl") else None,
        )
