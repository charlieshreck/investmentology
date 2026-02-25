"""Verdict Synthesizer — computes the final recommendation from all agent signals.

Takes the outputs of L2 (competence), L3 (4 agents), L4 (compatibility + adversarial)
and produces a single, objective verdict with clear reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from investmentology.adversarial.munger import AdversarialResult, MungerVerdict
from investmentology.compatibility.matrix import CompatibilityResult
from investmentology.models.signal import AgentSignalSet, SignalTag


class Verdict(StrEnum):
    """The finite set of recommendations the system can make."""

    STRONG_BUY = "STRONG_BUY"  # High conviction, all agents aligned, auditor clear
    BUY = "BUY"  # Positive consensus, manageable risk
    ACCUMULATE = "ACCUMULATE"  # Build position gradually, some caution flags
    HOLD = "HOLD"  # Already own — maintain position
    WATCHLIST = "WATCHLIST"  # Interesting but not ready — monitor for catalyst
    REDUCE = "REDUCE"  # Take some profit or reduce exposure
    SELL = "SELL"  # Exit position
    AVOID = "AVOID"  # Failed checks — do not invest
    DISCARD = "DISCARD"  # Fundamentally unsuitable — remove from consideration


class VotingMethod(StrEnum):
    """How to aggregate agent signals into a consensus."""

    WEIGHTED_VOTE = "WEIGHTED_VOTE"  # Default: weight * confidence as vote power
    SUPERMAJORITY = "SUPERMAJORITY"  # Need 3/4 agents agreeing for strong actions
    CONVICTION_WEIGHTED = "CONVICTION_WEIGHTED"  # Highest-confidence agent gets 2x on ties


# Agent weights for consensus (must sum to 1.0)
AGENT_WEIGHTS = {
    "warren": Decimal("0.30"),  # Fundamentals carry most weight
    "soros": Decimal("0.20"),  # Macro context
    "simons": Decimal("0.20"),  # Technical timing
    "auditor": Decimal("0.30"),  # Risk assessment — equal to Warren
}

# Signal tags that indicate bullish stance per agent category
_BULLISH = {
    SignalTag.UNDERVALUED, SignalTag.DEEP_VALUE, SignalTag.MOAT_WIDENING,
    SignalTag.MOAT_STABLE, SignalTag.EARNINGS_QUALITY_HIGH, SignalTag.REVENUE_ACCELERATING,
    SignalTag.MARGIN_EXPANDING, SignalTag.BALANCE_SHEET_STRONG,
    SignalTag.REGIME_BULL, SignalTag.SECTOR_ROTATION_INTO, SignalTag.CREDIT_EASING,
    SignalTag.FISCAL_STIMULUS, SignalTag.LIQUIDITY_ABUNDANT,
    SignalTag.TREND_UPTREND, SignalTag.MOMENTUM_STRONG, SignalTag.BREAKOUT_CONFIRMED,
    SignalTag.GOLDEN_CROSS, SignalTag.RELATIVE_STRENGTH_HIGH,
    SignalTag.LEVERAGE_OK, SignalTag.LIQUIDITY_OK, SignalTag.VOLATILITY_LOW,
    SignalTag.CORRELATION_LOW,
}

_BEARISH = {
    SignalTag.OVERVALUED, SignalTag.NO_MOAT, SignalTag.MOAT_NARROWING,
    SignalTag.EARNINGS_QUALITY_LOW, SignalTag.REVENUE_DECELERATING,
    SignalTag.MARGIN_COMPRESSING, SignalTag.BALANCE_SHEET_WEAK,
    SignalTag.REGIME_BEAR, SignalTag.SECTOR_ROTATION_OUT, SignalTag.CREDIT_TIGHTENING,
    SignalTag.GEOPOLITICAL_RISK, SignalTag.LIQUIDITY_TIGHT,
    SignalTag.TREND_DOWNTREND, SignalTag.MOMENTUM_WEAK, SignalTag.BREAKDOWN_CONFIRMED,
    SignalTag.DEATH_CROSS, SignalTag.RELATIVE_STRENGTH_LOW,
    SignalTag.LEVERAGE_HIGH, SignalTag.LIQUIDITY_LOW, SignalTag.VOLATILITY_HIGH,
    SignalTag.ACCOUNTING_RED_FLAG, SignalTag.GOVERNANCE_CONCERN, SignalTag.DRAWDOWN_RISK,
    SignalTag.CONCENTRATION, SignalTag.CORRELATION_HIGH,
}

# Action tags map directly to stance
_ACTION_BULLISH = {
    SignalTag.BUY_NEW, SignalTag.BUY_ADD, SignalTag.HOLD_STRONG,
    SignalTag.WATCHLIST_ADD, SignalTag.WATCHLIST_PROMOTE,
}
_ACTION_BEARISH = {
    SignalTag.SELL_FULL, SignalTag.SELL_PARTIAL, SignalTag.TRIM,
    SignalTag.REJECT, SignalTag.REJECT_HARD,
}


@dataclass
class AgentStance:
    """An individual agent's distilled stance."""

    name: str
    sentiment: float  # -1.0 (bearish) to +1.0 (bullish)
    confidence: Decimal
    key_signals: list[str]
    summary: str


