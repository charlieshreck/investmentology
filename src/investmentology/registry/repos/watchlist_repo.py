from __future__ import annotations

from investmentology.models.lifecycle import WatchlistState, validate_transition
from investmentology.registry.db import Database


class WatchlistRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def add_to_watchlist(
        self, ticker: str, state: WatchlistState = WatchlistState.UNIVERSE,
        source_run_id: int | None = None, notes: str | None = None,
    ) -> int:
        rows = self._db.execute(
            "INSERT INTO invest.watchlist (ticker, state, source_run_id, notes) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (ticker, state) DO UPDATE SET "
            "source_run_id = EXCLUDED.source_run_id, "
            "notes = EXCLUDED.notes, "
            "updated_at = NOW() "
            "RETURNING id",
            (ticker, state.value, source_run_id, notes),
        )
        return rows[0]["id"]

    def update_watchlist_state(self, ticker: str, new_state: WatchlistState) -> None:
        rows = self._db.execute(
            "SELECT state FROM invest.watchlist WHERE ticker = %s ORDER BY updated_at DESC LIMIT 1",
            (ticker,),
        )
        if not rows:
            raise ValueError(f"Ticker {ticker} not found in watchlist")

        current_state = WatchlistState(rows[0]["state"])
        if not validate_transition(current_state, new_state):
            raise ValueError(
                f"Invalid transition: {current_state.value} -> {new_state.value}"
            )

        self._db.execute(
            "UPDATE invest.watchlist SET state = %s, updated_at = NOW() "
            "WHERE ticker = %s AND state = %s",
            (new_state.value, ticker, current_state.value),
        )

    def get_watchlist_by_state(self, state: WatchlistState | None = None) -> list[dict]:
        if state is not None:
            return self._db.execute(
                "SELECT * FROM invest.watchlist WHERE state = %s ORDER BY updated_at DESC",
                (state.value,),
            )
        return self._db.execute(
            "SELECT * FROM invest.watchlist ORDER BY state, updated_at DESC"
        )
