"""Beneish M-Score: earnings manipulation detector.

The Beneish model uses 8 financial ratios comparing current to prior year.
M-Score > -1.78 flags a likely earnings manipulator (~76% detection rate).

Reference: Beneish, M.D. (1999). "The Detection of Earnings Manipulation."
           Financial Analysts Journal, 55(5), 24-36.

Used as a binary exclusion filter in the quant gate — not a composite component.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from investmentology.models.stock import FundamentalsSnapshot

logger = logging.getLogger(__name__)

ZERO = Decimal(0)
MANIPULATION_THRESHOLD = Decimal("-1.78")

# M-Score coefficients
INTERCEPT = Decimal("-4.84")
COEFF_DSRI = Decimal("0.920")
COEFF_GMI = Decimal("0.528")
COEFF_AQI = Decimal("0.404")
COEFF_SGI = Decimal("0.892")
COEFF_DEPI = Decimal("0.115")
COEFF_SGAI = Decimal("-0.172")
COEFF_LVGI = Decimal("-0.327")
COEFF_TATA = Decimal("4.679")


@dataclass
class BeneishResult:
    ticker: str
    m_score: Decimal
    is_manipulator: bool  # True if M > -1.78
    components: dict[str, Decimal | None]  # Individual index values
    data_sufficient: bool  # False if too many missing inputs


def calculate_beneish(
    current: FundamentalsSnapshot,
    prior: FundamentalsSnapshot | None,
) -> BeneishResult | None:
    """Calculate the Beneish M-Score from current and prior year fundamentals.

    Requires both current and prior year snapshots. Returns None if prior year
    is unavailable (cannot compute year-over-year ratios).

    The 8 variables:
    1. DSRI — Days Sales in Receivables Index
    2. GMI  — Gross Margin Index
    3. AQI  — Asset Quality Index
    4. SGI  — Sales Growth Index
    5. DEPI — Depreciation Index
    6. SGAI — SGA Index
    7. LVGI — Leverage Index
    8. TATA — Total Accruals to Total Assets
    """
    if prior is None:
        return None

    # Guard: need revenue in both periods
    if current.revenue <= ZERO or prior.revenue <= ZERO:
        logger.debug("Beneish: insufficient revenue data for %s", current.ticker)
        return None

    if current.total_assets <= ZERO or prior.total_assets <= ZERO:
        logger.debug("Beneish: insufficient total_assets for %s", current.ticker)
        return None

    components: dict[str, Decimal | None] = {}
    missing = 0

    # 1. DSRI = (Receivables_t / Revenue_t) / (Receivables_t-1 / Revenue_t-1)
    dsri = None
    if current.receivables > ZERO and prior.receivables > ZERO:
        curr_ratio = current.receivables / current.revenue
        prior_ratio = prior.receivables / prior.revenue
        if prior_ratio > ZERO:
            dsri = curr_ratio / prior_ratio
    elif current.receivables == ZERO and prior.receivables == ZERO:
        dsri = Decimal("1.0")  # No receivables change
    else:
        missing += 1
    components["dsri"] = dsri

    # 2. GMI = Gross_Margin_t-1 / Gross_Margin_t
    # (higher GMI = deteriorating margins = manipulation signal)
    gmi = None
    if prior.gross_profit > ZERO and current.gross_profit > ZERO:
        prior_gm = prior.gross_profit / prior.revenue
        curr_gm = current.gross_profit / current.revenue
        if curr_gm > ZERO:
            gmi = prior_gm / curr_gm
    elif prior.gross_profit == ZERO and current.gross_profit == ZERO:
        gmi = Decimal("1.0")
    else:
        missing += 1
    components["gmi"] = gmi

    # 3. AQI = (1 - (CA + PPE) / TA)_t / (1 - (CA + PPE) / TA)_t-1
    # Measures proportion of "soft" assets
    aqi = None
    curr_hard = (current.current_assets + current.net_ppe) / current.total_assets
    prior_hard = (prior.current_assets + prior.net_ppe) / prior.total_assets
    curr_soft = Decimal("1") - curr_hard
    prior_soft = Decimal("1") - prior_hard
    if prior_soft > ZERO:
        aqi = curr_soft / prior_soft
    elif curr_soft == ZERO and prior_soft == ZERO:
        aqi = Decimal("1.0")
    else:
        missing += 1
    components["aqi"] = aqi

    # 4. SGI = Revenue_t / Revenue_t-1
    sgi = current.revenue / prior.revenue
    components["sgi"] = sgi

    # 5. DEPI = (Depreciation Rate)_t-1 / (Depreciation Rate)_t
    # Depreciation Rate = Depreciation / (Depreciation + PPE)
    depi = None
    if current.depreciation > ZERO and prior.depreciation > ZERO:
        curr_base = current.depreciation + current.net_ppe
        prior_base = prior.depreciation + prior.net_ppe
        if curr_base > ZERO and prior_base > ZERO:
            curr_rate = current.depreciation / curr_base
            prior_rate = prior.depreciation / prior_base
            if curr_rate > ZERO:
                depi = prior_rate / curr_rate
    elif current.depreciation == ZERO and prior.depreciation == ZERO:
        depi = Decimal("1.0")
    else:
        missing += 1
    components["depi"] = depi

    # 6. SGAI = (SGA / Revenue)_t / (SGA / Revenue)_t-1
    sgai = None
    if current.sga > ZERO and prior.sga > ZERO:
        curr_ratio = current.sga / current.revenue
        prior_ratio = prior.sga / prior.revenue
        if prior_ratio > ZERO:
            sgai = curr_ratio / prior_ratio
    elif current.sga == ZERO and prior.sga == ZERO:
        sgai = Decimal("1.0")
    else:
        missing += 1
    components["sgai"] = sgai

    # 7. LVGI = (TL / TA)_t / (TL / TA)_t-1
    lvgi = None
    if current.total_liabilities > ZERO and prior.total_liabilities > ZERO:
        curr_lev = current.total_liabilities / current.total_assets
        prior_lev = prior.total_liabilities / prior.total_assets
        if prior_lev > ZERO:
            lvgi = curr_lev / prior_lev
    elif current.total_liabilities == ZERO and prior.total_liabilities == ZERO:
        lvgi = Decimal("1.0")
    else:
        missing += 1
    components["lvgi"] = lvgi

    # 8. TATA = (Net Income - Operating Cash Flow) / Total Assets
    tata = None
    if current.operating_cash_flow != ZERO or current.net_income != ZERO:
        tata = (current.net_income - current.operating_cash_flow) / current.total_assets
    else:
        missing += 1
    components["tata"] = tata

    # Need at least 5 of 8 components to produce a meaningful score
    data_sufficient = missing <= 3
    if not data_sufficient:
        logger.debug(
            "Beneish: only %d/8 components available for %s, skipping",
            8 - missing, current.ticker,
        )
        return BeneishResult(
            ticker=current.ticker,
            m_score=ZERO,
            is_manipulator=False,
            components=components,
            data_sufficient=False,
        )

    # Substitute 1.0 (neutral) for any missing components
    dsri = dsri if dsri is not None else Decimal("1.0")
    gmi = gmi if gmi is not None else Decimal("1.0")
    aqi = aqi if aqi is not None else Decimal("1.0")
    sgi = sgi if sgi is not None else Decimal("1.0")
    depi = depi if depi is not None else Decimal("1.0")
    sgai = sgai if sgai is not None else Decimal("1.0")
    lvgi = lvgi if lvgi is not None else Decimal("1.0")
    tata = tata if tata is not None else ZERO

    m_score = (
        INTERCEPT
        + COEFF_DSRI * dsri
        + COEFF_GMI * gmi
        + COEFF_AQI * aqi
        + COEFF_SGI * sgi
        + COEFF_DEPI * depi
        + COEFF_SGAI * sgai
        + COEFF_LVGI * lvgi
        + COEFF_TATA * tata
    )

    return BeneishResult(
        ticker=current.ticker,
        m_score=m_score,
        is_manipulator=m_score > MANIPULATION_THRESHOLD,
        components=components,
        data_sufficient=True,
    )