@dataclass
class ConsensusBreakdown:
    """Details of how the consensus was computed."""

    method: str  # VotingMethod used
    votes: dict[str, float] = field(default_factory=dict)  # agent -> vote power
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    supermajority_met: bool = False


@dataclass
class VerdictResult:
    """The final synthesized recommendation."""

    verdict: Verdict
    confidence: Decimal  # 0-1, weighted across agents
    reasoning: str  # Human-readable explanation
    agent_stances: list[AgentStance] = field(default_factory=list)
    consensus_score: float = 0.0  # -1.0 to +1.0
    risk_flags: list[str] = field(default_factory=list)
    auditor_override: bool = False  # True if auditor vetoed/capped
    munger_override: bool = False  # True if adversarial changed outcome
    consensus_breakdown: ConsensusBreakdown | None = None


def _compute_sentiment(signal_set: AgentSignalSet) -> float:
    """Compute sentiment score from -1.0 (bearish) to +1.0 (bullish)."""
    bullish = 0
    bearish = 0
    strength_mult = {"strong": 1.5, "moderate": 1.0, "weak": 0.5}

    for sig in signal_set.signals.signals:
        mult = strength_mult.get(sig.strength, 1.0)
        if sig.tag in _BULLISH or sig.tag in _ACTION_BULLISH:
            bullish += mult
        elif sig.tag in _BEARISH or sig.tag in _ACTION_BEARISH:
            bearish += mult

    total = bullish + bearish
    if total == 0:
        return 0.0
    return (bullish - bearish) / total


def _distill_stance(signal_set: AgentSignalSet) -> AgentStance:
    """Distill an agent's signals into a summary stance."""
    sentiment = _compute_sentiment(signal_set)

    # Pick top 3 strongest signals for the summary
    sorted_signals = sorted(
        signal_set.signals.signals,
        key=lambda s: {"strong": 3, "moderate": 2, "weak": 1}.get(s.strength, 0),
        reverse=True,
    )
    key_signals = [
        f"{s.tag.value} ({s.strength})" for s in sorted_signals[:3]
    ]

    return AgentStance(
        name=signal_set.agent_name,
        sentiment=round(sentiment, 3),
        confidence=signal_set.confidence,
        key_signals=key_signals,
        summary=signal_set.reasoning,
    )


