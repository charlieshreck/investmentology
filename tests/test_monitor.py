from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from investmentology.data.alerts import (
    Alert,
    AlertEngine,
    AlertSeverity,
    AlertType,
)
from investmentology.data.monitor import DailyMonitor, MonitorResult
from investmentology.data.yfinance_client import YFinanceClient
from investmentology.models.position import PortfolioPosition
from investmentology.models.prediction import Prediction
from investmentology.registry.queries import Registry


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_position(
    ticker: str = "AAPL",
    entry_price: Decimal = Decimal("150"),
    current_price: Decimal = Decimal("155"),
    shares: Decimal = Decimal("100"),
    weight: Decimal = Decimal("0.05"),
    stop_loss: Decimal | None = Decimal("140"),
    position_type: str = "core",
) -> PortfolioPosition:
    return PortfolioPosition(
        ticker=ticker,
        entry_date=date(2025, 1, 1),
        entry_price=entry_price,
        current_price=current_price,
        shares=shares,
        position_type=position_type,
        weight=weight,
        stop_loss=stop_loss,
    )


# ------------------------------------------------------------------
# AlertEngine: stop losses
# ------------------------------------------------------------------


class TestCheckStopLosses:
    def test_triggered_when_price_below_stop(self) -> None:
        engine = AlertEngine()
        pos = _make_position(current_price=Decimal("135"), stop_loss=Decimal("140"))
        alerts = engine.check_stop_losses([pos])

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.STOP_LOSS_TRIGGERED
        assert alerts[0].severity == AlertSeverity.ERROR
        assert alerts[0].ticker == "AAPL"

    def test_triggered_when_price_equals_stop(self) -> None:
        engine = AlertEngine()
        pos = _make_position(current_price=Decimal("140"), stop_loss=Decimal("140"))
        alerts = engine.check_stop_losses([pos])

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.STOP_LOSS_TRIGGERED

    def test_approaching_when_within_warning_pct(self) -> None:
        engine = AlertEngine(stop_loss_warning_pct=Decimal("0.02"))
        # Stop at 140, warning threshold = 140 * 1.02 = 142.80
        pos = _make_position(current_price=Decimal("141"), stop_loss=Decimal("140"))
        alerts = engine.check_stop_losses([pos])

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.STOP_LOSS_APPROACHING
        assert alerts[0].severity == AlertSeverity.WARNING

    def test_no_alert_when_price_safely_above_stop(self) -> None:
        engine = AlertEngine()
        pos = _make_position(current_price=Decimal("155"), stop_loss=Decimal("140"))
        alerts = engine.check_stop_losses([pos])

        assert len(alerts) == 0

    def test_no_alert_when_no_stop_loss(self) -> None:
        engine = AlertEngine()
        pos = _make_position(stop_loss=None)
        alerts = engine.check_stop_losses([pos])

        assert len(alerts) == 0


# ------------------------------------------------------------------
# AlertEngine: position concentration
# ------------------------------------------------------------------


class TestCheckConcentration:
    def test_warns_when_above_limit(self) -> None:
        engine = AlertEngine(max_position_pct=Decimal("0.40"))
        positions = [
            _make_position(ticker="AAPL", current_price=Decimal("100"), shares=Decimal("500")),
            _make_position(ticker="MSFT", current_price=Decimal("100"), shares=Decimal("100")),
        ]
        # AAPL: 50000 / 60000 = 83%  > 40%
        alerts = engine.check_concentration(positions)

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.POSITION_CONCENTRATION
        assert alerts[0].ticker == "AAPL"

    def test_no_alert_when_within_limit(self) -> None:
        engine = AlertEngine(max_position_pct=Decimal("0.60"))
        positions = [
            _make_position(ticker="AAPL", current_price=Decimal("100"), shares=Decimal("100")),
            _make_position(ticker="MSFT", current_price=Decimal("100"), shares=Decimal("100")),
        ]
        # Both at 50%, below 60%
        alerts = engine.check_concentration(positions)

        assert len(alerts) == 0

    def test_no_alert_when_empty_portfolio(self) -> None:
        engine = AlertEngine()
        alerts = engine.check_concentration([])

        assert len(alerts) == 0


# ------------------------------------------------------------------
# AlertEngine: sector concentration
# ------------------------------------------------------------------


