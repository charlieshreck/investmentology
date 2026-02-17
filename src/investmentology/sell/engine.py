from __future__ import annotations

from decimal import Decimal

from investmentology.models.position import PortfolioPosition
from investmentology.models.stock import FundamentalsSnapshot
from investmentology.sell.core import check_core_rules
from investmentology.sell.permanent import check_permanent_rules
from investmentology.sell.rules import SellSignal
from investmentology.sell.tactical import check_greenblatt_rotation, check_tactical_rules


class SellEngine:
    """Evaluates all sell rules for a portfolio of positions."""

    def evaluate_position(
        self,
        position: PortfolioPosition,
        fundamentals: list[FundamentalsSnapshot] | None = None,
        fair_value: Decimal | None = None,
        highest_price_since_entry: Decimal | None = None,
    ) -> list[SellSignal]:
        """Run appropriate sell rules based on position_type.

        - "permanent" -> permanent rules
        - "core" -> core rules
        - "tactical" -> tactical rules + greenblatt rotation
        """
        funda = fundamentals or []

        if position.position_type == "permanent":
            return check_permanent_rules(position, funda)

        if position.position_type == "core":
            return check_core_rules(
                position, funda,
                fair_value=fair_value,
                highest_price_since_entry=highest_price_since_entry,
            )

        if position.position_type == "tactical":
            signals = check_tactical_rules(position)
            rotation = check_greenblatt_rotation(position)
            if rotation is not None:
                signals.append(rotation)
            return signals

        return []

    def evaluate_portfolio(
        self,
        positions: list[PortfolioPosition],
        fundamentals_map: dict[str, list[FundamentalsSnapshot]] | None = None,
        fair_values: dict[str, Decimal] | None = None,
        highest_prices: dict[str, Decimal] | None = None,
    ) -> dict[str, list[SellSignal]]:
        """Run sell rules for all positions. Returns {ticker: [signals]}."""
        funda_map = fundamentals_map or {}
        fv_map = fair_values or {}
        hp_map = highest_prices or {}
        results: dict[str, list[SellSignal]] = {}

        for pos in positions:
            signals = self.evaluate_position(
                pos,
                fundamentals=funda_map.get(pos.ticker),
                fair_value=fv_map.get(pos.ticker),
                highest_price_since_entry=hp_map.get(pos.ticker),
            )
            if signals:
                results[pos.ticker] = signals

        return results
