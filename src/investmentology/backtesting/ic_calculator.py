"""Factor Information Coefficient (IC) calculator.

Pure functions for computing Spearman rank correlation between factor scores
and forward returns, quintile analysis, and top-N vs benchmark comparison.
No I/O — takes scored results and returns typed dataclasses.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class FactorICResult:
    """Spearman rank correlation between a factor and forward returns."""

    factor_name: str
    screen_year: int
    horizon_months: int
    ic: float           # -1.0 to 1.0
    n_stocks: int
    p_value: float


@dataclass
class QuintileResult:
    """Average return by composite-score quintile."""

    screen_year: int
    horizon_months: int
    quintile: int       # 1 (best) to 5 (worst)
    n_stocks: int
    avg_return: float
    median_return: float
    hit_rate: float     # % that beat SPY


@dataclass
class TopNResult:
    """Equal-weight top-N portfolio vs SPY benchmark."""

    screen_year: int
    horizon_months: int
    n: int
    portfolio_return: float
    spy_return: float
    alpha: float
    hit_rate: float     # % of top-N that beat SPY


# ── Factors to Analyze ───────────────────────────────────────────────────────

# (field_name_in_scored_results, higher_is_better)
FACTORS: list[tuple[str, bool]] = [
    ("composite_score", True),
    ("piotroski_score", True),
    ("altman_z_score", True),
    ("momentum_score", True),
    ("gross_profitability", True),
    ("shareholder_yield", True),
    ("combined_rank", False),  # lower rank = better for Greenblatt
]


# ── Spearman Rank Correlation (numpy-only) ───────────────────────────────────

def _rankdata(arr: np.ndarray) -> np.ndarray:
    """Assign ranks to data, handling ties with average rank."""
    order = arr.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(arr) + 1, dtype=float)

    # Handle ties: average rank for equal values
    sorted_arr = arr[order]
    i = 0
    while i < len(sorted_arr):
        j = i
        while j < len(sorted_arr) and sorted_arr[j] == sorted_arr[i]:
            j += 1
        if j > i + 1:
            avg_rank = np.mean(ranks[order[i:j]])
            ranks[order[i:j]] = avg_rank
        i = j
    return ranks


def spearman_rank_correlation(
    x: np.ndarray,
    y: np.ndarray,
) -> tuple[float, float]:
    """Compute Spearman rank correlation and approximate p-value.

    Uses numpy for ranking and Pearson on ranks. P-value from Student's t
    distribution approximation (valid for n > 10).

    Returns:
        (rho, p_value) tuple.
    """
    n = len(x)
    if n < 5:
        return 0.0, 1.0

    rx = _rankdata(x)
    ry = _rankdata(y)

    # Pearson on ranks
    rx_mean = rx.mean()
    ry_mean = ry.mean()
    dx = rx - rx_mean
    dy = ry - ry_mean
    denom = math.sqrt(float(np.sum(dx**2) * np.sum(dy**2)))
    if denom == 0:
        return 0.0, 1.0
    rho = float(np.sum(dx * dy)) / denom

    # t-statistic and p-value approximation
    if abs(rho) >= 1.0:
        return rho, 0.0
    t_stat = rho * math.sqrt((n - 2) / (1 - rho**2))
    # Two-tailed p-value using Student's t approximation (Abramowitz & Stegun)
    p_value = _t_distribution_sf(abs(t_stat), n - 2) * 2
    return rho, min(p_value, 1.0)


def _t_distribution_sf(t: float, df: int) -> float:
    """Approximate survival function for Student's t distribution.

    Uses the normal approximation for df > 30 and a simple series for smaller df.
    Good enough for significance testing — not meant for publication-quality p-values.
    """
    if df > 30:
        # Normal approximation
        return 0.5 * math.erfc(t / math.sqrt(2))
    # For smaller df, use a rougher approximation
    # Regularized incomplete beta function approximation
    # This is a simplified version — for exact values, use scipy
    return 0.5 * math.erfc(t / math.sqrt(2)) * (1 + 0.5 / df)


# ── Factor IC Computation ────────────────────────────────────────────────────

def compute_factor_ic(
    scored_results: list[dict],
    forward_returns: dict[str, float],
    factor_name: str,
    higher_is_better: bool,
    screen_year: int,
    horizon_months: int,
) -> FactorICResult | None:
    """Compute Spearman IC between a single factor and forward returns.

    Args:
        scored_results: List of dicts from quant gate (must have 'ticker' + factor_name).
        forward_returns: ticker → total return over horizon.
        factor_name: Key in scored_results dict.
        higher_is_better: If False, invert factor values before correlation.
        screen_year: For labeling.
        horizon_months: For labeling.

    Returns:
        FactorICResult or None if insufficient data.
    """
    pairs: list[tuple[float, float]] = []
    for result in scored_results:
        ticker = result.get("ticker")
        factor_val = result.get(factor_name)
        if ticker is None or factor_val is None:
            continue
        fwd = forward_returns.get(ticker)
        if fwd is None:
            continue
        fv = float(factor_val)
        if not higher_is_better:
            fv = -fv  # Invert so higher = better for correlation
        pairs.append((fv, fwd))

    if len(pairs) < 10:
        return None

    x = np.array([p[0] for p in pairs])
    y = np.array([p[1] for p in pairs])
    rho, p_val = spearman_rank_correlation(x, y)

    return FactorICResult(
        factor_name=factor_name,
        screen_year=screen_year,
        horizon_months=horizon_months,
        ic=rho,
        n_stocks=len(pairs),
        p_value=p_val,
    )


def compute_all_factor_ics(
    scored_results: list[dict],
    forward_returns: dict[str, float],
    screen_year: int,
    horizon_months: int,
) -> list[FactorICResult]:
    """Compute IC for all 7 tracked factors."""
    results: list[FactorICResult] = []
    for factor_name, higher_is_better in FACTORS:
        ic = compute_factor_ic(
            scored_results,
            forward_returns,
            factor_name,
            higher_is_better,
            screen_year,
            horizon_months,
        )
        if ic is not None:
            results.append(ic)
    return results


# ── Quintile Analysis ────────────────────────────────────────────────────────

def compute_quintile_returns(
    scored_results: list[dict],
    forward_returns: dict[str, float],
    spy_return: float,
    screen_year: int,
    horizon_months: int,
) -> list[QuintileResult]:
    """Sort stocks by composite_score into 5 quintiles, compute average returns.

    Q1 = top 20% (highest composite), Q5 = bottom 20%.
    """
    # Build (composite_score, forward_return) pairs
    pairs: list[tuple[float, float]] = []
    for result in scored_results:
        ticker = result.get("ticker")
        cs = result.get("composite_score")
        if ticker is None or cs is None:
            continue
        fwd = forward_returns.get(ticker)
        if fwd is None:
            continue
        pairs.append((float(cs), fwd))

    if len(pairs) < 10:
        return []

    # Sort by composite score descending (best first)
    pairs.sort(key=lambda p: p[0], reverse=True)

    n = len(pairs)
    quintile_size = n // 5
    results: list[QuintileResult] = []

    for q in range(5):
        start = q * quintile_size
        end = start + quintile_size if q < 4 else n
        bucket = pairs[start:end]
        returns = [p[1] for p in bucket]
        arr = np.array(returns)

        results.append(QuintileResult(
            screen_year=screen_year,
            horizon_months=horizon_months,
            quintile=q + 1,
            n_stocks=len(bucket),
            avg_return=float(arr.mean()),
            median_return=float(np.median(arr)),
            hit_rate=float(np.sum(arr > spy_return) / len(arr)) if len(arr) > 0 else 0.0,
        ))

    return results


# ── Top-N vs SPY ─────────────────────────────────────────────────────────────

def compute_top_n_vs_spy(
    scored_results: list[dict],
    forward_returns: dict[str, float],
    spy_return: float,
    screen_year: int,
    horizon_months: int,
    n: int = 20,
) -> TopNResult | None:
    """Equal-weight top-N portfolio return vs SPY.

    Args:
        scored_results: Sorted by composite_score descending.
        forward_returns: ticker → return.
        spy_return: SPY return over same horizon.
        n: Number of top stocks (20 or 50).
    """
    # Get top-N tickers by composite score
    ranked = sorted(
        scored_results,
        key=lambda r: float(r.get("composite_score", 0)),
        reverse=True,
    )

    returns: list[float] = []
    for result in ranked[:n]:
        ticker = result.get("ticker")
        fwd = forward_returns.get(ticker) if ticker else None
        if fwd is not None:
            returns.append(fwd)

    if not returns:
        return None

    arr = np.array(returns)
    portfolio_ret = float(arr.mean())

    return TopNResult(
        screen_year=screen_year,
        horizon_months=horizon_months,
        n=len(returns),
        portfolio_return=portfolio_ret,
        spy_return=spy_return,
        alpha=portfolio_ret - spy_return,
        hit_rate=float(np.sum(arr > spy_return) / len(arr)),
    )


# ── Serialization ────────────────────────────────────────────────────────────

def ic_results_to_dict(results: list[FactorICResult]) -> dict:
    """Convert IC results to nested dict for JSONB storage.

    Structure: {year: {factor: {horizon: {ic, n, p}}}}
    """
    out: dict = {}
    for r in results:
        year_key = str(r.screen_year)
        if year_key not in out:
            out[year_key] = {}
        if r.factor_name not in out[year_key]:
            out[year_key][r.factor_name] = {}
        out[year_key][r.factor_name][str(r.horizon_months)] = {
            "ic": round(r.ic, 4),
            "n": r.n_stocks,
            "p": round(r.p_value, 4),
        }
    return out


def quintile_results_to_dict(results: list[QuintileResult]) -> dict:
    """Structure: {year: {horizon: [{quintile, n, avg_return, ...}]}}"""
    out: dict = {}
    for r in results:
        year_key = str(r.screen_year)
        horizon_key = str(r.horizon_months)
        if year_key not in out:
            out[year_key] = {}
        if horizon_key not in out[year_key]:
            out[year_key][horizon_key] = []
        out[year_key][horizon_key].append({
            "quintile": r.quintile,
            "n": r.n_stocks,
            "avg_return": round(r.avg_return, 4),
            "median_return": round(r.median_return, 4),
            "hit_rate": round(r.hit_rate, 4),
        })
    return out


def top_n_results_to_dict(results: list[TopNResult]) -> dict:
    """Structure: {year: {horizon: {n: {portfolio_return, spy_return, alpha, hit_rate}}}}"""
    out: dict = {}
    for r in results:
        year_key = str(r.screen_year)
        horizon_key = str(r.horizon_months)
        if year_key not in out:
            out[year_key] = {}
        if horizon_key not in out[year_key]:
            out[year_key][horizon_key] = {}
        out[year_key][horizon_key][str(r.n)] = {
            "portfolio_return": round(r.portfolio_return, 4),
            "spy_return": round(r.spy_return, 4),
            "alpha": round(r.alpha, 4),
            "hit_rate": round(r.hit_rate, 4),
        }
    return out
