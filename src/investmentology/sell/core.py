from __future__ import annotations

from decimal import Decimal

from investmentology.models.position import PortfolioPosition
from investmentology.models.stock import FundamentalsSnapshot
from investmentology.sell.rules import SellReason, SellSignal, SellUrgency


def check_core_rules(
    position: PortfolioPosition,
    fundamentals: list[FundamentalsSnapshot],
    fair_value: Decimal | None = None,
    highest_price_since_entry: Decimal | None = None,
) -> list[SellSignal]:
    """Check sell rules for core holdings.

    SIGNAL level:
    - Trailing stop: 20% below peak (needs highest price since entry)
    - ROIC declining for 3 consecutive quarters
    - Debt/EBITDA > 3x
    - Insider selling > $10M in 6 months (placeholder)

    Take profit:
    - 150% of fair value estimate -> full exit SIGNAL
    - 120% of fair value estimate -> trim 1/3 SIGNAL

    Fundamentals should be ordered oldest-first.
    """
    signals: list[SellSignal] = []

    # --- Trailing stop: 20% below peak ---
    peak = highest_price_since_entry or position.current_price
    trailing_trigger = peak * Decimal("0.80")
    if position.current_price <= trailing_trigger:
        signals.append(
            SellSignal(
                ticker=position.ticker,
                reason=SellReason.TRAILING_STOP,
                urgency=SellUrgency.SIGNAL,
                detail=f"Price {position.current_price} is 20%+ below peak {peak}",
                current_price=position.current_price,
                trigger_price=trailing_trigger,
            )
        )

    # --- ROIC declining for 3 consecutive quarters ---
    if len(fundamentals) >= 3:
        roic_values = [f.roic for f in fundamentals if f.roic is not None]
        if len(roic_values) >= 3:
            last_three = roic_values[-3:]
            if last_three[0] > last_three[1] > last_three[2]:
                signals.append(
                    SellSignal(
                        ticker=position.ticker,
                        reason=SellReason.THESIS_BREAK,
                        urgency=SellUrgency.SIGNAL,
                        detail=(
                            f"ROIC declining 3 consecutive periods: "
                            f"{last_three[0]:.2%} -> {last_three[1]:.2%} -> {last_three[2]:.2%}"
                        ),
                        current_price=position.current_price,
                    )
                )

    # --- Debt/EBITDA > 3x ---
    if fundamentals:
        latest = fundamentals[-1]
        # Approximate EBITDA as operating_income (no D&A data available)
        ebitda = latest.operating_income
        if ebitda > 0 and latest.total_debt / ebitda > Decimal("3"):
            ratio = latest.total_debt / ebitda
            signals.append(
                SellSignal(
                    ticker=position.ticker,
                    reason=SellReason.THESIS_BREAK,
                    urgency=SellUrgency.SIGNAL,
                    detail=f"Debt/EBITDA ratio {ratio:.1f}x exceeds 3x threshold",
                    current_price=position.current_price,
                )
            )

    # --- Take profit rules ---
    if fair_value is not None and fair_value > 0:
        ratio = position.current_price / fair_value
        if ratio >= Decimal("1.50"):
            signals.append(
                SellSignal(
                    ticker=position.ticker,
                    reason=SellReason.OVERVALUED,
                    urgency=SellUrgency.SIGNAL,
                    detail=(
                        f"Price {position.current_price} is {ratio:.0%} of "
                        f"fair value {fair_value} — full exit"
                    ),
                    current_price=position.current_price,
                    trigger_price=fair_value * Decimal("1.50"),
                )
            )
        elif ratio >= Decimal("1.20"):
            signals.append(
                SellSignal(
                    ticker=position.ticker,
                    reason=SellReason.OVERVALUED,
                    urgency=SellUrgency.SIGNAL,
                    detail=(
                        f"Price {position.current_price} is {ratio:.0%} of "
                        f"fair value {fair_value} — trim 1/3"
                    ),
                    current_price=position.current_price,
                    trigger_price=fair_value * Decimal("1.20"),
                )
            )

    return signals