def synthesize(
    agent_signals: list[AgentSignalSet],
    compatibility: CompatibilityResult | None = None,
    adversarial: AdversarialResult | None = None,
    method: VotingMethod = VotingMethod.WEIGHTED_VOTE,
    weights: dict[str, Decimal] | None = None,
) -> VerdictResult:
    """Synthesize all agent outputs into a single verdict.

    This is the final computation that produces the recommendation.

    Args:
        method: Voting method to use. WEIGHTED_VOTE (default) uses static
            agent weights * confidence. SUPERMAJORITY requires 3/4 agents
            to agree for BUY/REJECT actions. CONVICTION_WEIGHTED gives the
            highest-confidence agent 2x weight on ties.
    """
    if not agent_signals:
        return VerdictResult(
            verdict=Verdict.DISCARD,
            confidence=Decimal("0"),
            reasoning="No agent signals available — cannot form an opinion.",
        )

    # Exclude agents that failed to parse LLM responses
    valid_signals = [ss for ss in agent_signals if not ss.parse_failed]
    if not valid_signals:
        failed_names = [ss.agent_name for ss in agent_signals]
        return VerdictResult(
            verdict=Verdict.DISCARD,
            confidence=Decimal("0"),
            reasoning=f"All agents failed to parse: {', '.join(failed_names)}.",
            risk_flags=["ALL_AGENTS_PARSE_FAILED"],
        )

    # Distill each agent's stance
    stances = [_distill_stance(ss) for ss in valid_signals]
    stance_map = {s.name: s for s in stances}

    # Compute consensus based on method
    # Use dynamic weights if provided, else default AGENT_WEIGHTS
    active_weights = weights or AGENT_WEIGHTS

    weighted_sentiment, weighted_confidence, breakdown = _compute_consensus(
        stances, method, active_weights,
    )

    # Auditor risk check — the devil's advocate has veto power
    auditor = stance_map.get("auditor")
    risk_flags: list[str] = []
    auditor_override = False

    if auditor:
        # Extract risk-specific signals from auditor
        auditor_ss = next((ss for ss in agent_signals if ss.agent_name == "auditor"), None)
        if auditor_ss:
            for sig in auditor_ss.signals.signals:
                if sig.tag in _BEARISH and sig.strength == "strong":
                    risk_flags.append(f"{sig.tag.value}: {sig.detail}")

        # If auditor is strongly bearish, cap the verdict
        if auditor.sentiment < -0.3 and auditor.confidence >= Decimal("0.6"):
            auditor_override = True

    # Adversarial (Munger) override
    munger_override = False
    if adversarial:
        if adversarial.verdict == MungerVerdict.VETO:
            munger_override = True
        elif adversarial.verdict == MungerVerdict.CAUTION:
            # Downgrade sentiment
            weighted_sentiment *= 0.6

    # --- Determine verdict ---
    verdict = _score_to_verdict(
        weighted_sentiment, weighted_confidence,
        auditor_override, munger_override,
        compatibility,
    )

    # --- Build reasoning ---
    reasoning = _build_reasoning(
        verdict, stances, weighted_sentiment, weighted_confidence,
        risk_flags, auditor_override, munger_override, adversarial,
    )

    return VerdictResult(
        verdict=verdict,
        confidence=weighted_confidence,
        reasoning=reasoning,
        agent_stances=stances,
        consensus_score=round(weighted_sentiment, 3),
        risk_flags=risk_flags,
        auditor_override=auditor_override,
        munger_override=munger_override,
        consensus_breakdown=breakdown,
    )


def _compute_consensus(
    stances: list[AgentStance],
    method: VotingMethod,
    weights: dict[str, Decimal] | None = None,
) -> tuple[float, Decimal, ConsensusBreakdown]:
    """Compute consensus using the specified voting method.

    Returns (weighted_sentiment, weighted_confidence, breakdown).
    """
    breakdown = ConsensusBreakdown(method=method.value)

    # Classify stances
    for s in stances:
        if s.sentiment > 0.1:
            breakdown.bullish_count += 1
        elif s.sentiment < -0.1:
            breakdown.bearish_count += 1
        else:
            breakdown.neutral_count += 1

    active_weights = weights or AGENT_WEIGHTS
    if method == VotingMethod.SUPERMAJORITY:
        return _consensus_supermajority(stances, breakdown, active_weights)
    elif method == VotingMethod.CONVICTION_WEIGHTED:
        return _consensus_conviction(stances, breakdown, active_weights)
    else:
        return _consensus_weighted(stances, breakdown, active_weights)


