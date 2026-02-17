from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from investmentology.compatibility.patterns import (
    ALL_PATTERNS,
    CONVICTION_BUY,
    HARD_REJECT,
    PatternDefinition,
    match_pattern,
    score_pattern,
)
from investmentology.models.signal import AgentSignalSet, SignalTag


@dataclass
class DisagreementRecord:
    agent_a: str
    agent_b: str
    signal_a: SignalTag
    signal_b: SignalTag
    is_dangerous: bool
    description: str


@dataclass
class CompatibilityResult:
    ticker: str
    matched_pattern: PatternDefinition | None
    pattern_score: float  # 0.0 to 1.0
    merged_signals: set[SignalTag]
    avg_confidence: Decimal
    disagreements: list[DisagreementRecord]
    dangerous_disagreement_count: int
    requires_munger: bool
    recommended_action: str


# Dangerous disagreement pairs -- these are RED FLAGS
# Each tuple: (set of signals from agent_a, set of signals from agent_b, description)
DANGEROUS_PAIRS: list[tuple[frozenset[SignalTag], frozenset[SignalTag], str]] = [
    # Warren says safe, Auditor flags risk
    (
        frozenset({SignalTag.BALANCE_SHEET_STRONG}),
        frozenset({SignalTag.LEVERAGE_HIGH}),
        "Fundamental vs Risk: balance sheet assessment conflict",
    ),
    (
        frozenset({SignalTag.UNDERVALUED}),
        frozenset({SignalTag.ACCOUNTING_RED_FLAG}),
        "Value vs Accounting: potential accounting manipulation",
    ),
    (
        frozenset({SignalTag.EARNINGS_QUALITY_HIGH}),
        frozenset({SignalTag.ACCOUNTING_RED_FLAG}),
        "Quality vs Fraud: earnings quality disputed",
    ),
    (
        frozenset({SignalTag.MOAT_WIDENING}),
        frozenset({SignalTag.GOVERNANCE_CONCERN}),
        "Moat vs Governance: moat assessment with governance risk",
    ),
    # Soros says buy, Auditor says risk
    (
        frozenset({SignalTag.REGIME_BULL}),
        frozenset({SignalTag.DRAWDOWN_RISK}),
        "Macro vs Risk: bullish macro but drawdown risk",
    ),
]

_SUSPICIOUS_UNANIMITY_THRESHOLD = Decimal("0.80")


class CompatibilityEngine:
    """Pattern matching engine for merged agent signal sets."""

    def merge_signals(self, agent_signals: list[AgentSignalSet]) -> set[SignalTag]:
        """Merge all agent signal tags into a single set."""
        merged: set[SignalTag] = set()
        for agent in agent_signals:
            merged |= agent.signals.tags
        return merged

    def detect_disagreements(
        self, agent_signals: list[AgentSignalSet]
    ) -> list[DisagreementRecord]:
        """Detect disagreements between agents.

        Two types:
        1. Healthy: different agents have conflicting signals -- normal, not dangerous
        2. Dangerous: matches DANGEROUS_PAIRS -- RED FLAG

        Also checks for suspicious unanimity (all agents agree with confidence > 0.80).
        """
        records: list[DisagreementRecord] = []

        # Check dangerous pairs across all agent combinations
        for i, agent_a in enumerate(agent_signals):
            tags_a = agent_a.signals.tags
            for agent_b in agent_signals[i + 1 :]:
                tags_b = agent_b.signals.tags
                for set1, set2, desc in DANGEROUS_PAIRS:
                    # Check both directions: a has set1 & b has set2
                    if (tags_a & set1) and (tags_b & set2):
                        signal_a = next(iter(tags_a & set1))
                        signal_b = next(iter(tags_b & set2))
                        records.append(
                            DisagreementRecord(
                                agent_a=agent_a.agent_name,
                                agent_b=agent_b.agent_name,
                                signal_a=signal_a,
                                signal_b=signal_b,
                                is_dangerous=True,
                                description=desc,
                            )
                        )
                    # Check reverse: a has set2 & b has set1
                    if (tags_a & set2) and (tags_b & set1):
                        signal_a = next(iter(tags_a & set2))
                        signal_b = next(iter(tags_b & set1))
                        records.append(
                            DisagreementRecord(
                                agent_a=agent_a.agent_name,
                                agent_b=agent_b.agent_name,
                                signal_a=signal_a,
                                signal_b=signal_b,
                                is_dangerous=True,
                                description=desc,
                            )
                        )

        # Check suspicious unanimity: all agents with confidence > 0.80
        if len(agent_signals) >= 2 and all(
            a.confidence > _SUSPICIOUS_UNANIMITY_THRESHOLD for a in agent_signals
        ):
            records.append(
                DisagreementRecord(
                    agent_a=agent_signals[0].agent_name,
                    agent_b=agent_signals[-1].agent_name,
                    signal_a=SignalTag.NO_ACTION,
                    signal_b=SignalTag.NO_ACTION,
                    is_dangerous=True,
                    description="Suspicious unanimity: all agents agree with high confidence (>0.80)",
                )
            )

        return records

    def evaluate(
        self, ticker: str, agent_signals: list[AgentSignalSet]
    ) -> CompatibilityResult:
        """Run full compatibility evaluation.

        1. Merge signals from all agents
        2. Calculate average confidence
        3. Match against patterns (priority: HARD_REJECT > CONFLICT > CONVICTION > others)
        4. Detect disagreements (healthy vs dangerous)
        5. Determine if Munger review needed
        6. Return CompatibilityResult
        """
        # 1. Merge signals
        merged = self.merge_signals(agent_signals)

        # 2. Average confidence
        if agent_signals:
            avg_confidence = sum(
                a.confidence for a in agent_signals
            ) / len(agent_signals)
        else:
            avg_confidence = Decimal("0")

        # 3. Match pattern
        matched = match_pattern(merged, float(avg_confidence))
        pattern_score = score_pattern(matched, merged) if matched else 0.0

        # 4. Detect disagreements
        disagreements = self.detect_disagreements(agent_signals)
        dangerous_count = sum(1 for d in disagreements if d.is_dangerous)

        # 5. Determine if Munger review needed
        requires_munger = (
            dangerous_count > 0
            or matched is CONVICTION_BUY
            or (
                len(agent_signals) >= 2
                and all(
                    a.confidence > _SUSPICIOUS_UNANIMITY_THRESHOLD
                    for a in agent_signals
                )
            )
        )

        # 6. Recommended action
        if matched:
            recommended_action = matched.action
        else:
            recommended_action = "No pattern matched — requires manual review"

        return CompatibilityResult(
            ticker=ticker,
            matched_pattern=matched,
            pattern_score=pattern_score,
            merged_signals=merged,
            avg_confidence=avg_confidence,
            disagreements=disagreements,
            dangerous_disagreement_count=dangerous_count,
            requires_munger=requires_munger,
            recommended_action=recommended_action,
        )
