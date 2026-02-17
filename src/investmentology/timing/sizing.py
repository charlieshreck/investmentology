from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass
class SizingResult:
    ticker: str
    shares: int
    dollar_amount: Decimal
    weight_pct: Decimal
    rationale: str
    sizing_method: str = "equal_weight"  # "equal_weight" or "kelly_half"


@dataclass
class SizingConfig:
    max_single_position_pct: Decimal = Decimal("0.05")  # 5%
    target_positions: int = 25
    max_positions: int = 40
    min_position_pct: Decimal = Decimal("0.01")  # 1%
    systematic_pct: Decimal = Decimal("0.80")  # 80% systematic
    discretionary_pct: Decimal = Decimal("0.20")  # 20% discretionary
    min_cash_pct: Decimal = Decimal("0.05")  # 5% min cash
    max_cash_pct: Decimal = Decimal("0.35")  # 35% max cash


# Minimum settled decisions before Kelly criterion activates
KELLY_MIN_DECISIONS = 50


class KellyCalculator:
    """Kelly Criterion position sizing.

    Kelly fraction = (win_rate * avg_win - (1-win_rate) * avg_loss) / avg_win

    We use half-Kelly (Kelly/2) for conservatism, as recommended by
    Thorp and standard institutional practice.
    """

    def __init__(self, win_rate: float, avg_win_pct: float, avg_loss_pct: float) -> None:
        self.win_rate = win_rate
        self.avg_win_pct = avg_win_pct
        self.avg_loss_pct = avg_loss_pct

    def calculate(self) -> float:
        """Calculate full Kelly fraction. Returns 0 if negative."""
        if self.avg_win_pct <= 0:
            return 0.0
        b = self.avg_win_pct / 100  # win ratio
        q = 1 - self.win_rate  # loss probability
        p = self.win_rate
        a = self.avg_loss_pct / 100  # loss ratio

        if b == 0:
            return 0.0

        # Kelly formula: f* = (p*b - q*a) / (b*a)
        # Simplified for win/loss: f* = p/a - q/b
        kelly = (p * b - q * a) / (b * a) if (b * a) > 0 else 0.0
        return max(0.0, kelly)

    def half_kelly(self) -> float:
        """Half-Kelly for conservatism. Capped at 4% per position."""
        return min(self.calculate() / 2, 0.04)


class PositionSizer:
    def __init__(
        self,
        config: SizingConfig | None = None,
        kelly: KellyCalculator | None = None,
    ) -> None:
        self.config = config or SizingConfig()
        self._kelly = kelly

    def calculate_base_size(
        self, portfolio_value: Decimal, current_position_count: int
    ) -> Decimal:
        """Calculate base position size (equal weight).

        = min(portfolio_value / target_positions, portfolio_value * max_single_position_pct)
        """
        equal_weight = portfolio_value / self.config.target_positions
        max_cap = portfolio_value * self.config.max_single_position_pct
        return min(equal_weight, max_cap)

    def calculate_size(
        self,
        portfolio_value: Decimal,
        price: Decimal,
        current_position_count: int,
        pendulum_multiplier: Decimal = Decimal("1.0"),
        ticker: str = "",
    ) -> SizingResult:
        """Calculate position size for a new buy.

        1. Base size from equal weight
        2. Apply pendulum multiplier
        3. Cap at max_single_position_pct
        4. Calculate shares (round down to whole shares)
        5. Check against max_positions limit
        """
        if current_position_count >= self.config.max_positions:
            return SizingResult(
                ticker=ticker,
                shares=0,
                dollar_amount=Decimal("0"),
                weight_pct=Decimal("0"),
                rationale=f"At max positions limit ({self.config.max_positions})",
            )

        # Determine sizing method
        sizing_method = "equal_weight"
        if self._kelly:
            kelly_fraction = self._kelly.half_kelly()
            if kelly_fraction > 0:
                kelly_base = portfolio_value * Decimal(str(kelly_fraction))
                equal_base = self.calculate_base_size(portfolio_value, current_position_count)
                # Use Kelly if it gives a different size, but cap at equal weight
                base = min(kelly_base, equal_base)
                sizing_method = "kelly_half"
            else:
                base = self.calculate_base_size(portfolio_value, current_position_count)
        else:
            base = self.calculate_base_size(portfolio_value, current_position_count)

        adjusted = base * pendulum_multiplier
        max_dollar = portfolio_value * self.config.max_single_position_pct
        dollar_amount = min(adjusted, max_dollar)

        shares = int((dollar_amount / price).to_integral_value(rounding=ROUND_DOWN))
        if shares <= 0:
            return SizingResult(
                ticker=ticker,
                shares=0,
                dollar_amount=Decimal("0"),
                weight_pct=Decimal("0"),
                rationale="Price too high for minimum position size",
            )

        actual_dollar = price * shares
        weight_pct = (actual_dollar / portfolio_value * 100).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )

        parts = [f"{sizing_method}_base=${base:.2f}"]
        if pendulum_multiplier != Decimal("1.0"):
            parts.append(f"pendulum_mult={pendulum_multiplier}")
        parts.append(f"{shares} shares @ ${price}")

        return SizingResult(
            ticker=ticker,
            shares=shares,
            dollar_amount=actual_dollar,
            weight_pct=weight_pct,
            rationale="; ".join(parts),
            sizing_method=sizing_method,
        )

    def check_portfolio_limits(
        self, positions: list, portfolio_value: Decimal
    ) -> dict:
        """Check portfolio-level limits.

        Returns dict with:
        - total_invested_pct
        - cash_pct
        - position_count
        - max_position_weight
        - within_limits: bool
        - violations: list[str]
        """
        violations: list[str] = []
        position_count = len(positions)

        if portfolio_value <= 0:
            return {
                "total_invested_pct": Decimal("0"),
                "cash_pct": Decimal("100"),
                "position_count": 0,
                "max_position_weight": Decimal("0"),
                "within_limits": False,
                "violations": ["Portfolio value must be positive"],
            }

        total_invested = sum(p.market_value for p in positions)
        total_invested_pct = total_invested / portfolio_value * 100
        cash_pct = Decimal("100") - total_invested_pct

        max_position_weight = Decimal("0")
        for p in positions:
            w = p.market_value / portfolio_value * 100
            if w > max_position_weight:
                max_position_weight = w
            if w > self.config.max_single_position_pct * 100:
                violations.append(
                    f"{p.ticker} weight {w:.1f}% exceeds max {self.config.max_single_position_pct * 100}%"
                )

        if position_count > self.config.max_positions:
            violations.append(
                f"Position count {position_count} exceeds max {self.config.max_positions}"
            )

        min_cash = self.config.min_cash_pct * 100
        if cash_pct < min_cash:
            violations.append(
                f"Cash {cash_pct:.1f}% below minimum {min_cash}%"
            )

        return {
            "total_invested_pct": total_invested_pct.quantize(Decimal("0.01")),
            "cash_pct": cash_pct.quantize(Decimal("0.01")),
            "position_count": position_count,
            "max_position_weight": max_position_weight.quantize(Decimal("0.01")),
            "within_limits": len(violations) == 0,
            "violations": violations,
        }
