from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from investmentology.models.stock import FundamentalsSnapshot

logger = logging.getLogger(__name__)

ZERO = Decimal(0)


@dataclass
class PiotroskiResult:
    ticker: str
    score: int  # 0-9
    details: dict[str, bool]  # Which tests passed


def _safe_div(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """Safe division returning None if denominator is zero."""
    if denominator == 0:
        return None
    return numerator / denominator


def calculate_piotroski(
    current: FundamentalsSnapshot,
    previous: FundamentalsSnapshot | None = None,
) -> PiotroskiResult:
    """Calculate Piotroski F-Score (0-9, higher = stronger).

    Profitability (4 points):
    1. Positive net income
    2. Positive operating cash flow (approximate: net_income + depreciation,
       using net_income > 0 as proxy when depreciation unavailable)
    3. ROA improving (current net_income/total_assets > previous)
    4. Cash flow > net income (accruals quality)

    Leverage (3 points):
    5. Debt ratio decreasing (total_debt/total_assets)
    6. Current ratio improving (current_assets/current_liabilities)
    7. No new shares issued (shares_outstanding not increased)

    Efficiency (2 points):
    8. Gross margin improving (approximate with operating_income/revenue)
    9. Asset turnover improving (revenue/total_assets)

    If no previous snapshot, score only what we can (points 1, 2, 4).
    """
    details: dict[str, bool] = {}

    # --- Profitability ---

    # 1. Positive net income
    details["positive_net_income"] = current.net_income > ZERO

    # 2. Positive operating cash flow (proxy: operating_income > 0)
    # Without a cash flow statement, operating income is the best available proxy.
    details["positive_ocf"] = current.operating_income > ZERO

    # 3. ROA improving
    if previous is not None and current.total_assets > ZERO and previous.total_assets > ZERO:
        current_roa = current.net_income / current.total_assets
        previous_roa = previous.net_income / previous.total_assets
        details["roa_improving"] = current_roa > previous_roa
    else:
        details["roa_improving"] = False

    # 4. Accruals quality: OCF > net income
    # Without real OCF, approximate: operating_income > net_income
    # (meaning real cash earnings exceed reported, i.e., low accruals)
    details["accruals_quality"] = current.operating_income > current.net_income

    # --- Leverage ---

    # 5. Debt ratio decreasing
    if previous is not None and current.total_assets > ZERO and previous.total_assets > ZERO:
        current_debt_ratio = _safe_div(current.total_debt, current.total_assets)
        previous_debt_ratio = _safe_div(previous.total_debt, previous.total_assets)
        if current_debt_ratio is not None and previous_debt_ratio is not None:
            details["debt_ratio_decreasing"] = current_debt_ratio < previous_debt_ratio
        else:
            details["debt_ratio_decreasing"] = False
    else:
        details["debt_ratio_decreasing"] = False

    # 6. Current ratio improving
    if previous is not None:
        current_cr = _safe_div(current.current_assets, current.current_liabilities)
        previous_cr = _safe_div(previous.current_assets, previous.current_liabilities)
        if current_cr is not None and previous_cr is not None:
            details["current_ratio_improving"] = current_cr > previous_cr
        else:
            details["current_ratio_improving"] = False
    else:
        details["current_ratio_improving"] = False

    # 7. No new shares issued
    if previous is not None:
        details["no_dilution"] = current.shares_outstanding <= previous.shares_outstanding
    else:
        details["no_dilution"] = False

    # --- Efficiency ---

    # 8. Gross margin improving (proxy: operating margin = operating_income/revenue)
    if previous is not None and current.revenue > ZERO and previous.revenue > ZERO:
        current_margin = current.operating_income / current.revenue
        previous_margin = previous.operating_income / previous.revenue
        details["gross_margin_improving"] = current_margin > previous_margin
    else:
        details["gross_margin_improving"] = False

    # 9. Asset turnover improving
    if previous is not None and current.total_assets > ZERO and previous.total_assets > ZERO:
        current_turnover = current.revenue / current.total_assets
        previous_turnover = previous.revenue / previous.total_assets
        details["asset_turnover_improving"] = current_turnover > previous_turnover
    else:
        details["asset_turnover_improving"] = False

    score = sum(1 for passed in details.values() if passed)

    return PiotroskiResult(ticker=current.ticker, score=score, details=details)
