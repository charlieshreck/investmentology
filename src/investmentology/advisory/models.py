"""Data models for the Advisory Board (L5.5) and CIO Synthesis (L6).

The Advisory Board consists of 8 legendary investor personas that review
the L5 verdict through their unique analytical lenses. The CIO narrates
the board's vote outcome into a coherent investment thesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class BoardVote(StrEnum):
    """How an advisory board member votes on the L5 verdict."""

    APPROVE = "APPROVE"  # Agrees with the verdict
    ADJUST_UP = "ADJUST_UP"  # Thinks verdict should be more bullish
    ADJUST_DOWN = "ADJUST_DOWN"  # Thinks verdict should be more bearish
    VETO = "VETO"  # Fundamentally disagrees — kill the trade


@dataclass
class AdvisorSpec:
    """Configuration for a single advisory board member."""

    key: str  # "dalio", "lynch", etc.
    display_name: str  # "Ray Dalio", "Peter Lynch", etc.
    philosophy: str  # Core investing philosophy
    data_focus: str  # What data this advisor cares about most
    evaluation_criteria: str  # How they evaluate investments
    bias_warning: str  # What they tend to over-do (makes LLM model personality better)
    vote_tendency: str  # Concrete examples of when they vote each way
    signature_question: str  # The one question this advisor always asks


@dataclass
class AdvisorOpinion:
    """Opinion from a single advisory board member."""

    advisor_name: str  # "dalio", "lynch", etc.
    display_name: str  # "Ray Dalio", "Peter Lynch", etc.
    vote: BoardVote
    confidence: Decimal  # 0-1
    assessment: str  # 1-2 sentence headline
    key_concern: str | None = None  # Primary risk or objection
    key_endorsement: str | None = None  # Primary positive factor
    reasoning: str = ""  # 2-3 paragraph analysis from this advisor's lens
    specific_numbers: dict = field(default_factory=dict)  # e.g. {"bear_case_price": 45.0}
    model: str = ""
    latency_ms: int = 0


@dataclass
class BoardNarrative:
    """CIO's narrative synthesis of the board's decision."""

    headline: str  # "BUY with caution — strong fundamentals, late-cycle risk"
    narrative: str  # 3-4 paragraphs explaining the recommendation
    risk_summary: str  # "What would make us wrong"
    pre_mortem: str  # "If this goes badly, it will be because..."
    conflict_resolution: str  # How competing views were reconciled
    verdict_adjustment: int = 0  # -1, 0, or +1 (CIO recommendation, not authoritative)
    adjusted_verdict: str | None = None  # Only set if adjustment != 0
    advisor_consensus: dict = field(default_factory=dict)  # {"endorsing": 6, "dissenting": 2, ...}
    model: str = ""
    latency_ms: int = 0


@dataclass
class BoardResult:
    """Complete result from the Advisory Board + CIO synthesis."""

    opinions: list[AdvisorOpinion] = field(default_factory=list)
    narrative: BoardNarrative | None = None
    # Vote synthesis (deterministic Python, not LLM)
    original_verdict: str = ""
    adjusted_verdict: str | None = None  # Set if board vote changes the verdict
    vote_counts: dict[str, int] = field(default_factory=dict)  # {"APPROVE": 5, "VETO": 1, ...}
    veto_count: int = 0
    total_latency_ms: int = 0

    @property
    def verdict_changed(self) -> bool:
        return self.adjusted_verdict is not None and self.adjusted_verdict != self.original_verdict
