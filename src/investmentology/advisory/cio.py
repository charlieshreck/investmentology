"""CIO Synthesis (L6) — narrates the Advisory Board's vote into a coherent thesis.

The CIO is a narrator, NOT a dictator. The board vote is authoritative.
The CIO writes the story that explains the vote outcome, reconciles
disagreements, and produces the risk summary and pre-mortem.

The CIO can suggest a ±1 adjustment as a recommendation, but only when:
  - It doesn't contradict the board vote direction
  - 4+ advisors were split (near-tie scenarios where CIO breaks the tie)
  - Cannot override a Forensic ACCOUNTING_RED_FLAG veto
  - Cannot upgrade past STRONG_BUY or downgrade past AVOID
"""

from __future__ import annotations

import logging
import time

from investmentology.advisory.board import _extract_json
from investmentology.advisory.models import (
    BoardNarrative,
    BoardResult,
    BoardVote,
)
from investmentology.agents.gateway import LLMGateway
from investmentology.verdict import AgentStance, VerdictResult

logger = logging.getLogger(__name__)

# Provider preference for CIO synthesis
CIO_PROVIDERS = ["deepseek", "groq"]


class CIOSynthesizer:
    """Produces the narrative synthesis of the advisory board's decision."""

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def synthesize(
        self,
        verdict: VerdictResult,
        board_result: BoardResult,
        stances: list[AgentStance],
        adversarial: object | None = None,
    ) -> BoardNarrative:
        """Generate the CIO narrative from the board's vote outcome."""
        start_time = time.monotonic()

        system_prompt = _build_cio_system_prompt()
        user_prompt = _build_cio_user_prompt(verdict, board_result, stances, adversarial)

        # Try providers in preference order
        last_error: Exception | None = None
        resp = None
        for provider in CIO_PROVIDERS:
            try:
                resp = await self._gateway.call(
                    provider=provider,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=3000,
                    temperature=0.3,
                )
                break
            except Exception as e:
                last_error = e
                logger.debug("CIO provider %s failed: %s", provider, e)

        latency_ms = int((time.monotonic() - start_time) * 1000)

        if resp is None:
            logger.warning("All CIO providers failed: %s", last_error)
            return _fallback_narrative(verdict, board_result, latency_ms)

        return _parse_cio_response(resp, verdict, board_result, latency_ms)


# ---------------------------------------------------------------------------
# Prompt Builders
# ---------------------------------------------------------------------------

def _build_cio_system_prompt() -> str:
    return """You are the Chief Investment Officer synthesizing an advisory board's decision into a coherent investment narrative. You are a NARRATOR, not a decision-maker — the board has already voted.

The board consists of 6 functional roles:
- **Risk Officer**: Portfolio risk, VaR, concentration, stress tests
- **Valuation Analyst**: DCF cross-check, relative valuation, margin of safety
- **Macro Strategist**: Regime alignment, cycle positioning, monetary policy
- **Devil's Advocate**: Bias detection, groupthink challenge, inversion analysis
- **Portfolio Constructor**: Position fit, sizing, sector balance, correlation
- **Thesis Integrity Reviewer**: Original thesis vs current evidence, catalyst tracking

Your job:
1. Write a compelling headline summarizing the board's recommendation
2. Write 3-4 paragraphs explaining WHY the board voted this way, reconciling disagreements
3. Summarize the key risks ("What would make us wrong")
4. Write a pre-mortem ("If this goes badly, it will be because...")
5. Explain how competing advisor views were reconciled

## Position Type Framing
When a position type is specified, frame the narrative accordingly:
- **Permanent**: "This is a generational holding. The question is whether the moat endures..."
- **Core**: "This is a multi-year competitive advantage play. The key is..."
- **Tactical**: "This is a defined-horizon opportunity. The catalyst window closes in..."

## Conflict Resolution Patterns
Use these when advisors disagree:
- **Risk vs Opportunity**: Risk Officer flags concentration but Valuation Analyst sees deep value → Size down, don't skip
- **Macro vs Micro**: Macro Strategist bearish on regime but company-level thesis is strong → Accumulate with caution
- **Thesis Drift**: Thesis Integrity flags degradation but Portfolio Constructor sees diversification value → Time-bound hold with review trigger
- **Valuation Gap**: Valuation Analyst and agents disagree on fair value → Use reverse DCF, show what's priced in
- **Consensus Too Uniform**: Devil's Advocate challenges and agents agree → Investigate the unaddressed bear case
- **Portfolio Fit**: Great stock but Portfolio Constructor flags concentration → Trim existing, then add
- **Forensic Veto**: Agents bullish but Risk Officer flags accounting concerns → AVOID (hard override)

Respond with ONLY valid JSON (no markdown fences):
{
    "headline": "One sentence summary of the board decision",
    "narrative": "3-4 paragraphs explaining the recommendation",
    "risk_summary": "What would make us wrong",
    "pre_mortem": "If this goes badly, it will be because...",
    "conflict_resolution": "How competing views were reconciled",
    "verdict_adjustment": 0,
    "adjusted_verdict": null
}

verdict_adjustment: -1 (more bearish), 0 (no change), or +1 (more bullish).
Only suggest adjustment when advisors are split (3-3 near-tie). Never override VETOs."""


