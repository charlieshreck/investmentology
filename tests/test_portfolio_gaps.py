"""Tests for portfolio gap analysis and allocation guidance."""

from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock

import pytest

from investmentology.advisory.portfolio_fit import (
    compute_portfolio_gaps,
    get_cash_regime_guidance,
    IDEAL_RISK_TARGETS,
    AllocationStance,
)
from investmentology.models.position import PortfolioPosition


def _make_position(ticker: str, price: float, shares: float, pos_type: str = "core") -> PortfolioPosition:
    return PortfolioPosition(
        ticker=ticker,
        entry_date=date(2025, 1, 1),
        entry_price=Decimal(str(price)),
        current_price=Decimal(str(price)),
        shares=Decimal(str(shares)),
        position_type=pos_type,
        weight=Decimal("5.0"),
    )


class TestPortfolioGaps:
    def test_empty_portfolio(self):
        """Empty portfolio → all categories underweight."""
        registry = MagicMock()
        registry.get_open_positions.return_value = []

        gaps = compute_portfolio_gaps(registry)
        assert gaps.position_count == 0
        assert gaps.total_value == 0
        assert len(gaps.underweight_categories) == len(IDEAL_RISK_TARGETS)
        assert "Portfolio is empty" in gaps.concentration_warnings

    def test_single_position_growth_heavy(self):
        """Single tech stock → growth overweight, everything else underweight."""
        registry = MagicMock()
        registry.get_open_positions.return_value = [
            _make_position("AAPL", 200.0, 100),
        ]
        registry._db.execute.return_value = [
            {"ticker": "AAPL", "sector": "Technology"},
        ]

        gaps = compute_portfolio_gaps(registry)
        assert gaps.position_count == 1
        assert gaps.risk_allocations["growth"]["current_pct"] == 100.0
        assert "growth" in gaps.overweight_categories
        # Defensive, cyclical, income should all be underweight
        assert "defensive" in gaps.underweight_categories
        assert "cyclical" in gaps.underweight_categories

    def test_balanced_portfolio(self):
        """Balanced portfolio near ideal targets → minimal gaps."""
        registry = MagicMock()
        positions = [
            _make_position("AAPL", 100, 35),   # Tech → growth (35%)
            _make_position("JPM", 100, 25),     # Financial → cyclical (25%)
            _make_position("PG", 100, 20),      # Consumer Def → defensive (20%)
            _make_position("JNJ", 100, 15),     # Healthcare → mixed (15%)
            _make_position("O", 100, 5),        # Real Estate → income (5%)
        ]
        registry.get_open_positions.return_value = positions
        registry._db.execute.return_value = [
            {"ticker": "AAPL", "sector": "Technology"},
            {"ticker": "JPM", "sector": "Financial Services"},
            {"ticker": "PG", "sector": "Consumer Defensive"},
            {"ticker": "JNJ", "sector": "Healthcare"},
            {"ticker": "O", "sector": "Real Estate"},
        ]

        gaps = compute_portfolio_gaps(registry)
        # All allocations should be at or near ideal
        assert len(gaps.underweight_categories) == 0
        assert len(gaps.overweight_categories) == 0

    def test_concentration_warning_sector(self):
        """Sector >40% triggers concentration warning."""
        registry = MagicMock()
        positions = [
            _make_position("AAPL", 100, 50),
            _make_position("MSFT", 100, 30),
            _make_position("PG", 100, 20),
        ]
        registry.get_open_positions.return_value = positions
        registry._db.execute.return_value = [
            {"ticker": "AAPL", "sector": "Technology"},
            {"ticker": "MSFT", "sector": "Technology"},
            {"ticker": "PG", "sector": "Consumer Defensive"},
        ]

        gaps = compute_portfolio_gaps(registry)
        # Tech = 80% → should trigger warning
        assert any("Technology" in w for w in gaps.concentration_warnings)

    def test_concentration_warning_single_position(self):
        """Single position >10% triggers warning."""
        registry = MagicMock()
        positions = [
            _make_position("AAPL", 100, 15),  # 15% of portfolio
            _make_position("MSFT", 100, 85),  # 85% of portfolio
        ]
        registry.get_open_positions.return_value = positions
        registry._db.execute.return_value = [
            {"ticker": "AAPL", "sector": "Technology"},
            {"ticker": "MSFT", "sector": "Technology"},
        ]

        gaps = compute_portfolio_gaps(registry)
        assert any("MSFT" in w for w in gaps.concentration_warnings)

    def test_sector_allocations_returned(self):
        """Sector allocation percentages are computed correctly."""
        registry = MagicMock()
        positions = [
            _make_position("AAPL", 100, 60),
            _make_position("PG", 100, 40),
        ]
        registry.get_open_positions.return_value = positions
        registry._db.execute.return_value = [
            {"ticker": "AAPL", "sector": "Technology"},
            {"ticker": "PG", "sector": "Consumer Defensive"},
        ]

        gaps = compute_portfolio_gaps(registry)
        assert gaps.sector_allocations["Technology"] == 60.0
        assert gaps.sector_allocations["Consumer Defensive"] == 40.0


class TestCashRegimeGuidance:
    def test_expansion_regime(self):
        g = get_cash_regime_guidance({"regime": "expansion", "confidence": 0.7})
        assert g.stance == AllocationStance.STANDARD
        assert g.equity_min_pct == 70
        assert g.equity_max_pct == 85

    def test_contraction_regime(self):
        g = get_cash_regime_guidance({"regime": "contraction", "confidence": 0.8})
        assert g.stance == AllocationStance.DEFENSIVE
        assert g.equity_min_pct == 40
        assert g.equity_max_pct == 50

    def test_recovery_regime(self):
        g = get_cash_regime_guidance({"regime": "recovery", "confidence": 0.6})
        assert g.stance == AllocationStance.AGGRESSIVE
        assert g.equity_min_pct == 80

    def test_low_confidence_defaults_to_standard(self):
        g = get_cash_regime_guidance({"regime": "contraction", "confidence": 0.2})
        assert g.stance == AllocationStance.STANDARD

    def test_none_regime(self):
        g = get_cash_regime_guidance(None)
        assert g.stance == AllocationStance.STANDARD
        assert g.regime == "unknown"
