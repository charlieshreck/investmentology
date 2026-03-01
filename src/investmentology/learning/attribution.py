"""Agent performance attribution — tracks which agents' signals are most predictive.

Queries agent_signals and verdicts tables to compute per-agent accuracy,
signal tag performance, and dynamic weight recommendations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

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
class OverrideOutcome:
    """Outcome analysis for auditor/munger overrides."""

    override_type: str  # "auditor" or "munger"
    total_overrides: int = 0
    total_settled: int = 0
    override_correct: int = 0  # override improved the outcome
    override_wrong: int = 0  # original verdict was actually better
    value_added_pct: float = 0.0  # positive = overrides help, negative = hurt


@dataclass
class AttributionReport:
    """Full attribution report across all agents."""

    agents: dict[str, AgentAttribution]
    recommended_weights: dict[str, float]
    top_signals: list[tuple[str, str, float]]  # (agent, signal_tag, accuracy)
    worst_signals: list[tuple[str, str, float]]
    recommendations: list[str]
    override_outcomes: list[OverrideOutcome] | None = None


class AgentAttributionEngine:
    """Compute per-agent performance and recommend weight adjustments.

    Works with the actual invest.agent_signals and invest.verdicts tables.
    """

    MIN_VERDICTS_FOR_ATTRIBUTION = 20

    def __init__(self, registry) -> None:
        self._registry = registry

    def compute_attribution(self) -> AttributionReport | None:
        """Compute attribution from verdict history and agent stances.

        For each verdict, checks if each agent's stance direction aligned
        with the final verdict direction. Bullish agents on BUY verdicts
        are "correct"; bearish agents on AVOID verdicts are "correct".
        """
        try:
            rows = self._registry._db.execute(
                "SELECT id, ticker, verdict, confidence, agent_stances "
                "FROM invest.verdicts ORDER BY created_at DESC LIMIT 10000"
            )
        except Exception:
            logger.exception("Failed to fetch verdicts for attribution")
            return None

        if len(rows) < self.MIN_VERDICTS_FOR_ATTRIBUTION:
            logger.info(
                "Only %d verdicts, need %d for attribution",
                len(rows), self.MIN_VERDICTS_FOR_ATTRIBUTION,
            )
            return None

        agents: dict[str, AgentAttribution] = {
            name: AgentAttribution(name=name) for name in DEFAULT_WEIGHTS
        }

        # Verdicts that indicate positive outcome
        bullish_verdicts = {"STRONG_BUY", "BUY", "ACCUMULATE"}
        bearish_verdicts = {"SELL", "AVOID", "DISCARD", "REDUCE"}

        for row in rows:
            verdict_str = row["verdict"]
            stances = row.get("agent_stances") or []

            verdict_is_bullish = verdict_str in bullish_verdicts
            verdict_is_bearish = verdict_str in bearish_verdicts

            if not verdict_is_bullish and not verdict_is_bearish:
                continue  # Skip HOLD/WATCHLIST — ambiguous

            for stance in stances:
                agent_name = stance.get("name", "").lower()
                if agent_name not in agents:
                    agents[agent_name] = AgentAttribution(name=agent_name)

                attr = agents[agent_name]
                attr.total_calls += 1

                sentiment = stance.get("sentiment", 0)
                agent_is_bullish = sentiment > 0
                agent_is_bearish = sentiment < 0

                # Agent was correct if direction matches verdict
                if agent_is_bullish:
                    attr.bullish_total += 1
                    if verdict_is_bullish:
                        attr.correct_calls += 1
                        attr.bullish_correct += 1
                elif agent_is_bearish:
                    attr.bearish_total += 1
                    if verdict_is_bearish:
                        attr.correct_calls += 1
                        attr.bearish_correct += 1

                # Track signal tags
                for signal_str in stance.get("key_signals", []):
                    # Format: "TAG_NAME (strength)"
                    tag = signal_str.split(" (")[0] if " (" in signal_str else signal_str
                    if tag not in attr.signal_accuracy:
                        attr.signal_accuracy[tag] = (0, 0)
                    correct_count, total_count = attr.signal_accuracy[tag]
                    was_correct = (
                        (agent_is_bullish and verdict_is_bullish) or
                        (agent_is_bearish and verdict_is_bearish)
                    )
                    attr.signal_accuracy[tag] = (
                        correct_count + (1 if was_correct else 0),
                        total_count + 1,
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

        # Override outcome analysis
        override_outcomes = self._analyze_overrides()

        return AttributionReport(
            agents=agents,
            recommended_weights=recommended,
            top_signals=top_signals[:10],
            worst_signals=worst_signals[:10],
            recommendations=recommendations,
            override_outcomes=override_outcomes,
        )

    def _compute_weights(self, agents: dict[str, AgentAttribution]) -> dict[str, float]:
        """Compute accuracy-proportional weights, smoothed toward defaults."""
        accuracies: dict[str, float] = {}
        for name, attr in agents.items():
            if attr.total_calls >= 10:
                accuracies[name] = attr.accuracy
            else:
                accuracies[name] = DEFAULT_WEIGHTS.get(name, 0.25)

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
                    f"(accuracy: {attr.accuracy:.0%} over {attr.total_calls} verdicts)"
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
            recs.append("All agents performing within normal parameters.")

        return recs

    def _analyze_overrides(self) -> list[OverrideOutcome]:
        """Analyze whether auditor/munger overrides add or destroy value.

        Compares overridden verdicts against settled predictions to determine
        if the override direction aligned with actual price movement.
        """
        results = []

        for override_type, column in [("auditor", "auditor_override"), ("munger", "munger_override")]:
            try:
                rows = self._registry._db.execute(
                    f"""SELECT v.ticker, v.verdict, v.confidence, v.{column},
                               p.predicted_value, p.actual_value, p.is_settled
                        FROM invest.verdicts v
                        LEFT JOIN invest.predictions p
                            ON p.ticker = v.ticker
                            AND p.created_at >= v.created_at - INTERVAL '1 day'
                            AND p.created_at <= v.created_at + INTERVAL '1 day'
                            AND p.prediction_type LIKE 'verdict_direction_%'
                        WHERE v.{column} = TRUE
                        ORDER BY v.created_at DESC"""
                )

                outcome = OverrideOutcome(override_type=override_type)
                outcome.total_overrides = len(set(r["ticker"] for r in rows)) if rows else 0

                # Check settled predictions for overridden verdicts
                bearish = {"SELL", "AVOID", "DISCARD", "REDUCE"}

                for r in rows or []:
                    if not r.get("is_settled") or r.get("actual_value") is None:
                        continue

                    outcome.total_settled += 1
                    verdict = r["verdict"]
                    actual = float(r["actual_value"])

                    # Override made verdict bearish (capped to WATCHLIST/AVOID)
                    # If price actually went down, override was correct
                    verdict_is_bearish = verdict in bearish or verdict in {"WATCHLIST", "HOLD"}

                    if verdict_is_bearish and actual < 0:
                        outcome.override_correct += 1
                    elif not verdict_is_bearish and actual > 0:
                        outcome.override_correct += 1
                    else:
                        outcome.override_wrong += 1

                if outcome.total_settled > 0:
                    correct_rate = outcome.override_correct / outcome.total_settled
                    outcome.value_added_pct = round((correct_rate - 0.5) * 100, 1)

                results.append(outcome)
            except Exception:
                logger.debug("Failed to analyze %s overrides", override_type)
                results.append(OverrideOutcome(override_type=override_type))

        return results