def _build_cio_user_prompt(
    verdict: VerdictResult,
    board_result: BoardResult,
    stances: list[AgentStance],
    adversarial: object | None,
) -> str:
    parts: list[str] = []

    # Board vote outcome
    effective_verdict = board_result.adjusted_verdict or board_result.original_verdict
    parts.append("## Board Decision")
    parts.append(f"Original Verdict: {board_result.original_verdict}")
    if board_result.adjusted_verdict:
        parts.append(f"Board-Adjusted Verdict: {board_result.adjusted_verdict}")
    parts.append(f"Effective Verdict: {effective_verdict}")
    parts.append(f"Vote Counts: {board_result.vote_counts}")
    parts.append(f"VETOs: {board_result.veto_count}")

    # Individual advisor opinions
    parts.append("\n## Advisory Opinions")
    for op in board_result.opinions:
        parts.append(
            f"- **{op.display_name}** ({op.vote.value}, {float(op.confidence):.0%}): "
            f"{op.assessment}"
        )
        if op.key_concern:
            parts.append(f"  Concern: {op.key_concern}")
        if op.key_endorsement:
            parts.append(f"  Endorsement: {op.key_endorsement}")
        if op.reasoning:
            parts.append(f"  Reasoning: {op.reasoning[:200]}")

    # Original agent stances for context
    parts.append("\n## L3 Agent Stances (for context)")
    for s in stances:
        direction = "BULLISH" if s.sentiment > 0.1 else "BEARISH" if s.sentiment < -0.1 else "NEUTRAL"
        parts.append(f"- {s.name.capitalize()}: {direction} ({s.sentiment:.2f})")

    # Adversarial
    if adversarial:
        adv_verdict = getattr(adversarial, "verdict", None)
        if adv_verdict:
            parts.append(f"\n## Adversarial: {adv_verdict.value if hasattr(adv_verdict, 'value') else adv_verdict}")

    # Risk flags
    if verdict.risk_flags:
        parts.append(f"\n## Risk Flags: {'; '.join(verdict.risk_flags[:5])}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Response Parsing
# ---------------------------------------------------------------------------

def _parse_cio_response(
    resp,
    verdict: VerdictResult,
    board_result: BoardResult,
    latency_ms: int,
) -> BoardNarrative:
    """Parse CIO LLM response into BoardNarrative."""
    data = _extract_json(resp.content)
    if data is None:
        logger.warning("CIO response not valid JSON, using fallback: %s...", resp.content[:200])
        return _fallback_narrative(verdict, board_result, latency_ms)

    # Build consensus summary
    endorsing = sum(
        1 for op in board_result.opinions if op.vote == BoardVote.APPROVE
    )
    dissenting = len(board_result.opinions) - endorsing
    key_dissents = [
        f"{op.display_name}: {op.key_concern}"
        for op in board_result.opinions
        if op.vote in (BoardVote.VETO, BoardVote.ADJUST_DOWN) and op.key_concern
    ]

    # Validate verdict adjustment
    adjustment = data.get("verdict_adjustment", 0)
    adjusted = data.get("adjusted_verdict")
    if adjustment != 0:
        # CIO can only break ties, not override clear majorities
        if board_result.veto_count >= 3:
            adjustment = 0
            adjusted = None
        # CIO cannot upgrade past STRONG_BUY or downgrade past AVOID
        if adjusted and adjusted not in (
            "STRONG_BUY", "BUY", "ACCUMULATE", "HOLD", "WATCHLIST",
            "REDUCE", "SELL", "AVOID", "DISCARD",
        ):
            adjustment = 0
            adjusted = None

    return BoardNarrative(
        headline=data.get("headline", "Board review complete"),
        narrative=data.get("narrative", ""),
        risk_summary=data.get("risk_summary", "No specific risks identified"),
        pre_mortem=data.get("pre_mortem", ""),
        conflict_resolution=data.get("conflict_resolution", ""),
        verdict_adjustment=adjustment,
        adjusted_verdict=adjusted if adjustment != 0 else None,
        advisor_consensus={
            "endorsing": endorsing,
            "dissenting": dissenting,
            "total": len(board_result.opinions),
            "key_dissents": key_dissents[:3],
        },
        model=resp.model,
        latency_ms=latency_ms,
    )


def _fallback_narrative(
    verdict: VerdictResult,
    board_result: BoardResult,
    latency_ms: int,
) -> BoardNarrative:
    """Generate a basic narrative when CIO LLM call fails."""
    total = len(board_result.opinions)
    approvals = sum(1 for op in board_result.opinions if op.vote == BoardVote.APPROVE)
    vetoes = board_result.veto_count

    effective = board_result.adjusted_verdict or board_result.original_verdict

    headline = f"{effective} — {approvals}/{total} advisors approve"
    if vetoes > 0:
        headline += f", {vetoes} veto(s)"

    concerns = [op.key_concern for op in board_result.opinions if op.key_concern]
    risk_summary = "; ".join(concerns[:3]) if concerns else "See individual advisor opinions"

    return BoardNarrative(
        headline=headline,
        narrative=f"The advisory board reviewed the {board_result.original_verdict} verdict. "
                  f"{approvals} of {total} advisors approved the recommendation.",
        risk_summary=risk_summary,
        pre_mortem="CIO narrative unavailable — see individual advisor opinions for detail.",
        conflict_resolution="Automated fallback — individual opinions available.",
        advisor_consensus={
            "endorsing": approvals,
            "dissenting": total - approvals,
            "total": total,
        },
        model="fallback",
        latency_ms=latency_ms,
    )
