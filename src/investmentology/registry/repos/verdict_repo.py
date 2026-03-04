from __future__ import annotations

import json
from decimal import Decimal

from investmentology.registry.db import Database


class VerdictRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def insert_verdict(
        self, ticker: str, verdict: str, confidence: Decimal,
        consensus_score: float, reasoning: str,
        agent_stances: list[dict], risk_flags: list[str],
        auditor_override: bool, munger_override: bool,
        advisory_opinions: list[dict] | None = None,
        board_narrative: dict | None = None,
        board_adjusted_verdict: str | None = None,
        adversarial_result: dict | None = None,
    ) -> int:
        if advisory_opinions is not None or board_narrative is not None or adversarial_result is not None:
            try:
                rows = self._db.execute(
                    "INSERT INTO invest.verdicts "
                    "(ticker, verdict, confidence, consensus_score, reasoning, "
                    "agent_stances, risk_flags, auditor_override, munger_override, "
                    "advisory_opinions, board_narrative, board_adjusted_verdict, "
                    "adversarial_result) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        ticker, verdict, confidence, consensus_score, reasoning,
                        json.dumps(agent_stances), json.dumps(risk_flags),
                        auditor_override, munger_override,
                        json.dumps(advisory_opinions) if advisory_opinions else None,
                        json.dumps(board_narrative) if board_narrative else None,
                        board_adjusted_verdict,
                        json.dumps(adversarial_result) if adversarial_result else None,
                    ),
                )
                return rows[0]["id"]
            except Exception:
                pass

        rows = self._db.execute(
            "INSERT INTO invest.verdicts "
            "(ticker, verdict, confidence, consensus_score, reasoning, "
            "agent_stances, risk_flags, auditor_override, munger_override) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                ticker, verdict, confidence, consensus_score, reasoning,
                json.dumps(agent_stances), json.dumps(risk_flags),
                auditor_override, munger_override,
            ),
        )
        return rows[0]["id"]

    def get_latest_verdict(self, ticker: str) -> dict | None:
        rows = self._db.execute(
            "SELECT id, ticker, verdict, confidence, consensus_score, "
            "reasoning, agent_stances, risk_flags, "
            "auditor_override, munger_override, "
            "advisory_opinions, board_narrative, board_adjusted_verdict, "
            "adversarial_result, created_at "
            "FROM invest.verdicts WHERE ticker = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (ticker,),
        )
        return rows[0] if rows else None

    def get_verdict_history(self, ticker: str, limit: int = 20) -> list[dict]:
        return self._db.execute(
            "SELECT id, ticker, verdict, confidence, consensus_score, "
            "reasoning, agent_stances, risk_flags, "
            "auditor_override, munger_override, "
            "advisory_opinions, board_narrative, board_adjusted_verdict, "
            "adversarial_result, created_at "
            "FROM invest.verdicts WHERE ticker = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (ticker, limit),
        )
