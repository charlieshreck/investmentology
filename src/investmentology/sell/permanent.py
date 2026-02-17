from __future__ import annotations

from decimal import Decimal

from investmentology.models.position import PortfolioPosition
from investmentology.models.stock import FundamentalsSnapshot
from investmentology.sell.rules import SellReason, SellSignal, SellUrgency


def check_permanent_rules(
    position: PortfolioPosition,
    fundamentals: list[FundamentalsSnapshot],
) -> list[SellSignal]:
    """Check sell rules for permanent holdings.

    FLAG only (never auto-sell):
    - Revenue decline > 15% YoY for 2+ consecutive quarters
    - Margin compression > 500 basis points (operating_income/revenue drop)

    Fundamentals should be ordered oldest-first.
    """
    signals: list[SellSignal] = []

    if len(fundamentals) < 2:
        return signals

    # --- Revenue decline > 15% YoY for 2+ consecutive quarters ---
    consecutive_declines = 0
    for i in range(1, len(fundamentals)):
        prev_rev = fundamentals[i - 1].revenue
        curr_rev = fundamentals[i].revenue
        if prev_rev > 0:
            yoy_change = (curr_rev - prev_rev) / prev_rev
            if yoy_change < Decimal("-0.15"):
                consecutive_declines += 1
            else:
                consecutive_declines = 0

    if consecutive_declines >= 2:
        signals.append(
            SellSignal(
                ticker=position.ticker,
                reason=SellReason.THESIS_BREAK,
                urgency=SellUrgency.FLAG,
                detail=(
                    f"Revenue declined >15% for {consecutive_declines} "
                    f"consecutive periods"
                ),
                current_price=position.current_price,
            )
        )

    # --- Margin compression > 500 basis points ---
    earliest = fundamentals[0]
    latest = fundamentals[-1]
    if earliest.revenue > 0 and latest.revenue > 0:
        margin_early = earliest.operating_income / earliest.revenue
        margin_late = latest.operating_income / latest.revenue
        compression_bps = (margin_early - margin_late) * Decimal("10000")
        if compression_bps > Decimal("500"):
            signals.append(
                SellSignal(
                    ticker=position.ticker,
                    reason=SellReason.THESIS_BREAK,
                    urgency=SellUrgency.FLAG,
                    detail=(
                        f"Operating margin compressed {compression_bps:.0f} bps "
                        f"({margin_early:.2%} -> {margin_late:.2%})"
                    ),
                    current_price=position.current_price,
                )
            )

    return signals
