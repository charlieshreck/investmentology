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


# Agent weights for consensus — derived from SKILLS registry (single source of truth).
# Importing lazily to avoid circular imports; weights are cached on first access.
_agent_weights_cache: dict[str, Decimal] | None = None


def _get_agent_weights() -> dict[str, Decimal]:
    """Return agent weights derived from SKILLS base_weight values."""
    global _agent_weights_cache
    if _agent_weights_cache is None:
        from investmentology.agents.skills import SKILLS
        _agent_weights_cache = {
            name: Decimal(str(skill.base_weight))
            for name, skill in SKILLS.items()
            if skill.base_weight > 0
        }
    return _agent_weights_cache



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
    regime_label: str | None = None  # Pendulum regime at analysis time
    # Batch 3 additions
    verdict_margin: float = 0.0  # Distance to nearest threshold boundary
    conviction_gap: bool = False  # True when headcount >75% but sentiment below BUY
    headcount_summary: str = ""  # e.g., "6 of 8 agents recommend buying"
    watchlist_reason: str | None = None  # INSUFFICIENT_DATA, AWAITING_CATALYST, ABOVE_ENTRY_PRICE
    watchlist_graduation_trigger: str | None = None
    # L5.5: Advisory Board results
    advisory_opinions: list = field(default_factory=list)  # list[AdvisorOpinion]
    board_narrative: object | None = None  # BoardNarrative
    board_adjusted_verdict: str | None = None  # Set if board vote changes verdict


def _compute_sentiment(signal_set: AgentSignalSet) -> float:
    """Compute sentiment score from -1.0 (bearish) to +1.0 (bullish).

    Uses evidence scaling: sentiment is dampened when total signal count is low
    (e.g. parse failures, truncated responses). Expected ~5 signals per agent.
    """
    bullish = 0.0
    bearish = 0.0
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

    raw_sentiment = (bullish - bearish) / total
    # Evidence scaling: dampen when few signals present (expected ~5)
    evidence_factor = min(1.0, total / 5.0)
    return raw_sentiment * evidence_factor


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


# --- Provider correlation groups ---
_PROVIDER_GROUPS: dict[str, set[str]] = {
    "claude": {"warren", "klarman", "auditor"},
    "gemini": {"soros", "druckenmiller", "dalio"},
    "other": {"simons", "lynch"},
}
_CORRELATION_DISCOUNT = Decimal("0.85")  # 15% discount per additional same-provider agent


def _get_provider(agent_name: str) -> str:
    for provider, agents in _PROVIDER_GROUPS.items():
        if agent_name in agents:
            return provider
    return "other"


def _apply_correlation_discount(
    stances: list[AgentStance],
    weights: dict[str, Decimal],
) -> dict[str, Decimal]:
    """Discount weight of 2nd+ agent from same provider.

    Highest-weighted agent per provider keeps full weight; 2nd gets 0.85x; 3rd 0.72x.
    """
    adjusted: dict[str, Decimal] = {}
    seen_providers: dict[str, int] = {}
    # Process in descending weight order so highest-weighted keeps full weight
    for stance in sorted(stances, key=lambda s: weights.get(s.name, Decimal("0")), reverse=True):
        provider = _get_provider(stance.name)
        count = seen_providers.get(provider, 0)
        discount = _CORRELATION_DISCOUNT ** count if count > 0 else Decimal("1")
        adjusted[stance.name] = weights.get(stance.name, Decimal("0.05")) * discount
        seen_providers[provider] = count + 1
    return adjusted


def _impute_missing_agents(
    stances: list[AgentStance],
) -> list[AgentStance]:
    """Impute neutral stance for missing agents.

    A missing agent votes neutral with low confidence — dampens consensus
    rather than amplifying remaining agents.
    """
    all_agent_names = set(_get_agent_weights().keys())
    present = {s.name for s in stances}
    for name in all_agent_names:
        if name not in present:
            stances.append(AgentStance(
                name=name,
                sentiment=0.0,
                confidence=Decimal("0.3"),
                key_signals=["IMPUTED_NEUTRAL"],
                summary=f"{name} did not provide signals (imputed neutral).",
            ))
    return stances


