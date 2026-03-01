from __future__ import annotations

from dataclasses import dataclass
from investmentology.models.signal import SignalTag


@dataclass(frozen=True)
class PatternDefinition:
    name: str
    description: str
    action: str
    required_signals: frozenset[SignalTag]  # ALL must be present
    supportive_signals: frozenset[SignalTag] = frozenset()  # Strengthen match if present
    absent_signals: frozenset[SignalTag] = frozenset()  # Must NOT be present (disqualifiers)
    min_confidence: float = 0.0  # Minimum agent confidence to match


CONVICTION_BUY = PatternDefinition(
    name="CONVICTION_BUY",
    description="Warren bullish + Simons confirms trend + Auditor no risk flags",
    action="Buy at full position size",
    required_signals=frozenset({SignalTag.UNDERVALUED, SignalTag.TREND_UPTREND}),
    supportive_signals=frozenset({
        SignalTag.MOAT_WIDENING, SignalTag.MOMENTUM_STRONG,
        SignalTag.EARNINGS_QUALITY_HIGH, SignalTag.BALANCE_SHEET_STRONG,
    }),
    absent_signals=frozenset({
        SignalTag.ACCOUNTING_RED_FLAG, SignalTag.GOVERNANCE_CONCERN,
        SignalTag.CONCENTRATION, SignalTag.LEVERAGE_HIGH,
    }),
    min_confidence=0.70,
)

WATCHLIST_EARLY = PatternDefinition(
    name="WATCHLIST_EARLY",
    description="Value signals present but timing/macro not aligned",
    action="Monitor, wait for technical or macro confirmation",
    required_signals=frozenset({SignalTag.UNDERVALUED}),
    supportive_signals=frozenset({SignalTag.MOAT_STABLE, SignalTag.EARNINGS_QUALITY_HIGH}),
    absent_signals=frozenset({SignalTag.TREND_UPTREND, SignalTag.MOMENTUM_STRONG}),
)

WATCHLIST_CATALYST = PatternDefinition(
    name="WATCHLIST_CATALYST",
    description="Good setup but needs specific catalyst to trigger",
    action="Monitor with trigger, set expiry date",
    required_signals=frozenset({SignalTag.UNDERVALUED}),
    supportive_signals=frozenset({
        SignalTag.SPINOFF_ANNOUNCED, SignalTag.MERGER_TARGET,
        SignalTag.PATENT_CATALYST, SignalTag.REGULATORY_CHANGE,
        SignalTag.INSIDER_CLUSTER_BUY,
    }),
    absent_signals=frozenset({SignalTag.ACCOUNTING_RED_FLAG}),
)

CONTRARIAN_VALUE = PatternDefinition(
    name="CONTRARIAN_VALUE",
    description="Warren strongly bullish but Soros/Simons bearish — classic contrarian",
    action="Small position if Auditor clear, monitor closely",
    required_signals=frozenset({SignalTag.DEEP_VALUE}),
    supportive_signals=frozenset({SignalTag.INSIDER_CLUSTER_BUY, SignalTag.BALANCE_SHEET_STRONG}),
    absent_signals=frozenset({SignalTag.ACCOUNTING_RED_FLAG, SignalTag.GOVERNANCE_CONCERN}),
)

EARLY_RECOVERY = PatternDefinition(
    name="EARLY_RECOVERY",
    description="Beaten down stock with improving fundamentals",
    action="Build position slowly, dollar-cost average",
    required_signals=frozenset({SignalTag.DEEP_VALUE, SignalTag.REVENUE_ACCELERATING}),
    supportive_signals=frozenset({
        SignalTag.MARGIN_EXPANDING, SignalTag.RSI_OVERSOLD, SignalTag.MANAGEMENT_CHANGE,
    }),
    absent_signals=frozenset({SignalTag.ACCOUNTING_RED_FLAG, SignalTag.LEVERAGE_HIGH}),
)

QUALITY_FAIR_PRICE = PatternDefinition(
    name="QUALITY_FAIR_PRICE",
    description="Great company but not cheap enough",
    action="Watchlist at lower price target",
    required_signals=frozenset({SignalTag.FAIRLY_VALUED, SignalTag.MOAT_WIDENING}),
    supportive_signals=frozenset({SignalTag.EARNINGS_QUALITY_HIGH, SignalTag.MANAGEMENT_ALIGNED}),
    absent_signals=frozenset(),
)

FORCED_SELLING_OVERRIDE = PatternDefinition(
    name="FORCED_SELLING_OVERRIDE",
    description="Known forced seller + fundamentals intact",
    action="Aggressive buy — forced selling creates temporary mispricing",
    required_signals=frozenset({SignalTag.DEEP_VALUE, SignalTag.VOLUME_CLIMAX}),
    supportive_signals=frozenset({
        SignalTag.BALANCE_SHEET_STRONG, SignalTag.EARNINGS_QUALITY_HIGH,
        SignalTag.INSIDER_CLUSTER_BUY,
    }),
    absent_signals=frozenset({SignalTag.ACCOUNTING_RED_FLAG, SignalTag.REVENUE_DECELERATING}),
)