class TestCheckSectorConcentration:
    def test_warns_when_sector_above_limit(self) -> None:
        engine = AlertEngine(max_sector_pct=Decimal("0.30"))
        positions = [
            _make_position(ticker="AAPL", current_price=Decimal("100"), shares=Decimal("400")),
            _make_position(ticker="MSFT", current_price=Decimal("100"), shares=Decimal("300")),
            _make_position(ticker="JPM", current_price=Decimal("100"), shares=Decimal("300")),
        ]
        sector_map = {"AAPL": "Tech", "MSFT": "Tech", "JPM": "Finance"}
        # Tech: 70000/100000 = 70% > 30%
        alerts = engine.check_sector_concentration(positions, sector_map)

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.SECTOR_CONCENTRATION
        assert "Tech" in alerts[0].message

    def test_no_alert_when_sectors_balanced(self) -> None:
        engine = AlertEngine(max_sector_pct=Decimal("0.60"))
        positions = [
            _make_position(ticker="AAPL", current_price=Decimal("100"), shares=Decimal("100")),
            _make_position(ticker="JPM", current_price=Decimal("100"), shares=Decimal("100")),
        ]
        sector_map = {"AAPL": "Tech", "JPM": "Finance"}
        alerts = engine.check_sector_concentration(positions, sector_map)

        assert len(alerts) == 0


# ------------------------------------------------------------------
# AlertEngine: circuit breakers
# ------------------------------------------------------------------


class TestCheckCircuitBreakers:
    def test_l1_on_elevated_vix(self) -> None:
        engine = AlertEngine()
        alerts = engine.check_circuit_breakers(Decimal("26"), Decimal("0"))

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.CIRCUIT_BREAKER_L1
        assert alerts[0].severity == AlertSeverity.WARNING

    def test_l1_on_spy_drawdown(self) -> None:
        engine = AlertEngine()
        alerts = engine.check_circuit_breakers(Decimal("15"), Decimal("6"))

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.CIRCUIT_BREAKER_L1

    def test_l2_on_high_vix(self) -> None:
        engine = AlertEngine()
        alerts = engine.check_circuit_breakers(Decimal("36"), Decimal("0"))

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.CIRCUIT_BREAKER_L2
        assert alerts[0].severity == AlertSeverity.ERROR

    def test_l2_on_spy_drawdown(self) -> None:
        engine = AlertEngine()
        alerts = engine.check_circuit_breakers(Decimal("15"), Decimal("11"))

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.CIRCUIT_BREAKER_L2

    def test_l3_on_extreme_vix(self) -> None:
        engine = AlertEngine()
        alerts = engine.check_circuit_breakers(Decimal("50"), Decimal("0"))

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.CIRCUIT_BREAKER_L3
        assert alerts[0].severity == AlertSeverity.CRITICAL

    def test_l3_on_spy_crash(self) -> None:
        engine = AlertEngine()
        alerts = engine.check_circuit_breakers(Decimal("15"), Decimal("16"))

        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.CIRCUIT_BREAKER_L3

    def test_no_alert_when_calm(self) -> None:
        engine = AlertEngine()
        alerts = engine.check_circuit_breakers(Decimal("15"), Decimal("2"))

        assert len(alerts) == 0


# ------------------------------------------------------------------
# AlertEngine: evaluate_all sorted by severity
# ------------------------------------------------------------------


class TestEvaluateAll:
    def test_returns_sorted_critical_first(self) -> None:
        engine = AlertEngine(max_position_pct=Decimal("0.01"))
        positions = [
            _make_position(
                ticker="AAPL",
                current_price=Decimal("135"),
                stop_loss=Decimal("140"),
                shares=Decimal("100"),
            ),
        ]
        sector_map = {"AAPL": "Tech"}
        # Stop loss triggered (ERROR) + position concentration (WARNING) + L3 breaker (CRITICAL)
        alerts = engine.evaluate_all(
            positions, sector_map, vix=Decimal("50"), spy_drawdown_pct=Decimal("0"),
        )

        assert len(alerts) >= 2
        # First alert should be CRITICAL
        assert alerts[0].severity == AlertSeverity.CRITICAL
        # Verify ordering: each alert severity >= next
        from investmentology.data.alerts import _SEVERITY_ORDER
        for i in range(len(alerts) - 1):
            assert _SEVERITY_ORDER[alerts[i].severity] >= _SEVERITY_ORDER[alerts[i + 1].severity]


# ------------------------------------------------------------------
# DailyMonitor: full run cycle
# ------------------------------------------------------------------


