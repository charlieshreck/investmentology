from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from investmentology.registry.db import Database


def _dumps(obj) -> str:
    """json.dumps with Decimal→float coercion."""
    return json.dumps(obj, default=lambda o: float(o) if isinstance(o, Decimal) else str(o))


class SignalRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def insert_market_snapshot(self, snapshot: dict) -> int:
        rows = self._db.execute(
            "INSERT INTO invest.market_snapshots "
            "(snapshot_date, spy_price, qqq_price, iwm_price, vix, "
            "ten_year_yield, two_year_yield, hy_oas, put_call_ratio, "
            "sector_data, pendulum_score, regime_score) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                snapshot.get("snapshot_date", date.today()),
                snapshot.get("spy_price"),
                snapshot.get("qqq_price"),
                snapshot.get("iwm_price"),
                snapshot.get("vix"),
                snapshot.get("ten_year_yield"),
                snapshot.get("two_year_yield"),
                snapshot.get("hy_oas"),
                snapshot.get("put_call_ratio"),
                json.dumps(snapshot.get("sector_data"), default=str) if snapshot.get("sector_data") else None,
                snapshot.get("pendulum_score"),
                snapshot.get("regime_score"),
            ),
        )
        return rows[0]["id"]

    def insert_agent_signals(
        self, ticker: str, agent_name: str, model: str,
        signals: dict, confidence: Decimal, reasoning: str,
        token_usage: dict | None = None, latency_ms: int | None = None,
        run_id: int | None = None,
    ) -> int:
        rows = self._db.execute(
            "INSERT INTO invest.agent_signals "
            "(ticker, agent_name, model, signals, confidence, reasoning, "
            "token_usage, latency_ms, run_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                ticker, agent_name, model, _dumps(signals), confidence,
                reasoning, _dumps(token_usage) if token_usage else None,
                latency_ms, run_id,
            ),
        )
        return rows[0]["id"]
