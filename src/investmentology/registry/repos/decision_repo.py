from __future__ import annotations

import json
from decimal import Decimal

from investmentology.models.decision import Decision, DecisionType
from investmentology.registry.db import Database


class DecisionRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def log_decision(self, decision: Decision) -> int:
        rows = self._db.execute(
            "INSERT INTO invest.decisions "
            "(ticker, decision_type, layer_source, confidence, reasoning, signals, metadata) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                decision.ticker, decision.decision_type.value, decision.layer_source,
                decision.confidence, decision.reasoning,
                json.dumps(decision.signals) if decision.signals else None,
                json.dumps(decision.metadata) if decision.metadata else None,
            ),
        )
        return rows[0]["id"]

    def get_decisions(
        self, ticker: str | None = None, decision_type: DecisionType | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[Decision]:
        conditions: list[str] = []
        params: list = []

        if ticker is not None:
            conditions.append("ticker = %s")
            params.append(ticker)
        if decision_type is not None:
            conditions.append("decision_type = %s")
            params.append(decision_type.value)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        rows = self._db.execute(
            f"SELECT id, ticker, decision_type, layer_source, confidence, "
            f"reasoning, signals, metadata, created_at "
            f"FROM invest.decisions {where} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params + [limit, offset]),
        )
        return [self._row_to_decision(r) for r in rows]

    @staticmethod
    def _row_to_decision(r: dict) -> Decision:
        return Decision(
            id=r["id"],
            ticker=r["ticker"],
            decision_type=DecisionType(r["decision_type"]),
            layer_source=r["layer_source"],
            confidence=Decimal(str(r["confidence"])) if r["confidence"] is not None else None,
            reasoning=r["reasoning"] or "",
            signals=r["signals"],
            metadata=r["metadata"],
            created_at=r["created_at"],
        )
