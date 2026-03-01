from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from investmentology.learning.lifecycle import StockLifecycleManager
from investmentology.learning.predictions import PredictionManager
from investmentology.learning.registry import DecisionLogger
from investmentology.models.decision import Decision
from investmentology.models.lifecycle import WatchlistState
from investmentology.registry.db import Database
from investmentology.registry.queries import Registry


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=Database)


@pytest.fixture
def registry(mock_db: MagicMock) -> Registry:
    return Registry(mock_db)


@pytest.fixture
def decision_logger(registry: Registry) -> DecisionLogger:
    return DecisionLogger(registry)


@pytest.fixture
def prediction_manager(registry: Registry) -> PredictionManager:
    return PredictionManager(registry)


@pytest.fixture
def lifecycle_manager(
    registry: Registry, decision_logger: DecisionLogger
) -> StockLifecycleManager:
    return StockLifecycleManager(registry, decision_logger)


# ------------------------------------------------------------------
# TestDecisionLogger
# ------------------------------------------------------------------


class TestDecisionLogger:
    def test_log_screen_decision_creates_correct_type(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 1}]
        decision_id = decision_logger.log_screen_decision(
            run_id=42, universe_size=5000, passed_count=100
        )
        assert decision_id == 1
        # Verify the SQL was called with correct decision type
        call_args = mock_db.execute.call_args
        assert "INSERT INTO invest.decisions" in call_args[0][0]
        params = call_args[0][1]
        assert params[0] == "__BATCH__"  # ticker
        assert params[1] == "SCREEN"  # decision_type
        assert params[2] == "L1_QUANT_GATE"  # layer_source

    def test_log_screen_decision_metadata(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 2}]
        decision_logger.log_screen_decision(
            run_id=42, universe_size=5000, passed_count=100
        )
        call_args = mock_db.execute.call_args
        params = call_args[0][1]
        # metadata is the last param, JSON-encoded
        import json
        metadata = json.loads(params[6])
        assert metadata["run_id"] == 42
        assert metadata["universe_size"] == 5000
        assert metadata["passed_count"] == 100

    def test_log_competence_pass(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 3}]
        decision_id = decision_logger.log_competence_decision(
            ticker="AAPL", passed=True, reasoning="Strong moat", confidence=Decimal("0.85")
        )
        assert decision_id == 3
        params = mock_db.execute.call_args[0][1]
        assert params[0] == "AAPL"
        assert params[1] == "COMPETENCE_PASS"
        assert params[2] == "L2_COMPETENCE"

    def test_log_competence_fail(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 4}]
        decision_id = decision_logger.log_competence_decision(
            ticker="XYZ", passed=False, reasoning="No moat", confidence=Decimal("0.30")
        )
        assert decision_id == 4
        params = mock_db.execute.call_args[0][1]
        assert params[1] == "COMPETENCE_FAIL"

    def test_log_trade_decision_buy(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 5}]
        decision_id = decision_logger.log_trade_decision(
            ticker="AAPL", action="BUY", reasoning="Undervalued",
            confidence=Decimal("0.80"),
        )
        assert decision_id == 5
        params = mock_db.execute.call_args[0][1]
        assert params[1] == "BUY"

    def test_log_trade_decision_sell(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 6}]
        decision_logger.log_trade_decision(
            ticker="AAPL", action="SELL", reasoning="Overvalued",
        )
        params = mock_db.execute.call_args[0][1]
        assert params[1] == "SELL"

    def test_log_trade_decision_trim(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 7}]
        decision_logger.log_trade_decision(
            ticker="MSFT", action="trim", reasoning="Rebalance",
        )
        params = mock_db.execute.call_args[0][1]
        assert params[1] == "TRIM"

    def test_log_trade_decision_hold(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 8}]
        decision_logger.log_trade_decision(
            ticker="GOOG", action="hold", reasoning="Wait for catalyst",
        )
        params = mock_db.execute.call_args[0][1]
        assert params[1] == "HOLD"

    def test_log_trade_decision_case_insensitive(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 9}]
        decision_logger.log_trade_decision(
            ticker="AAPL", action="buy", reasoning="Test",
        )
        params = mock_db.execute.call_args[0][1]
        assert params[1] == "BUY"

    def test_log_trade_decision_unknown_action(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        with pytest.raises(ValueError, match="Unknown action"):
            decision_logger.log_trade_decision(
                ticker="AAPL", action="YOLO", reasoning="Bad idea",
            )

    def test_log_trade_decision_manual_flag(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 10}]
        decision_logger.log_trade_decision(
            ticker="AAPL", action="BUY", reasoning="Manual entry",
            metadata={"manual": True},
        )
        params = mock_db.execute.call_args[0][1]
        assert params[2] == "MANUAL"  # layer_source

    def test_log_trade_decision_automated(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 11}]
        decision_logger.log_trade_decision(
            ticker="AAPL", action="BUY", reasoning="Auto signal",
        )
        params = mock_db.execute.call_args[0][1]
        assert params[2] == "AUTOMATED"  # layer_source

    def test_all_decisions_have_timestamps_field(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        """Verify log_decision is called (it stores created_at via DB DEFAULT)."""
        mock_db.execute.return_value = [{"id": 1}]
        decision_logger.log_screen_decision(run_id=1, universe_size=100, passed_count=10)
        # The INSERT query doesn't include created_at — it relies on DB DEFAULT
        # This verifies the decision flows through to the DB correctly
        assert mock_db.execute.called

    def test_get_decision_count(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [
            {"id": 1, "ticker": "AAPL", "decision_type": "BUY", "layer_source": "L3",
             "confidence": Decimal("0.8"), "reasoning": "test", "signals": None,
             "metadata": None, "created_at": datetime(2026, 2, 10)},
            {"id": 2, "ticker": "AAPL", "decision_type": "HOLD", "layer_source": "L3",
             "confidence": Decimal("0.7"), "reasoning": "test2", "signals": None,
             "metadata": None, "created_at": datetime(2026, 2, 10)},
        ]
        count = decision_logger.get_decision_count(ticker="AAPL")
        assert count == 2

    def test_get_recent_decisions(
        self, decision_logger: DecisionLogger, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [
            {"id": 1, "ticker": "AAPL", "decision_type": "BUY", "layer_source": "L3",
             "confidence": Decimal("0.8"), "reasoning": "test", "signals": None,
             "metadata": None, "created_at": datetime(2026, 2, 10)},
        ]
        decisions = decision_logger.get_recent_decisions(limit=10)
        assert len(decisions) == 1
        assert isinstance(decisions[0], Decision)


# ------------------------------------------------------------------
# TestPredictionManager
# ------------------------------------------------------------------


class TestPredictionManager:
    def test_log_prediction_valid(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 100}]
        future_date = date.today() + timedelta(days=90)
        pred_id = prediction_manager.log_prediction(
            ticker="AAPL",
            prediction_type="price_direction",
            predicted_value=Decimal("220"),
            confidence=Decimal("0.75"),
            horizon_days=90,
            source="warren_agent",
            settlement_date=future_date,
        )
        assert pred_id == 100

    def test_log_prediction_confidence_too_high(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            prediction_manager.log_prediction(
                ticker="AAPL",
                prediction_type="price",
                predicted_value=Decimal("200"),
                confidence=Decimal("1.5"),
                horizon_days=30,
                source="test",
            )

    def test_log_prediction_confidence_negative(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            prediction_manager.log_prediction(
                ticker="AAPL",
                prediction_type="price",
                predicted_value=Decimal("200"),
                confidence=Decimal("-0.1"),
                horizon_days=30,
                source="test",
            )

    def test_log_prediction_confidence_boundary_zero(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 101}]
        # confidence=0 is valid
        pred_id = prediction_manager.log_prediction(
            ticker="AAPL",
            prediction_type="price",
            predicted_value=Decimal("200"),
            confidence=Decimal("0"),
            horizon_days=30,
            source="test",
        )
        assert pred_id == 101

    def test_log_prediction_confidence_boundary_one(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 102}]
        # confidence=1 is valid
        pred_id = prediction_manager.log_prediction(
            ticker="AAPL",
            prediction_type="price",
            predicted_value=Decimal("200"),
            confidence=Decimal("1"),
            horizon_days=30,
            source="test",
        )
        assert pred_id == 102

    def test_log_prediction_horizon_zero(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        with pytest.raises(ValueError, match="horizon_days must be > 0"):
            prediction_manager.log_prediction(
                ticker="AAPL",
                prediction_type="price",
                predicted_value=Decimal("200"),
                confidence=Decimal("0.5"),
                horizon_days=0,
                source="test",
            )

    def test_log_prediction_horizon_negative(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        with pytest.raises(ValueError, match="horizon_days must be > 0"):
            prediction_manager.log_prediction(
                ticker="AAPL",
                prediction_type="price",
                predicted_value=Decimal("200"),
                confidence=Decimal("0.5"),
                horizon_days=-10,
                source="test",
            )

    def test_log_prediction_calculates_settlement_from_horizon(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 103}]
        prediction_manager.log_prediction(
            ticker="AAPL",
            prediction_type="price",
            predicted_value=Decimal("200"),
            confidence=Decimal("0.7"),
            horizon_days=90,
            source="test",
        )
        # Verify the Prediction passed to log_prediction has correct settlement_date
        call_args = mock_db.execute.call_args[0][1]
        expected_date = date.today() + timedelta(days=90)
        assert call_args[5] == expected_date  # settlement_date param

    def test_log_prediction_rejects_past_settlement(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        past_date = date.today() - timedelta(days=1)
        with pytest.raises(ValueError, match="settlement_date must be in the future"):
            prediction_manager.log_prediction(
                ticker="AAPL",
                prediction_type="price",
                predicted_value=Decimal("200"),
                confidence=Decimal("0.7"),
                horizon_days=30,
                source="test",
                settlement_date=past_date,
            )

    def test_log_prediction_rejects_today_settlement(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        with pytest.raises(ValueError, match="settlement_date must be in the future"):
            prediction_manager.log_prediction(
                ticker="AAPL",
                prediction_type="price",
                predicted_value=Decimal("200"),
                confidence=Decimal("0.7"),
                horizon_days=30,
                source="test",
                settlement_date=date.today(),
            )

    def test_settle_due_predictions_returns_settled_ids(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        # get_unsettled_predictions returns due predictions
        mock_db.execute.side_effect = [
            # get_unsettled_predictions query
            [
                {"id": 5, "ticker": "AAPL", "prediction_type": "price",
                 "predicted_value": Decimal("200"), "confidence": Decimal("0.70"),
                 "horizon_days": 90, "settlement_date": date(2026, 2, 1),
                 "actual_value": None, "is_settled": False, "settled_at": None,
                 "source": "warren", "created_at": datetime(2025, 11, 1)},
                {"id": 6, "ticker": "MSFT", "prediction_type": "price",
                 "predicted_value": Decimal("400"), "confidence": Decimal("0.80"),
                 "horizon_days": 60, "settlement_date": date(2026, 1, 15),
                 "actual_value": None, "is_settled": False, "settled_at": None,
                 "source": "soros", "created_at": datetime(2025, 11, 15)},
            ],
            # settle_prediction calls (one per prediction)
            [],
            [],
        ]
        settled = prediction_manager.settle_due_predictions(as_of=date(2026, 2, 10))
        assert len(settled) == 2
        assert settled[0][0] == 5
        assert settled[1][0] == 6

    def test_settle_due_predictions_empty(
        self, prediction_manager: PredictionManager, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = []
        settled = prediction_manager.settle_due_predictions(as_of=date(2026, 2, 10))
        assert settled == []

    def test_get_calibration_data_structure(
        self, prediction_manager: PredictionManager
    ) -> None:
        result = prediction_manager.get_calibration_data()
        assert "total_settled" in result
        assert "total_correct" in result
        assert "buckets" in result
        assert "ece" in result
        assert "brier" in result
        assert len(result["buckets"]) == 5

    def test_compute_calibration_with_data(self) -> None:
        """Test the static calibration computation helper directly."""
        settled = [
            (Decimal("0.55"), True),
            (Decimal("0.55"), False),
            (Decimal("0.75"), True),
            (Decimal("0.75"), True),
            (Decimal("0.75"), False),
            (Decimal("0.95"), True),
        ]
        result = PredictionManager._compute_calibration(settled)
        assert result["total_settled"] == 6
        assert result["total_correct"] == 4
        # Check bucket counts
        bucket_05 = result["buckets"][0]  # 0.5-0.6
        assert bucket_05["count"] == 2
        assert bucket_05["correct"] == 1
        assert bucket_05["accuracy"] == 0.5

        bucket_07 = result["buckets"][2]  # 0.7-0.8
        assert bucket_07["count"] == 3
        assert bucket_07["correct"] == 2
        assert abs(bucket_07["accuracy"] - 2 / 3) < 1e-9

        bucket_09 = result["buckets"][4]  # 0.9-1.0
        assert bucket_09["count"] == 1
        assert bucket_09["correct"] == 1
        assert bucket_09["accuracy"] == 1.0

        assert result["ece"] >= 0
        assert result["brier"] >= 0

    def test_compute_calibration_empty(self) -> None:
        result = PredictionManager._compute_calibration([])
        assert result["total_settled"] == 0
        assert result["total_correct"] == 0
        assert result["ece"] == 0.0
        assert result["brier"] == 0.0


# ------------------------------------------------------------------
# TestStockLifecycleManager
# ------------------------------------------------------------------


class TestStockLifecycleManager:
    def test_transition_logs_decision(
        self, lifecycle_manager: StockLifecycleManager, mock_db: MagicMock
    ) -> None:
        # update_watchlist_state: first call returns current state, second does update
        # log_decision for the audit trail
        mock_db.execute.side_effect = [
            [{"state": "CANDIDATE"}],  # current state lookup
            [],  # update watchlist state
            [{"id": 20}],  # log_decision
        ]
        lifecycle_manager.transition(
            ticker="AAPL",
            new_state=WatchlistState.ASSESSED,
            reason="Passed L2 competence",
            layer_source="L2_COMPETENCE",
            confidence=Decimal("0.80"),
        )
        # Verify 3 execute calls: state lookup, state update, decision log
        assert mock_db.execute.call_count == 3
        # Third call should be the decision INSERT
        decision_call = mock_db.execute.call_args_list[2]
        assert "INSERT INTO invest.decisions" in decision_call[0][0]
        params = decision_call[0][1]
        assert params[0] == "AAPL"
        assert params[1] == "WATCHLIST"

    def test_transition_raises_on_invalid(
        self, lifecycle_manager: StockLifecycleManager, mock_db: MagicMock
    ) -> None:
        # update_watchlist_state with invalid transition
        mock_db.execute.return_value = [{"state": "CANDIDATE"}]
        with pytest.raises(ValueError, match="Invalid transition"):
            lifecycle_manager.transition(
                ticker="AAPL",
                new_state=WatchlistState.POSITION_HOLD,
                reason="Skip the queue",
                layer_source="TEST",
            )

    def test_transition_raises_ticker_not_found(
        self, lifecycle_manager: StockLifecycleManager, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = []
        with pytest.raises(ValueError, match="not found"):
            lifecycle_manager.transition(
                ticker="UNKNOWN",
                new_state=WatchlistState.ASSESSED,
                reason="test",
                layer_source="TEST",
            )

    def test_promote_candidates(
        self, lifecycle_manager: StockLifecycleManager, mock_db: MagicMock
    ) -> None:
        mock_db.execute.return_value = [{"id": 1}]
        count = lifecycle_manager.promote_candidates(
            tickers=["AAPL", "MSFT", "GOOG"], source_run_id=42
        )
        assert count == 3
        # Verify add_to_watchlist was called for each ticker
        assert mock_db.execute.call_count == 3
        for i, ticker in enumerate(["AAPL", "MSFT", "GOOG"]):
            call_args = mock_db.execute.call_args_list[i]
            assert "INSERT INTO invest.watchlist" in call_args[0][0]
            params = call_args[0][1]
            assert params[0] == ticker
            assert params[1] == "CANDIDATE"
            assert params[2] == 42  # source_run_id

    def test_promote_candidates_empty(
        self, lifecycle_manager: StockLifecycleManager, mock_db: MagicMock
    ) -> None:
        count = lifecycle_manager.promote_candidates(tickers=[], source_run_id=42)
        assert count == 0
        assert mock_db.execute.call_count == 0

    def test_get_pipeline_summary(
        self, lifecycle_manager: StockLifecycleManager, mock_db: MagicMock
    ) -> None:
        def mock_execute(query: str, params: tuple | None = None) -> list[dict]:
            if params is None:
                return []
            state_val = params[0]
            if state_val == "CANDIDATE":
                return [{"id": 1, "ticker": "AAPL"}, {"id": 2, "ticker": "MSFT"}]
            if state_val == "ASSESSED":
                return [{"id": 3, "ticker": "GOOG"}]
            return []

        mock_db.execute.side_effect = mock_execute

        summary = lifecycle_manager.get_pipeline_summary()
        assert summary["CANDIDATE"] == 2
        assert summary["ASSESSED"] == 1
        assert summary["UNIVERSE"] == 0
        assert summary["REJECTED"] == 0
        # All states should be present
        for state in WatchlistState:
            assert state.value in summary
