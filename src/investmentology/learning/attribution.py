"""Agent performance attribution — tracks which agents' signals are most predictive.

Extends the calibration engine with per-agent signal accuracy tracking,
dynamic weight recommendations, and signal tag performance analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

logger = logging.getLogger(__name__)

# Default agent weights (from orchestrator)
DEFAULT_WEIGHTS = {
    "warren": 0.30,
    "soros": 0.25,
    "simons": 0.20,
    "auditor": 0.25,
}


@dataclass
class AgentAttribution:
    """Performance attribution for a single agent."""

    name: str
    total_calls: int = 0
    correct_calls: int = 0
    bullish_correct: int = 0
    bullish_total: int = 0
    bearish_correct: int = 0
    bearish_total: int = 0
    signal_accuracy: dict[str, tuple[int, int]] = field(default_factory=dict)  # tag -> (correct, total)

    @property
    def accuracy(self) -> float:
        return self.correct_calls / self.total_calls if self.total_calls > 0 else 0.0

    @property
    def bullish_accuracy(self) -> float:
        return self.bullish_correct / self.bullish_total if self.bullish_total > 0 else 0.0

    @property
    def bearish_accuracy(self) -> float:
        return self.bearish_correct / self.bearish_total if self.bearish_total > 0 else 0.0


@dataclass
class AttributionReport:
    """Full attribution report across all agents."""

    agents: dict[str, AgentAttribution]
    recommended_weights: dict[str, float]
    top_signals: list[tuple[str, str, float]]  # (agent, signal_tag, accuracy)
    worst_signals: list[tuple[str, str, float]]
    recommendations: list[str]


class AgentAttributionEngine:
    """Compute per-agent performance and recommend weight adjustments."""

    MIN_DECISIONS_FOR_ATTRIBUTION = 20

    def __init__(self, registry) -> None:
        self._registry = registry

    def compute_attribution(self) -> AttributionReport | None:
        """Compute attribution from decision history.

        Queries decisions that have been settled (have an outcome recorded)
        and traces back which agent signals were correct.
        """
        try:
            decisions = self._registry.get_decisions(limit=10_000)
        except Exception:
            logger.exception("Failed to fetch decisions for attribution")
            return None

        if len(decisions) < self.MIN_DECISIONS_FOR_ATTRIBUTION:
            logger.info(
                "Only %d decisions, need %d for attribution",
                len(decisions), self.MIN_DECISIONS_FOR_ATTRIBUTION,
            )
            return None

        agents: dict[str, AgentAttribution] = {
            name: AgentAttribution(name=name) for name in DEFAULT_WEIGHTS
        }

        for decision in decisions:
            outcome = decision.get("outcome")
            if outcome is None:
                continue

            was_profitable = outcome in ("win", "profitable", True)
            agent_signals = decision.get("agent_signals", {})

            for agent_name, signals in agent_signals.items():
                agent_key = agent_name.lower()
                if agent_key not in agents:
                    agents[agent_key] = AgentAttribution(name=agent_key)

                attr = agents[agent_key]
                attr.total_calls += 1

                sentiment = signals.get("sentiment", "").lower()
                if sentiment in ("bullish", "buy", "strong_buy"):
                    attr.bullish_total += 1
                    if was_profitable:
                        attr.correct_calls += 1
                        attr.bullish_correct += 1
                elif sentiment in ("bearish", "sell", "strong_sell"):
                    attr.bearish_total += 1
                    if not was_profitable:
                        attr.correct_calls += 1
                        attr.bearish_correct += 1
                else:
                    if was_profitable:
                        attr.correct_calls += 1

                # Track individual signal tags
                for tag in signals.get("tags", []):
                    if tag not in attr.signal_accuracy:
                        attr.signal_accuracy[tag] = (0, 0)
                    correct, total = attr.signal_accuracy[tag]
                    attr.signal_accuracy[tag] = (
                        correct + (1 if was_profitable else 0),
                        total + 1,
                    )

        # Compute recommended weights
        recommended = self._compute_weights(agents)

        # Find top and worst signals
        top_signals = []
        worst_signals = []
        for agent_key, attr in agents.items():
            for tag, (correct, total) in attr.signal_accuracy.items():
                if total >= 5:
                    acc = correct / total
                    top_signals.append((agent_key, tag, acc))
                    worst_signals.append((agent_key, tag, acc))

        top_signals.sort(key=lambda x: x[2], reverse=True)
        worst_signals.sort(key=lambda x: x[2])

        # Generate recommendations
        recommendations = self._generate_recommendations(agents, recommended)

        return AttributionReport(
            agents=agents,
            recommended_weights=recommended,
            top_signals=top_signals[:10],
            worst_signals=worst_signals[:10],
            recommendations=recommendations,
        )

    def _compute_weights(self, agents: dict[str, AgentAttribution]) -> dict[str, float]:
        """Compute accuracy-proportional weights, smoothed toward defaults."""
        accuracies: dict[str, float] = {}
        for name, attr in agents.items():
            if attr.total_calls >= 10:
                accuracies[name] = attr.accuracy
            else:
                accuracies[name] = DEFAULT_WEIGHTS.get(name, 0.25)

        # Softmax-style normalization with smoothing toward defaults
        total_acc = sum(accuracies.values())
        if total_acc == 0:
            return dict(DEFAULT_WEIGHTS)

        raw_weights = {name: acc / total_acc for name, acc in accuracies.items()}

        # Blend 60% performance-based, 40% default (conservative adjustment)
        blended = {}
        for name in DEFAULT_WEIGHTS:
            default_w = DEFAULT_WEIGHTS.get(name, 0.25)
            perf_w = raw_weights.get(name, default_w)
            blended[name] = round(0.6 * perf_w + 0.4 * default_w, 3)

        # Normalize to sum to 1.0
        total = sum(blended.values())
        if total > 0:
            blended = {k: round(v / total, 3) for k, v in blended.items()}

        return blended

    def _generate_recommendations(
        self,
        agents: dict[str, AgentAttribution],
        recommended: dict[str, float],
    ) -> list[str]:
        recs = []

        for name, attr in agents.items():
            if attr.total_calls < 10:
                continue

            current_w = DEFAULT_WEIGHTS.get(name, 0.25)
            new_w = recommended.get(name, current_w)
            diff = new_w - current_w

            if abs(diff) > 0.03:
                direction = "increase" if diff > 0 else "decrease"
                recs.append(
                    f"{name.capitalize()}: {direction} weight from "
                    f"{current_w:.0%} to {new_w:.0%} "
                    f"(accuracy: {attr.accuracy:.0%} over {attr.total_calls} decisions)"
                )

            if attr.accuracy < 0.40 and attr.total_calls >= 20:
                recs.append(
                    f"WARNING: {name.capitalize()} accuracy is only {attr.accuracy:.0%}. "
                    f"Review agent prompts and model selection."
                )

            if attr.bullish_total >= 10 and attr.bearish_total >= 10:
                if abs(attr.bullish_accuracy - attr.bearish_accuracy) > 0.20:
                    better = "bullish" if attr.bullish_accuracy > attr.bearish_accuracy else "bearish"
                    recs.append(
                        f"{name.capitalize()} is significantly better at {better} calls "
                        f"(bull: {attr.bullish_accuracy:.0%}, bear: {attr.bearish_accuracy:.0%})"
                    )

        if not recs:
            recs.append("Insufficient data for attribution recommendations. Need 10+ settled decisions per agent.")

        return recs