def _consensus_weighted(
    stances: list[AgentStance],
    breakdown: ConsensusBreakdown,
    weights: dict[str, Decimal] | None = None,
) -> tuple[float, Decimal, ConsensusBreakdown]:
    """Default: weight * confidence as vote power, normalized for partial agent sets."""
    weighted_sentiment = 0.0
    weighted_confidence = Decimal("0")
    total_weight = Decimal("0")
    for stance in stances:
        weight = (weights or AGENT_WEIGHTS).get(stance.name, Decimal("0.25"))
        total_weight += weight
        vote_power = float(stance.confidence * weight)
        breakdown.votes[stance.name] = vote_power
        weighted_sentiment += stance.sentiment * float(weight)
        weighted_confidence += stance.confidence * weight
    # Renormalize when fewer agents present (weights won't sum to 1.0)
    if total_weight > 0 and total_weight != Decimal("1"):
        weighted_sentiment /= float(total_weight)
        weighted_confidence /= total_weight
    return weighted_sentiment, weighted_confidence, breakdown


def _consensus_supermajority(
    stances: list[AgentStance],
    breakdown: ConsensusBreakdown,
    weights: dict[str, Decimal] | None = None,
) -> tuple[float, Decimal, ConsensusBreakdown]:
    """Need 3/4 agents agreeing for strong actions (BUY/REJECT).

    If supermajority not met, falls back to weighted but sentiment is dampened.
    """
    total = len(stances)
    threshold = max(3, int(total * 0.75))
    breakdown.supermajority_met = (
        breakdown.bullish_count >= threshold or breakdown.bearish_count >= threshold
    )

    # Still compute weighted as base
    weighted_sentiment = 0.0
    weighted_confidence = Decimal("0")
    total_weight = Decimal("0")
    for stance in stances:
        weight = (weights or AGENT_WEIGHTS).get(stance.name, Decimal("0.25"))
        total_weight += weight
        vote_power = float(stance.confidence * weight)
        breakdown.votes[stance.name] = vote_power
        weighted_sentiment += stance.sentiment * float(weight)
        weighted_confidence += stance.confidence * weight

    # Renormalize for partial agent sets
    if total_weight > 0 and total_weight != Decimal("1"):
        weighted_sentiment /= float(total_weight)
        weighted_confidence /= total_weight

    # If supermajority not met, dampen sentiment toward neutral
    if not breakdown.supermajority_met:
        weighted_sentiment *= 0.6

    return weighted_sentiment, weighted_confidence, breakdown


def _consensus_conviction(
    stances: list[AgentStance],
    breakdown: ConsensusBreakdown,
    weights: dict[str, Decimal] | None = None,
) -> tuple[float, Decimal, ConsensusBreakdown]:
    """Highest-confidence agent gets 2x weight on ties (2-2 split)."""
    # Check if it's a tie (equal bullish and bearish)
    is_tie = breakdown.bullish_count == breakdown.bearish_count and breakdown.bullish_count > 0

    # Find most confident agent
    most_confident = max(stances, key=lambda s: s.confidence)

    weighted_sentiment = 0.0
    weighted_confidence = Decimal("0")
    total_weight = Decimal("0")
    for stance in stances:
        weight = (weights or AGENT_WEIGHTS).get(stance.name, Decimal("0.25"))
        # Give 2x weight to highest-confidence on ties
        if is_tie and stance.name == most_confident.name:
            weight *= 2
        total_weight += weight
        vote_power = float(stance.confidence * weight)
        breakdown.votes[stance.name] = vote_power
        weighted_sentiment += stance.sentiment * float(weight)
        weighted_confidence += stance.confidence * weight

    # Renormalize both sentiment and confidence for inflated/partial weights
    if total_weight > 0 and total_weight != Decimal("1"):
        weighted_sentiment /= float(total_weight)
        weighted_confidence /= total_weight

    return weighted_sentiment, weighted_confidence, breakdown


