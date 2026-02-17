"""Tests for the FastAPI REST API layer.

Uses FastAPI TestClient with mocked Registry (same mock_db pattern as
existing tests). Every endpoint has at least one test.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from investmentology.api.app import create_app
from investmentology.api.deps import app_state
from investmentology.learning.calibration import CalibrationEngine
from investmentology.learning.predictions import PredictionManager
from investmentology.learning.registry import DecisionLogger
from investmentology.models.decision import Decision, DecisionType
from investmentology.models.position import PortfolioPosition
from investmentology.models.stock import Stock
from investmentology.orchestrator import AnalysisOrchestrator, CandidateAnalysis, PipelineResult
from investmentology.registry.db import Database
from investmentology.registry.queries import Registry


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock(spec=Database)


@pytest.fixture
def registry(mock_db: MagicMock) -> Registry:
    return Registry(mock_db)


@pytest.fixture
def client(registry: Registry, mock_db: MagicMock) -> TestClient:
    """Create a TestClient with mocked dependencies injected into app_state."""
    # Build the app without lifespan (we inject deps manually)
    app = create_app(use_lifespan=False)

    # Inject mocked state
    app_state.db = mock_db
    app_state.registry = registry
    app_state.gateway = MagicMock()
    app_state.decision_logger = DecisionLogger(registry)
    app_state.prediction_manager = PredictionManager(registry)
    app_state.calibration_engine = CalibrationEngine(registry)
    app_state.orchestrator = MagicMock(spec=AnalysisOrchestrator)

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    # Cleanup
    app_state.db = None
    app_state.registry = None
    app_state.gateway = None
    app_state.decision_logger = None
    app_state.prediction_manager = None
    app_state.calibration_engine = None
    app_state.orchestrator = None


# ------------------------------------------------------------------
# Portfolio
# ------------------------------------------------------------------


class TestPortfolio:
    def test_get_portfolio_empty(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        resp = client.get("/api/invest/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["positions"] == []
        assert data["totalValue"] == 0
        assert data["alerts"] == []

    def test_get_portfolio_with_positions(self, client: TestClient, mock_db: MagicMock) -> None:
        # get_open_positions query
        mock_db.execute.side_effect = [
            # get_open_positions
            [
                {
                    "id": 1, "ticker": "AAPL", "entry_date": date(2025, 1, 15),
                    "entry_price": Decimal("150"), "current_price": Decimal("175"),
                    "shares": Decimal("100"), "position_type": "core",
                    "weight": Decimal("0.10"), "stop_loss": Decimal("130"),
                    "fair_value_estimate": Decimal("200"), "thesis": "Strong moat",
                },
            ],
            # get_active_stocks (called inside portfolio route for sector)
            [
                {"ticker": "AAPL", "name": "Apple", "sector": "Technology",
                 "industry": "Consumer Electronics", "market_cap": Decimal("3000000000000"),
                 "exchange": "NASDAQ", "is_active": True},
            ],
        ]
        resp = client.get("/api/invest/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["positions"]) == 1
        assert data["positions"][0]["ticker"] == "AAPL"
        assert data["totalValue"] == 17500.0

    def test_get_portfolio_alerts_no_alerts(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        resp = client.get("/api/invest/portfolio/alerts")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_get_portfolio_alerts_stop_loss(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {
                "id": 1, "ticker": "AAPL", "entry_date": date(2025, 1, 15),
                "entry_price": Decimal("150"), "current_price": Decimal("125"),
                "shares": Decimal("100"), "position_type": "core",
                "weight": Decimal("0.10"), "stop_loss": Decimal("130"),
                "fair_value_estimate": Decimal("200"), "thesis": "Strong moat",
            },
        ]
        resp = client.get("/api/invest/portfolio/alerts")
        assert resp.status_code == 200
        data = resp.json()
        # Should have stop_loss_breach and drawdown alerts
        types = [a["type"] for a in data["alerts"]]
        assert "stop_loss_breach" in types
        assert "drawdown" in types

    def test_get_portfolio_alerts_medium_drawdown(self, client: TestClient, mock_db: MagicMock) -> None:
        # pnl_pct = (132 - 150) / 150 = -0.12 -> medium severity
        mock_db.execute.return_value = [
            {
                "id": 2, "ticker": "META", "entry_date": date(2025, 3, 1),
                "entry_price": Decimal("150"), "current_price": Decimal("132"),
                "shares": Decimal("50"), "position_type": "tactical",
                "weight": Decimal("0.05"), "stop_loss": None,
                "fair_value_estimate": None, "thesis": "Social recovery",
            },
        ]
        resp = client.get("/api/invest/portfolio/alerts")
        assert resp.status_code == 200
        data = resp.json()
        dd_alerts = [a for a in data["alerts"] if a["type"] == "drawdown"]
        assert len(dd_alerts) == 1
        assert dd_alerts[0]["severity"] == "medium"

    def test_get_portfolio_alerts_fair_value_overshoot(self, client: TestClient, mock_db: MagicMock) -> None:
        # current_price (225) > fair_value_estimate * 1.1 (200 * 1.1 = 220) -> above_fair_value
        mock_db.execute.return_value = [
            {
                "id": 3, "ticker": "NVDA", "entry_date": date(2025, 2, 1),
                "entry_price": Decimal("150"), "current_price": Decimal("225"),
                "shares": Decimal("30"), "position_type": "core",
                "weight": Decimal("0.08"), "stop_loss": None,
                "fair_value_estimate": Decimal("200"), "thesis": "AI leader",
            },
        ]
        resp = client.get("/api/invest/portfolio/alerts")
        assert resp.status_code == 200
        data = resp.json()
        fv_alerts = [a for a in data["alerts"] if a["type"] == "above_fair_value"]
        assert len(fv_alerts) == 1
        assert fv_alerts[0]["severity"] == "medium"

    def test_get_portfolio_alerts_sorted_by_severity(self, client: TestClient, mock_db: MagicMock) -> None:
        # Two positions: one with stop-loss breach (critical), one with medium drawdown
        mock_db.execute.return_value = [
            {
                "id": 1, "ticker": "AAPL", "entry_date": date(2025, 1, 15),
                "entry_price": Decimal("150"), "current_price": Decimal("125"),
                "shares": Decimal("100"), "position_type": "core",
                "weight": Decimal("0.10"), "stop_loss": Decimal("130"),
                "fair_value_estimate": None, "thesis": "Moat",
            },
            {
                "id": 2, "ticker": "META", "entry_date": date(2025, 3, 1),
                "entry_price": Decimal("150"), "current_price": Decimal("132"),
                "shares": Decimal("50"), "position_type": "tactical",
                "weight": Decimal("0.05"), "stop_loss": None,
                "fair_value_estimate": None, "thesis": "Social",
            },
        ]
        resp = client.get("/api/invest/portfolio/alerts")
        data = resp.json()
        severities = [a["severity"] for a in data["alerts"]]
        # critical should come before medium and high
        assert severities.index("critical") < severities.index("medium")


# ------------------------------------------------------------------
# Quant Gate
# ------------------------------------------------------------------


class TestQuantGate:
    def test_latest_no_runs(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        resp = client.get("/api/invest/quant-gate/latest")
        assert resp.status_code == 200
        assert resp.json()["latestRun"] is None

    def test_latest_with_run(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.side_effect = [
            # quant_gate_runs query
            [{"id": 42, "run_date": date(2025, 6, 1), "universe_size": 5000,
              "passed_count": 100, "config": {}, "data_quality": {"coverage": 0.95}}],
            # quant_gate_results query (JOIN with stocks + LATERAL verdict)
            [{"ticker": "AAPL", "earnings_yield": Decimal("0.08"), "roic": Decimal("0.35"),
              "ey_rank": 5, "roic_rank": 3, "combined_rank": 4,
              "piotroski_score": 8, "altman_z_score": Decimal("4.5"),
              "composite_score": Decimal("0.8234"), "altman_zone": "safe",
              "name": "Apple Inc.", "sector": "Technology", "market_cap": Decimal("3000000000000"),
              "verdict": "BUY", "verdict_confidence": Decimal("0.82"), "verdict_date": datetime(2025, 6, 1)}],
        ]
        resp = client.get("/api/invest/quant-gate/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["latestRun"]["id"] == "42"
        assert data["latestRun"]["analyzedCount"] == 1
        assert len(data["latestRun"]["results"]) == 1
        assert data["latestRun"]["results"][0]["ticker"] == "AAPL"
        assert data["latestRun"]["results"][0]["verdict"] == "BUY"

    def test_delta_insufficient_runs(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"id": 1, "run_date": date(2025, 6, 1)},
        ]
        resp = client.get("/api/invest/quant-gate/delta")
        assert resp.status_code == 200
        assert resp.json()["delta"] is None

    def test_delta_with_two_runs(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.side_effect = [
            # Two runs
            [
                {"id": 2, "run_date": date(2025, 6, 8)},
                {"id": 1, "run_date": date(2025, 6, 1)},
            ],
            # Current run tickers
            [{"ticker": "AAPL"}, {"ticker": "MSFT"}, {"ticker": "NVDA"}],
            # Previous run tickers
            [{"ticker": "AAPL"}, {"ticker": "GOOG"}],
        ]
        resp = client.get("/api/invest/quant-gate/delta")
        assert resp.status_code == 200
        data = resp.json()
        assert "MSFT" in data["added"]
        assert "NVDA" in data["added"]
        assert "GOOG" in data["removed"]
        assert "AAPL" in data["retained"]


# ------------------------------------------------------------------
# Stocks
# ------------------------------------------------------------------


class TestStocks:
    @patch("investmentology.api.routes.stocks.get_or_fetch_profile", return_value=None)
    def test_get_stock_not_found(self, _mock_profile, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        resp = client.get("/api/invest/stock/XYZ")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "XYZ"
        assert data["fundamentals"] is None

    @patch("investmentology.api.routes.stocks.get_or_fetch_profile")
    def test_get_stock_with_data(self, mock_profile, client: TestClient, mock_db: MagicMock) -> None:
        now = datetime(2025, 6, 1, 12, 0, 0)
        mock_profile.return_value = {
            "sector": "Technology", "industry": "Consumer Electronics",
            "business_summary": "Apple designs consumer electronics.",
            "website": "https://apple.com", "employees": 160000,
            "city": "Cupertino", "country": "US",
            "beta": Decimal("1.2"), "dividend_yield": Decimal("0.005"),
            "trailing_pe": Decimal("28.5"), "forward_pe": Decimal("25.0"),
            "price_to_book": Decimal("45.0"), "price_to_sales": Decimal("8.5"),
            "fifty_two_week_high": Decimal("220"), "fifty_two_week_low": Decimal("155"),
            "average_volume": 50000000,
            "analyst_target": Decimal("210"), "analyst_recommendation": "buy",
            "analyst_count": 35,
        }
        mock_db.execute.side_effect = [
            # get_latest_fundamentals
            [{
                "ticker": "AAPL", "fetched_at": now,
                "operating_income": Decimal("100000000000"),
                "market_cap": Decimal("3000000000000"),
                "total_debt": Decimal("100000000000"),
                "cash": Decimal("60000000000"),
                "current_assets": Decimal("150000000000"),
                "current_liabilities": Decimal("120000000000"),
                "net_ppe": Decimal("40000000000"),
                "revenue": Decimal("380000000000"),
                "net_income": Decimal("95000000000"),
                "total_assets": Decimal("350000000000"),
                "total_liabilities": Decimal("250000000000"),
                "shares_outstanding": 15000000000,
                "price": Decimal("200"),
            }],
            # agent_signals
            [{"agent_name": "warren", "model": "deepseek-r1", "signals": {"tags": ["UNDERVALUED"]},
              "confidence": Decimal("0.85"), "reasoning": "Strong fundamentals", "created_at": now}],
            # get_decisions (most recent first)
            [{"id": 2, "ticker": "AAPL", "decision_type": "BUY", "layer_source": "L4_FINAL",
              "confidence": Decimal("0.82"), "reasoning": "Conviction buy",
              "signals": None, "metadata": None, "created_at": now},
             {"id": 1, "ticker": "AAPL", "decision_type": "COMPETENCE_PASS", "layer_source": "L2_COMPETENCE",
              "confidence": Decimal("0.85"), "reasoning": "Clear business model",
              "signals": {"in_circle": True, "confidence": 0.85, "sector_familiarity": "high",
                          "moat": {"type": "wide", "sources": ["brand"], "trajectory": "stable",
                                   "durability_years": 15, "confidence": 0.8, "reasoning": "Strong brand"}},
              "metadata": None, "created_at": now}],
            # watchlist
            [{"state": "CONVICTION_BUY", "notes": "Strong moat", "updated_at": now}],
            # quant_gate_results
            [{"combined_rank": 5, "ey_rank": 3, "roic_rank": 2, "piotroski_score": 8,
              "altman_z_score": Decimal("4.5"), "altman_zone": "safe",
              "composite_score": Decimal("0.85"), "name": "Apple Inc.", "sector": "Technology",
              "market_cap": Decimal("3000000000000")}],
            # get_verdict_history
            [],
            # stocks table (name, sector, industry)
            [{"name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics"}],
        ]
        resp = client.get("/api/invest/stock/aapl")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["industry"] == "Consumer Electronics"
        assert data["profile"] is not None
        assert data["profile"]["businessSummary"] == "Apple designs consumer electronics."
        assert data["profile"]["beta"] == 1.2
        assert data["fundamentals"]["market_cap"] == 3000000000000.0
        assert len(data["signals"]) == 1
        assert len(data["decisions"]) == 2
        assert data["watchlist"]["state"] == "CONVICTION_BUY"
        assert data["competence"] is not None
        assert data["competence"]["passed"] is True
        assert data["competence"]["moat"]["type"] == "wide"
        assert data["quantGate"]["compositeScore"] == 0.85
        assert data["quantGate"]["piotroskiScore"] == 8
        assert data["verdict"] is None
        assert data["verdictHistory"] == []

    @patch("investmentology.api.routes.stocks.get_or_fetch_profile", return_value=None)
    def test_get_stock_uppercases_ticker(self, _mock_profile, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        resp = client.get("/api/invest/stock/msft")
        assert resp.status_code == 200
        assert resp.json()["ticker"] == "MSFT"

    def test_get_stock_signals(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"id": 1, "agent_name": "warren", "model": "deepseek-r1",
             "signals": {"tags": ["UNDERVALUED"]}, "confidence": Decimal("0.85"),
             "reasoning": "Strong value", "token_usage": {"total_tokens": 1500},
             "latency_ms": 2000, "created_at": datetime(2025, 6, 1)},
        ]
        resp = client.get("/api/invest/stock/AAPL/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert len(data["signals"]) == 1
        assert data["signals"][0]["agent_name"] == "warren"

    def test_get_stock_signals_empty(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        resp = client.get("/api/invest/stock/AAPL/signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "AAPL"
        assert data["signals"] == []

    def test_get_stock_decisions(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"id": 10, "ticker": "MSFT", "decision_type": "BUY", "layer_source": "L4_FINAL",
             "confidence": Decimal("0.78"), "reasoning": "Cloud dominance",
             "signals": {"action": "CONVICTION_BUY"}, "metadata": None,
             "created_at": datetime(2025, 6, 1)},
        ]
        resp = client.get("/api/invest/stock/MSFT/decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ticker"] == "MSFT"
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["decision_type"] == "BUY"


# ------------------------------------------------------------------
# Watchlist
# ------------------------------------------------------------------


class TestWatchlist:
    def test_get_watchlist_empty(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        resp = client.get("/api/invest/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["groupedByState"] == {}

    def test_get_watchlist_grouped(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"id": 1, "ticker": "AAPL", "state": "CONVICTION_BUY",
             "notes": "Strong", "price_at_add": Decimal("180"), "entered_at": datetime(2025, 5, 1),
             "updated_at": datetime(2025, 6, 1), "name": "Apple Inc.", "sector": "Technology",
             "current_price": Decimal("200"), "market_cap": Decimal("3000000000000"),
             "composite_score": Decimal("0.85"), "piotroski_score": 8, "altman_zone": "safe",
             "combined_rank": 5, "altman_z_score": Decimal("4.5"),
             "verdict": "BUY", "verdict_confidence": Decimal("0.82"),
             "consensus_score": Decimal("0.5"), "verdict_reasoning": "Solid fundamentals",
             "agent_stances": [], "risk_flags": [], "verdict_date": datetime(2025, 6, 1)},
            {"id": 2, "ticker": "GOOG", "state": "WATCHLIST_EARLY",
             "notes": None, "price_at_add": None, "entered_at": datetime(2025, 5, 15),
             "updated_at": datetime(2025, 6, 1), "name": "Alphabet", "sector": "Technology",
             "current_price": None, "market_cap": None,
             "composite_score": None, "piotroski_score": None, "altman_zone": None,
             "combined_rank": None, "altman_z_score": None,
             "verdict": None, "verdict_confidence": None,
             "consensus_score": None, "verdict_reasoning": None,
             "agent_stances": None, "risk_flags": None, "verdict_date": None},
            {"id": 3, "ticker": "MSFT", "state": "CONVICTION_BUY",
             "notes": "Cloud", "price_at_add": Decimal("400"), "entered_at": datetime(2025, 5, 1),
             "updated_at": datetime(2025, 6, 1), "name": "Microsoft", "sector": "Technology",
             "current_price": Decimal("420"), "market_cap": Decimal("2800000000000"),
             "composite_score": Decimal("0.78"), "piotroski_score": 7, "altman_zone": "safe",
             "combined_rank": 8, "altman_z_score": Decimal("3.8"),
             "verdict": None, "verdict_confidence": None,
             "consensus_score": None, "verdict_reasoning": None,
             "agent_stances": None, "risk_flags": None, "verdict_date": None},
        ]
        resp = client.get("/api/invest/watchlist")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["groupedByState"]["CONVICTION_BUY"]) == 2
        assert len(data["groupedByState"]["WATCHLIST_EARLY"]) == 1
        assert len(data["items"]) == 3
        # Verify enriched fields
        aapl = data["items"][0]
        assert aapl["currentPrice"] == 200.0
        assert aapl["compositeScore"] == 0.85
        assert aapl["verdict"]["recommendation"] == "BUY"


# ------------------------------------------------------------------
# Decisions
# ------------------------------------------------------------------


class TestDecisions:
    def test_get_decisions_empty(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        resp = client.get("/api/invest/decisions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["decisions"] == []
        assert data["total"] == 0

    def test_get_decisions_with_filter(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.side_effect = [
            # get_decisions query
            [{"id": 5, "ticker": "AAPL", "decision_type": "BUY", "layer_source": "L4_FINAL",
              "confidence": Decimal("0.80"), "reasoning": "Conviction",
              "signals": None, "metadata": None, "created_at": datetime(2025, 6, 1)}],
            # COUNT query
            [{"n": 1}],
        ]
        resp = client.get("/api/invest/decisions?ticker=aapl&type=BUY&pageSize=10&page=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["ticker"] == "AAPL"
        assert data["pageSize"] == 10

    def test_get_decisions_with_ticker_only(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.side_effect = [
            [{"id": 7, "ticker": "GOOG", "decision_type": "SCREEN", "layer_source": "L1_quant_gate",
              "confidence": Decimal("0.70"), "reasoning": "Strong EY",
              "signals": None, "metadata": None, "created_at": datetime(2025, 6, 2)}],
            [{"n": 1}],
        ]
        resp = client.get("/api/invest/decisions?ticker=goog")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["ticker"] == "GOOG"

    def test_get_decisions_pagination(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.side_effect = [[], [{"n": 0}]]
        resp = client.get("/api/invest/decisions?pageSize=5&page=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pageSize"] == 5
        assert data["page"] == 3

    def test_get_decisions_bad_type(self, client: TestClient, mock_db: MagicMock) -> None:
        resp = client.get("/api/invest/decisions?type=NONEXISTENT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["decisions"] == []


# ------------------------------------------------------------------
# Learning
# ------------------------------------------------------------------


class TestLearning:
    def test_get_calibration(self, client: TestClient, mock_db: MagicMock) -> None:
        # PredictionManager.get_calibration_data calls registry.get_decisions
        mock_db.execute.return_value = []
        resp = client.get("/api/invest/learning/calibration")
        assert resp.status_code == 200
        data = resp.json()
        assert "brierScore" in data
        assert "totalPredictions" in data
        assert "buckets" in data

    def test_get_agent_performance(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"agent_name": "warren", "total_signals": 50,
             "avg_confidence": Decimal("0.78"), "avg_latency_ms": Decimal("2100")},
            {"agent_name": "soros", "total_signals": 48,
             "avg_confidence": Decimal("0.72"), "avg_latency_ms": Decimal("1800")},
        ]
        resp = client.get("/api/invest/learning/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 2
        assert data["agents"][0]["agent_name"] == "warren"


# ------------------------------------------------------------------
# System
# ------------------------------------------------------------------


class TestSystem:
    def test_health_check(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.health_check.return_value = True
        mock_db.execute.side_effect = [
            # decision count
            [{"n": 350}],
            # quant gate run
            [{"run_date": date(2025, 6, 1)}],
        ]
        resp = client.get("/api/invest/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["database"] is True
        assert data["decisionsLogged"] == 350

    def test_health_check_degraded(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.health_check.return_value = False
        mock_db.execute.side_effect = [
            [{"n": 0}],  # decision count
            [],  # no quant gate runs
        ]
        resp = client.get("/api/invest/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["database"] is False
        assert data["decisionsLogged"] == 0


# ------------------------------------------------------------------
# Analyse
# ------------------------------------------------------------------


class TestAnalyse:
    def test_trigger_analysis(self, client: TestClient) -> None:
        # Mock the orchestrator's analyze_candidates method
        mock_result = PipelineResult(
            candidates_in=2, passed_competence=1, analyzed=1,
            conviction_buys=1, vetoed=0,
            results=[
                CandidateAnalysis(
                    ticker="AAPL", passed_competence=True,
                    final_action="CONVICTION_BUY", final_confidence=Decimal("0.85"),
                ),
                CandidateAnalysis(
                    ticker="GOOG", passed_competence=False,
                    final_action="NO_ACTION", final_confidence=Decimal("0"),
                ),
            ],
        )

        async def mock_analyze(tickers, **kwargs):
            return mock_result

        app_state.orchestrator.analyze_candidates = mock_analyze

        resp = client.post("/api/invest/analyse", json={"tickers": ["AAPL", "GOOG"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidates_in"] == 2
        assert data["conviction_buys"] == 1
        assert len(data["results"]) == 2
        assert data["results"][0]["ticker"] == "AAPL"
        assert data["results"][0]["final_action"] == "CONVICTION_BUY"

    def test_trigger_analysis_empty(self, client: TestClient) -> None:
        mock_result = PipelineResult(
            candidates_in=0, passed_competence=0, analyzed=0,
            conviction_buys=0, vetoed=0, results=[],
        )

        async def mock_analyze(tickers, **kwargs):
            return mock_result

        app_state.orchestrator.analyze_candidates = mock_analyze

        resp = client.post("/api/invest/analyse", json={"tickers": []})
        assert resp.status_code == 200
        assert resp.json()["candidates_in"] == 0

    def test_trigger_analysis_uppercases_tickers(self, client: TestClient) -> None:
        mock_result = PipelineResult(
            candidates_in=1, passed_competence=0, analyzed=0,
            conviction_buys=0, vetoed=0, results=[],
        )
        calls = []

        async def mock_analyze(tickers, **kwargs):
            calls.append(tickers)
            return mock_result

        app_state.orchestrator.analyze_candidates = mock_analyze

        resp = client.post("/api/invest/analyse", json={"tickers": ["aapl", "goog"]})
        assert resp.status_code == 200
        assert calls[0] == ["AAPL", "GOOG"]

    def test_trigger_analysis_missing_body(self, client: TestClient) -> None:
        resp = client.post("/api/invest/analyse")
        assert resp.status_code == 422  # Validation error


# ------------------------------------------------------------------
# Recommendations
# ------------------------------------------------------------------


class TestRecommendations:
    def test_get_recommendations_empty(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        resp = client.get("/api/invest/recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["totalCount"] == 0
        assert data["groupedByVerdict"] == {}

    def test_get_recommendations_grouped(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"ticker": "AAPL", "verdict": "STRONG_BUY", "confidence": Decimal("0.85"),
             "consensus_score": Decimal("0.7"), "reasoning": "Strong fundamentals",
             "agent_stances": [], "risk_flags": [],
             "auditor_override": False, "munger_override": False,
             "created_at": datetime(2026, 2, 1),
             "name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics",
             "current_price": Decimal("270"), "market_cap": Decimal("4000000000000"),
             "watchlist_state": "CONVICTION_BUY"},
            {"ticker": "FDS", "verdict": "BUY", "confidence": Decimal("0.61"),
             "consensus_score": Decimal("0.4"), "reasoning": "Undervalued",
             "agent_stances": [], "risk_flags": ["Outside Circle of Competence"],
             "auditor_override": False, "munger_override": False,
             "created_at": datetime(2026, 2, 1),
             "name": "FactSet", "sector": "Financial Services", "industry": "Data",
             "current_price": Decimal("200"), "market_cap": Decimal("15000000000"),
             "watchlist_state": "CONVICTION_BUY"},
        ]
        resp = client.get("/api/invest/recommendations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalCount"] == 2
        assert "STRONG_BUY" in data["groupedByVerdict"]
        assert "BUY" in data["groupedByVerdict"]
        assert len(data["groupedByVerdict"]["STRONG_BUY"]) == 1
        assert data["items"][0]["ticker"] == "AAPL"
        assert data["items"][0]["confidence"] == 0.85
        assert data["items"][1]["riskFlags"] == ["Outside Circle of Competence"]


# ------------------------------------------------------------------
# Portfolio (additional — create/close/closed)
# ------------------------------------------------------------------


class TestPortfolioPositions:
    def test_create_position(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.side_effect = [
            [],            # get_open_positions (no existing position for AAPL)
            [{"id": 1}],  # create_position INSERT RETURNING id
        ]
        resp = client.post("/api/invest/portfolio/positions", json={
            "ticker": "aapl", "entry_price": 150.0, "shares": 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["ticker"] == "AAPL"
        assert data["status"] == "created"

    def test_close_position(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.side_effect = [
            # get_position_by_id
            [{"id": 1, "ticker": "AAPL", "entry_date": date(2025, 1, 1),
              "entry_price": Decimal("150"), "current_price": Decimal("175"),
              "shares": Decimal("100"), "position_type": "core",
              "weight": Decimal("0.1"), "stop_loss": None,
              "fair_value_estimate": None, "thesis": "",
              "exit_date": None, "exit_price": None,
              "is_closed": False, "realized_pnl": None}],
            # close_position UPDATE
            [],
        ]
        resp = client.post("/api/invest/portfolio/positions/1/close", json={
            "exit_price": 175.0,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    def test_close_already_closed(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [
            {"id": 1, "ticker": "AAPL", "entry_date": date(2025, 1, 1),
             "entry_price": Decimal("150"), "current_price": Decimal("175"),
             "shares": Decimal("100"), "position_type": "core",
             "weight": Decimal("0.1"), "stop_loss": None,
             "fair_value_estimate": None, "thesis": "",
             "exit_date": date(2025, 2, 1), "exit_price": Decimal("175"),
             "is_closed": True, "realized_pnl": Decimal("2500")}
        ]
        resp = client.post("/api/invest/portfolio/positions/1/close", json={
            "exit_price": 180.0,
        })
        assert resp.status_code == 400

    def test_close_not_found(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        resp = client.post("/api/invest/portfolio/positions/999/close", json={
            "exit_price": 100.0,
        })
        assert resp.status_code == 404

    def test_get_closed_positions(self, client: TestClient, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = []
        resp = client.get("/api/invest/portfolio/closed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["closedPositions"] == []
        assert data["totalRealizedPnl"] == 0.0
