"""Tests for the quant gate module: Greenblatt, Piotroski, Altman, Screener."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch


from investmentology.models.decision import DecisionType
from investmentology.models.lifecycle import WatchlistState
from investmentology.models.stock import FundamentalsSnapshot
from investmentology.quant_gate.altman import AltmanResult, calculate_altman
from investmentology.quant_gate.greenblatt import (
    GreenblattResult,
    rank_by_greenblatt,
    should_exclude,
    should_exclude_with_sector,
)
from investmentology.quant_gate.piotroski import PiotroskiResult, calculate_piotroski
from investmentology.quant_gate.screener import (
    DataQualityReport,
    QuantGateScreener,
    ScreenerResult,
    _dict_to_snapshot,
    _dict_to_stock,
)

NOW = datetime.now(UTC)


def _make_snapshot(
    ticker: str = "AAPL",
    operating_income: Decimal = Decimal("50000"),
    market_cap: Decimal = Decimal("1000000"),
    total_debt: Decimal = Decimal("100000"),
    cash: Decimal = Decimal("50000"),
    current_assets: Decimal = Decimal("200000"),
    current_liabilities: Decimal = Decimal("100000"),
    net_ppe: Decimal = Decimal("300000"),
    revenue: Decimal = Decimal("500000"),
    net_income: Decimal = Decimal("40000"),
    total_assets: Decimal = Decimal("800000"),
    total_liabilities: Decimal = Decimal("400000"),
    shares_outstanding: int = 1000000,
    price: Decimal = Decimal("150"),
) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        ticker=ticker,
        fetched_at=NOW,
        operating_income=operating_income,
        market_cap=market_cap,
        total_debt=total_debt,
        cash=cash,
        current_assets=current_assets,
        current_liabilities=current_liabilities,
        net_ppe=net_ppe,
        revenue=revenue,
        net_income=net_income,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        shares_outstanding=shares_outstanding,
        price=price,
    )


# ========================================================================
# Greenblatt Tests
# ========================================================================


class TestGreenblattExclusions:
    def test_exclude_negative_ebit(self) -> None:
        snap = _make_snapshot(operating_income=Decimal("-1000"))
        excluded, reason = should_exclude(snap)
        assert excluded is True
        assert reason == "negative_or_zero_ebit"

    def test_exclude_zero_ebit(self) -> None:
        snap = _make_snapshot(operating_income=Decimal("0"))
        excluded, reason = should_exclude(snap)
        assert excluded is True
        assert reason == "negative_or_zero_ebit"

    def test_exclude_missing_market_cap(self) -> None:
        snap = _make_snapshot(market_cap=Decimal("0"))
        excluded, reason = should_exclude(snap)
        assert excluded is True
        assert reason == "missing_market_cap"

    def test_exclude_negative_invested_capital(self) -> None:
        # invested_capital = net_working_capital + net_ppe
        # net_working_capital = current_assets - current_liabilities
        # Make current_liabilities >> current_assets + net_ppe
        snap = _make_snapshot(
            current_assets=Decimal("10"),
            current_liabilities=Decimal("1000"),
            net_ppe=Decimal("0"),
        )
        assert snap.invested_capital <= 0
        excluded, reason = should_exclude(snap)
        assert excluded is True
        assert reason == "negative_invested_capital"

    def test_exclude_negative_enterprise_value(self) -> None:
        # EV = market_cap + total_debt - cash
        # Make cash >> market_cap + total_debt
        snap = _make_snapshot(
            market_cap=Decimal("100"),
            total_debt=Decimal("0"),
            cash=Decimal("200"),
            # Need positive invested capital still
            current_assets=Decimal("500"),
            current_liabilities=Decimal("100"),
            net_ppe=Decimal("100"),
        )
        assert snap.enterprise_value < 0
        excluded, reason = should_exclude(snap)
        assert excluded is True
        assert reason == "negative_enterprise_value"

    def test_no_exclusion_healthy_stock(self) -> None:
        snap = _make_snapshot()
        excluded, reason = should_exclude(snap)
        assert excluded is False
        assert reason == ""

    def test_exclude_financial_services_sector(self) -> None:
        snap = _make_snapshot()
        excluded, reason = should_exclude_with_sector(snap, "Financial Services")
        assert excluded is True
        assert "excluded_sector" in reason

    def test_exclude_utilities_sector(self) -> None:
        snap = _make_snapshot()
        excluded, reason = should_exclude_with_sector(snap, "Utilities")
        assert excluded is True
        assert "excluded_sector" in reason

    def test_no_sector_exclusion_for_tech(self) -> None:
        snap = _make_snapshot()
        excluded, reason = should_exclude_with_sector(snap, "Technology")
        assert excluded is False


class TestGreenblattRanking:
    def test_ranking_order_by_combined_rank(self) -> None:
        """Stocks with best combined earnings yield + ROIC should rank first."""
        # Stock A: high EY, high ROIC -> should rank best
        a = _make_snapshot(
            ticker="A",
            operating_income=Decimal("100000"),
            market_cap=Decimal("500000"),
            total_debt=Decimal("50000"),
            cash=Decimal("10000"),
            current_assets=Decimal("200000"),
            current_liabilities=Decimal("100000"),
            net_ppe=Decimal("100000"),
        )
        # Stock B: medium EY, medium ROIC
        b = _make_snapshot(
            ticker="B",
            operating_income=Decimal("50000"),
            market_cap=Decimal("500000"),
            total_debt=Decimal("50000"),
            cash=Decimal("10000"),
            current_assets=Decimal("200000"),
            current_liabilities=Decimal("100000"),
            net_ppe=Decimal("200000"),
        )
        # Stock C: low EY, low ROIC
        c = _make_snapshot(
            ticker="C",
            operating_income=Decimal("10000"),
            market_cap=Decimal("500000"),
            total_debt=Decimal("50000"),
            cash=Decimal("10000"),
            current_assets=Decimal("200000"),
            current_liabilities=Decimal("100000"),
            net_ppe=Decimal("400000"),
        )

        results = rank_by_greenblatt([a, b, c])

        assert len(results) == 3
        assert results[0].ticker == "A"
        assert results[1].ticker == "B"
        assert results[2].ticker == "C"

    def test_combined_rank_is_sum(self) -> None:
        """Combined rank should equal ey_rank + roic_rank."""
        a = _make_snapshot(ticker="A", operating_income=Decimal("100000"))
        b = _make_snapshot(ticker="B", operating_income=Decimal("50000"))

        results = rank_by_greenblatt([a, b])
        for r in results:
            assert r.combined_rank == r.ey_rank + r.roic_rank

    def test_excludes_bad_stocks(self) -> None:
        """Stocks failing exclusion criteria should be removed from ranking."""
        good = _make_snapshot(ticker="GOOD")
        bad = _make_snapshot(ticker="BAD", operating_income=Decimal("-1000"))

        results = rank_by_greenblatt([good, bad])
        tickers = [r.ticker for r in results]
        assert "GOOD" in tickers
        assert "BAD" not in tickers

    def test_empty_input(self) -> None:
        results = rank_by_greenblatt([])
        assert results == []

    def test_all_excluded(self) -> None:
        bad1 = _make_snapshot(ticker="BAD1", operating_income=Decimal("-1"))
        bad2 = _make_snapshot(ticker="BAD2", market_cap=Decimal("0"))
        results = rank_by_greenblatt([bad1, bad2])
        assert results == []

    def test_sector_exclusion_in_ranking(self) -> None:
        """Stocks in excluded sectors should be filtered when sectors provided."""
        tech = _make_snapshot(ticker="TECH")
        bank = _make_snapshot(ticker="BANK")

        sectors = {"TECH": "Technology", "BANK": "Financial Services"}
        results = rank_by_greenblatt([tech, bank], sectors=sectors)

        tickers = [r.ticker for r in results]
        assert "TECH" in tickers
        assert "BANK" not in tickers

    def test_result_types(self) -> None:
        snap = _make_snapshot()
        results = rank_by_greenblatt([snap])
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, GreenblattResult)
        assert isinstance(r.earnings_yield, Decimal)
        assert isinstance(r.roic, Decimal)
        assert isinstance(r.ey_rank, int)
        assert isinstance(r.roic_rank, int)
        assert isinstance(r.combined_rank, int)


# ========================================================================
# Piotroski Tests
# ========================================================================


class TestPiotroski:
    def test_all_passing_with_previous(self) -> None:
        """Score should be 9 when all criteria pass."""
        previous = _make_snapshot(
            net_income=Decimal("30000"),
            total_assets=Decimal("800000"),
            total_debt=Decimal("150000"),
            current_assets=Decimal("150000"),
            current_liabilities=Decimal("120000"),
            shares_outstanding=1100000,
            revenue=Decimal("400000"),
            operating_income=Decimal("30000"),  # margin = 30000/400000 = 7.5%
        )
        current = _make_snapshot(
            net_income=Decimal("40000"),       # positive (1)
            operating_income=Decimal("50000"), # > net_income (accruals 4)
            total_assets=Decimal("800000"),
            total_debt=Decimal("100000"),      # lower ratio (5)
            current_assets=Decimal("200000"),  # better ratio (6)
            current_liabilities=Decimal("100000"),
            shares_outstanding=1000000,        # fewer shares (7)
            revenue=Decimal("500000"),         # higher turnover (9) and margin (8)
        )

        result = calculate_piotroski(current, previous)

        assert isinstance(result, PiotroskiResult)
        assert result.score == 9
        assert all(result.details.values())

    def test_no_previous_data(self) -> None:
        """Without previous data, only points 1, 2, 4 can be scored."""
        current = _make_snapshot(
            net_income=Decimal("40000"),
            operating_income=Decimal("50000"),
        )

        result = calculate_piotroski(current, None)

        # Points 1 (positive_net_income), 2 (positive_ocf), 4 (accruals_quality)
        assert result.details["positive_net_income"] is True
        assert result.details["positive_ocf"] is True
        assert result.details["accruals_quality"] is True

        # Comparative points should be False without previous
        assert result.details["roa_improving"] is False
        assert result.details["debt_ratio_decreasing"] is False
        assert result.details["current_ratio_improving"] is False
        assert result.details["no_dilution"] is False
        assert result.details["gross_margin_improving"] is False
        assert result.details["asset_turnover_improving"] is False

        assert result.score == 3

    def test_all_failing(self) -> None:
        """Score should be 0 when nothing passes."""
        previous = _make_snapshot(
            net_income=Decimal("50000"),
            total_assets=Decimal("800000"),
            total_debt=Decimal("50000"),
            current_assets=Decimal("250000"),
            current_liabilities=Decimal("80000"),
            shares_outstanding=900000,
            revenue=Decimal("600000"),
            operating_income=Decimal("60000"),
        )
        current = _make_snapshot(
            net_income=Decimal("-10000"),       # negative (fails 1, 2)
            operating_income=Decimal("-20000"), # < net_income (fails 4)
            total_assets=Decimal("800000"),
            total_debt=Decimal("200000"),       # higher ratio (fails 5)
            current_assets=Decimal("100000"),   # worse ratio (fails 6)
            current_liabilities=Decimal("150000"),
            shares_outstanding=1200000,         # more shares (fails 7)
            revenue=Decimal("300000"),          # lower turnover (fails 9), lower margin (fails 8)
        )

        result = calculate_piotroski(current, previous)
        assert result.score == 0
        assert not any(result.details.values())

    def test_details_keys(self) -> None:
        """All 9 test keys should be present."""
        result = calculate_piotroski(_make_snapshot())
        expected_keys = {
            "positive_net_income",
            "positive_ocf",
            "roa_improving",
            "accruals_quality",
            "debt_ratio_decreasing",
            "current_ratio_improving",
            "no_dilution",
            "gross_margin_improving",
            "asset_turnover_improving",
        }
        assert set(result.details.keys()) == expected_keys

    def test_score_is_int(self) -> None:
        result = calculate_piotroski(_make_snapshot())
        assert isinstance(result.score, int)
        assert 0 <= result.score <= 9


# ========================================================================
# Altman Tests
# ========================================================================


class TestAltman:
    def test_safe_zone(self) -> None:
        """A healthy company should be in the safe zone (>2.99)."""
        snap = _make_snapshot(
            operating_income=Decimal("200000"),
            market_cap=Decimal("2000000"),
            total_assets=Decimal("500000"),
            total_liabilities=Decimal("100000"),
            revenue=Decimal("600000"),
            net_income=Decimal("150000"),
            current_assets=Decimal("300000"),
            current_liabilities=Decimal("50000"),
        )

        result = calculate_altman(snap)

        assert result is not None
        assert isinstance(result, AltmanResult)
        assert result.zone == "safe"
        assert result.z_score > Decimal("2.99")

    def test_distress_zone(self) -> None:
        """A heavily indebted company with losses should be in distress."""
        snap = _make_snapshot(
            operating_income=Decimal("-50000"),
            market_cap=Decimal("50000"),
            total_assets=Decimal("500000"),
            total_liabilities=Decimal("450000"),
            revenue=Decimal("100000"),
            net_income=Decimal("-80000"),
            current_assets=Decimal("50000"),
            current_liabilities=Decimal("200000"),
        )

        result = calculate_altman(snap)

        assert result is not None
        assert result.zone == "distress"
        assert result.z_score < Decimal("1.81")

    def test_grey_zone(self) -> None:
        """Moderate financials should land in the grey zone."""
        snap = _make_snapshot(
            operating_income=Decimal("30000"),
            market_cap=Decimal("300000"),
            total_assets=Decimal("500000"),
            total_liabilities=Decimal("250000"),
            revenue=Decimal("400000"),
            net_income=Decimal("20000"),
            current_assets=Decimal("150000"),
            current_liabilities=Decimal("120000"),
        )

        result = calculate_altman(snap)

        assert result is not None
        assert result.zone == "grey"
        assert Decimal("1.81") <= result.z_score <= Decimal("2.99")

    def test_zero_total_assets_returns_none(self) -> None:
        snap = _make_snapshot(total_assets=Decimal("0"))
        result = calculate_altman(snap)
        assert result is None

    def test_zero_total_liabilities_returns_none(self) -> None:
        snap = _make_snapshot(total_liabilities=Decimal("0"))
        result = calculate_altman(snap)
        assert result is None

    def test_z_score_formula_manual(self) -> None:
        """Verify Z-score calculation against manual computation."""
        snap = _make_snapshot(
            current_assets=Decimal("200"),
            current_liabilities=Decimal("100"),
            net_income=Decimal("50"),
            operating_income=Decimal("80"),
            market_cap=Decimal("500"),
            total_liabilities=Decimal("200"),
            revenue=Decimal("300"),
            total_assets=Decimal("400"),
        )

        # Manual calculation:
        # A = (200 - 100) / 400 = 0.25
        # B = 50 / 400 = 0.125
        # C = 80 / 400 = 0.2
        # D = 500 / 200 = 2.5
        # E = 300 / 400 = 0.75
        # Z = 1.2*0.25 + 1.4*0.125 + 3.3*0.2 + 0.6*2.5 + 1.0*0.75
        #   = 0.3 + 0.175 + 0.66 + 1.5 + 0.75 = 3.385
        expected = Decimal("1.2") * Decimal("0.25") + \
                   Decimal("1.4") * Decimal("0.125") + \
                   Decimal("3.3") * Decimal("0.2") + \
                   Decimal("0.6") * Decimal("2.5") + \
                   Decimal("1.0") * Decimal("0.75")

        result = calculate_altman(snap)
        assert result is not None
        assert result.z_score == expected

    def test_result_types(self) -> None:
        snap = _make_snapshot()
        result = calculate_altman(snap)
        assert result is not None
        assert isinstance(result.z_score, Decimal)
        assert isinstance(result.zone, str)
        assert result.zone in ("safe", "grey", "distress")


# ========================================================================
# Screener Tests
# ========================================================================


class TestDictToSnapshot:
    def test_valid_conversion(self) -> None:
        d = {
            "ticker": "AAPL",
            "fetched_at": NOW.isoformat(),
            "operating_income": Decimal("50000"),
            "market_cap": Decimal("1000000"),
            "total_debt": Decimal("100000"),
            "cash": Decimal("50000"),
            "current_assets": Decimal("200000"),
            "current_liabilities": Decimal("100000"),
            "net_tangible_assets": Decimal("300000"),
            "revenue": Decimal("500000"),
            "net_income": Decimal("40000"),
            "total_assets": Decimal("800000"),
            "total_liabilities": Decimal("400000"),
            "shares_outstanding": Decimal("1000000"),
            "price": Decimal("150"),
        }
        snap = _dict_to_snapshot(d)
        assert snap is not None
        assert snap.ticker == "AAPL"
        assert snap.operating_income == Decimal("50000")

    def test_missing_ticker_returns_none(self) -> None:
        d = {"fetched_at": NOW.isoformat()}
        snap = _dict_to_snapshot(d)
        assert snap is None

    def test_none_values_default_to_zero(self) -> None:
        d = {
            "ticker": "TEST",
            "fetched_at": NOW.isoformat(),
            "operating_income": None,
            "market_cap": None,
            "total_debt": None,
            "cash": None,
            "current_assets": None,
            "current_liabilities": None,
            "net_tangible_assets": None,
            "revenue": None,
            "net_income": None,
            "total_assets": None,
            "total_liabilities": None,
            "shares_outstanding": None,
            "price": None,
        }
        snap = _dict_to_snapshot(d)
        assert snap is not None
        assert snap.operating_income == Decimal(0)
        assert snap.shares_outstanding == 0


class TestDictToStock:
    def test_valid_conversion(self) -> None:
        d = {
            "ticker": "AAPL",
            "name": "Apple Inc",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": 3000000000000,
            "exchange": "NASDAQ",
        }
        stock = _dict_to_stock(d)
        assert stock.ticker == "AAPL"
        assert stock.sector == "Technology"
        assert stock.market_cap == Decimal("3000000000000")


class TestScreenerOrchestration:
    """Test the QuantGateScreener pipeline with mocked dependencies."""

    def _make_mock_config(self) -> MagicMock:
        config = MagicMock()
        config.quant_gate_top_n = 10
        config.universe_min_market_cap = 200_000_000
        return config

    def _make_universe_data(self, n: int = 5) -> list[dict]:
        tickers = [f"T{i:03d}" for i in range(n)]
        return [
            {
                "ticker": t,
                "name": f"Company {t}",
                "sector": "Technology",
                "industry": "Software",
                "market_cap": 1_000_000_000,
                "exchange": "NASDAQ",
            }
            for t in tickers
        ]

    def _make_fundamentals_data(self, tickers: list[str]) -> list[dict]:
        results = []
        for i, t in enumerate(tickers):
            results.append({
                "ticker": t,
                "fetched_at": NOW.isoformat(),
                "operating_income": Decimal(str(50000 + i * 10000)),
                "market_cap": Decimal("1000000"),
                "total_debt": Decimal("100000"),
                "cash": Decimal("50000"),
                "current_assets": Decimal("200000"),
                "current_liabilities": Decimal("100000"),
                "net_tangible_assets": Decimal("300000"),
                "revenue": Decimal("500000"),
                "net_income": Decimal("40000"),
                "total_assets": Decimal("800000"),
                "total_liabilities": Decimal("400000"),
                "shares_outstanding": Decimal("1000000"),
                "price": Decimal("150"),
            })
        return results

    @patch("investmentology.quant_gate.screener.load_full_universe")
    def test_full_pipeline(self, mock_universe: MagicMock) -> None:
        """Verify the screener calls each pipeline step."""
        universe = self._make_universe_data(5)
        mock_universe.return_value = universe

        tickers = [u["ticker"] for u in universe]
        fundamentals = self._make_fundamentals_data(tickers)

        mock_yf = MagicMock()
        mock_yf.get_fundamentals_batch.return_value = fundamentals
        mock_yf.is_healthy = True

        mock_registry = MagicMock()
        mock_registry.create_quant_gate_run.return_value = 42
        mock_registry.log_decision.return_value = 1

        config = self._make_mock_config()

        screener = QuantGateScreener(mock_registry, mock_yf, config)
        result = screener.run()

        # Verify pipeline steps were called
        mock_universe.assert_called_once()
        mock_registry.upsert_stocks.assert_called_once()
        mock_yf.get_fundamentals_batch.assert_called_once_with(tickers)
        mock_registry.insert_fundamentals.assert_called_once()
        mock_registry.create_quant_gate_run.assert_called_once()
        mock_registry.insert_quant_gate_results.assert_called_once()
        mock_registry.log_decision.assert_called_once()

        # Verify result structure
        assert isinstance(result, ScreenerResult)
        assert result.run_id == 42
        assert len(result.top_results) == 5
        assert isinstance(result.data_quality, DataQualityReport)
        assert result.data_quality.universe_size == 5

    @patch("investmentology.quant_gate.screener.load_full_universe")
    def test_empty_universe(self, mock_universe: MagicMock) -> None:
        """Empty universe should return empty result without crashing."""
        mock_universe.return_value = []

        mock_yf = MagicMock()
        mock_yf.is_healthy = True
        mock_registry = MagicMock()
        config = self._make_mock_config()

        screener = QuantGateScreener(mock_registry, mock_yf, config)
        result = screener.run()

        assert result.run_id == 0
        assert result.top_results == []
        assert result.data_quality.universe_size == 0

    @patch("investmentology.quant_gate.screener.load_full_universe")
    def test_top_n_limit(self, mock_universe: MagicMock) -> None:
        """Screener should limit results to config.quant_gate_top_n."""
        universe = self._make_universe_data(20)
        mock_universe.return_value = universe

        tickers = [u["ticker"] for u in universe]
        fundamentals = self._make_fundamentals_data(tickers)

        mock_yf = MagicMock()
        mock_yf.get_fundamentals_batch.return_value = fundamentals
        mock_yf.is_healthy = True

        mock_registry = MagicMock()
        mock_registry.create_quant_gate_run.return_value = 1

        config = self._make_mock_config()
        config.quant_gate_top_n = 5

        screener = QuantGateScreener(mock_registry, mock_yf, config)
        result = screener.run()

        assert len(result.top_results) == 5

    @patch("investmentology.quant_gate.screener.load_full_universe")
    def test_results_have_enrichment_scores(self, mock_universe: MagicMock) -> None:
        """Top results should include piotroski_score and altman_z_score."""
        universe = self._make_universe_data(3)
        mock_universe.return_value = universe

        tickers = [u["ticker"] for u in universe]
        fundamentals = self._make_fundamentals_data(tickers)

        mock_yf = MagicMock()
        mock_yf.get_fundamentals_batch.return_value = fundamentals
        mock_yf.is_healthy = True

        mock_registry = MagicMock()
        mock_registry.create_quant_gate_run.return_value = 1

        config = self._make_mock_config()

        screener = QuantGateScreener(mock_registry, mock_yf, config)
        result = screener.run()

        for r in result.top_results:
            assert "piotroski_score" in r
            assert "altman_z_score" in r
            assert "combined_rank" in r
            assert "earnings_yield" in r
            assert isinstance(r["piotroski_score"], int)

    @patch("investmentology.quant_gate.screener.load_full_universe")
    def test_watchlist_additions(self, mock_universe: MagicMock) -> None:
        """Screener should add top results to watchlist as CANDIDATE."""
        universe = self._make_universe_data(3)
        mock_universe.return_value = universe

        tickers = [u["ticker"] for u in universe]
        fundamentals = self._make_fundamentals_data(tickers)

        mock_yf = MagicMock()
        mock_yf.get_fundamentals_batch.return_value = fundamentals
        mock_yf.is_healthy = True

        mock_registry = MagicMock()
        mock_registry.create_quant_gate_run.return_value = 1

        config = self._make_mock_config()

        screener = QuantGateScreener(mock_registry, mock_yf, config)
        result = screener.run()

        # Should have called add_to_watchlist for each result
        assert mock_registry.add_to_watchlist.call_count == len(result.top_results)

        # Check the state passed was CANDIDATE
        for call in mock_registry.add_to_watchlist.call_args_list:
            assert call.kwargs.get("state") == WatchlistState.CANDIDATE or \
                   call[1].get("state") == WatchlistState.CANDIDATE

    @patch("investmentology.quant_gate.screener.load_full_universe")
    def test_decision_logged(self, mock_universe: MagicMock) -> None:
        """Screener should log a SCREEN decision."""
        universe = self._make_universe_data(3)
        mock_universe.return_value = universe

        tickers = [u["ticker"] for u in universe]
        fundamentals = self._make_fundamentals_data(tickers)

        mock_yf = MagicMock()
        mock_yf.get_fundamentals_batch.return_value = fundamentals
        mock_yf.is_healthy = True

        mock_registry = MagicMock()
        mock_registry.create_quant_gate_run.return_value = 1

        config = self._make_mock_config()

        screener = QuantGateScreener(mock_registry, mock_yf, config)
        screener.run()

        mock_registry.log_decision.assert_called_once()
        decision = mock_registry.log_decision.call_args[0][0]
        assert decision.decision_type == DecisionType.SCREEN
        assert decision.layer_source == "quant_gate"


# ====================================================================
# Composite Score
# ====================================================================

class TestCompositeScore:
    """Tests for composite_score()."""

    def test_best_possible_score(self) -> None:
        from investmentology.quant_gate.composite import composite_score
        score = composite_score(
            greenblatt_rank=1, total_ranked=100,
            piotroski_score=9, has_prior_year=True,
            altman_zone="safe",
        )
        assert score == Decimal("1.0000")

    def test_worst_possible_score(self) -> None:
        from investmentology.quant_gate.composite import composite_score
        score = composite_score(
            greenblatt_rank=100, total_ranked=100,
            piotroski_score=0, has_prior_year=True,
            altman_zone="distress",
        )
        assert score == Decimal("0.0000")

    def test_safe_zone_beats_distress(self) -> None:
        from investmentology.quant_gate.composite import composite_score
        safe = composite_score(
            greenblatt_rank=50, total_ranked=100,
            piotroski_score=5, has_prior_year=True,
            altman_zone="safe",
        )
        distress = composite_score(
            greenblatt_rank=50, total_ranked=100,
            piotroski_score=5, has_prior_year=True,
            altman_zone="distress",
        )
        assert safe > distress

    def test_high_piotroski_beats_low(self) -> None:
        from investmentology.quant_gate.composite import composite_score
        high_f = composite_score(
            greenblatt_rank=50, total_ranked=100,
            piotroski_score=8, has_prior_year=True,
            altman_zone="grey",
        )
        low_f = composite_score(
            greenblatt_rank=50, total_ranked=100,
            piotroski_score=2, has_prior_year=True,
            altman_zone="grey",
        )
        assert high_f > low_f

    def test_without_prior_year_normalizes_to_4(self) -> None:
        from investmentology.quant_gate.composite import composite_score
        # 3/4 without prior should be same ratio as 6.75/9 with prior
        no_prior = composite_score(
            greenblatt_rank=1, total_ranked=100,
            piotroski_score=3, has_prior_year=False,
            altman_zone="safe",
        )
        # Without prior, max piotroski is 4, so 3/4 = 0.75 piotroski component
        assert no_prior > Decimal("0.8")  # 0.5 + 0.225 + 0.2 = 0.925

    def test_missing_altman_treated_as_grey(self) -> None:
        from investmentology.quant_gate.composite import composite_score
        missing = composite_score(
            greenblatt_rank=50, total_ranked=100,
            piotroski_score=5, has_prior_year=True,
            altman_zone=None,
        )
        grey = composite_score(
            greenblatt_rank=50, total_ranked=100,
            piotroski_score=5, has_prior_year=True,
            altman_zone="grey",
        )
        # None gets 0.3, grey gets 0.5 — so missing should be < grey
        assert missing < grey
