from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from investmentology.models.stock import FundamentalsSnapshot

logger = logging.getLogger(__name__)

ZERO = Decimal(0)

# Original Altman Z-Score (manufacturing): Z = 1.2A + 1.4B + 3.3C + 0.6D + 1.0E
SAFE_THRESHOLD = Decimal("2.99")
GREY_THRESHOLD = Decimal("1.81")
COEFF_A = Decimal("1.2")
COEFF_B = Decimal("1.4")
COEFF_C = Decimal("3.3")
COEFF_D = Decimal("0.6")
COEFF_E = Decimal("1.0")

# Altman Z'' (non-manufacturing): Z'' = 6.56A + 3.26B + 6.72C + 1.05D
# Drops Revenue/Assets (E) term since services/tech are asset-light.
# D uses Book Value of Equity / Total Liabilities (not Market Cap).
ZPP_SAFE_THRESHOLD = Decimal("2.60")
ZPP_GREY_THRESHOLD = Decimal("1.10")
ZPP_COEFF_A = Decimal("6.56")
ZPP_COEFF_B = Decimal("3.26")
ZPP_COEFF_C = Decimal("6.72")
ZPP_COEFF_D = Decimal("1.05")

# Sectors that use the original manufacturing Z formula.
# All other sectors use Z'' (non-manufacturing).
_MANUFACTURING_SECTORS = frozenset({
    "Industrials",
    "Basic Materials",
    "Energy",
})


@dataclass
class AltmanResult:
    ticker: str
    z_score: Decimal
    zone: str  # "safe" (>2.99), "grey" (1.81-2.99), "distress" (<1.81)
    is_approximate: bool = False


def _classify_zone(z_score: Decimal, *, use_zpp: bool = False) -> str:
    """Classify the Z-score into safe/grey/distress zones."""
    safe = ZPP_SAFE_THRESHOLD if use_zpp else SAFE_THRESHOLD
    grey = ZPP_GREY_THRESHOLD if use_zpp else GREY_THRESHOLD
    if z_score > safe:
        return "safe"
    if z_score >= grey:
        return "grey"
    return "distress"


def calculate_altman(
    snapshot: FundamentalsSnapshot,
    sector: str = "",
) -> AltmanResult | None:
    """Calculate Altman Z-Score, routing to Z (manufacturing) or Z'' (non-manufacturing).

    Original Z (manufacturing): Z = 1.2A + 1.4B + 3.3C + 0.6D + 1.0E
        D = Market Cap / Total Liabilities
        Thresholds: safe > 2.99, grey 1.81-2.99, distress < 1.81

    Z'' (non-manufacturing): Z'' = 6.56A + 3.26B + 6.72C + 1.05D
        D = Book Value of Equity / Total Liabilities (asset-light adjustment)
        Thresholds: safe > 2.60, grey 1.10-2.60, distress < 1.10

    Returns None if required data is missing (zero total_assets or total_liabilities).
    """
    if snapshot.total_assets <= ZERO:
        logger.debug("Cannot calculate Altman Z for %s: zero total_assets", snapshot.ticker)
        return None

    if snapshot.total_liabilities <= ZERO:
        logger.debug("Cannot calculate Altman Z for %s: zero total_liabilities", snapshot.ticker)
        return None

    ta = snapshot.total_assets
    use_zpp = sector not in _MANUFACTURING_SECTORS

    # A: Working Capital / Total Assets
    working_capital = snapshot.current_assets - snapshot.current_liabilities
    a = working_capital / ta

    # B: Retained Earnings / Total Assets
    # Use real retained_earnings when available; fall back to net_income as proxy.
    re = snapshot.retained_earnings if snapshot.retained_earnings != ZERO else snapshot.net_income
    b = re / ta
    has_real_re = snapshot.retained_earnings != ZERO

    # C: EBIT / Total Assets
    c = snapshot.operating_income / ta

    if use_zpp:
        # Z'' (non-manufacturing): D = Book Value of Equity / Total Liabilities
        book_equity = snapshot.total_assets - snapshot.total_liabilities
        d = book_equity / snapshot.total_liabilities
        z_score = (ZPP_COEFF_A * a) + (ZPP_COEFF_B * b) + (ZPP_COEFF_C * c) + (ZPP_COEFF_D * d)
    else:
        # Original Z (manufacturing): D = Market Cap / TL, E = Revenue / TA
        d = snapshot.market_cap / snapshot.total_liabilities
        e = snapshot.revenue / ta
        z_score = (COEFF_A * a) + (COEFF_B * b) + (COEFF_C * c) + (COEFF_D * d) + (COEFF_E * e)

    return AltmanResult(
        ticker=snapshot.ticker,
        z_score=z_score,
        zone=_classify_zone(z_score, use_zpp=use_zpp),
        is_approximate=not has_real_re,
    )