def _score_to_verdict(
    sentiment: float,
    confidence: Decimal,
    auditor_override: bool,
    munger_override: bool,
    compatibility: CompatibilityResult | None,
) -> Verdict:
    """Map consensus score + overrides to a verdict."""
    # Hard overrides first
    if munger_override:
        return Verdict.AVOID

    if auditor_override:
        # Auditor caps at WATCHLIST max
        if sentiment > 0.2:
            return Verdict.WATCHLIST
        if sentiment > -0.2:
            return Verdict.AVOID
        return Verdict.AVOID

    # Dangerous disagreements → needs more research
    if compatibility and compatibility.dangerous_disagreement_count >= 2:
        return Verdict.WATCHLIST

    # Score-based
    if sentiment >= 0.6 and confidence >= Decimal("0.7"):
        return Verdict.STRONG_BUY
    if sentiment >= 0.3 and confidence >= Decimal("0.5"):
        return Verdict.BUY
    if sentiment >= 0.15:
        return Verdict.ACCUMULATE
    if sentiment >= -0.1:
        if confidence >= Decimal("0.4"):
            return Verdict.HOLD
        return Verdict.WATCHLIST
    if sentiment >= -0.3:
        return Verdict.REDUCE
    if sentiment >= -0.5:
        return Verdict.SELL
    return Verdict.AVOID


_SENTIMENT_WORD = {
    "warren": ("value", "fundamentals"),
    "soros": ("macro tailwinds", "macro headwinds"),
    "simons": ("technical strength", "technical weakness"),
    "auditor": ("risk clarity", "risk concerns"),
}


def _build_reasoning(
    verdict: Verdict,
    stances: list[AgentStance],
    sentiment: float,
    confidence: Decimal,
    risk_flags: list[str],
    auditor_override: bool,
    munger_override: bool,
    adversarial: AdversarialResult | None,
) -> str:
    """Build a human-readable reasoning chain."""
    parts: list[str] = []

    # Agent summary line
    agent_summaries = []
    for s in stances:
        label_pos, label_neg = _SENTIMENT_WORD.get(s.name, ("positive", "negative"))
        if s.sentiment > 0.1:
            agent_summaries.append(
                f"{s.name.capitalize()} sees {label_pos} ({s.confidence * 100:.0f}% confidence)"
            )
        elif s.sentiment < -0.1:
            agent_summaries.append(
                f"{s.name.capitalize()} flags {label_neg} ({s.confidence * 100:.0f}% confidence)"
            )
        else:
            agent_summaries.append(f"{s.name.capitalize()} is neutral ({s.confidence * 100:.0f}%)")

    parts.append(". ".join(agent_summaries) + ".")

    # Override explanations
    if munger_override:
        reason = adversarial.reasoning[:120] if adversarial and adversarial.reasoning else "critical flaws identified"
        parts.append(f"Adversarial review vetoed: {reason}.")
    elif auditor_override:
        parts.append("Auditor override: high-confidence risk flags limit the recommendation.")

    # Risk flags
    if risk_flags:
        parts.append(f"Risk flags: {'; '.join(risk_flags[:3])}.")

    # Verdict statement
    verdict_text = {
        Verdict.STRONG_BUY: "Strong consensus with clear risk profile. Recommended for full position.",
        Verdict.BUY: "Positive consensus. Recommended for entry.",
        Verdict.ACCUMULATE: "Leaning positive but some caution. Build position gradually.",
        Verdict.HOLD: "Mixed signals. Maintain existing position, no new entry.",
        Verdict.WATCHLIST: "Not ready for action. Add to watchlist and monitor.",
        Verdict.REDUCE: "Deteriorating outlook. Consider reducing exposure.",
        Verdict.SELL: "Negative consensus. Recommended exit.",
        Verdict.AVOID: "Failed analysis checks. Do not invest.",
        Verdict.DISCARD: "Fundamentally unsuitable. Remove from consideration.",
    }
    parts.append(verdict_text.get(verdict, ""))

    return " ".join(parts)