MOMENTUM_ONLY = PatternDefinition(
    name="MOMENTUM_ONLY",
    description="Technical momentum with no fundamental support",
    action="Skip — not our strategy",
    required_signals=frozenset({SignalTag.MOMENTUM_STRONG, SignalTag.TREND_UPTREND}),
    supportive_signals=frozenset(),
    absent_signals=frozenset({SignalTag.UNDERVALUED, SignalTag.DEEP_VALUE, SignalTag.FAIRLY_VALUED}),
)

VALUE_TRAP = PatternDefinition(
    name="VALUE_TRAP",
    description="Looks cheap but fundamentals deteriorating",
    action="Reject — value trap",
    required_signals=frozenset({SignalTag.UNDERVALUED, SignalTag.REVENUE_DECELERATING}),
    supportive_signals=frozenset({SignalTag.MARGIN_COMPRESSING, SignalTag.MOAT_NARROWING}),
    absent_signals=frozenset(),
)

HARD_REJECT = PatternDefinition(
    name="HARD_REJECT",
    description="Auditor kill signal or Munger veto",
    action="Hard no — do not revisit without material change",
    required_signals=frozenset(),
    supportive_signals=frozenset(),
    absent_signals=frozenset(),
)

CONFLICT_REVIEW = PatternDefinition(
    name="CONFLICT_REVIEW",
    description="Unresolvable agent disagreement requiring human review",
    action="Flag for human review",
    required_signals=frozenset({SignalTag.CONFLICT_FLAG}),
    supportive_signals=frozenset(),
    absent_signals=frozenset(),
)

ALL_PATTERNS: list[PatternDefinition] = [
    CONVICTION_BUY, WATCHLIST_EARLY, WATCHLIST_CATALYST, CONTRARIAN_VALUE,
    EARLY_RECOVERY, QUALITY_FAIR_PRICE, FORCED_SELLING_OVERRIDE,
    MOMENTUM_ONLY, VALUE_TRAP, HARD_REJECT, CONFLICT_REVIEW,
]

# Tags that trigger HARD_REJECT when present
_HARD_REJECT_TRIGGERS: frozenset[SignalTag] = frozenset({
    SignalTag.ACCOUNTING_RED_FLAG,
    SignalTag.GOVERNANCE_CONCERN,
    SignalTag.MUNGER_VETO,
})


def match_pattern(
    signals: set[SignalTag], avg_confidence: float = 0.0
) -> PatternDefinition | None:
    """Find the best matching pattern for a set of signals.

    Priority order: HARD_REJECT > CONFLICT_REVIEW > CONVICTION_BUY > others

    For HARD_REJECT: matches if ACCOUNTING_RED_FLAG, GOVERNANCE_CONCERN, or MUNGER_VETO present.
    For others: all required_signals must be present, no absent_signals present.

    Returns the highest-priority matching pattern, or None if no match.
    """
    # Priority 1: HARD_REJECT
    if signals & _HARD_REJECT_TRIGGERS:
        return HARD_REJECT

    # Priority 2: CONFLICT_REVIEW
    if SignalTag.CONFLICT_FLAG in signals:
        return CONFLICT_REVIEW

    # Priority 3: CONVICTION_BUY (checked first among general patterns due to confidence gate)
    if _pattern_matches(CONVICTION_BUY, signals, avg_confidence):
        return CONVICTION_BUY

    # Remaining patterns: prefer more specific (more required signals) over less specific
    candidates = [
        p for p in ALL_PATTERNS
        if p not in (CONVICTION_BUY, HARD_REJECT, CONFLICT_REVIEW)
        and _pattern_matches(p, signals, avg_confidence)
    ]
    if candidates:
        candidates.sort(key=lambda p: len(p.required_signals), reverse=True)
        return candidates[0]

    return None


def _pattern_matches(
    pattern: PatternDefinition, signals: set[SignalTag], avg_confidence: float
) -> bool:
    """Check if a signal set satisfies a pattern's constraints."""
    if avg_confidence < pattern.min_confidence:
        return False
    if pattern.required_signals and not pattern.required_signals.issubset(signals):
        return False
    if pattern.absent_signals and (signals & pattern.absent_signals):
        return False
    return True


def score_pattern(pattern: PatternDefinition, signals: set[SignalTag]) -> float:
    """Score how well a signal set matches a pattern (0.0 to 1.0).

    - 0.0 if any required signal missing or any absent signal present
    - Base score from required signals present
    - Bonus from supportive signals present
    """
    # Disqualify if required signals missing
    if pattern.required_signals and not pattern.required_signals.issubset(signals):
        return 0.0

    # Disqualify if absent signals present
    if pattern.absent_signals and (signals & pattern.absent_signals):
        return 0.0

    # Base score: 0.5 for having all required signals (or 0.5 if none required)
    base = 0.5

    # Bonus from supportive signals (up to 0.5)
    if pattern.supportive_signals:
        matched_supportive = len(signals & pattern.supportive_signals)
        total_supportive = len(pattern.supportive_signals)
        bonus = 0.5 * (matched_supportive / total_supportive)
    else:
        bonus = 0.0

    return base + bonus
