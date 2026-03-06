from __future__ import annotations

import logging
from datetime import datetime, timezone

from investmentology.registry.db import Database

logger = logging.getLogger(__name__)


class EnrichedRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_enriched_watchlist(self) -> list[dict]:
        return self._db.execute("""
            WITH latest_watchlist AS (
                SELECT DISTINCT ON (ticker) *
                FROM invest.watchlist
                ORDER BY ticker, updated_at DESC
            )
            SELECT
                w.id, w.ticker, w.state, w.notes, w.price_at_add,
                w.entered_at, w.updated_at,
                s.name, s.sector,
                f.price AS current_price, f.market_cap,
                qg.composite_score, qg.piotroski_score, qg.altman_zone,
                qg.combined_rank, qg.altman_z_score,
                v.verdict, v.confidence AS verdict_confidence,
                v.consensus_score, v.reasoning AS verdict_reasoning,
                v.agent_stances, v.risk_flags,
                v.created_at AS verdict_date
            FROM latest_watchlist w
            LEFT JOIN invest.stocks s ON s.ticker = w.ticker
            LEFT JOIN LATERAL (
                SELECT price, market_cap
                FROM invest.fundamentals_cache fc
                WHERE fc.ticker = w.ticker
                ORDER BY fc.fetched_at DESC LIMIT 1
            ) f ON TRUE
            LEFT JOIN LATERAL (
                SELECT composite_score, piotroski_score, altman_zone,
                       combined_rank, altman_z_score
                FROM invest.quant_gate_results qgr
                WHERE qgr.ticker = w.ticker
                ORDER BY qgr.run_id DESC LIMIT 1
            ) qg ON TRUE
            LEFT JOIN LATERAL (
                SELECT verdict, confidence, consensus_score, reasoning,
                       agent_stances, risk_flags,
                       advisory_opinions, board_narrative, board_adjusted_verdict,
                       created_at
                FROM invest.verdicts vd
                WHERE vd.ticker = w.ticker
                ORDER BY vd.created_at DESC LIMIT 1
            ) v ON TRUE
            ORDER BY
                CASE w.state::text
                    WHEN 'CONVICTION_BUY' THEN 1
                    WHEN 'POSITION_HOLD' THEN 2
                    WHEN 'POSITION_TRIM' THEN 3
                    WHEN 'WATCHLIST_EARLY' THEN 4
                    WHEN 'WATCHLIST_CATALYST' THEN 5
                    WHEN 'ASSESSED' THEN 6
                    WHEN 'CANDIDATE' THEN 7
                    WHEN 'CONFLICT_REVIEW' THEN 8
                    WHEN 'POSITION_SELL' THEN 9
                    WHEN 'REJECTED' THEN 10
                    WHEN 'UNIVERSE' THEN 11
                    ELSE 12
                END,
                COALESCE(qg.composite_score, 0) DESC,
                w.updated_at DESC
        """)

    def get_all_actionable_verdicts(self) -> list[dict]:
        return self._db.execute("""
            WITH latest_verdicts AS (
                SELECT DISTINCT ON (v.ticker)
                    v.id, v.ticker, v.verdict, v.confidence, v.consensus_score,
                    v.reasoning, v.agent_stances, v.risk_flags,
                    v.auditor_override, v.munger_override,
                    v.advisory_opinions, v.board_narrative, v.board_adjusted_verdict,
                    v.adversarial_result, v.created_at
                FROM invest.verdicts v
                WHERE v.verdict != 'DISCARD'
                ORDER BY v.ticker, v.created_at DESC
            )
            SELECT
                lv.id, lv.ticker, lv.verdict, lv.confidence, lv.consensus_score,
                lv.reasoning, lv.agent_stances, lv.risk_flags,
                lv.auditor_override, lv.munger_override,
                lv.advisory_opinions, lv.board_narrative, lv.board_adjusted_verdict,
                lv.adversarial_result, lv.created_at,
                s.name, s.sector, s.industry,
                f.price AS current_price, f.market_cap,
                w.state AS watchlist_state,
                entry.price AS entry_price,
                ph.history AS price_history
            FROM latest_verdicts lv
            LEFT JOIN invest.stocks s ON s.ticker = lv.ticker
            LEFT JOIN LATERAL (
                SELECT price, market_cap
                FROM invest.fundamentals_cache fc
                WHERE fc.ticker = lv.ticker
                ORDER BY fc.fetched_at DESC LIMIT 1
            ) f ON TRUE
            LEFT JOIN LATERAL (
                SELECT state
                FROM invest.watchlist wl
                WHERE wl.ticker = lv.ticker
                ORDER BY wl.updated_at DESC LIMIT 1
            ) w ON TRUE
            LEFT JOIN LATERAL (
                SELECT price
                FROM invest.fundamentals_cache fc
                WHERE fc.ticker = lv.ticker
                  AND fc.price > 0
                  AND fc.fetched_at <= lv.created_at + interval '1 day'
                ORDER BY fc.fetched_at DESC LIMIT 1
            ) entry ON TRUE
            LEFT JOIN LATERAL (
                SELECT json_agg(
                    json_build_object('date', dt::text, 'price', p)
                    ORDER BY dt
                ) AS history
                FROM (
                    SELECT DISTINCT ON (fc.fetched_at::date)
                        fc.fetched_at::date AS dt, fc.price AS p
                    FROM invest.fundamentals_cache fc
                    WHERE fc.ticker = lv.ticker AND fc.price > 0
                    ORDER BY fc.fetched_at::date, fc.fetched_at DESC
                ) daily
            ) ph ON TRUE
        """)

    def get_blocked_tickers(self) -> set[str]:
        try:
            rows = self._db.execute(
                "SELECT DISTINCT ticker FROM invest.reentry_blocks "
                "WHERE is_cleared = FALSE"
            )
            return {r["ticker"] for r in rows}
        except Exception:
            return set()

    def get_watchlist_tickers_for_reanalysis(
        self, states: list[str], min_hours: int = 20,
        min_move_pct: float = 0.0, force_after_hours: int = 0,
    ) -> list[str]:
        held_states = {"CONVICTION_BUY", "POSITION_HOLD"}
        blocked = self.get_blocked_tickers()

        if min_move_pct > 0:
            rows = self._db.execute(
                """
                SELECT w.ticker, w.state,
                       latest_v.created_at AS last_verdict_at,
                       latest_v.price_at_verdict,
                       current_p.price AS current_price
                FROM invest.watchlist w
                LEFT JOIN LATERAL (
                    SELECT v.created_at,
                           fc.price AS price_at_verdict
                    FROM invest.verdicts v
                    LEFT JOIN LATERAL (
                        SELECT price FROM invest.fundamentals_cache fc2
                        WHERE fc2.ticker = v.ticker
                          AND fc2.price > 0
                          AND fc2.fetched_at <= v.created_at + interval '1 hour'
                        ORDER BY fc2.fetched_at DESC LIMIT 1
                    ) fc ON TRUE
                    WHERE v.ticker = w.ticker
                    ORDER BY v.created_at DESC LIMIT 1
                ) latest_v ON TRUE
                LEFT JOIN LATERAL (
                    SELECT price FROM invest.fundamentals_cache fc3
                    WHERE fc3.ticker = w.ticker AND fc3.price > 0
                    ORDER BY fc3.fetched_at DESC LIMIT 1
                ) current_p ON TRUE
                WHERE w.state = ANY(%s)
                  AND (latest_v.created_at IS NULL
                       OR latest_v.created_at < NOW() - make_interval(hours => %s))
                ORDER BY latest_v.created_at ASC NULLS FIRST
                """,
                (states, min_hours),
            )

            result = []
            for r in rows:
                ticker = r["ticker"]
                state = r.get("state", "")

                if r.get("last_verdict_at") is None:
                    result.append(ticker)
                    continue

                if state in held_states:
                    result.append(ticker)
                    continue

                if ticker in blocked:
                    continue

                if force_after_hours > 0:
                    last_at = r["last_verdict_at"]
                    if hasattr(last_at, "tzinfo") and last_at.tzinfo is None:
                        last_at = last_at.replace(tzinfo=timezone.utc)
                    hours_since = (datetime.now(timezone.utc) - last_at).total_seconds() / 3600
                    if hours_since >= force_after_hours:
                        result.append(ticker)
                        continue

                old_price = r.get("price_at_verdict")
                new_price = r.get("current_price")
                if old_price and new_price and float(old_price) > 0:
                    move_pct = abs(float(new_price) - float(old_price)) / float(old_price) * 100
                    if move_pct >= min_move_pct:
                        result.append(ticker)
                else:
                    result.append(ticker)

            return result

        rows = self._db.execute(
            """
            SELECT w.ticker, w.state
            FROM invest.watchlist w
            LEFT JOIN LATERAL (
                SELECT created_at
                FROM invest.verdicts v
                WHERE v.ticker = w.ticker
                ORDER BY v.created_at DESC LIMIT 1
            ) latest_v ON TRUE
            WHERE w.state = ANY(%s)
              AND (latest_v.created_at IS NULL
                   OR latest_v.created_at < NOW() - make_interval(hours => %s))
            ORDER BY latest_v.created_at ASC NULLS FIRST
            """,
            (states, min_hours),
        )
        return [
            r["ticker"] for r in rows
            if r["ticker"] not in blocked or r.get("state") in held_states
        ]

    def get_watch_verdicts_enriched(self) -> list[dict]:
        return self._db.execute("""
            WITH portfolio_tickers AS (
                SELECT ticker FROM invest.portfolio_positions
                WHERE is_closed = false AND shares > 0
            ),
            latest_watchlist_verdicts AS (
                SELECT DISTINCT ON (v.ticker)
                    v.id, v.ticker, v.verdict, v.confidence, v.consensus_score,
                    v.reasoning, v.agent_stances, v.risk_flags,
                    v.auditor_override, v.munger_override, v.created_at
                FROM invest.verdicts v
                WHERE v.verdict = 'WATCHLIST'
                  AND v.ticker NOT IN (SELECT ticker FROM portfolio_tickers)
                ORDER BY v.ticker, v.created_at DESC
            )
            SELECT
                lw.id, lw.ticker, lw.verdict, lw.confidence, lw.consensus_score,
                lw.reasoning, lw.agent_stances, lw.risk_flags,
                lw.auditor_override, lw.munger_override, lw.created_at,
                s.name, s.sector, s.industry,
                cur.price AS current_price, cur.market_cap,
                entry.price AS entry_price,
                w.state AS watchlist_state,
                w.entered_at AS watchlist_entered,
                w.watchlist_reason,
                w.watchlist_blocking_factors,
                w.watchlist_graduation_criteria,
                w.target_entry_price,
                w._next_catalyst_date,
                w._qg_rank,
                ph.history AS price_history
            FROM latest_watchlist_verdicts lw
            LEFT JOIN invest.stocks s ON s.ticker = lw.ticker
            LEFT JOIN LATERAL (
                SELECT price, market_cap
                FROM invest.fundamentals_cache fc
                WHERE fc.ticker = lw.ticker
                ORDER BY fc.fetched_at DESC LIMIT 1
            ) cur ON TRUE
            LEFT JOIN LATERAL (
                SELECT price
                FROM invest.fundamentals_cache fc
                WHERE fc.ticker = lw.ticker
                  AND fc.price > 0
                  AND fc.fetched_at <= lw.created_at + interval '1 day'
                ORDER BY fc.fetched_at DESC LIMIT 1
            ) entry ON TRUE
            LEFT JOIN LATERAL (
                SELECT state, entered_at,
                       reason AS watchlist_reason,
                       blocking_factors AS watchlist_blocking_factors,
                       graduation_criteria AS watchlist_graduation_criteria,
                       target_entry_price,
                       next_catalyst_date AS _next_catalyst_date,
                       qg_rank AS _qg_rank
                FROM invest.watchlist wl
                WHERE wl.ticker = lw.ticker
                ORDER BY wl.updated_at DESC LIMIT 1
            ) w ON TRUE
            LEFT JOIN LATERAL (
                SELECT json_agg(
                    json_build_object('date', dt::text, 'price', p)
                    ORDER BY dt
                ) AS history
                FROM (
                    SELECT DISTINCT ON (fc.fetched_at::date)
                        fc.fetched_at::date AS dt, fc.price AS p
                    FROM invest.fundamentals_cache fc
                    WHERE fc.ticker = lw.ticker AND fc.price > 0
                    ORDER BY fc.fetched_at::date, fc.fetched_at DESC
                ) daily
            ) ph ON TRUE
            ORDER BY lw.confidence DESC NULLS LAST
        """)
