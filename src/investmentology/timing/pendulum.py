from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PendulumReading:
    score: int  # 0-100 (0=extreme fear, 100=extreme greed)
    label: str  # "extreme_fear", "fear", "neutral", "greed", "extreme_greed"
    sizing_multiplier: Decimal  # 0.80 to 1.20
    components: dict  # Individual indicator scores


_LABEL_MULTIPLIERS: dict[str, Decimal] = {
    "extreme_fear": Decimal("1.20"),
    "fear": Decimal("1.10"),
    "neutral": Decimal("1.00"),
    "greed": Decimal("0.90"),
    "extreme_greed": Decimal("0.80"),
}


def _score_to_label(score: int) -> str:
    if score < 20:
        return "extreme_fear"
    if score < 40:
        return "fear"
    if score < 60:
        return "neutral"
    if score < 80:
        return "greed"
    return "extreme_greed"


class PendulumReader:
    """Reads market sentiment from quantitative indicators.

    Indicators (each scored 0-100):
    - VIX level: low VIX = greed, high VIX = fear
    - Credit spreads (HY OAS): tight = greed, wide = fear
    - Put/call ratio: low = greed, high = fear
    - Market momentum: SPY above/below 200 SMA

    Composite score = weighted average.
    """

    def __init__(
        self,
        vix_weight: float = 0.30,
        credit_weight: float = 0.25,
        putcall_weight: float = 0.20,
        momentum_weight: float = 0.25,
    ) -> None:
        self.vix_weight = vix_weight
        self.credit_weight = credit_weight
        self.putcall_weight = putcall_weight
        self.momentum_weight = momentum_weight

    def read(
        self,
        vix: Decimal,
        hy_oas: Decimal | None = None,
        put_call_ratio: Decimal | None = None,
        spy_above_200sma: bool | None = None,
    ) -> PendulumReading:
        """Calculate pendulum reading from market data.

        VIX scoring: <15=90, 15-20=70, 20-25=50, 25-35=30, >35=10
        HY OAS scoring: <3.0=80, 3-4=60, 4-5=40, 5-7=20, >7=10
        Put/call scoring: <0.7=80 (greedy), 0.7-0.85=60, 0.85-1.0=40, >1.0=20 (fearful)

        Labels: 0-20=extreme_fear, 20-40=fear, 40-60=neutral, 60-80=greed, 80-100=extreme_greed

        Sizing multiplier:
        - extreme_fear: 1.20 (buy more when fearful)
        - fear: 1.10
        - neutral: 1.00
        - greed: 0.90
        - extreme_greed: 0.80 (buy less when greedy)
        """
        components: dict[str, int] = {}
        total_weight = 0.0
        weighted_sum = 0.0

        # VIX is always required
        vix_score = self._score_vix(vix)
        components["vix"] = vix_score
        weighted_sum += vix_score * self.vix_weight
        total_weight += self.vix_weight

        if hy_oas is not None:
            oas_score = self._score_hy_oas(hy_oas)
            components["hy_oas"] = oas_score
            weighted_sum += oas_score * self.credit_weight
            total_weight += self.credit_weight

        if put_call_ratio is not None:
            pc_score = self._score_put_call(put_call_ratio)
            components["put_call"] = pc_score
            weighted_sum += pc_score * self.putcall_weight
            total_weight += self.putcall_weight

        if spy_above_200sma is not None:
            momentum_score = 80 if spy_above_200sma else 20
            components["momentum"] = momentum_score
            weighted_sum += momentum_score * self.momentum_weight
            total_weight += self.momentum_weight

        composite = int(round(weighted_sum / total_weight)) if total_weight > 0 else 50
        # Clamp to 0-100
        composite = max(0, min(100, composite))

        label = _score_to_label(composite)
        multiplier = _LABEL_MULTIPLIERS[label]

        return PendulumReading(
            score=composite,
            label=label,
            sizing_multiplier=multiplier,
            components=components,
        )

    @staticmethod
    def _score_vix(vix: Decimal) -> int:
        """Score VIX: low VIX = greed (high score), high VIX = fear (low score)."""
        if vix < 15:
            return 90
        if vix < 20:
            return 70
        if vix < 25:
            return 50
        if vix < 35:
            return 30
        return 10

    @staticmethod
    def _score_hy_oas(hy_oas: Decimal) -> int:
        """Score HY OAS: tight spreads = greed, wide = fear."""
        if hy_oas < 3:
            return 80
        if hy_oas < 4:
            return 60
        if hy_oas < 5:
            return 40
        if hy_oas < 7:
            return 20
        return 10

    @staticmethod
    def _score_put_call(ratio: Decimal) -> int:
        """Score put/call ratio: low = greed, high = fear."""
        if ratio < Decimal("0.7"):
            return 80
        if ratio < Decimal("0.85"):
            return 60
        if ratio < Decimal("1.0"):
            return 40
        return 20
