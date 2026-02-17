from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest

from investmentology.models.decision import Decision, DecisionType
from investmentology.models.lifecycle import WatchlistState
from investmentology.models.position import PortfolioPosition
from investmentology.models.prediction import Prediction
from investmentology.models.stock import FundamentalsSnapshot, Stock
from investmentology.registry.db import Database
from investmentology.registry.queries import Registry


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock(spec=Database)
    return db


@pytest.fixture
def registry(mock_db: MagicMock) -> Registry:
    return Registry(mock_db)


# ------------------------------------------------------------------
# Stock universe
# ------------------------------------------------------------------


class TestUpsertStocks:
    def test_upsert_calls_execute_many(self, registry: Registry, mock_db: MagicMock) -> None:
        stocks = [
            Stock(ticker="AAPL", name="Apple", sector="Tech", industry="Consumer Electronics",
                  market_cap=Decimal("3000000000000"), exchange="NASDAQ"),
            Stock(ticker="MSFT", name="Microsoft", sector="Tech", industry="Software",
                  market_cap=Decimal("2800000000000"), exchange="NASDAQ"),
        ]
        mock_db.execute_many.return_value = 2
        result = registry.upsert_stocks(stocks)
        assert result == 2
        mock_db.execute_many.assert_called_once()
        args = mock_db.execute_many.call_args
        assert "INSERT INTO invest.stocks" in args[0][0]
        assert len(args[0][1]) == 2

    def test_upsert_empty_list(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute_many.return_value = 0
        result = registry.upsert_stocks([])
        assert result == 0


class TestGetActiveStocks:
    def test_returns_stock_objects(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"ticker": "AAPL", "name": "Apple", "sector": "Tech", "industry": "CE",
             "market_cap": Decimal("3000000000000"), "exchange": "NASDAQ", "is_active": True},
        ]
        stocks = registry.get_active_stocks()
        assert len(stocks) == 1
        assert stocks[0].ticker == "AAPL"
        assert isinstance(stocks[0], Stock)

    def test_handles_null_fields(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"ticker": "XYZ", "name": "Unknown", "sector": None, "industry": None,
             "market_cap": None, "exchange": None, "is_active": True},
        ]
        stocks = registry.get_active_stocks()
        assert stocks[0].sector == ""
        assert stocks[0].market_cap == Decimal(0)


# ------------------------------------------------------------------
# Fundamentals
# ------------------------------------------------------------------