class TestDailyMonitorRun:
    def test_run_executes_full_cycle(self) -> None:
        mock_registry = MagicMock(spec=Registry)
        mock_yf = MagicMock(spec=YFinanceClient)
        engine = AlertEngine()

        # Setup: registry returns positions
        positions = [
            _make_position(ticker="AAPL"),
            _make_position(ticker="MSFT", stop_loss=Decimal("200")),
        ]
        mock_registry.get_open_positions.return_value = positions
        mock_registry.log_cron_start.return_value = 42
        mock_registry.insert_market_snapshot.return_value = 99

        # YF returns prices
        mock_yf.get_prices_batch.return_value = {
            "AAPL": Decimal("160"),
            "MSFT": Decimal("310"),
        }

        # No unsettled predictions
        mock_registry.get_unsettled_predictions.return_value = []

        # Mock fetch_market_snapshot
        with patch("investmentology.data.monitor.fetch_market_snapshot") as mock_snap:
            mock_snap.return_value = {
                "snapshot_date": date.today(),
                "spy_price": Decimal("450"),
                "vix": Decimal("15"),
            }

            monitor = DailyMonitor(mock_registry, mock_yf, engine)
            result = monitor.run()

        assert result.cron_run_id == 42
        assert result.market_snapshot_id == 99
        assert result.positions_updated == 2
        assert result.predictions_settled == 0
        assert result.duration_seconds > 0
        mock_registry.log_cron_start.assert_called_once_with("daily_monitor")
        mock_registry.log_cron_finish.assert_called_once_with(42, "success")

    def test_run_settles_predictions(self) -> None:
        mock_registry = MagicMock(spec=Registry)
        mock_yf = MagicMock(spec=YFinanceClient)
        engine = AlertEngine()

        mock_registry.get_open_positions.return_value = []
        mock_registry.log_cron_start.return_value = 1
        mock_registry.insert_market_snapshot.return_value = 1

        prediction = Prediction(
            id=10,
            ticker="AAPL",
            prediction_type="price_target",
            predicted_value=Decimal("180"),
            confidence=Decimal("0.70"),
            horizon_days=30,
            settlement_date=date.today(),
            source="L3_warren",
        )
        mock_registry.get_unsettled_predictions.return_value = [prediction]
        mock_yf.get_price.return_value = Decimal("175")

        with patch("investmentology.data.monitor.fetch_market_snapshot") as mock_snap:
            mock_snap.return_value = {"vix": Decimal("15")}

            monitor = DailyMonitor(mock_registry, mock_yf, engine)
            result = monitor.run()

        assert result.predictions_settled == 1
        mock_registry.settle_prediction.assert_called_once_with(10, Decimal("175"))

    def test_run_logs_error_on_failure(self) -> None:
        mock_registry = MagicMock(spec=Registry)
        mock_yf = MagicMock(spec=YFinanceClient)
        engine = AlertEngine()

        mock_registry.log_cron_start.return_value = 5
        mock_registry.get_open_positions.side_effect = RuntimeError("DB down")

        monitor = DailyMonitor(mock_registry, mock_yf, engine)
        with pytest.raises(RuntimeError, match="DB down"):
            monitor.run()

        mock_registry.log_cron_finish.assert_called_once()
        args = mock_registry.log_cron_finish.call_args
        assert args[0][0] == 5
        assert args[0][1] == "error"
        assert "DB down" in args[0][2]


# ------------------------------------------------------------------
# DailyMonitor: premarket
# ------------------------------------------------------------------


class TestDailyMonitorPremarket:
    def test_premarket_only_checks_breakers_and_stops(self) -> None:
        mock_registry = MagicMock(spec=Registry)
        mock_yf = MagicMock(spec=YFinanceClient)
        engine = AlertEngine()

        positions = [
            _make_position(
                ticker="AAPL",
                current_price=Decimal("135"),
                stop_loss=Decimal("140"),
            ),
        ]
        mock_registry.get_open_positions.return_value = positions
        mock_registry.log_cron_start.return_value = 7

        # VIX at 30 -> L1 breaker
        mock_yf.get_price.return_value = Decimal("30")

        monitor = DailyMonitor(mock_registry, mock_yf, engine)
        result = monitor.run_premarket()

        assert result.cron_run_id == 7
        # Should have stop loss triggered + L1 circuit breaker
        alert_types = [a.alert_type for a in result.alerts]
        assert AlertType.STOP_LOSS_TRIGGERED in alert_types
        assert AlertType.CIRCUIT_BREAKER_L1 in alert_types
        # Should NOT have called settle_prediction or insert_market_snapshot
        mock_registry.get_unsettled_predictions.assert_not_called()
        mock_registry.insert_market_snapshot.assert_not_called()

    def test_premarket_no_alerts_when_calm(self) -> None:
        mock_registry = MagicMock(spec=Registry)
        mock_yf = MagicMock(spec=YFinanceClient)
        engine = AlertEngine()

        positions = [
            _make_position(current_price=Decimal("155"), stop_loss=Decimal("140")),
        ]
        mock_registry.get_open_positions.return_value = positions
        mock_registry.log_cron_start.return_value = 8

        mock_yf.get_price.return_value = Decimal("15")  # Calm VIX

        monitor = DailyMonitor(mock_registry, mock_yf, engine)
        result = monitor.run_premarket()

        assert len(result.alerts) == 0
