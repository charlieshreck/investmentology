from __future__ import annotations

import json
import logging
from datetime import date, datetime
from decimal import Decimal

from investmentology.models.decision import Decision, DecisionOutcome, DecisionType
from investmentology.models.lifecycle import WatchlistState, validate_transition
from investmentology.models.position import PortfolioPosition
from investmentology.models.prediction import Prediction
from investmentology.models.stock import FundamentalsSnapshot, Stock
from investmentology.registry.db import Database

logger = logging.getLogger(__name__)


class Registry:
    """Query layer bridging Python models and the invest schema."""

    def __init__(self, db: Database) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Stock universe
    # ------------------------------------------------------------------

    def upsert_stocks(self, stocks: list[Stock]) -> int:
        """Insert or update stocks. Returns count of affected rows."""
        query = """
            INSERT INTO invest.stocks (ticker, name, sector, industry, market_cap, exchange, is_active, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (ticker) DO UPDATE SET
                name = EXCLUDED.name,
                sector = EXCLUDED.sector,
                industry = EXCLUDED.industry,
                market_cap = EXCLUDED.market_cap,
                exchange = EXCLUDED.exchange,
                is_active = EXCLUDED.is_active,
                updated_at = NOW()
        """
        params = [
            (s.ticker, s.name, s.sector, s.industry, s.market_cap, s.exchange, s.is_active)
            for s in stocks
        ]
        return self._db.execute_many(query, params)

    def get_active_stocks(self) -> list[Stock]:
        """Return all active stocks."""
        rows = self._db.execute(
            "SELECT ticker, name, sector, industry, market_cap, exchange, is_active "
            "FROM invest.stocks WHERE is_active = TRUE ORDER BY ticker"
        )
        return [
            Stock(
                ticker=r["ticker"],
                name=r["name"],
                sector=r["sector"] or "",
                industry=r["industry"] or "",
                market_cap=Decimal(str(r["market_cap"])) if r["market_cap"] else Decimal(0),
                exchange=r["exchange"] or "",
                is_active=r["is_active"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Fundamentals
    # ------------------------------------------------------------------

    def insert_fundamentals(self, snapshots: list[FundamentalsSnapshot]) -> int:
        """Insert fundamental snapshots. Returns count inserted."""
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
        """Get the most recent fundamentals for a single ticker."""
        rows = self._db.execute(
            "SELECT * FROM invest.fundamentals_cache "
            "WHERE ticker = %s ORDER BY fetched_at DESC LIMIT 1",
            (ticker,),
        )
        if not rows:
            return None
        return self._row_to_fundamentals(rows[0])

    def get_all_latest_fundamentals(self) -> list[FundamentalsSnapshot]:
        """Get the most recent fundamentals for all tickers."""
        rows = self._db.execute("""
            SELECT DISTINCT ON (ticker) *
            FROM invest.fundamentals_cache
            ORDER BY ticker, fetched_at DESC
        """)
        return [self._row_to_fundamentals(r) for r in rows]

    # ------------------------------------------------------------------
    # Quant Gate
    # ------------------------------------------------------------------

    def create_quant_gate_run(
        self, universe_size: int, passed_count: int, config: dict, data_quality: dict | None = None,
    ) -> int:
        """Create a new quant gate run. Returns the run_id."""
        rows = self._db.execute(
            "INSERT INTO invest.quant_gate_runs (run_date, universe_size, passed_count, config, data_quality) "
            "VALUES (CURRENT_DATE, %s, %s, %s, %s) RETURNING id",
            (universe_size, passed_count, json.dumps(config), json.dumps(data_quality or {})),
        )
        return rows[0]["id"]

    def insert_quant_gate_results(self, run_id: int, results: list[dict]) -> int:
        """Insert quant gate ranking results. Returns count inserted."""
        query = """
            INSERT INTO invest.quant_gate_results (
                run_id, ticker, earnings_yield, roic, ey_rank, roic_rank,
                combined_rank, piotroski_score, altman_z_score,
                composite_score, altman_zone
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            (
                run_id, r["ticker"], r.get("earnings_yield"), r.get("roic"),
                r.get("ey_rank"), r.get("roic_rank"), r.get("combined_rank"),
                r.get("piotroski_score"), r.get("altman_z_score"),
                r.get("composite_score"), r.get("altman_zone"),
            )
            for r in results
        ]
        return self._db.execute_many(query, params)

    # ------------------------------------------------------------------
    # Decisions (append-only)
    # ------------------------------------------------------------------

    def log_decision(self, decision: Decision) -> int:
        """Log a decision. Returns the decision id."""
        rows = self._db.execute(
            "INSERT INTO invest.decisions "
            "(ticker, decision_type, layer_source, confidence, reasoning, signals, metadata) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                decision.ticker,
                decision.decision_type.value,
                decision.layer_source,
                decision.confidence,
                decision.reasoning,
                json.dumps(decision.signals) if decision.signals else None,
                json.dumps(decision.metadata) if decision.metadata else None,
            ),
        )
        return rows[0]["id"]

    def get_decisions(
        self,
        ticker: str | None = None,
        decision_type: DecisionType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Decision]:
        """Get decisions with optional filters."""
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

    # ------------------------------------------------------------------
    # Predictions
    # ------------------------------------------------------------------

    def log_prediction(self, prediction: Prediction) -> int:
        """Log a prediction. Returns the prediction id."""
        rows = self._db.execute(
            "INSERT INTO invest.predictions "
            "(ticker, prediction_type, predicted_value, confidence, horizon_days, "
            "settlement_date, source) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                prediction.ticker,
                prediction.prediction_type,
                prediction.predicted_value,
                prediction.confidence,
                prediction.horizon_days,
                prediction.settlement_date,
                prediction.source,
            ),
        )
        return rows[0]["id"]

    def settle_prediction(self, prediction_id: int, actual_value: Decimal) -> None:
        """Settle a prediction with its actual outcome."""
        self._db.execute(
            "UPDATE invest.predictions "
            "SET actual_value = %s, is_settled = TRUE, settled_at = NOW() "
            "WHERE id = %s",
            (actual_value, prediction_id),
        )

    def get_unsettled_predictions(self, as_of: date | None = None) -> list[Prediction]:
        """Get predictions due for settlement."""
        target = as_of or date.today()
        rows = self._db.execute(
            "SELECT * FROM invest.predictions "
            "WHERE is_settled = FALSE AND settlement_date <= %s "
            "ORDER BY settlement_date",
            (target,),
        )
        return [self._row_to_prediction(r) for r in rows]

    # ------------------------------------------------------------------
    # Watchlist
    # ------------------------------------------------------------------

    def add_to_watchlist(
        self, ticker: str, state: WatchlistState = WatchlistState.UNIVERSE,
        source_run_id: int | None = None, notes: str | None = None,
    ) -> int:
        """Add a stock to the watchlist. Returns watchlist id.

        Uses ON CONFLICT to update existing entries rather than creating duplicates.
        """
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
        """Update watchlist state with transition validation."""
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
        """Get watchlist items, optionally filtered by state."""
        if state is not None:
            return self._db.execute(
                "SELECT * FROM invest.watchlist WHERE state = %s ORDER BY updated_at DESC",
                (state.value,),
            )
        return self._db.execute(
            "SELECT * FROM invest.watchlist ORDER BY state, updated_at DESC"
        )

    # ------------------------------------------------------------------
    # Portfolio positions
    # ------------------------------------------------------------------

    def upsert_position(self, position: PortfolioPosition) -> None:
        """Insert or update a portfolio position."""
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
        """Get all open (non-closed) portfolio positions."""
        rows = self._db.execute(
            "SELECT * FROM invest.portfolio_positions "
            "WHERE is_closed = FALSE ORDER BY ticker"
        )
        return [self._row_to_position(r) for r in rows]

    def create_position(
        self,
        ticker: str,
        entry_date: date,
        entry_price: Decimal,
        shares: Decimal,
        position_type: str,
        weight: Decimal,
        stop_loss: Decimal | None = None,
        fair_value_estimate: Decimal | None = None,
        thesis: str = "",
    ) -> int:
        """Create a new portfolio position. Returns position id."""
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
        """Close a position with exit price and compute realized P&L."""
        actual_exit_date = exit_date or date.today()
        self._db.execute(
            "UPDATE invest.portfolio_positions SET "
            "exit_date = %s, exit_price = %s, is_closed = TRUE, "
            "realized_pnl = ((%s - entry_price) * shares), "
            "updated_at = NOW() "
            "WHERE id = %s AND is_closed = FALSE",
            (actual_exit_date, exit_price, exit_price, position_id),
        )

    def update_position_analysis(
        self, ticker: str, fair_value_estimate: Decimal | None = None,
        stop_loss: Decimal | None = None, thesis: str | None = None,
    ) -> bool:
        """Update fair_value_estimate, stop_loss, and/or thesis on an open position.

        Returns True if a row was updated.
        """
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
        """Get all closed positions for P&L history."""
        rows = self._db.execute(
            "SELECT * FROM invest.portfolio_positions "
            "WHERE is_closed = TRUE ORDER BY exit_date DESC"
        )
        return [self._row_to_position(r) for r in rows]

    def get_position_by_id(self, position_id: int) -> PortfolioPosition | None:
        """Get a single position by ID."""
        rows = self._db.execute(
            "SELECT * FROM invest.portfolio_positions WHERE id = %s",
            (position_id,),
        )
        if not rows:
            return None
        return self._row_to_position(rows[0])

    # ------------------------------------------------------------------
    # Cron audit
    # ------------------------------------------------------------------

    def log_cron_start(self, job_name: str) -> int:
        """Log the start of a cron job. Returns cron_run id."""
        rows = self._db.execute(
            "INSERT INTO invest.cron_runs (job_name, started_at, status) "
            "VALUES (%s, NOW(), 'running') RETURNING id",
            (job_name,),
        )
        return rows[0]["id"]

    def log_cron_finish(self, cron_id: int, status: str, error: str | None = None) -> None:
        """Log the completion of a cron job."""
        self._db.execute(
            "UPDATE invest.cron_runs SET finished_at = NOW(), status = %s, error = %s WHERE id = %s",
            (status, error, cron_id),
        )

    # ------------------------------------------------------------------
    # Market snapshots
    # ------------------------------------------------------------------

    def insert_market_snapshot(self, snapshot: dict) -> int:
        """Insert a daily market snapshot. Returns snapshot id."""
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

    # ------------------------------------------------------------------
    # Agent signals
    # ------------------------------------------------------------------

    def insert_agent_signals(
        self, ticker: str, agent_name: str, model: str,
        signals: dict, confidence: Decimal, reasoning: str,
        token_usage: dict | None = None, latency_ms: int | None = None,
        run_id: int | None = None,
    ) -> int:
        """Insert agent signal output. Returns signal id."""
        rows = self._db.execute(
            "INSERT INTO invest.agent_signals "
            "(ticker, agent_name, model, signals, confidence, reasoning, "
            "token_usage, latency_ms, run_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                ticker, agent_name, model, json.dumps(signals), confidence,
                reasoning, json.dumps(token_usage) if token_usage else None,
                latency_ms, run_id,
            ),
        )
        return rows[0]["id"]

    # ------------------------------------------------------------------
    # Verdicts
    # ------------------------------------------------------------------

    def insert_verdict(
        self, ticker: str, verdict: str, confidence: Decimal,
        consensus_score: float, reasoning: str,
        agent_stances: list[dict], risk_flags: list[str],
        auditor_override: bool, munger_override: bool,
    ) -> int:
        """Insert a computed verdict. Returns verdict id."""
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
        """Get the most recent verdict for a ticker."""
        rows = self._db.execute(
            "SELECT id, ticker, verdict, confidence, consensus_score, "
            "reasoning, agent_stances, risk_flags, "
            "auditor_override, munger_override, created_at "
            "FROM invest.verdicts WHERE ticker = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (ticker,),
        )
        return rows[0] if rows else None

    def get_verdict_history(self, ticker: str, limit: int = 20) -> list[dict]:
        """Get verdict history for a ticker, newest first."""
        return self._db.execute(
            "SELECT id, ticker, verdict, confidence, consensus_score, "
            "reasoning, agent_stances, risk_flags, "
            "auditor_override, munger_override, created_at "
            "FROM invest.verdicts WHERE ticker = %s "
            "ORDER BY created_at DESC LIMIT %s",
            (ticker, limit),
        )

    def get_enriched_watchlist(self) -> list[dict]:
        """Get watchlist items enriched with prices, scores, and verdicts.

        Uses LATERAL joins to pull latest price, quant gate scores,
        and verdict for each watchlist item in a single query.
        """
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
                       agent_stances, risk_flags, created_at
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
        """Get the latest verdict for every ticker, enriched with stock info and prices.

        Returns only actionable verdicts (not DISCARD), one per ticker.
        Includes price_history for sparkline charts.
        """
        return self._db.execute("""
            WITH latest_verdicts AS (
                SELECT DISTINCT ON (v.ticker)
                    v.id, v.ticker, v.verdict, v.confidence, v.consensus_score,
                    v.reasoning, v.agent_stances, v.risk_flags,
                    v.auditor_override, v.munger_override, v.created_at
                FROM invest.verdicts v
                WHERE v.verdict != 'DISCARD'
                ORDER BY v.ticker, v.created_at DESC
            )
            SELECT
                lv.id, lv.ticker, lv.verdict, lv.confidence, lv.consensus_score,
                lv.reasoning, lv.agent_stances, lv.risk_flags,
                lv.auditor_override, lv.munger_override, lv.created_at,
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

    def get_watchlist_tickers_for_reanalysis(
        self, states: list[str], min_hours: int = 20,
    ) -> list[str]:
        """Get watchlist tickers that haven't been analyzed recently.

        Returns tickers in the given states whose latest verdict is older
        than min_hours, or who have never been analyzed.
        """
        rows = self._db.execute(
            """
            SELECT w.ticker
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
        return [r["ticker"] for r in rows]

    def get_watch_verdicts_enriched(self) -> list[dict]:
        """Get WATCHLIST verdicts enriched with entry price, current price, and price history.

        For each ticker with a WATCHLIST verdict:
        - entry_price: price closest to verdict date
        - current_price: latest price
        - price_history: daily prices as JSON array [{date, price}, ...]
        """
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
                SELECT state, entered_at
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Base rate queries (for pre-mortem calibration)
    # ------------------------------------------------------------------

    def get_sector_outcomes(self, sector: str) -> dict:
        """Get historical outcome stats for a sector.

        Returns dict with: total, successful, failed, success_rate,
        avg_confidence, common_verdicts.
        """
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
        """Get most common failure/rejection reasons for a sector."""
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
        """Get overall win/loss statistics for Kelly criterion.

        Returns dict with: win_rate, avg_win_pct, avg_loss_pct, total_settled.
        Requires positions with both entry and exit prices.
        """
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

    @staticmethod
    def _row_to_prediction(r: dict) -> Prediction:
        return Prediction(
            id=r["id"],
            ticker=r["ticker"],
            prediction_type=r["prediction_type"],
            predicted_value=Decimal(str(r["predicted_value"])),
            confidence=Decimal(str(r["confidence"])) if r["confidence"] is not None else Decimal(0),
            horizon_days=r["horizon_days"],
            settlement_date=r["settlement_date"],
            source=r["source"] or "",
            actual_value=Decimal(str(r["actual_value"])) if r["actual_value"] is not None else None,
            is_settled=r["is_settled"],
            settled_at=r["settled_at"],
            created_at=r["created_at"],
        )
