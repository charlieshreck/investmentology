"""Prediction Card — structured stock outcome view.

For every analyzed stock, produces a single prediction card that summarizes
everything needed to make a decision:
  - Composite target price (weighted average of agent targets)
  - Price range (min-max agent estimates → confidence interval)
  - Bear case price (conservative downside)
  - Risk/reward ratio (upside to target ÷ downside to bear case)
  - Calibrated confidence
  - Conviction tier
  - Holding period suggestion
  - Earnings proximity warning
  - Settlement benchmark (SPY price at verdict time)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ConvictionTier(StrEnum):
    ALL_SIGNALS_ALIGNED = "ALL_SIGNALS_ALIGNED"
    HIGH_CONVICTION = "HIGH_CONVICTION"
    MODERATE = "MODERATE"
    LOW_CONVICTION = "LOW_CONVICTION"
    MIXED_SIGNALS = "MIXED_SIGNALS"


@dataclass
class AgentTarget:
    agent: str
    target_price: float
    weight: float


@dataclass
class PredictionCard:
    ticker: str
    current_price: float
    verdict: str
    confidence: float

    # Prices
    composite_target: float | None
    target_range_low: float | None
    target_range_high: float | None
    bear_case: float | None

    # Computed
    upside_pct: float | None
    downside_pct: float | None
    risk_reward_ratio: float | None

    # Meta
    conviction_tier: ConvictionTier
    agent_consensus_pct: float  # 0-100
    quant_gate_rank: int | None
    piotroski_score: int | None
    altman_zone: str | None  # "safe", "grey", "distress"

    # Timing
    holding_period: str  # e.g. "12-18 months"
    earnings_warning: str | None  # from earnings calendar
    settlement_benchmark_spy: float | None  # SPY price at verdict time

    # Source
    agent_targets: list[AgentTarget] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "ticker": self.ticker,
            "currentPrice": self.current_price,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "compositeTarget": self.composite_target,
            "targetRangeLow": self.target_range_low,
            "targetRangeHigh": self.target_range_high,
            "bearCase": self.bear_case,
            "upsidePct": self.upside_pct,
            "downsidePct": self.downside_pct,
            "riskRewardRatio": self.risk_reward_ratio,
            "convictionTier": self.conviction_tier.value,
            "agentConsensusPct": self.agent_consensus_pct,
            "quantGateRank": self.quant_gate_rank,
            "piotroskiScore": self.piotroski_score,
            "altmanZone": self.altman_zone,
            "holdingPeriod": self.holding_period,
            "earningsWarning": self.earnings_warning,
            "settlementBenchmarkSpy": self.settlement_benchmark_spy,
            "agentTargets": [
                {"agent": t.agent, "targetPrice": t.target_price, "weight": t.weight}
                for t in self.agent_targets
            ],
        }


@dataclass
class PredictionCardInputs:
    """All data needed to build a prediction card."""

    ticker: str
    current_price: float
    verdict: str
    confidence: float

    # Agent-produced target prices with weights
    agent_targets: list[AgentTarget] = field(default_factory=list)

    # Bear case (typically from conservative agents)
    bear_case_price: float | None = None

    # Quant metrics
    agent_consensus_pct: float = 0.0  # 0-100, % of agents bullish
    quant_gate_rank: int | None = None
    piotroski_score: int | None = None
    altman_zone: str | None = None
    momentum_percentile: float | None = None  # 0.0-1.0

    # Timing
    holding_period: str = "12-18 months"
    earnings_warning: str | None = None
    spy_price: float | None = None


def build_prediction_card(inputs: PredictionCardInputs) -> PredictionCard:
    """Build a prediction card from structured inputs."""
    price = inputs.current_price

    # Composite target: weighted average of agent targets
    composite_target = _weighted_target(inputs.agent_targets)

    # Range from agent estimates
    target_range_low = None
    target_range_high = None
    if inputs.agent_targets:
        prices = [t.target_price for t in inputs.agent_targets]
        target_range_low = min(prices)
        target_range_high = max(prices)

    # Bear case: explicit or fall back to lowest agent target
    bear_case = inputs.bear_case_price
    if bear_case is None and target_range_low is not None:
        bear_case = target_range_low

    # Upside/downside percentages
    upside_pct = None
    downside_pct = None
    risk_reward = None

    if composite_target is not None and price > 0:
        upside_pct = round((composite_target - price) / price * 100, 1)

    if bear_case is not None and price > 0:
        downside_pct = round((price - bear_case) / price * 100, 1)

    if upside_pct is not None and downside_pct is not None and downside_pct > 0:
        risk_reward = round(upside_pct / downside_pct, 1)

    # Conviction tier
    conviction = _determine_conviction(inputs)

    return PredictionCard(
        ticker=inputs.ticker,
        current_price=price,
        verdict=inputs.verdict,
        confidence=inputs.confidence,
        composite_target=composite_target,
        target_range_low=target_range_low,
        target_range_high=target_range_high,
        bear_case=bear_case,
        upside_pct=upside_pct,
        downside_pct=downside_pct,
        risk_reward_ratio=risk_reward,
        conviction_tier=conviction,
        agent_consensus_pct=inputs.agent_consensus_pct,
        quant_gate_rank=inputs.quant_gate_rank,
        piotroski_score=inputs.piotroski_score,
        altman_zone=inputs.altman_zone,
        holding_period=inputs.holding_period,
        earnings_warning=inputs.earnings_warning,
        settlement_benchmark_spy=inputs.spy_price,
        agent_targets=inputs.agent_targets,
    )


def _weighted_target(targets: list[AgentTarget]) -> float | None:
    """Compute weighted average target price."""
    if not targets:
        return None

    total_weight = sum(t.weight for t in targets)
    if total_weight <= 0:
        # Equal weight fallback
        return round(sum(t.target_price for t in targets) / len(targets), 2)

    weighted_sum = sum(t.target_price * t.weight for t in targets)
    return round(weighted_sum / total_weight, 2)


def _determine_conviction(inputs: PredictionCardInputs) -> ConvictionTier:
    """Determine conviction tier from multiple signal sources."""
    score = 0
    checks = 0

    # Agent consensus
    if inputs.agent_consensus_pct >= 80:
        score += 2
    elif inputs.agent_consensus_pct >= 60:
        score += 1
    checks += 1

    # Confidence
    if inputs.confidence >= 0.75:
        score += 2
    elif inputs.confidence >= 0.55:
        score += 1
    checks += 1

    # Quant gate rank
    if inputs.quant_gate_rank is not None:
        if inputs.quant_gate_rank <= 15:
            score += 2
        elif inputs.quant_gate_rank <= 50:
            score += 1
        checks += 1

    # Piotroski
    if inputs.piotroski_score is not None:
        if inputs.piotroski_score >= 7:
            score += 2
        elif inputs.piotroski_score >= 5:
            score += 1
        checks += 1

    # Altman
    if inputs.altman_zone is not None:
        if inputs.altman_zone == "safe":
            score += 2
        elif inputs.altman_zone == "grey":
            score += 1
        checks += 1

    # Momentum
    if inputs.momentum_percentile is not None:
        if inputs.momentum_percentile >= 0.75:
            score += 1
        checks += 1

    if checks == 0:
        return ConvictionTier.LOW_CONVICTION

    ratio = score / (checks * 2)  # max 2 per check

    if ratio >= 0.85:
        return ConvictionTier.ALL_SIGNALS_ALIGNED
    elif ratio >= 0.65:
        return ConvictionTier.HIGH_CONVICTION
    elif ratio >= 0.45:
        return ConvictionTier.MODERATE
    elif ratio >= 0.25:
        return ConvictionTier.LOW_CONVICTION
    else:
        return ConvictionTier.MIXED_SIGNALS
