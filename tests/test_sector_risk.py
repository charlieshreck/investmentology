"""Tests for sector concentration and correlation risk analysis."""

from investmentology.advisory.sector_risk import (
    CorrelationPair,
    PositionWeight,
    compute_correlation_matrix,
    compute_sector_concentration,
)


# ===========================================================================
# Sector concentration
# ===========================================================================

class TestSectorConcentration:
    def test_empty_portfolio(self):
        result = compute_sector_concentration([])
        assert result.exposures == []
        assert result.warnings == []
        assert result.hhi == 0.0

    def test_single_sector_100_pct(self):
        positions = [
            PositionWeight("AAPL", "Technology", 1000.0),
            PositionWeight("MSFT", "Technology", 500.0),
        ]
        result = compute_sector_concentration(positions)
        assert len(result.exposures) == 1
        assert result.exposures[0].sector == "Technology"
        assert result.exposures[0].weight_pct == 100.0
        assert result.exposures[0].warning is True
        assert len(result.warnings) == 1

    def test_balanced_portfolio_no_warnings(self):
        positions = [
            PositionWeight("AAPL", "Technology", 250.0),
            PositionWeight("JNJ", "Healthcare", 250.0),
            PositionWeight("JPM", "Financial Services", 250.0),
            PositionWeight("XOM", "Energy", 250.0),
        ]
        result = compute_sector_concentration(positions)
        assert len(result.exposures) == 4
        assert all(e.weight_pct == 25.0 for e in result.exposures)
        assert all(e.warning is False for e in result.exposures)
        assert result.warnings == []

    def test_warning_at_30_pct(self):
        positions = [
            PositionWeight("AAPL", "Technology", 350.0),
            PositionWeight("MSFT", "Technology", 150.0),
            PositionWeight("JNJ", "Healthcare", 250.0),
            PositionWeight("XOM", "Energy", 250.0),
        ]
        result = compute_sector_concentration(positions)
        tech = next(e for e in result.exposures if e.sector == "Technology")
        assert tech.weight_pct == 50.0
        assert tech.warning is True
        assert len(result.warnings) == 1
        assert "Technology" in result.warnings[0]

    def test_hhi_perfectly_diversified(self):
        """4 equal sectors → HHI = 4 × 25² = 2500."""
        positions = [
            PositionWeight("A", "S1", 100.0),
            PositionWeight("B", "S2", 100.0),
            PositionWeight("C", "S3", 100.0),
            PositionWeight("D", "S4", 100.0),
        ]
        result = compute_sector_concentration(positions)
        assert result.hhi == 2500.0

    def test_hhi_concentrated(self):
        """1 sector → HHI = 10000."""
        positions = [PositionWeight("A", "Tech", 100.0)]
        result = compute_sector_concentration(positions)
        assert result.hhi == 10000.0

    def test_tickers_grouped_correctly(self):
        positions = [
            PositionWeight("AAPL", "Technology", 100.0),
            PositionWeight("MSFT", "Technology", 100.0),
            PositionWeight("JNJ", "Healthcare", 100.0),
        ]
        result = compute_sector_concentration(positions)
        tech = next(e for e in result.exposures if e.sector == "Technology")
        assert sorted(tech.tickers) == ["AAPL", "MSFT"]

    def test_unknown_sector_handled(self):
        positions = [
            PositionWeight("XYZ", None, 100.0),
            PositionWeight("ABC", "Technology", 100.0),
        ]
        result = compute_sector_concentration(positions)
        sectors = {e.sector for e in result.exposures}
        assert "Unknown" in sectors
        assert "Technology" in sectors

    def test_sorted_by_weight_descending(self):
        positions = [
            PositionWeight("A", "Small", 100.0),
            PositionWeight("B", "Large", 900.0),
        ]
        result = compute_sector_concentration(positions)
        assert result.exposures[0].sector == "Large"
        assert result.exposures[1].sector == "Small"


# ===========================================================================
# Correlation matrix
# ===========================================================================

class TestCorrelationMatrix:
    def test_empty_returns(self):
        result = compute_correlation_matrix({})
        assert result.pairs == []
        assert result.high_correlation_count == 0
        assert result.effective_positions == 0.0

    def test_single_ticker(self):
        result = compute_correlation_matrix({"AAPL": [0.01, 0.02, -0.01, 0.03, 0.01]})
        assert result.pairs == []
        assert result.effective_positions == 1.0

    def test_perfectly_correlated(self):
        returns = {
            "A": [0.01, 0.02, -0.01, 0.03, -0.02],
            "B": [0.01, 0.02, -0.01, 0.03, -0.02],
        }
        result = compute_correlation_matrix(returns)
        assert len(result.pairs) == 1
        assert result.pairs[0].correlation == 1.0
        assert result.pairs[0].high is True
        assert result.high_correlation_count == 1

    def test_negatively_correlated(self):
        returns = {
            "A": [0.01, 0.02, -0.01, 0.03, -0.02],
            "B": [-0.01, -0.02, 0.01, -0.03, 0.02],
        }
        result = compute_correlation_matrix(returns)
        assert len(result.pairs) == 1
        assert result.pairs[0].correlation == -1.0
        assert result.pairs[0].high is False

    def test_uncorrelated(self):
        # Near-zero correlation
        returns = {
            "A": [0.01, -0.01, 0.01, -0.01, 0.01, -0.01],
            "B": [0.01, 0.01, -0.01, -0.01, 0.01, 0.01],
        }
        result = compute_correlation_matrix(returns)
        assert len(result.pairs) == 1
        assert abs(result.pairs[0].correlation) < 0.5

    def test_high_correlation_warning(self):
        returns = {
            "A": [0.01, 0.02, -0.01, 0.03, -0.02],
            "B": [0.01, 0.02, -0.01, 0.03, -0.02],
        }
        result = compute_correlation_matrix(returns)
        assert len(result.warnings) == 1
        assert "A-B" in result.warnings[0]

    def test_three_tickers(self):
        returns = {
            "A": [0.01, 0.02, -0.01, 0.03, -0.02],
            "B": [0.01, 0.02, -0.01, 0.03, -0.02],
            "C": [-0.01, -0.02, 0.01, -0.03, 0.02],
        }
        result = compute_correlation_matrix(returns)
        # 3 pairs: A-B, A-C, B-C
        assert len(result.pairs) == 3

    def test_effective_positions_perfect_correlation(self):
        """All perfectly correlated → effective = 1."""
        returns = {
            "A": [0.01, 0.02, -0.01, 0.03, -0.02],
            "B": [0.01, 0.02, -0.01, 0.03, -0.02],
            "C": [0.01, 0.02, -0.01, 0.03, -0.02],
        }
        result = compute_correlation_matrix(returns)
        assert result.effective_positions == 1.0

    def test_insufficient_data_skipped(self):
        """Pairs with < 5 data points are skipped."""
        returns = {
            "A": [0.01, 0.02, -0.01],
            "B": [0.01, 0.02, -0.01],
        }
        result = compute_correlation_matrix(returns)
        assert result.pairs == []

    def test_sorted_by_correlation_descending(self):
        returns = {
            "A": [0.01, 0.02, -0.01, 0.03, -0.02],
            "B": [0.01, 0.02, -0.01, 0.03, -0.02],
            "C": [-0.01, -0.02, 0.01, -0.03, 0.02],
        }
        result = compute_correlation_matrix(returns)
        correlations = [p.correlation for p in result.pairs]
        assert correlations == sorted(correlations, reverse=True)
