"""Composite scoring: blends Greenblatt rank, Piotroski F-Score, and Altman Z-Score.

Weights:
    50% — Greenblatt rank percentile (lower rank = better score)
    30% — Piotroski F-Score (higher = better, normalized to 0-1)
    20% — Altman Z-Score zone (safe=1.0, grey=0.5, distress=0.0)

Output: 0.0 (worst) to 1.0 (best).
"""

from __future__ import annotations

from decimal import Decimal

WEIGHT_GREENBLATT = Decimal("0.50")
WEIGHT_PIOTROSKI = Decimal("0.30")
WEIGHT_ALTMAN = Decimal("0.20")

# Piotroski max possible is 9, but without prior-year data only 4 tests
# are scoreable. We normalize against the number of tests that could fire.
PIOTROSKI_MAX_WITHOUT_PRIOR = 4
PIOTROSKI_MAX_WITH_PRIOR = 9

# Altman zone scores
ALTMAN_ZONE_SCORES: dict[str | None, Decimal] = {
    "safe": Decimal("1.0"),
    "grey": Decimal("0.5"),
    "distress": Decimal("0.0"),
    None: Decimal("0.3"),  # missing data — treated as grey-ish
}


def composite_score(
    *,
    greenblatt_rank: int,
    total_ranked: int,
    piotroski_score: int,
    has_prior_year: bool,
    altman_zone: str | None,
) -> Decimal:
    """Calculate composite score (0.0-1.0, higher = better).

    Args:
        greenblatt_rank: Combined rank from Greenblatt (lower = better).
        total_ranked: Total number of ranked stocks (for percentile).
        piotroski_score: F-Score (0-9).
        has_prior_year: Whether prior-year data was available for Piotroski.
        altman_zone: "safe", "grey", "distress", or None.
    """
    # Greenblatt component: rank 1 of 100 = 0.99, rank 100 of 100 = 0.0
    if total_ranked > 1:
        greenblatt_pct = Decimal(total_ranked - greenblatt_rank) / Decimal(total_ranked - 1)
    else:
        greenblatt_pct = Decimal("1.0")
    greenblatt_pct = max(Decimal("0"), min(Decimal("1"), greenblatt_pct))

    # Piotroski component: normalize against achievable max
    piotroski_max = PIOTROSKI_MAX_WITH_PRIOR if has_prior_year else PIOTROSKI_MAX_WITHOUT_PRIOR
    piotroski_pct = Decimal(piotroski_score) / Decimal(piotroski_max)
    piotroski_pct = min(Decimal("1"), piotroski_pct)

    # Altman component
    altman_pct = ALTMAN_ZONE_SCORES.get(altman_zone, Decimal("0.3"))

    score = (
        WEIGHT_GREENBLATT * greenblatt_pct
        + WEIGHT_PIOTROSKI * piotroski_pct
        + WEIGHT_ALTMAN * altman_pct
    )
    return round(score, 4)