def synthesize(
    agent_signals: list[AgentSignalSet],
    compatibility: CompatibilityResult | None = None,
    adversarial: AdversarialResult | None = None,
    method: VotingMethod = VotingMethod.WEIGHTED_VOTE,
    weights: dict[str, Decimal] | None = None,
    position_type: str | None = None,
    regime_label: str | None = None,
    calibrator: object | None = None,
    previous_verdict: str | None = None,
) -> VerdictResult:
    """Synthesize all agent outputs into a single verdict.

    Uses confidence-weighted consensus with correlation discount,
    neutral imputation for missing agents, and pre-verdict sell-side
    bias correction.
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

    # Impute neutral for missing agents (prevents bias from who's missing)
    stances = _impute_missing_agents(stances)

    stance_map = {s.name: s for s in stances}

    # Use dynamic weights if provided, else SKILLS-derived weights
    active_weights = weights or _get_agent_weights()

    # Apply correlation discount (same-provider agents get diminished weight)
    discounted_weights = _apply_correlation_discount(stances, active_weights)

    # Compute consensus via confidence-weighted formula
    weighted_sentiment, weighted_confidence, breakdown = _confidence_weighted_consensus(
        stances, discounted_weights, calibrator=calibrator,
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

    # Portfolio Risk Manager veto check
    risk_agent = stance_map.get("portfolio_risk")
    if risk_agent:
        risk_ss = next((ss for ss in agent_signals if ss.agent_name == "portfolio_risk"), None)
        if risk_ss:
            from investmentology.models.signal import SignalTag
            for sig in risk_ss.signals.signals:
                if sig.tag.value == "VETO":
                    risk_flags.append(f"PORTFOLIO_RISK_VETO: {sig.detail}")
                    auditor_override = True  # Cap verdict like auditor veto
                elif sig.tag.value in ("REVIEW_REQUIRED", "CONCENTRATION",
                                       "CORRELATION_HIGH", "DRAWDOWN_RISK",
                                       "REGIME_MISALIGNED"):
                    risk_flags.append(f"PORTFOLIO_RISK: {sig.tag.value} — {sig.detail}")

    # Adversarial (Munger) override
    munger_override = False
    if adversarial:
        if adversarial.verdict == MungerVerdict.VETO:
            munger_override = True
        elif adversarial.verdict == MungerVerdict.CAUTION:
            weighted_sentiment *= 0.6

    # --- Determine verdict (with regime-dependent thresholds) ---
    verdict, margin_to_boundary = _score_to_verdict(
        weighted_sentiment, weighted_confidence,
        auditor_override, munger_override,
        compatibility,
        position_type=position_type,
        regime_label=regime_label,
        previous_verdict=previous_verdict,
    )

    # --- Conviction gap detection ---
    total_stances = len([s for s in stances if "IMPUTED_NEUTRAL" not in s.key_signals])
    bullish_headcount = sum(1 for s in stances if s.sentiment > 0.1 and "IMPUTED_NEUTRAL" not in s.key_signals)
    headcount_ratio = bullish_headcount / total_stances if total_stances > 0 else 0
    conviction_gap = (
        headcount_ratio >= 0.75
        and weighted_sentiment < 0.30
    )
    headcount_summary = f"{bullish_headcount} of {total_stances} agents recommend buying"

    # --- WATCHLIST sub-typing ---
    watchlist_reason: str | None = None
    watchlist_graduation_trigger: str | None = None
    if verdict == Verdict.WATCHLIST:
        watchlist_reason, watchlist_graduation_trigger = _classify_watchlist(
            weighted_sentiment, weighted_confidence, stances,
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
        verdict_margin=round(margin_to_boundary, 3),
        conviction_gap=conviction_gap,
        headcount_summary=headcount_summary,
        watchlist_reason=watchlist_reason,
        watchlist_graduation_trigger=watchlist_graduation_trigger,
    )


def _confidence_weighted_consensus(
    stances: list[AgentStance],
    weights: dict[str, Decimal],
    calibrator: object | None = None,
) -> tuple[float, Decimal, ConsensusBreakdown]:
    """Single confidence-weighted consensus formula.

    numerator = sum(w_i * c_i * s_i)
    denominator = sum(w_i * c_i)
    consensus_sentiment = numerator / denominator
    final_confidence = sum(w_i * c_i) / sum(w_i)

    Includes pre-verdict sell-side bias correction: bearish agents get 1.3x
    confidence boost in the vote power calculation (not cosmetic post-hoc).
    """
    breakdown = ConsensusBreakdown(method="CONFIDENCE_WEIGHTED")

    # Classify stances (excluding imputed)
    for s in stances:
        if "IMPUTED_NEUTRAL" in s.key_signals:
            continue
        if s.sentiment > 0.1:
            breakdown.bullish_count += 1
        elif s.sentiment < -0.1:
            breakdown.bearish_count += 1
        else:
            breakdown.neutral_count += 1

    numerator = 0.0
    denominator = Decimal("0")
    total_weight = Decimal("0")
    raw_confidence_sum = Decimal("0")

    for stance in stances:
        w = weights.get(stance.name, Decimal("0.05"))
        total_weight += w
        c = stance.confidence

        # Isotonic calibration: use data-driven calibrated confidence when
        # the agent has enough settled predictions (100+). Falls back to
        # the 1.3x sell-side stopgap otherwise.
        if calibrator and hasattr(calibrator, "is_calibrated") and calibrator.is_calibrated(stance.name):
            corrected_c = calibrator.calibrate(stance.name, c)
        elif stance.sentiment < 0:
            # Pre-verdict sell-side bias correction (stopgap):
            # Bearish agents get 1.3x confidence in vote power to correct
            # the systematic bias where BUY confidence averages 0.655 vs SELL 0.420.
            corrected_c = min(c * Decimal("1.3"), Decimal("1"))
        else:
            corrected_c = c

        vote_power = float(w * corrected_c)
        breakdown.votes[stance.name] = vote_power

        numerator += stance.sentiment * float(w * corrected_c)
        denominator += w * corrected_c
        raw_confidence_sum += w * c

    if denominator > 0:
        consensus_sentiment = numerator / float(denominator)
    else:
        consensus_sentiment = 0.0

    if total_weight > 0:
        final_confidence = raw_confidence_sum / total_weight
    else:
        final_confidence = Decimal("0")

    return consensus_sentiment, final_confidence, breakdown


# Regime-dependent threshold adjustments
_REGIME_THRESHOLD_ADJ: dict[str, dict[str, Decimal]] = {
    "fear": {
        "buy_sentiment": Decimal("0.35"),
        "strong_buy_confidence": Decimal("0.75"),
    },
    "extreme_fear": {
        "buy_sentiment": Decimal("0.40"),
        "strong_buy_confidence": Decimal("0.80"),
    },
}

# Position-type × regime overrides (tactical in crisis needs even more conviction)
_TYPE_REGIME_OVERRIDES: dict[tuple[str, str], dict[str, Decimal]] = {
    ("tactical", "extreme_fear"): {"buy_sentiment": Decimal("0.45")},
    ("tactical", "fear"): {"buy_sentiment": Decimal("0.40")},
    ("permanent", "fear"): {},  # permanent positions less affected
    ("permanent", "extreme_fear"): {},
}


def _get_thresholds(
    position_type: str | None = None,
    regime_label: str | None = None,
) -> dict[str, Decimal]:
    """Return verdict thresholds, adjusted for regime and position type."""
    base = {
        "strong_buy_sentiment": Decimal("0.55"),
        "strong_buy_confidence": Decimal("0.70"),
        "buy_sentiment": Decimal("0.30"),
        "buy_confidence": Decimal("0.50"),
        "accumulate_sentiment": Decimal("0.15"),
        "accumulate_confidence": Decimal("0.40"),
        "watchlist_sentiment": Decimal("0.10"),
    }

    # Apply regime adjustments
    if regime_label:
        adj = _REGIME_THRESHOLD_ADJ.get(regime_label, {})
        for key, val in adj.items():
            if key in base:
                base[key] = val

        # Apply position-type × regime overrides
        if position_type:
            override = _TYPE_REGIME_OVERRIDES.get((position_type, regime_label), {})
            for key, val in override.items():
                if key in base:
                    base[key] = val

    return base


_POSITIVE_VERDICTS = {Verdict.STRONG_BUY, Verdict.BUY, Verdict.ACCUMULATE}
_NEGATIVE_VERDICTS = {Verdict.REDUCE, Verdict.SELL, Verdict.AVOID}

# Verdict stability dampener — prevents rapid flip-flopping.
# When the previous verdict was positive, the sentiment must drop below this
# (more negative) threshold before the new verdict can flip to sell-side.
# Without this, a sentiment of -0.11 (barely past the -0.10 HOLD boundary)
# would flip STRONG_BUY → REDUCE in one cycle.
_FLIP_DAMPENING_BAND = Decimal("0.15")  # Extra sentiment required to flip direction


def _score_to_verdict(
    sentiment: float,
    confidence: Decimal,
    auditor_override: bool,
    munger_override: bool,
    compatibility: CompatibilityResult | None,
    position_type: str | None = None,
    regime_label: str | None = None,
    previous_verdict: "Verdict | str | None" = None,
) -> tuple[Verdict, float]:
    """Map consensus score + overrides to a verdict.

    Returns (verdict, margin_to_boundary) where margin is distance to
    nearest threshold boundary.

    Includes verdict stability dampener: when flipping direction (positive →
    negative or vice versa), requires extra conviction (the dampening band)
    to prevent small sentiment fluctuations from causing whipsaw verdicts.
    """
    # Hard overrides first — these bypass stability dampener
    if munger_override:
        return Verdict.AVOID, 0.0

    if auditor_override:
        if sentiment > 0.2:
            return Verdict.WATCHLIST, sentiment - 0.2
        return Verdict.AVOID, 0.0

    # Dangerous disagreements → needs more research
    if compatibility and compatibility.dangerous_disagreement_count >= 2:
        return Verdict.WATCHLIST, 0.0

    # Get regime-adjusted thresholds
    t = _get_thresholds(position_type, regime_label)

    sent = Decimal(str(round(sentiment, 4)))

    # Resolve previous verdict direction for stability dampener
    prev_positive = False
    prev_negative = False
    if previous_verdict:
        prev_v = previous_verdict if isinstance(previous_verdict, Verdict) else None
        if prev_v is None:
            try:
                prev_v = Verdict(str(previous_verdict))
            except (ValueError, KeyError):
                pass
        if prev_v in _POSITIVE_VERDICTS:
            prev_positive = True
        elif prev_v in _NEGATIVE_VERDICTS:
            prev_negative = True

    # Score-based with margin tracking
    if sent >= t["strong_buy_sentiment"] and confidence >= t["strong_buy_confidence"]:
        margin = float(min(sent - t["strong_buy_sentiment"], confidence - t["strong_buy_confidence"]))
        return Verdict.STRONG_BUY, margin
    if sent >= t["buy_sentiment"] and confidence >= t["buy_confidence"]:
        margin = float(min(sent - t["buy_sentiment"], confidence - t["buy_confidence"]))
        return Verdict.BUY, margin
    if sent >= t["accumulate_sentiment"] and confidence >= t["accumulate_confidence"]:
        margin = float(min(sent - t["accumulate_sentiment"], confidence - t["accumulate_confidence"]))
        return Verdict.ACCUMULATE, margin
    if sent >= t["watchlist_sentiment"] and confidence < t["accumulate_confidence"]:
        # Stability dampener: previously negative → require extra conviction to flip positive
        if prev_negative and sent < t["watchlist_sentiment"] + _FLIP_DAMPENING_BAND:
            return Verdict.HOLD, float(sent - Decimal("-0.10"))
        margin = float(sent - t["watchlist_sentiment"])
        return Verdict.WATCHLIST, margin
    if sent >= Decimal("-0.10"):
        margin = float(sent - Decimal("-0.10"))
        return Verdict.HOLD, margin

    # --- Sell-side verdicts ---

    # Stability dampener: previously positive → sentiment must exceed the HOLD
    # boundary by the dampening band before we allow REDUCE/SELL/AVOID.
    # This is the core flip-prevention: a STRONG_BUY with sentiment dropping
    # to -0.12 stays HOLD instead of flipping to REDUCE.
    if prev_positive and sent >= Decimal("-0.10") - _FLIP_DAMPENING_BAND:
        return Verdict.HOLD, float(sent - Decimal("-0.10"))

    # Sell-side confidence gates mirror buy-side: low confidence → HOLD
    if confidence < Decimal("0.40"):
        return Verdict.HOLD, float(sent - Decimal("-0.10"))
    if sent >= Decimal("-0.30"):
        margin = float(sent - Decimal("-0.30"))
        return Verdict.REDUCE, margin
    if confidence < Decimal("0.50"):
        # Strongly negative but only moderate confidence → cap at REDUCE
        margin = float(sent - Decimal("-0.30"))
        return Verdict.REDUCE, margin
    if sent >= Decimal("-0.50"):
        margin = float(sent - Decimal("-0.50"))
        return Verdict.SELL, margin
    return Verdict.AVOID, float(abs(sent + Decimal("0.50")))


def _classify_watchlist(
    sentiment: float,
    confidence: Decimal,
    stances: list[AgentStance],
) -> tuple[str, str]:
    """Classify WATCHLIST sub-type and graduation trigger."""
    imputed_count = sum(1 for s in stances if "IMPUTED_NEUTRAL" in s.key_signals)

    # INSUFFICIENT_DATA: too many imputed or very low confidence
    if imputed_count >= 3 or confidence < Decimal("0.35"):
        return "INSUFFICIENT_DATA", "New data raises confidence above 0.50"

    # ABOVE_ENTRY_PRICE: strong fundamentals but price too high
    if sentiment >= 0.25:
        return "ABOVE_ENTRY_PRICE", "Price drops below 25th-percentile agent target"

    # AWAITING_CATALYST: positive but no near-term trigger
    return "AWAITING_CATALYST", "Catalyst identified by reanalysis"


_SENTIMENT_WORD = {
    "warren": ("value", "fundamentals"),
    "soros": ("macro tailwinds", "macro headwinds"),
    "simons": ("technical strength", "technical weakness"),
    "auditor": ("risk clarity", "risk concerns"),
    "klarman": ("margin of safety", "valuation risk"),
    "druckenmiller": ("catalyst conviction", "asymmetry concerns"),
    "dalio": ("all-weather resilience", "regime vulnerability"),
    "lynch": ("growth at value", "growth concerns"),
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
