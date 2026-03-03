"""Deterministic pre-filter — removes obviously unviable stocks before LLM screening.

Fast, zero-cost filter that catches the bottom ~10-15% of tickers that are
clearly not worth ANY LLM compute. Conservative by design — only rejects
stocks that fail hard quantitative cutoffs.

Runs after data_validate and before screener LLM calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Sectors exempt from debt/equity filters (naturally high leverage)
_FINANCIAL_SECTORS = {"Financial Services", "Financial", "Banking", "Insurance"}


@dataclass
class PreFilterResult:
    """Result of the deterministic pre-filter."""

    ticker: str
    passed: bool
    rejection_reason: str | None = None
    rules_checked: int = 0
    rules_failed: list[str] = field(default_factory=list)


def deterministic_pre_filter(
    fundamentals: dict,
    quant_gate: dict | None = None,
    technical_indicators: dict | None = None,
) -> PreFilterResult:
    """Apply hard quantitative cutoffs to filter obviously unviable stocks.

    Args:
        fundamentals: Cached yfinance fundamentals dict.
        quant_gate: Dict with combined_rank, piotroski_score, altman_z_score.
        technical_indicators: Cached technical indicators dict.

    Returns:
        PreFilterResult with passed=True/False and rejection reasons.
    """
    ticker = fundamentals.get("ticker", "???")
    result = PreFilterResult(ticker=ticker, passed=True)
    sector = fundamentals.get("sector", "")
    is_financial = sector in _FINANCIAL_SECTORS

    def _float(val) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    # Extract fields
    operating_income = _float(fundamentals.get("operating_income"))
    net_income = _float(fundamentals.get("net_income"))
    revenue_growth = _float(fundamentals.get("revenue_growth"))
    pe_ratio = _float(fundamentals.get("pe_ratio"))
    total_debt = _float(fundamentals.get("total_debt"))
    total_assets = _float(fundamentals.get("total_assets"))

    # Quant gate scores
    altman_z = None
    piotroski = None
    if quant_gate:
        altman_z = _float(quant_gate.get("altman_z_score"))
        piotroski = _float(quant_gate.get("piotroski_score"))

    # --- Rule 1: Altman extreme distress ---
    result.rules_checked += 1
    if altman_z is not None and altman_z < 1.0 and not is_financial:
        result.rules_failed.append(
            f"altman_z_distress: Z={altman_z:.2f} < 1.0 (extreme distress)"
        )

    # --- Rule 2: Piotroski catastrophic ---
    result.rules_checked += 1
    if piotroski is not None and piotroski <= 1:
        result.rules_failed.append(
            f"piotroski_catastrophic: score={int(piotroski)}/9 (near-total failure)"
        )

    # --- Rule 3: Triple negative ---
    result.rules_checked += 1
    if (
        operating_income is not None
        and net_income is not None
        and revenue_growth is not None
        and operating_income < 0
        and net_income < 0
        and revenue_growth < -0.10
    ):
        result.rules_failed.append(
            f"triple_negative: OI={operating_income:.0f}, NI={net_income:.0f}, "
            f"rev_growth={revenue_growth:.1%} (losing money AND shrinking)"
        )

    # --- Rule 4: Extreme P/E with no growth ---
    result.rules_checked += 1
    if (
        pe_ratio is not None
        and pe_ratio > 100
        and (revenue_growth is None or revenue_growth < 0.05)
    ):
        rg_str = f"{revenue_growth:.1%}" if revenue_growth is not None else "N/A"
        result.rules_failed.append(
            f"extreme_pe_no_growth: P/E={pe_ratio:.1f} > 100 with "
            f"revenue_growth={rg_str} (speculation without growth)"
        )

    # --- Rule 5: Losing + shrinking ---
    result.rules_checked += 1
    if (
        pe_ratio is not None
        and pe_ratio < 0
        and revenue_growth is not None
        and revenue_growth < -0.05
    ):
        result.rules_failed.append(
            f"losing_and_shrinking: P/E={pe_ratio:.1f} (negative) with "
            f"revenue_growth={revenue_growth:.1%} (no thesis)"
        )

    # --- Rule 6: Debt implosion (non-financials only) ---
    result.rules_checked += 1
    if (
        not is_financial
        and total_debt is not None
        and total_assets is not None
        and total_assets > 0
        and total_debt / total_assets > 0.95
    ):
        ratio = total_debt / total_assets
        result.rules_failed.append(
            f"debt_implosion: debt/assets={ratio:.2f} > 0.95 (near-insolvent)"
        )

    # --- Verdict ---
    if result.rules_failed:
        result.passed = False
        result.rejection_reason = "; ".join(result.rules_failed)
        logger.info(
            "Pre-filter REJECT %s: %s", ticker, result.rejection_reason,
        )
    else:
        logger.debug(
            "Pre-filter PASS %s (%d rules checked)", ticker, result.rules_checked,
        )

    return result
