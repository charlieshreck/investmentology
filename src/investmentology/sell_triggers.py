"""Sell discipline framework — position-type-aware exit triggers.

Provides three tiers of sell triggers:
- Tier 1: Hard stops (automatic sell queue flags)
- Tier 2: Thesis-age confidence floors
- Tier 3: Portfolio-level limits (position weight, sector concentration)

Also includes portfolio drawdown gates and tax-awareness.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

logger = logging.getLogger(__name__)


# --- Tier 1: Hard stops per position type ---

_HARD_STOPS: dict[str, dict[str, Decimal]] = {
    "permanent": {
        "cost_basis_stop": Decimal("-0.35"),    # -35% from entry
        "trailing_stop": Decimal("-0.20"),       # -20% from HWM
        "trailing_activation": Decimal("0.30"),  # Activate trailing at +30%
    },
    "core": {
        "cost_basis_stop": Decimal("-0.25"),
        "trailing_stop": Decimal("-0.15"),
        "trailing_activation": Decimal("0.20"),
    },
    "tactical": {
        "cost_basis_stop": Decimal("-0.15"),
        "trailing_stop": Decimal("-0.15"),
        "trailing_activation": Decimal("0.20"),
    },
}

# --- Tier 2: Thesis-age confidence floors ---
# Older positions require less confidence to sell (accumulated evidence)

_CONFIDENCE_FLOORS: list[tuple[int, Decimal]] = [
    (30, Decimal("0.45")),    # <30 days: need high sell confidence
    (90, Decimal("0.35")),    # 30-90 days
    (365, Decimal("0.30")),   # 90-365 days
    (99999, Decimal("0.25")), # >365 days: lower bar for selling
]

# --- Tier 3: Portfolio-level ---

POSITION_WEIGHT_TRIM = Decimal("2.0")  # Trim when position hits 2x original weight
SECTOR_CONCENTRATION_MAX = Decimal("0.25")  # 25% max sector exposure

# --- Drawdown gates ---

DRAWDOWN_GATES: dict[str, dict[str, Decimal]] = {
    "tactical": {
        "warn": Decimal("-0.10"),
        "halt_buys": Decimal("-0.15"),
        "forced_review": Decimal("-0.20"),
    },
    "core": {
        "warn": Decimal("-0.15"),
        "halt_buys": Decimal("-0.20"),
        "forced_review": Decimal("-0.30"),
    },
    "permanent": {
        "warn": Decimal("-0.20"),
        "halt_buys": Decimal("-0.30"),
        "forced_review": Decimal("-0.40"),
    },
}

# Portfolio-level drawdown gates
PORTFOLIO_DRAWDOWN = {
    "halt_tactical": Decimal("-0.15"),  # Halt new tactical buys
    "halt_all": Decimal("-0.20"),       # Halt all new buys
    "forced_review": Decimal("-0.25"),  # Force portfolio-wide reanalysis
}


@dataclass
class SellTrigger:
    """A triggered sell condition."""

    ticker: str
    trigger_type: str  # "hard_stop", "trailing_stop", "confidence_floor", "weight_trim", "sector_limit"
    severity: str  # "warning", "action_required", "immediate"
    detail: str
    position_type: str = ""
    tax_context: dict = field(default_factory=dict)


def check_hard_stops(
    ticker: str,
    position_type: str,
    entry_price: Decimal,
    current_price: Decimal,
    high_water_mark: Decimal | None = None,
) -> SellTrigger | None:
    """Check Tier 1 hard stops."""
    stops = _HARD_STOPS.get(position_type, _HARD_STOPS["core"])

    pnl_pct = (current_price - entry_price) / entry_price

    # Cost basis stop
    if pnl_pct <= stops["cost_basis_stop"]:
        return SellTrigger(
            ticker=ticker,
            trigger_type="hard_stop",
            severity="immediate",
            detail=f"Cost basis stop hit: {pnl_pct:.1%} (limit {stops['cost_basis_stop']:.0%})",
            position_type=position_type,
        )

    # Trailing stop (only active after sufficient gain)
    if high_water_mark and high_water_mark > entry_price:
        gain_from_entry = (high_water_mark - entry_price) / entry_price
        if gain_from_entry >= stops["trailing_activation"]:
            drawdown_from_hwm = (current_price - high_water_mark) / high_water_mark
            if drawdown_from_hwm <= stops["trailing_stop"]:
                return SellTrigger(
                    ticker=ticker,
                    trigger_type="trailing_stop",
                    severity="action_required",
                    detail=(
                        f"Trailing stop: {drawdown_from_hwm:.1%} from HWM "
                        f"(limit {stops['trailing_stop']:.0%}, HWM ${high_water_mark:.2f})"
                    ),
                    position_type=position_type,
                )

    return None


def check_confidence_floor(
    ticker: str,
    days_held: int,
    sell_confidence: Decimal,
) -> bool:
    """Check if sell confidence meets the thesis-age floor.

    Returns True if confidence is sufficient to justify selling.
    """
    for day_limit, floor in _CONFIDENCE_FLOORS:
        if days_held < day_limit:
            return sell_confidence >= floor
    return sell_confidence >= Decimal("0.25")


def check_portfolio_drawdown(
    portfolio_return: Decimal,
) -> dict:
    """Check portfolio-level drawdown gates.

    Returns dict with gate status:
    - halt_tactical: bool
    - halt_all: bool
    - forced_review: bool
    """
    return {
        "halt_tactical": portfolio_return <= PORTFOLIO_DRAWDOWN["halt_tactical"],
        "halt_all": portfolio_return <= PORTFOLIO_DRAWDOWN["halt_all"],
        "forced_review": portfolio_return <= PORTFOLIO_DRAWDOWN["forced_review"],
    }


def tax_aware_sell_context(
    entry_date: date,
    pnl_pct: Decimal,
    is_hard_stop: bool = False,
) -> dict:
    """Add tax awareness to sell recommendations."""
    days_held = (date.today() - entry_date).days
    days_to_long_term = max(0, 366 - days_held)
    holding_period = "long_term" if days_held >= 366 else "short_term"

    tax_note = ""
    if (
        holding_period == "short_term"
        and days_to_long_term <= 30
        and not is_hard_stop
        and pnl_pct > 0
    ):
        tax_note = (
            f"Consider holding {days_to_long_term} more days for long-term "
            f"capital gains treatment."
        )

    return {
        "holding_period": holding_period,
        "days_held": days_held,
        "days_to_long_term": days_to_long_term,
        "tax_impact_note": tax_note,
    }
