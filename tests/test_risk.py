"""Tests for risk management: drawdown engine + VaR."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from investmentology.models.position import PortfolioPosition
from investmentology.risk.drawdown import DrawdownEngine, RiskSnapshot, _classify_risk


def _make_position(ticker: str, price: float, shares: float) -> PortfolioPosition:
    return PortfolioPosition(
        ticker=ticker,
        entry_date=date(2025, 1, 1),
        entry_price=Decimal(str(price)),
        current_price=Decimal(str(price)),
        shares=Decimal(str(shares)),
        position_type="core",
        weight=Decimal("0"),
    )


class TestClassifyRisk:
    def test_normal(self):
        assert _classify_risk(0) == "NORMAL"
        assert _classify_risk(5) == "NORMAL"
        assert _classify_risk(9.9) == "NORMAL"

    def test_elevated(self):
        assert _classify_risk(10) == "ELEVATED"
        assert _classify_risk(14.9) == "ELEVATED"

    def test_high(self):
        assert _classify_risk(15) == "HIGH"
        assert _classify_risk(19.9) == "HIGH"

    def test_critical(self):
        assert _classify_risk(20) == "CRITICAL"
        assert _classify_risk(50) == "CRITICAL"


class TestDrawdownEngine:
    def _make_engine(self, hwm: float = 0) -> tuple[DrawdownEngine, MagicMock]:
        mock_db = MagicMock()
        # Mock the HWM query
        mock_db.execute.return_value = [{"hwm": Decimal(str(hwm))}]
        engine = DrawdownEngine(mock_db)
        return engine, mock_db

    def test_compute_snapshot_no_drawdown(self):
        engine, mock_db = self._make_engine(hwm=0)
        positions = [_make_position("AAPL", 100, 10)]  # $1000
        cash = Decimal("500")

        snapshot = engine.compute_snapshot(positions, cash)
        assert snapshot.total_value == Decimal("1500")
        assert snapshot.high_water_mark == Decimal("1500")  # New HWM
        assert snapshot.drawdown_pct == Decimal("0")
        assert snapshot.risk_level == "NORMAL"
        assert snapshot.position_count == 1

    def test_compute_snapshot_with_drawdown(self):
        engine, mock_db = self._make_engine(hwm=2000)
        positions = [_make_position("AAPL", 100, 10)]  # $1000
        cash = Decimal("500")

        snapshot = engine.compute_snapshot(positions, cash)
        assert snapshot.total_value == Decimal("1500")
        assert snapshot.high_water_mark == Decimal("2000")  # Previous HWM retained
        # Drawdown = (2000 - 1500) / 2000 * 100 = 25%
        assert float(snapshot.drawdown_pct) == 25.0
        assert snapshot.risk_level == "CRITICAL"

    def test_compute_snapshot_new_hwm(self):
        engine, mock_db = self._make_engine(hwm=1000)
        positions = [_make_position("AAPL", 200, 10)]  # $2000
        cash = Decimal("500")

        snapshot = engine.compute_snapshot(positions, cash)
        assert snapshot.high_water_mark == Decimal("2500")  # New HWM

    def test_compute_snapshot_empty_portfolio(self):
        engine, mock_db = self._make_engine(hwm=1000)
        snapshot = engine.compute_snapshot([], Decimal("500"))
        assert snapshot.total_value == Decimal("500")
        assert snapshot.position_count == 0

    def test_top_position_weight(self):
        engine, mock_db = self._make_engine(hwm=0)
        # Sector lookup mock
        def mock_execute(query, params=None):
            if "MAX(high_water_mark)" in query:
                return [{"hwm": Decimal("0")}]
            if "sector" in query.lower():
                return [{"sector": "Technology"}]
            return []
        mock_db.execute.side_effect = mock_execute

        positions = [
            _make_position("AAPL", 100, 10),  # $1000
            _make_position("MSFT", 100, 5),   # $500
        ]
        cash = Decimal("0")
        snapshot = engine.compute_snapshot(positions, cash)
        # Top weight = 1000/1500 * 100 = 66.67%
        assert float(snapshot.top_position_weight) > 66

    def test_save_snapshot(self):
        engine, mock_db = self._make_engine()
        snapshot = RiskSnapshot(
            snapshot_date=date.today(),
            total_value=Decimal("1000"),
            position_count=1,
            drawdown_pct=Decimal("5"),
            high_water_mark=Decimal("1050"),
            sector_concentration={"Technology": 100.0},
            top_position_weight=Decimal("100"),
            risk_level="NORMAL",
        )
        engine.save_snapshot(snapshot)
        mock_db.execute.assert_called()
        call_sql = mock_db.execute.call_args[0][0]
        assert "INSERT INTO invest.portfolio_risk_snapshots" in call_sql
        assert "ON CONFLICT" in call_sql

    def test_get_max_drawdown(self):
        engine, mock_db = self._make_engine()
        mock_db.execute.return_value = [{"max_dd": Decimal("12.5")}]
        result = engine.get_max_drawdown(days=252)
        assert result == Decimal("12.5")

    def test_get_history(self):
        engine, mock_db = self._make_engine()
        mock_db.execute.return_value = [
            {
                "snapshot_date": date(2026, 3, 1),
                "total_value": Decimal("50000"),
                "portfolio_drawdown_pct": Decimal("5.2"),
                "high_water_mark": Decimal("52750"),
                "risk_level": "NORMAL",
                "sector_concentration": {"Tech": 40},
                "top_position_weight": Decimal("15.3"),
            }
        ]
        history = engine.get_history(days=90)
        assert len(history) == 1
        assert history[0]["date"] == "2026-03-01"
        assert history[0]["riskLevel"] == "NORMAL"


class TestVaRResult:
    def test_dataclass_fields(self):
        from investmentology.risk.var import VaRResult
        result = VaRResult(
            var_95=1.5,
            var_99=2.8,
            cvar_95=2.1,
            dollar_var_95=750.0,
            horizon_days=1,
            observation_count=252,
        )
        assert result.var_95 == 1.5
        assert result.dollar_var_95 == 750.0
        assert result.horizon_days == 1
