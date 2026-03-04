from __future__ import annotations

import logging

from investmentology.registry.db import Database

logger = logging.getLogger(__name__)


class LearningRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_sector_outcomes(self, sector: str) -> dict:
        try:
            rows = self._db.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE do.outcome = 'CORRECT') AS successful,
                    COUNT(*) FILTER (WHERE do.outcome = 'INCORRECT') AS failed,
                    AVG(d.confidence) AS avg_confidence
                FROM invest.decisions d
                JOIN invest.decision_outcomes do ON do.decision_id = d.id
                JOIN invest.stocks s ON s.ticker = d.ticker
                WHERE s.sector = %s
                """,
                (sector,),
            )
            if not rows or rows[0]["total"] == 0:
                return {}
            r = rows[0]
            total = r["total"]
            return {
                "total": total,
                "successful": r["successful"] or 0,
                "failed": r["failed"] or 0,
                "success_rate": round((r["successful"] or 0) / total, 3) if total else 0,
                "avg_confidence": float(r["avg_confidence"]) if r["avg_confidence"] else 0,
            }
        except Exception:
            logger.debug("get_sector_outcomes failed for %s", sector)
            return {}

    def get_failure_modes(self, sector: str, limit: int = 5) -> list[str]:
        try:
            rows = self._db.execute(
                """
                SELECT d.reasoning
                FROM invest.decisions d
                JOIN invest.stocks s ON s.ticker = d.ticker
                WHERE s.sector = %s
                  AND d.decision_type IN ('REJECT', 'SELL')
                  AND d.reasoning IS NOT NULL
                ORDER BY d.created_at DESC
                LIMIT %s
                """,
                (sector, limit),
            )
            return [r["reasoning"][:200] for r in rows if r.get("reasoning")]
        except Exception:
            logger.debug("get_failure_modes failed for %s", sector)
            return []

    def get_win_loss_stats(self) -> dict:
        try:
            rows = self._db.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE exit_price > entry_price) AS wins,
                    AVG(CASE WHEN exit_price > entry_price
                        THEN (exit_price - entry_price) / entry_price * 100
                        ELSE NULL END) AS avg_win_pct,
                    AVG(CASE WHEN exit_price <= entry_price
                        THEN (entry_price - exit_price) / entry_price * 100
                        ELSE NULL END) AS avg_loss_pct
                FROM invest.portfolio_positions
                WHERE exit_price IS NOT NULL
                  AND entry_price > 0
                """
            )
            if not rows or rows[0]["total"] == 0:
                return {}
            r = rows[0]
            total = r["total"]
            wins = r["wins"] or 0
            return {
                "total_settled": total,
                "win_rate": round(wins / total, 3) if total else 0,
                "avg_win_pct": float(r["avg_win_pct"]) if r["avg_win_pct"] else 0,
                "avg_loss_pct": float(r["avg_loss_pct"]) if r["avg_loss_pct"] else 0,
            }
        except Exception:
            logger.debug("get_win_loss_stats failed")
            return {}
