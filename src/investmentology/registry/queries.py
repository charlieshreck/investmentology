from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from investmentology.models.decision import Decision, DecisionType
from investmentology.models.lifecycle import WatchlistState
from investmentology.models.position import PortfolioPosition
from investmentology.models.prediction import Prediction
from investmentology.models.stock import FundamentalsSnapshot, Stock
from investmentology.registry.db import Database
from investmentology.registry.repos import (
    CronRepo,
    DecisionRepo,
    EnrichedRepo,
    FundamentalsRepo,
    LearningRepo,
    PositionRepo,
    PredictionRepo,
    QuantGateRepo,
    SignalRepo,
    StockRepo,
    VerdictRepo,
    WatchlistRepo,
)

logger = logging.getLogger(__name__)


class Registry:
    """Query layer bridging Python models and the invest schema.

    Thin facade delegating to domain-specific repo classes.
    """

    def __init__(self, db: Database) -> None:
        self._db = db
        self._stocks = StockRepo(db)
        self._fundamentals = FundamentalsRepo(db)
        self._quant_gate = QuantGateRepo(db)
        self._decisions = DecisionRepo(db)
        self._predictions = PredictionRepo(db)
        self._watchlist = WatchlistRepo(db)
        self._positions = PositionRepo(db)
        self._signals = SignalRepo(db)
        self._verdicts = VerdictRepo(db)
        self._enriched = EnrichedRepo(db)
        self._cron = CronRepo(db)
        self._learning = LearningRepo(db)

    # ------------------------------------------------------------------
    # Stock universe
    # ------------------------------------------------------------------

    def upsert_stocks(self, stocks: list[Stock]) -> int:
        return self._stocks.upsert_stocks(stocks)

    def get_active_stocks(self) -> list[Stock]:
        return self._stocks.get_active_stocks()

    # ------------------------------------------------------------------
    # Fundamentals
    # ------------------------------------------------------------------

    def insert_fundamentals(self, snapshots: list[FundamentalsSnapshot]) -> int:
        return self._fundamentals.insert_fundamentals(snapshots)

    def get_latest_fundamentals(self, ticker: str) -> FundamentalsSnapshot | None:
        return self._fundamentals.get_latest_fundamentals(ticker)

    def get_all_latest_fundamentals(self) -> list[FundamentalsSnapshot]:
        return self._fundamentals.get_all_latest_fundamentals()

    # ------------------------------------------------------------------
    # Quant Gate
    # ------------------------------------------------------------------

    def create_quant_gate_run(
        self, universe_size: int, passed_count: int,
        config: dict, data_quality: dict | None = None,
    ) -> int:
        return self._quant_gate.create_quant_gate_run(
            universe_size, passed_count, config, data_quality,
        )

    def insert_quant_gate_results(self, run_id: int, results: list[dict]) -> int:
        return self._quant_gate.insert_quant_gate_results(run_id, results)

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def log_decision(self, decision: Decision) -> int:
        return self._decisions.log_decision(decision)

    def get_decisions(
        self, ticker: str | None = None, decision_type: DecisionType | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[Decision]:
        return self._decisions.get_decisions(ticker, decision_type, limit, offset)

    # ------------------------------------------------------------------
    # Predictions
    # ------------------------------------------------------------------

    def log_prediction(self, prediction: Prediction) -> int:
        return self._predictions.log_prediction(prediction)

    def settle_prediction(self, prediction_id: int, actual_value: Decimal) -> None:
        self._predictions.settle_prediction(prediction_id, actual_value)

    def get_unsettled_predictions(self, as_of: date | None = None) -> list[Prediction]:
        return self._predictions.get_unsettled_predictions(as_of)

    # ------------------------------------------------------------------
    # Watchlist
    # ------------------------------------------------------------------

    def add_to_watchlist(
        self, ticker: str, state: WatchlistState = WatchlistState.UNIVERSE,
        source_run_id: int | None = None, notes: str | None = None,
    ) -> int:
        return self._watchlist.add_to_watchlist(ticker, state, source_run_id, notes)

    def update_watchlist_state(self, ticker: str, new_state: WatchlistState) -> None:
        self._watchlist.update_watchlist_state(ticker, new_state)

    def get_watchlist_by_state(self, state: WatchlistState | None = None) -> list[dict]:
        return self._watchlist.get_watchlist_by_state(state)

    # ------------------------------------------------------------------
    # Portfolio positions
    # ------------------------------------------------------------------

    def upsert_position(self, position: PortfolioPosition) -> None:
        self._positions.upsert_position(position)

    def get_open_positions(self) -> list[PortfolioPosition]:
        return self._positions.get_open_positions()

    def create_position(
        self, ticker: str, entry_date: date, entry_price: Decimal,
        shares: Decimal, position_type: str, weight: Decimal,
        stop_loss: Decimal | None = None, fair_value_estimate: Decimal | None = None,
        thesis: str = "",
    ) -> int:
        return self._positions.create_position(
            ticker, entry_date, entry_price, shares, position_type,
            weight, stop_loss, fair_value_estimate, thesis,
        )

    def close_position(
        self, position_id: int, exit_price: Decimal, exit_date: date | None = None,
    ) -> None:
        self._positions.close_position(position_id, exit_price, exit_date)

    def create_position_atomic(
        self, ticker: str, entry_date: date, entry_price: Decimal,
        shares: Decimal, position_type: str, weight: Decimal,
        purchase_cost: Decimal, stop_loss: Decimal | None = None,
        fair_value_estimate: Decimal | None = None, thesis: str = "",
    ) -> int:
        return self._positions.create_position_atomic(
            ticker, entry_date, entry_price, shares, position_type,
            weight, purchase_cost, stop_loss, fair_value_estimate, thesis,
        )

    def close_position_atomic(
        self, position_id: int, exit_price: Decimal,
        proceeds: Decimal, exit_date: date | None = None,
    ) -> None:
        self._positions.close_position_atomic(
            position_id, exit_price, proceeds, exit_date,
        )

    def update_position_analysis(
        self, ticker: str, fair_value_estimate: Decimal | None = None,
        stop_loss: Decimal | None = None, thesis: str | None = None,
    ) -> bool:
        return self._positions.update_position_analysis(
            ticker, fair_value_estimate, stop_loss, thesis,
        )

    def get_closed_positions(self) -> list[PortfolioPosition]:
        return self._positions.get_closed_positions()

    def get_position_by_id(self, position_id: int) -> PortfolioPosition | None:
        return self._positions.get_position_by_id(position_id)

    # ------------------------------------------------------------------
    # Cron audit
    # ------------------------------------------------------------------

    def log_cron_start(self, job_name: str) -> int:
        return self._cron.log_cron_start(job_name)

    def log_cron_finish(self, cron_id: int, status: str, error: str | None = None) -> None:
        self._cron.log_cron_finish(cron_id, status, error)

    # ------------------------------------------------------------------
    # Market snapshots
    # ------------------------------------------------------------------

    def insert_market_snapshot(self, snapshot: dict) -> int:
        return self._signals.insert_market_snapshot(snapshot)

    # ------------------------------------------------------------------
    # Agent signals
    # ------------------------------------------------------------------

    def insert_agent_signals(
        self, ticker: str, agent_name: str, model: str,
        signals: dict, confidence: Decimal, reasoning: str,
        token_usage: dict | None = None, latency_ms: int | None = None,
        run_id: int | None = None,
    ) -> int:
        return self._signals.insert_agent_signals(
            ticker, agent_name, model, signals, confidence, reasoning,
            token_usage, latency_ms, run_id,
        )

    # ------------------------------------------------------------------
    # Verdicts
    # ------------------------------------------------------------------

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
        return self._verdicts.insert_verdict(
            ticker, verdict, confidence, consensus_score, reasoning,
            agent_stances, risk_flags, auditor_override, munger_override,
            advisory_opinions, board_narrative, board_adjusted_verdict,
            adversarial_result,
        )

    def get_latest_verdict(self, ticker: str) -> dict | None:
        return self._verdicts.get_latest_verdict(ticker)

    def get_verdict_history(self, ticker: str, limit: int = 20) -> list[dict]:
        return self._verdicts.get_verdict_history(ticker, limit)

    # ------------------------------------------------------------------
    # Enriched queries
    # ------------------------------------------------------------------

    def get_enriched_watchlist(self) -> list[dict]:
        return self._enriched.get_enriched_watchlist()

    def get_all_actionable_verdicts(self) -> list[dict]:
        return self._enriched.get_all_actionable_verdicts()

    def get_blocked_tickers(self) -> set[str]:
        return self._enriched.get_blocked_tickers()

    def get_watchlist_tickers_for_reanalysis(
        self, states: list[str], min_hours: int = 20,
        min_move_pct: float = 0.0, force_after_hours: int = 0,
    ) -> list[str]:
        return self._enriched.get_watchlist_tickers_for_reanalysis(
            states, min_hours, min_move_pct, force_after_hours,
        )

    def get_watch_verdicts_enriched(self) -> list[dict]:
        return self._enriched.get_watch_verdicts_enriched()

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------

    def get_sector_outcomes(self, sector: str) -> dict:
        return self._learning.get_sector_outcomes(sector)

    def get_failure_modes(self, sector: str, limit: int = 5) -> list[str]:
        return self._learning.get_failure_modes(sector, limit)

    def get_win_loss_stats(self) -> dict:
        return self._learning.get_win_loss_stats()
