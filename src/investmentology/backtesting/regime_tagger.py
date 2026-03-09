"""Market regime tagging and regime-conditioned factor IC analysis.

Assigns market regime labels to screen years and computes which factors
performed best in each regime. Produces compact text for agent prompt injection.
"""

from __future__ import annotations

from dataclasses import dataclass

from investmentology.backtesting.ic_calculator import FactorICResult

# ── Regime Assignments ───────────────────────────────────────────────────────

SCREEN_YEAR_REGIMES: dict[int, str] = {
    2020: "contraction",    # COVID crash + initial recovery
    2021: "recovery",       # Post-COVID, low rates, momentum dominant
    2022: "contraction",    # Rate hike cycle, bear market
    2023: "late_cycle",     # Soft landing uncertainty, quality premium
    2024: "expansion",      # AI boom, growth resurgent
    2025: "late_cycle",     # Tariff uncertainty, policy-driven
}

REGIME_DESCRIPTIONS: dict[str, str] = {
    "recovery": "Post-downturn recovery, low rates, broad market lift",
    "expansion": "Economic growth, rising earnings, momentum-driven",
    "late_cycle": "Slowing growth, uncertainty, quality premium",
    "contraction": "Rate hikes or recession, value compression, defensive",
}


@dataclass
class RegimeFactorIC:
    """Average factor IC within a specific market regime."""

    regime: str
    factor_name: str
    horizon_months: int
    avg_ic: float
    years: list[int]
    n_obs: int


# ── Functions ────────────────────────────────────────────────────────────────

def tag_regime(screen_year: int) -> str:
    """Return market regime label for a given screen year."""
    return SCREEN_YEAR_REGIMES.get(screen_year, "unknown")


def compute_regime_ic_table(
    all_ic_results: list[FactorICResult],
) -> list[RegimeFactorIC]:
    """Group IC results by regime and compute average IC per factor.

    Returns a list of RegimeFactorIC, one per (regime, factor, horizon) triple.
    """
    # Group: (regime, factor, horizon) -> list of (ic, n_stocks, year)
    groups: dict[tuple[str, str, int], list[tuple[float, int, int]]] = {}
    for r in all_ic_results:
        regime = tag_regime(r.screen_year)
        key = (regime, r.factor_name, r.horizon_months)
        if key not in groups:
            groups[key] = []
        groups[key].append((r.ic, r.n_stocks, r.screen_year))

    results: list[RegimeFactorIC] = []
    for (regime, factor, horizon), entries in sorted(groups.items()):
        total_n = sum(e[1] for e in entries)
        # Weighted average IC by sample size
        if total_n > 0:
            avg_ic = sum(e[0] * e[1] for e in entries) / total_n
        else:
            avg_ic = sum(e[0] for e in entries) / len(entries)
        years = sorted(e[2] for e in entries)

        results.append(RegimeFactorIC(
            regime=regime,
            factor_name=factor,
            horizon_months=horizon,
            avg_ic=avg_ic,
            years=years,
            n_obs=total_n,
        ))

    return results


def regime_ic_to_dict(results: list[RegimeFactorIC]) -> dict:
    """Serialize to JSONB-friendly dict.

    Structure: {regime: {factor: {horizon: {avg_ic, years, n_obs}}}}
    """
    out: dict = {}
    for r in results:
        if r.regime not in out:
            out[r.regime] = {}
        if r.factor_name not in out[r.regime]:
            out[r.regime][r.factor_name] = {}
        out[r.regime][r.factor_name][str(r.horizon_months)] = {
            "avg_ic": round(r.avg_ic, 4),
            "years": r.years,
            "n_obs": r.n_obs,
        }
    return out


def format_calibration_context(
    regime_ics: list[RegimeFactorIC],
    current_regime: str | None = None,
) -> str:
    """Produce compact text block for agent prompt injection.

    Example output:
        Historical Factor Performance (Spearman IC, 12m horizon):
          Recovery (2021): Composite=0.18, Greenblatt=0.21, Momentum=0.15
          Contraction (2022): Piotroski=0.08, Greenblatt=0.14
          Current regime: expansion → Greenblatt and Momentum strongest
    """
    # Group by regime, use 12m horizon only for compact display
    regime_factors: dict[str, list[tuple[str, float, list[int]]]] = {}
    for r in regime_ics:
        if r.horizon_months != 12:
            continue
        if r.regime not in regime_factors:
            regime_factors[r.regime] = []
        regime_factors[r.regime].append((r.factor_name, r.avg_ic, r.years))

    if not regime_factors:
        return ""

    # Pretty factor name mapping
    _names: dict[str, str] = {
        "composite_score": "Composite",
        "combined_rank": "Greenblatt",
        "piotroski_score": "Piotroski",
        "altman_z_score": "Altman",
        "momentum_score": "Momentum",
        "gross_profitability": "GrossProfit",
        "shareholder_yield": "ShareholderYield",
    }

    lines = ["Historical Factor Performance (Spearman IC, 12m forward returns):"]

    regime_order = ["recovery", "expansion", "late_cycle", "contraction"]
    for regime in regime_order:
        factors = regime_factors.get(regime)
        if not factors:
            continue
        # Sort by absolute IC descending
        factors.sort(key=lambda f: abs(f[1]), reverse=True)
        years_str = ",".join(str(y) for y in factors[0][2])
        parts = [f"{_names.get(f, f)}={ic:.2f}" for f, ic, _ in factors[:4]]
        lines.append(f"  {regime.replace('_', '-').title()} ({years_str}): {', '.join(parts)}")

    if current_regime:
        # Find strongest factors for current regime
        cur_factors = regime_factors.get(current_regime, [])
        if cur_factors:
            cur_factors.sort(key=lambda f: f[1], reverse=True)
            top2 = [_names.get(f, f) for f, ic, _ in cur_factors[:2] if ic > 0]
            if top2:
                lines.append(
                    f"  Current regime: {current_regime} → "
                    f"{' and '.join(top2)} factors historically strongest"
                )

    return "\n".join(lines)
