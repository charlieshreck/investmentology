"""Convergence logic — determines when debate and synthesis should trigger.

Debate is hybrid: it only fires when agents disagree significantly.
When consensus is strong (>= 75% agreement), synthesis proceeds directly.
"""

from __future__ import annotations

import logging
from collections import Counter

from investmentology.models.signal import AgentSignalSet, SignalTag

logger = logging.getLogger(__name__)

# Minimum primary agent agreement for skipping debate
CONSENSUS_THRESHOLD = 0.75

# Tags that indicate overall sentiment — expanded to include fundamentals
_BULLISH_TAGS = frozenset({
    # Action
    SignalTag.BUY_NEW, SignalTag.BUY_ADD, SignalTag.HOLD_STRONG,
    SignalTag.WATCHLIST_ADD, SignalTag.WATCHLIST_PROMOTE,
    # Fundamental
    SignalTag.UNDERVALUED, SignalTag.DEEP_VALUE,
    SignalTag.MOAT_WIDENING, SignalTag.MOAT_STABLE,
    SignalTag.REVENUE_ACCELERATING, SignalTag.MARGIN_EXPANDING,
    SignalTag.BALANCE_SHEET_STRONG,
    SignalTag.CAPITAL_ALLOCATION_EXCELLENT, SignalTag.DIVIDEND_GROWING,
    SignalTag.BUYBACK_ACTIVE, SignalTag.INSIDER_CLUSTER_BUY,
})
_BEARISH_TAGS = frozenset({
    # Action
    SignalTag.SELL_FULL, SignalTag.SELL_PARTIAL, SignalTag.TRIM,
    SignalTag.REJECT, SignalTag.REJECT_HARD,
    # Fundamental
    SignalTag.OVERVALUED, SignalTag.MOAT_NARROWING,
    SignalTag.REVENUE_DECELERATING, SignalTag.MARGIN_COMPRESSING,
    SignalTag.BALANCE_SHEET_WEAK, SignalTag.LEVERAGE_HIGH,
    SignalTag.INSIDER_CLUSTER_SELL, SignalTag.ACCOUNTING_RED_FLAG,
})
_NEUTRAL_TAGS = frozenset({
    SignalTag.HOLD, SignalTag.NO_ACTION,
})


def classify_sentiment(signal_set: AgentSignalSet) -> str:
    """Classify an agent's signal set as bullish, bearish, or neutral."""
    tags = signal_set.signals.tags

    bullish = len(tags & _BULLISH_TAGS)
    bearish = len(tags & _BEARISH_TAGS)
    neutral = len(tags & _NEUTRAL_TAGS)

    if bullish > bearish and bullish > neutral:
        return "bullish"
    if bearish > bullish and bearish > neutral:
        return "bearish"
    return "neutral"


def should_debate(agent_signals: list[AgentSignalSet]) -> bool:
    """Determine if a debate round is needed based on agent agreement.

    Returns True when agents disagree significantly (< 75% on same sentiment).
    """
    if not agent_signals:
        return False

    sentiments = [classify_sentiment(ss) for ss in agent_signals]
    counts = Counter(sentiments)
    majority_count = counts.most_common(1)[0][1]
    agreement = majority_count / len(sentiments)

    logger.info(
        "Convergence check: %s, agreement=%.0f%%, debate=%s",
        dict(counts),
        agreement * 100,
        agreement < CONSENSUS_THRESHOLD,
    )

    return agreement < CONSENSUS_THRESHOLD


def synthesis_ready(
    primary_completed: int,
    total_primary: int,
    debate_completed: bool,
    debate_required: bool,
) -> bool:
    """Check if synthesis can proceed.

    Requires:
    - At least total_primary - 2 primary agents completed (allow 2 failures)
    - Debate completed (or not required)
    """
    min_agents = max(total_primary - 2, 1)
    agents_ready = primary_completed >= min_agents
    debate_ready = debate_completed or not debate_required

    return agents_ready and debate_ready
