from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from investmentology.models.stock import FundamentalsSnapshot

logger = logging.getLogger(__name__)

# Sectors excluded per Greenblatt's original methodology
EXCLUDED_SECTORS = frozenset({"Financial Services", "Utilities"})


@dataclass
class GreenblattResult:
    ticker: str
    earnings_yield: Decimal | None
    roic: Decimal | None
    ey_rank: int
    roic_rank: int
    combined_rank: int  # ey_rank + roic_rank (lowest = best)


def should_exclude(snapshot: FundamentalsSnapshot) -> tuple[bool, str]:
    """Check Greenblatt exclusion criteria. Returns (excluded, reason)."""
    # We don't have sector on FundamentalsSnapshot directly,
    # but we do have the numeric fields. Sector filtering is handled
    # upstream by universe.py. Here we enforce data-quality exclusions.

    if not snapshot.operating_income or snapshot.operating_income <= 0:
        return True, "negative_or_zero_ebit"

    if not snapshot.market_cap or snapshot.market_cap <= 0:
        return True, "missing_market_cap"

    if snapshot.invested_capital <= 0:
        return True, "negative_invested_capital"

    ev = snapshot.enterprise_value
    if ev <= 0:
        return True, "negative_enterprise_value"

    return False, ""


def should_exclude_with_sector(
    snapshot: FundamentalsSnapshot, sector: str,
) -> tuple[bool, str]:
    """Check exclusion criteria including sector check."""
    if sector in EXCLUDED_SECTORS:
        return True, f"excluded_sector:{sector}"
    return should_exclude(snapshot)


def rank_by_greenblatt(
    snapshots: list[FundamentalsSnapshot],
    sectors: dict[str, str] | None = None,
) -> list[GreenblattResult]:
    """Apply Greenblatt Magic Formula ranking.

    1. Filter out excluded stocks
    2. Rank by earnings_yield (highest = rank 1)
    3. Rank by ROIC (highest = rank 1)
    4. Combined rank = ey_rank + roic_rank
    5. Sort by combined_rank ascending (lowest = best)

    Args:
        snapshots: List of fundamentals snapshots to rank.
        sectors: Optional ticker->sector mapping for sector exclusions.
    """
    eligible: list[FundamentalsSnapshot] = []
    exclusion_counts: dict[str, int] = {}

    for snap in snapshots:
        if sectors:
            excluded, reason = should_exclude_with_sector(
                snap, sectors.get(snap.ticker, ""),
            )
        else:
            excluded, reason = should_exclude(snap)

        if excluded:
            exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
            continue
        eligible.append(snap)

    if exclusion_counts:
        logger.info("Greenblatt exclusions: %s", exclusion_counts)

    if not eligible:
        return []

    # Sort by earnings_yield descending (highest = rank 1)
    by_ey = sorted(
        eligible,
        key=lambda s: s.earnings_yield or Decimal(0),
        reverse=True,
    )
    ey_ranks: dict[str, int] = {
        snap.ticker: rank for rank, snap in enumerate(by_ey, start=1)
    }

    # Sort by ROIC descending (highest = rank 1)
    by_roic = sorted(
        eligible,
        key=lambda s: s.roic or Decimal(0),
        reverse=True,
    )
    roic_ranks: dict[str, int] = {
        snap.ticker: rank for rank, snap in enumerate(by_roic, start=1)
    }

    # Build results with combined rank
    results: list[GreenblattResult] = []
    for snap in eligible:
        ey_rank = ey_ranks[snap.ticker]
        roic_rank = roic_ranks[snap.ticker]
        results.append(GreenblattResult(
            ticker=snap.ticker,
            earnings_yield=snap.earnings_yield,
            roic=snap.roic,
            ey_rank=ey_rank,
            roic_rank=roic_rank,
            combined_rank=ey_rank + roic_rank,
        ))

    # Sort by combined rank ascending (lowest = best)
    results.sort(key=lambda r: r.combined_rank)
    return results