class TestFundamentals:
    def test_insert_fundamentals(self, registry: Registry, mock_db: MagicMock) -> None:
        snapshot = FundamentalsSnapshot(
            ticker="AAPL", fetched_at=datetime(2026, 2, 10),
            operating_income=Decimal("120000000000"), market_cap=Decimal("3000000000000"),
            total_debt=Decimal("100000000000"), cash=Decimal("60000000000"),
            current_assets=Decimal("150000000000"), current_liabilities=Decimal("120000000000"),
            net_ppe=Decimal("40000000000"), revenue=Decimal("400000000000"),
            net_income=Decimal("100000000000"), total_assets=Decimal("350000000000"),
            total_liabilities=Decimal("250000000000"), shares_outstanding=15000000000,
            price=Decimal("200"),
        )
        mock_db.execute_many.return_value = 1
        result = registry.insert_fundamentals([snapshot])
        assert result == 1

    def test_get_latest_fundamentals_found(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"ticker": "AAPL", "fetched_at": datetime(2026, 2, 10),
             "operating_income": Decimal("120e9"), "market_cap": Decimal("3000e9"),
             "total_debt": Decimal("100e9"), "cash": Decimal("60e9"),
             "current_assets": Decimal("150e9"), "current_liabilities": Decimal("120e9"),
             "net_ppe": Decimal("40e9"), "revenue": Decimal("400e9"),
             "net_income": Decimal("100e9"), "total_assets": Decimal("350e9"),
             "total_liabilities": Decimal("250e9"), "shares_outstanding": 15000000000,
             "price": Decimal("200")},
        ]
        result = registry.get_latest_fundamentals("AAPL")
        assert result is not None
        assert result.ticker == "AAPL"
        assert isinstance(result, FundamentalsSnapshot)

    def test_get_latest_fundamentals_not_found(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        result = registry.get_latest_fundamentals("UNKNOWN")
        assert result is None


# ------------------------------------------------------------------
# Quant Gate
# ------------------------------------------------------------------


class TestQuantGate:
    def test_create_run(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [{"id": 42}]
        run_id = registry.create_quant_gate_run(
            universe_size=5847, passed_count=100,
            config={"top_n": 100}, data_quality={"coverage": 0.94},
        )
        assert run_id == 42

    def test_insert_results(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute_many.return_value = 2
        results = [
            {"ticker": "AAPL", "earnings_yield": Decimal("0.15"), "roic": Decimal("0.40"),
             "ey_rank": 5, "roic_rank": 3, "combined_rank": 8, "piotroski_score": 7,
             "altman_z_score": Decimal("3.2")},
            {"ticker": "MSFT", "earnings_yield": Decimal("0.12"), "roic": Decimal("0.35"),
             "ey_rank": 10, "roic_rank": 7, "combined_rank": 17, "piotroski_score": 8,
             "altman_z_score": Decimal("4.1")},
        ]
        count = registry.insert_quant_gate_results(run_id=42, results=results)
        assert count == 2


# ------------------------------------------------------------------
# Decisions
# ------------------------------------------------------------------


class TestDecisions:
    def test_log_decision(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [{"id": 1}]
        decision = Decision(
            ticker="AAPL",
            decision_type=DecisionType.BUY,
            layer_source="L3_AGENT",
            confidence=Decimal("0.84"),
            reasoning="Strong fundamentals and momentum",
            signals={"tags": ["UNDERVALUED", "MOMENTUM_STRONG"]},
        )
        decision_id = registry.log_decision(decision)
        assert decision_id == 1
        args = mock_db.execute.call_args
        assert "INSERT INTO invest.decisions" in args[0][0]

    def test_get_decisions_no_filter(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"id": 1, "ticker": "AAPL", "decision_type": "BUY", "layer_source": "L3",
             "confidence": Decimal("0.84"), "reasoning": "test", "signals": None,
             "metadata": None, "created_at": datetime(2026, 2, 10)},
        ]
        decisions = registry.get_decisions()
        assert len(decisions) == 1
        assert decisions[0].decision_type == DecisionType.BUY

    def test_get_decisions_with_filter(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        decisions = registry.get_decisions(ticker="AAPL", decision_type=DecisionType.BUY)
        assert decisions == []
        query = mock_db.execute.call_args[0][0]
        assert "ticker = %s" in query
        assert "decision_type = %s" in query


# ------------------------------------------------------------------
# Predictions
# ------------------------------------------------------------------


class TestPredictions:
    def test_log_prediction(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [{"id": 10}]
        pred = Prediction(
            ticker="AAPL",
            prediction_type="price_direction",
            predicted_value=Decimal("215"),
            confidence=Decimal("0.72"),
            horizon_days=365,
            settlement_date=date(2027, 2, 10),
            source="warren_agent",
        )
        pred_id = registry.log_prediction(pred)
        assert pred_id == 10

    def test_settle_prediction(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        registry.settle_prediction(prediction_id=10, actual_value=Decimal("220"))
        args = mock_db.execute.call_args
        assert "UPDATE invest.predictions" in args[0][0]
        assert args[0][1] == (Decimal("220"), 10)

    def test_get_unsettled(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"id": 5, "ticker": "AAPL", "prediction_type": "price",
             "predicted_value": Decimal("200"), "confidence": Decimal("0.70"),
             "horizon_days": 90, "settlement_date": date(2026, 2, 1),
             "actual_value": None, "is_settled": False, "settled_at": None,
             "source": "warren", "created_at": datetime(2025, 11, 1)},
        ]
        preds = registry.get_unsettled_predictions(as_of=date(2026, 2, 10))
        assert len(preds) == 1
        assert preds[0].ticker == "AAPL"
        assert preds[0].is_settled is False


# ------------------------------------------------------------------
# Watchlist
# ------------------------------------------------------------------


class TestWatchlist:
    def test_add_to_watchlist(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [{"id": 1}]
        wl_id = registry.add_to_watchlist("AAPL", WatchlistState.CANDIDATE, source_run_id=42)
        assert wl_id == 1

    def test_update_state_valid_transition(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.side_effect = [
            [{"state": "CANDIDATE"}],  # current state lookup
            [],  # update
        ]
        registry.update_watchlist_state("AAPL", WatchlistState.ASSESSED)
        assert mock_db.execute.call_count == 2

    def test_update_state_invalid_transition(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [{"state": "CANDIDATE"}]
        with pytest.raises(ValueError, match="Invalid transition"):
            registry.update_watchlist_state("AAPL", WatchlistState.POSITION_HOLD)

    def test_update_state_not_found(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        with pytest.raises(ValueError, match="not found"):
            registry.update_watchlist_state("UNKNOWN", WatchlistState.ASSESSED)


# ------------------------------------------------------------------
# Portfolio positions
# ------------------------------------------------------------------


class TestPositions:
    def test_get_open_positions(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"id": 1, "ticker": "AAPL", "entry_date": date(2026, 1, 17),
             "entry_price": Decimal("180"), "current_price": Decimal("200"),
             "shares": Decimal("50"), "position_type": "core", "weight": Decimal("0.048"),
             "stop_loss": Decimal("153"), "fair_value_estimate": Decimal("225"),
             "thesis": "Strong moat", "updated_at": datetime(2026, 2, 10),
             "created_at": datetime(2026, 1, 17)},
        ]
        positions = registry.get_open_positions()
        assert len(positions) == 1
        assert positions[0].ticker == "AAPL"
        assert positions[0].pnl_pct > 0


# ------------------------------------------------------------------
# Cron audit
# ------------------------------------------------------------------


class TestCronAudit:
    def test_log_cron_start(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [{"id": 99}]
        cron_id = registry.log_cron_start("quant-gate-weekly")
        assert cron_id == 99

    def test_log_cron_finish(self, registry: Registry, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        registry.log_cron_finish(99, status="success")
        args = mock_db.execute.call_args
        assert "UPDATE invest.cron_runs" in args[0][0]
