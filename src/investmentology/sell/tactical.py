from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from investmentology.models.position import PortfolioPosition
from investmentology.sell.rules import SellReason, SellSignal, SellUrgency


def check_tactical_rules(
    position: PortfolioPosition,
    today: date | None = None,
) -> list[SellSignal]:
    """Check sell rules for tactical holdings.

    EXECUTE level (auto-execute):
    - Hard stop: 15% below entry price
    - Time stop 6 months: trim 50% (SIGNAL)
    - Time stop 12 months: full exit (EXECUTE)
    """
    if today is None:
        today = date.today()

    signals: list[SellSignal] = []

    # --- Hard stop: 15% below entry ---
    hard_stop_price = position.entry_price * Decimal("0.85")
    if position.current_price <= hard_stop_price:
        signals.append(
            SellSignal(
                ticker=position.ticker,
                reason=SellReason.STOP_LOSS,
                urgency=SellUrgency.EXECUTE,
                detail=(
                    f"Price {position.current_price} hit hard stop "
                    f"15% below entry {position.entry_price}"
                ),
                current_price=position.current_price,
                trigger_price=hard_stop_price,
            )
        )

    # --- Time stop: 12 months -> full exit (EXECUTE) ---
    days_held = (today - position.entry_date).days
    if days_held >= 365:
        signals.append(
            SellSignal(
                ticker=position.ticker,
                reason=SellReason.TIME_STOP,
                urgency=SellUrgency.EXECUTE,
                detail=f"Held {days_held} days (>= 12 months) — full exit",
                current_price=position.current_price,
            )
        )
    elif days_held >= 183:
        # --- Time stop: 6 months -> trim 50% (SIGNAL) ---
        signals.append(
            SellSignal(
                ticker=position.ticker,
                reason=SellReason.TIME_STOP,
                urgency=SellUrgency.SIGNAL,
                detail=f"Held {days_held} days (>= 6 months) — trim 50%",
                current_price=position.current_price,
            )
        )

    return signals


def check_greenblatt_rotation(
    position: PortfolioPosition,
    today: date | None = None,
) -> SellSignal | None:
    """Greenblatt mechanical rotation.

    - Losers: sell at 51 weeks (357 days) for tax loss harvesting
    - Winners: sell at 53 weeks (371 days) for long-term capital gains
    """
    if today is None:
        today = date.today()

    days_held = (today - position.entry_date).days
    is_winner = position.current_price >= position.entry_price

    if is_winner and days_held >= 371:
        return SellSignal(
            ticker=position.ticker,
            reason=SellReason.GREENBLATT_ROTATION,
            urgency=SellUrgency.EXECUTE,
            detail=(
                f"Winner held {days_held} days (>= 53 weeks) — "
                f"rotate for long-term capital gains"
            ),
            current_price=position.current_price,
        )

    if not is_winner and days_held >= 357:
        return SellSignal(
            ticker=position.ticker,
            reason=SellReason.GREENBLATT_ROTATION,
            urgency=SellUrgency.EXECUTE,
            detail=(
                f"Loser held {days_held} days (>= 51 weeks) — "
                f"rotate for tax loss harvesting"
            ),
            current_price=position.current_price,
        )

    return None
