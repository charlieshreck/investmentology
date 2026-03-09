from __future__ import annotations

from decimal import Decimal

from investmentology.models.position import PortfolioPosition
from investmentology.models.stock import FundamentalsSnapshot
from investmentology.sell.core import check_core_rules
from investmentology.sell.discipline import DisciplineContext, check_discipline_triggers
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
        discipline_ctx: DisciplineContext | None = None,
    ) -> list[SellSignal]:
        """Run appropriate sell rules based on position_type.

        - "permanent" -> permanent rules
        - "core" -> core rules
        - "tactical" -> tactical rules + greenblatt rotation
        - ALL types -> discipline triggers (if context provided)
        """
        funda = fundamentals or []

        if position.position_type == "permanent":
            signals = check_permanent_rules(position, funda)
        elif position.position_type == "core":
            signals = check_core_rules(
                position, funda,
                fair_value=fair_value,
                highest_price_since_entry=highest_price_since_entry,
            )
        elif position.position_type == "tactical":
            signals = check_tactical_rules(position)
            rotation = check_greenblatt_rotation(position)
            if rotation is not None:
                signals.append(rotation)
        else:
            signals = []

        # Discipline triggers apply to ALL position types
        if discipline_ctx is not None:
            signals.extend(check_discipline_triggers(position, discipline_ctx))

        return signals

    def evaluate_portfolio(
        self,
        positions: list[PortfolioPosition],
        fundamentals_map: dict[str, list[FundamentalsSnapshot]] | None = None,
        fair_values: dict[str, Decimal] | None = None,
        highest_prices: dict[str, Decimal] | None = None,
        discipline_contexts: dict[str, DisciplineContext] | None = None,
    ) -> dict[str, list[SellSignal]]:
        """Run sell rules for all positions. Returns {ticker: [signals]}."""
        funda_map = fundamentals_map or {}
        fv_map = fair_values or {}
        hp_map = highest_prices or {}
        disc_map = discipline_contexts or {}
        results: dict[str, list[SellSignal]] = {}

        for pos in positions:
            signals = self.evaluate_position(
                pos,
                fundamentals=funda_map.get(pos.ticker),
                fair_value=fv_map.get(pos.ticker),
                highest_price_since_entry=hp_map.get(pos.ticker),
                discipline_ctx=disc_map.get(pos.ticker),
            )
            if signals:
                results[pos.ticker] = signals

        return results
