"""Sector concentration and correlation risk analysis.

Two portfolio risk tools:
  1. Sector concentration: portfolio weight per sector with 30% warning threshold
  2. Pairwise correlation: 60-day rolling return correlations for held positions

These are advisory tools — they surface risk, not execute trades.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SECTOR_CONCENTRATION_WARN_PCT = 30.0
CORRELATION_HIGH_THRESHOLD = 0.70


@dataclass
class SectorExposure:
    sector: str
    weight_pct: float
    tickers: list[str]
    warning: bool = False  # True if >= 30%


@dataclass
class SectorConcentrationResult:
    exposures: list[SectorExposure]
    warnings: list[str]
    hhi: float  # Herfindahl-Hirschman Index (0-10000)


@dataclass
class CorrelationPair:
    ticker_a: str
    ticker_b: str
    correlation: float
    high: bool = False  # True if >= 0.70


@dataclass
class CorrelationResult:
    pairs: list[CorrelationPair]
    high_correlation_count: int
    effective_positions: float  # Diversification ratio
    warnings: list[str]


@dataclass
class PositionWeight:
    """Lightweight position data for sector analysis."""

    ticker: str
    sector: str
    market_value: float


def compute_sector_concentration(
    positions: list[PositionWeight],
) -> SectorConcentrationResult:
    """Compute sector concentration from portfolio positions.

    Args:
        positions: List of held positions with sector and market value.

    Returns:
        SectorConcentrationResult with per-sector weights and warnings.
    """
    if not positions:
        return SectorConcentrationResult(exposures=[], warnings=[], hhi=0.0)

    total_value = sum(p.market_value for p in positions)
    if total_value <= 0:
        return SectorConcentrationResult(exposures=[], warnings=[], hhi=0.0)

    # Aggregate by sector
    sector_data: dict[str, dict] = {}
    for p in positions:
        s = p.sector or "Unknown"
        if s not in sector_data:
            sector_data[s] = {"value": 0.0, "tickers": []}
        sector_data[s]["value"] += p.market_value
        sector_data[s]["tickers"].append(p.ticker)

    exposures: list[SectorExposure] = []
    warnings: list[str] = []
    hhi = 0.0

    for sector, data in sorted(sector_data.items(), key=lambda x: -x[1]["value"]):
        weight_pct = data["value"] / total_value * 100
        is_warning = weight_pct >= SECTOR_CONCENTRATION_WARN_PCT
        exposures.append(
            SectorExposure(
                sector=sector,
                weight_pct=round(weight_pct, 1),
                tickers=sorted(data["tickers"]),
                warning=is_warning,
            )
        )
        hhi += weight_pct ** 2
        if is_warning:
            warnings.append(
                f"{sector} at {weight_pct:.1f}% — exceeds {SECTOR_CONCENTRATION_WARN_PCT:.0f}% threshold"
            )

    return SectorConcentrationResult(
        exposures=exposures,
        warnings=warnings,
        hhi=round(hhi, 1),
    )


def compute_correlation_matrix(
    daily_returns: dict[str, list[float]],
) -> CorrelationResult:
    """Compute pairwise correlations from daily return series.

    Args:
        daily_returns: {ticker: [daily_return_1, daily_return_2, ...]}
            All lists should have the same length (aligned dates).

    Returns:
        CorrelationResult with all pairs and diversification metrics.
    """
    tickers = sorted(daily_returns.keys())
    n = len(tickers)

    if n < 2:
        return CorrelationResult(
            pairs=[], high_correlation_count=0, effective_positions=float(n), warnings=[],
        )

    pairs: list[CorrelationPair] = []
    warnings: list[str] = []
    high_count = 0

    for i in range(n):
        for j in range(i + 1, n):
            corr = _pearson(daily_returns[tickers[i]], daily_returns[tickers[j]])
            if corr is None:
                continue
            is_high = corr >= CORRELATION_HIGH_THRESHOLD
            pairs.append(
                CorrelationPair(
                    ticker_a=tickers[i],
                    ticker_b=tickers[j],
                    correlation=round(corr, 3),
                    high=is_high,
                )
            )
            if is_high:
                high_count += 1
                warnings.append(
                    f"{tickers[i]}-{tickers[j]} correlation {corr:.2f} — "
                    f"positions may move together"
                )

    # Effective positions: n / (1 + (n-1) * avg_corr)
    # Lower = more concentrated risk
    avg_corr = _average_correlation(pairs)
    if avg_corr is not None and n > 1:
        denominator = 1 + (n - 1) * avg_corr
        effective = n / denominator if denominator > 0 else float(n)
    else:
        effective = float(n)

    return CorrelationResult(
        pairs=sorted(pairs, key=lambda p: -p.correlation),
        high_correlation_count=high_count,
        effective_positions=round(effective, 1),
        warnings=warnings,
    )


def _pearson(x: list[float], y: list[float]) -> float | None:
    """Compute Pearson correlation coefficient between two series."""
    n = min(len(x), len(y))
    if n < 5:
        return None

    x = x[:n]
    y = y[:n]

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)

    denom = (var_x * var_y) ** 0.5
    if denom == 0:
        return None

    return cov / denom


def _average_correlation(pairs: list[CorrelationPair]) -> float | None:
    """Average absolute correlation across all pairs."""
    if not pairs:
        return None
    return sum(abs(p.correlation) for p in pairs) / len(pairs)
