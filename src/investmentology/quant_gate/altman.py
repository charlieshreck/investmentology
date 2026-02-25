from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from investmentology.models.stock import FundamentalsSnapshot

logger = logging.getLogger(__name__)

ZERO = Decimal(0)

# Altman Z-Score thresholds
SAFE_THRESHOLD = Decimal("2.99")
GREY_THRESHOLD = Decimal("1.81")

# Altman Z-Score coefficients
COEFF_A = Decimal("1.2")
COEFF_B = Decimal("1.4")
COEFF_C = Decimal("3.3")
COEFF_D = Decimal("0.6")
COEFF_E = Decimal("1.0")


@dataclass
class AltmanResult:
    ticker: str
    z_score: Decimal
    zone: str  # "safe" (>2.99), "grey" (1.81-2.99), "distress" (<1.81)
    is_approximate: bool = False


def _classify_zone(z_score: Decimal) -> str:
    """Classify the Z-score into safe/grey/distress zones."""
    if z_score > SAFE_THRESHOLD:
        return "safe"
    if z_score >= GREY_THRESHOLD:
        return "grey"
    return "distress"


def calculate_altman(snapshot: FundamentalsSnapshot) -> AltmanResult | None:
    """Calculate Altman Z-Score.

    Z = 1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E

    A = Working Capital / Total Assets
    B = Retained Earnings / Total Assets (approximated: net_income / total_assets)
    C = EBIT / Total Assets (operating_income / total_assets)
    D = Market Cap / Total Liabilities
    E = Revenue / Total Assets

    Returns None if required data is missing (zero total_assets or total_liabilities).
    """
    if snapshot.total_assets <= ZERO:
        logger.debug("Cannot calculate Altman Z for %s: zero total_assets", snapshot.ticker)
        return None

    if snapshot.total_liabilities <= ZERO:
        logger.debug("Cannot calculate Altman Z for %s: zero total_liabilities", snapshot.ticker)
        return None

    ta = snapshot.total_assets

    # A: Working Capital / Total Assets
    working_capital = snapshot.current_assets - snapshot.current_liabilities
    a = working_capital / ta

    # B: Retained Earnings / Total Assets
    # NOTE: Uses net_income as proxy — retained_earnings not available from yfinance/EDGAR bulk.
    # This understates B for mature companies with large accumulated RE.
    b = snapshot.net_income / ta

    # C: EBIT / Total Assets
    c = snapshot.operating_income / ta

    # D: Market Cap / Total Liabilities
    d = snapshot.market_cap / snapshot.total_liabilities

    # E: Revenue / Total Assets
    e = snapshot.revenue / ta

    z_score = (COEFF_A * a) + (COEFF_B * b) + (COEFF_C * c) + (COEFF_D * d) + (COEFF_E * e)

    return AltmanResult(
        ticker=snapshot.ticker,
        z_score=z_score,
        zone=_classify_zone(z_score),
        is_approximate=True,  # net_income proxy for retained_earnings
    )
