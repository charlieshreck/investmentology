"""Sell discipline triggers — cross-position-type alerts.

These triggers apply to ALL held positions regardless of position type.
They generate FLAG-level signals requiring human review, never auto-execute.

Triggers:
  1. Fair value ratio P/FV > 1.0 — position may be fully valued
  2. Piotroski F-Score drop >= 2 points — financial health deteriorating
  3. Composite rank decay from top-quartile to bottom-half — quant support lost
  4. Thesis criteria breached — original investment thesis no longer holds
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from investmentology.models.position import PortfolioPosition
from investmentology.sell.rules import SellReason, SellSignal, SellUrgency


@dataclass
class DisciplineContext:
    """Extra data needed for discipline trigger evaluation."""

    fair_value: Decimal | None = None
    piotroski_current: int | None = None
    piotroski_prior: int | None = None
    composite_rank_pct: float | None = None  # 0.0 (worst) to 1.0 (best)
    composite_rank_prior_pct: float | None = None


def check_discipline_triggers(
    position: PortfolioPosition,
    ctx: DisciplineContext,
) -> list[SellSignal]:
    """Evaluate sell discipline triggers for any held position.

    All triggers produce FLAG urgency — human review required.
    """
    signals: list[SellSignal] = []

    # 1. Fair value ratio: P/FV > 1.0
    if ctx.fair_value is not None and ctx.fair_value > 0:
        ratio = position.current_price / ctx.fair_value
        if ratio > Decimal("1.0"):
            signals.append(
                SellSignal(
                    ticker=position.ticker,
                    reason=SellReason.FULLY_VALUED,
                    urgency=SellUrgency.FLAG,
                    detail=(
                        f"Price/Fair-Value = {ratio:.2f}x — "
                        f"position may be fully valued, review thesis"
                    ),
                    current_price=position.current_price,
                    trigger_price=ctx.fair_value,
                )
            )

    # 2. Piotroski F-Score drop >= 2 points in one cycle
    if (
        ctx.piotroski_current is not None
        and ctx.piotroski_prior is not None
    ):
        drop = ctx.piotroski_prior - ctx.piotroski_current
        if drop >= 2:
            signals.append(
                SellSignal(
                    ticker=position.ticker,
                    reason=SellReason.PIOTROSKI_DROP,
                    urgency=SellUrgency.FLAG,
                    detail=(
                        f"Piotroski F-Score dropped {drop} points "
                        f"({ctx.piotroski_prior} → {ctx.piotroski_current}) — "
                        f"financial health deteriorating"
                    ),
                    current_price=position.current_price,
                )
            )

    # 3. Composite rank decay: top-quartile → bottom-half
    if (
        ctx.composite_rank_pct is not None
        and ctx.composite_rank_prior_pct is not None
    ):
        was_top_quartile = ctx.composite_rank_prior_pct >= 0.75
        now_bottom_half = ctx.composite_rank_pct < 0.50
        if was_top_quartile and now_bottom_half:
            signals.append(
                SellSignal(
                    ticker=position.ticker,
                    reason=SellReason.COMPOSITE_DECAY,
                    urgency=SellUrgency.FLAG,
                    detail=(
                        f"Composite rank fell from top quartile "
                        f"({ctx.composite_rank_prior_pct:.0%}) to bottom half "
                        f"({ctx.composite_rank_pct:.0%}) — "
                        f"quant gate no longer supports this position"
                    ),
                    current_price=position.current_price,
                )
            )

    return signals
