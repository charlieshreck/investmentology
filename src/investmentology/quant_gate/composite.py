"""Composite scoring: 6-factor O'Shaughnessy-style composite.

Weights:
    30% — Greenblatt rank percentile (EV/EBIT + ROIC)
    20% — Piotroski F-Score (financial health quality)
    10% — Altman Z-Score zone (distress risk)
    15% — Momentum (Jegadeesh-Titman 12-1 month)
    15% — Gross Profitability (Novy-Marx: gross profit / total assets)
    10% — Shareholder Yield (dividend yield + net buyback yield)

When optional factors are unavailable, their weight is redistributed
proportionally among available factors.

Value-momentum intersection: +3% bonus when BOTH value (Greenblatt top
quartile) AND momentum (top quartile) score in the top 25%.

Output: 0.0 (worst) to ~1.03 (best, with intersection bonus).
"""

from __future__ import annotations

from decimal import Decimal

WEIGHT_GREENBLATT = Decimal("0.30")
WEIGHT_PIOTROSKI = Decimal("0.20")
WEIGHT_ALTMAN = Decimal("0.10")
WEIGHT_MOMENTUM = Decimal("0.15")
WEIGHT_GROSS_PROFITABILITY = Decimal("0.15")
WEIGHT_SHAREHOLDER_YIELD = Decimal("0.10")

# Value-momentum intersection bonus
VM_INTERSECTION_BONUS = Decimal("0.03")
VM_TOP_QUARTILE = Decimal("0.75")

PIOTROSKI_MAX_WITH_PRIOR = 9

# Altman zone scores
ALTMAN_ZONE_SCORES: dict[str | None, Decimal] = {
    "safe": Decimal("1.0"),
    "grey": Decimal("0.5"),
    "distress": Decimal("0.0"),
    None: Decimal("0.3"),
}


def composite_score(
    *,
    greenblatt_rank: int,
    total_ranked: int,
    piotroski_score: int,
    has_prior_year: bool,
    altman_zone: str | None,
    momentum_score: float | None = None,
    gross_profitability: float | None = None,
    shareholder_yield: float | None = None,
) -> Decimal:
    """Calculate 6-factor composite score (0.0-1.0+, higher = better).

    Args:
        greenblatt_rank: Combined rank from Greenblatt (lower = better).
        total_ranked: Total number of ranked stocks (for percentile).
        piotroski_score: F-Score (0-9).
        has_prior_year: Whether prior-year data was available for Piotroski.
        altman_zone: "safe", "grey", "distress", or None.
        momentum_score: Cross-sectional momentum rank (0.0-1.0), or None.
        gross_profitability: Cross-sectional gross profitability rank (0.0-1.0), or None.
        shareholder_yield: Cross-sectional shareholder yield rank (0.0-1.0), or None.
    """
    # Greenblatt component: rank 1 of 100 = 0.99, rank 100 of 100 = 0.0
    if total_ranked > 1:
        greenblatt_pct = Decimal(total_ranked - greenblatt_rank) / Decimal(total_ranked - 1)
    else:
        greenblatt_pct = Decimal("1.0")
    greenblatt_pct = max(Decimal("0"), min(Decimal("1"), greenblatt_pct))

    # Piotroski component
    piotroski_pct = Decimal(piotroski_score) / Decimal(PIOTROSKI_MAX_WITH_PRIOR)
    if not has_prior_year:
        piotroski_pct = min(piotroski_pct, Decimal("0.5"))
    piotroski_pct = min(Decimal("1"), piotroski_pct)

    # Altman component
    altman_pct = ALTMAN_ZONE_SCORES.get(altman_zone, Decimal("0.3"))

    # Build weighted components — only include factors that have data
    components: list[tuple[Decimal, Decimal]] = [
        (WEIGHT_GREENBLATT, greenblatt_pct),
        (WEIGHT_PIOTROSKI, piotroski_pct),
        (WEIGHT_ALTMAN, altman_pct),
    ]

    if momentum_score is not None:
        mom_pct = Decimal(str(max(0.0, min(1.0, momentum_score))))
        components.append((WEIGHT_MOMENTUM, mom_pct))

    if gross_profitability is not None:
        gp_pct = Decimal(str(max(0.0, min(1.0, gross_profitability))))
        components.append((WEIGHT_GROSS_PROFITABILITY, gp_pct))

    if shareholder_yield is not None:
        sy_pct = Decimal(str(max(0.0, min(1.0, shareholder_yield))))
        components.append((WEIGHT_SHAREHOLDER_YIELD, sy_pct))

    # Redistribute unavailable weights proportionally
    total_weight = sum(w for w, _ in components)
    score = sum((w / total_weight) * v for w, v in components)

    # Value-momentum intersection bonus: both in top quartile
    if momentum_score is not None and greenblatt_pct >= VM_TOP_QUARTILE:
        mom_pct_check = Decimal(str(momentum_score))
        if mom_pct_check >= VM_TOP_QUARTILE:
            score += VM_INTERSECTION_BONUS

    return round(score, 4)
