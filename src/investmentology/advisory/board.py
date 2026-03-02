"""Advisory Board (L5.5) — 8 legendary investor personas review the L5 verdict.

Each pair of advisors shares one LLM call but produces independent opinions.
Pairs are chosen for complementary tension. All 4 calls run concurrently.

The board VOTES — this is the primary decision mechanism. The CIO (L6)
narrates the vote outcome but does NOT override it.

Vote synthesis (pure Python):
  - 3+ VETOs → cap verdict at WATCHLIST (hard override)
  - 5+ ADJUST_UP → shift verdict up one level
  - 5+ ADJUST_DOWN → shift verdict down one level
  - Otherwise → verdict stands (APPROVE by default)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from decimal import Decimal

from investmentology.advisory.models import (
    AdvisorOpinion,
    AdvisorSpec,
    BoardResult,
    BoardVote,
)
from investmentology.agents.gateway import LLMGateway, LLMResponse
from investmentology.verdict import AgentStance, Verdict, VerdictResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 8 Board Members — distinct investment philosophies
# ---------------------------------------------------------------------------

BOARD_MEMBERS: dict[str, AdvisorSpec] = {
    "dalio": AdvisorSpec(
        key="dalio",
        display_name="Ray Dalio",
        philosophy=(
            "You think in terms of the economic machine — debt cycles, productivity, "
            "and the balance of payments. You stress-test every thesis against regime "
            "changes and believe in radical diversification across uncorrelated return "
            "streams. Your All Weather framework demands investments work across "
            "growth/inflation regimes."
        ),
        data_focus=(
            "Debt-to-GDP trends, real interest rates, credit spreads, currency dynamics, "
            "central bank policy, productivity metrics, current account balances."
        ),
        evaluation_criteria=(
            "Does this investment work in ALL weather conditions — rising/falling growth "
            "AND rising/falling inflation? What happens if the debt cycle turns? "
            "How correlated is this to existing portfolio risks?"
        ),
        bias_warning=(
            "You tend to over-weight macro factors and can miss company-specific catalysts. "
            "You sometimes see regime changes that aren't happening."
        ),
        vote_tendency=(
            "VETO when macro regime makes the entire sector uninvestable. "
            "ADJUST_DOWN when late-cycle indicators flash but company is otherwise strong. "
            "APPROVE when thesis works across multiple economic scenarios."
        ),
        signature_question="Does this work in ALL weather conditions, or only the current one?",
    ),
    "lynch": AdvisorSpec(
        key="lynch",
        display_name="Peter Lynch",
        philosophy=(
            "You classify every company: Slow Grower, Stalwart, Fast Grower, Cyclical, "
            "Turnaround, or Asset Play. Each category has different buy/sell criteria. "
            "You believe in investing in what you understand — if you can't explain the "
            "thesis to a 12-year-old in 2 minutes, it's too complex. PEG ratio is your "
            "north star for growth stocks."
        ),
        data_focus=(
            "Revenue growth rate, PEG ratio, inventory trends, cash position relative "
            "to debt, institutional ownership %, insider buying/selling, "
            "the 'story' — what does this company actually do?"
        ),
        evaluation_criteria=(
            "What category does this company fall into? Is the PEG < 1 for growth? "
            "For turnarounds, has the balance sheet improved? For cyclicals, "
            "are we buying at the right point in the cycle? Can I explain this simply?"
        ),
        bias_warning=(
            "You tend to favor simple, understandable businesses and may miss "
            "complex technology companies with real competitive advantages. "
            "You can be too dismissive of high-multiple stocks."
        ),
        vote_tendency=(
            "VETO when the thesis is too complex to explain simply. "
            "ADJUST_UP for underfollowed fast growers with PEG < 1. "
            "ADJUST_DOWN for stalwarts trading above fair value."
        ),
        signature_question="What's the story here, and is it simple enough?",
    ),
    "druckenmiller": AdvisorSpec(
        key="druckenmiller",
        display_name="Stanley Druckenmiller",
        philosophy=(
            "You size positions based on conviction — when you see asymmetry, you bet big. "
            "You look for 3:1+ risk/reward and near-term catalysts that can unlock value. "
            "The biggest mistake is not being wrong, it's being right and not betting enough. "
            "You combine top-down macro with bottom-up stock picking."
        ),
        data_focus=(
            "Risk/reward asymmetry, upcoming catalysts (earnings, FDA approvals, "
            "management changes), relative value vs peers, short interest, "
            "position sizing implications, momentum + macro alignment."
        ),
        evaluation_criteria=(
            "Is the risk/reward skewed at least 3:1? What's the catalyst that "
            "will move the stock in the next 3-6 months? How big should the "
            "position be relative to conviction? Is the broader macro supportive?"
        ),
        bias_warning=(
            "You tend toward aggressive sizing and can concentrate too heavily. "
            "You may overvalue near-term catalysts at the expense of longer-term risks. "
            "Your macro overlay can make you too bullish in bull markets."
        ),
        vote_tendency=(
            "ADJUST_UP when risk/reward is highly asymmetric with clear catalyst. "
            "APPROVE for solid setups with reasonable sizing. "
            "ADJUST_DOWN when risk/reward is symmetric or unclear."
        ),
        signature_question="Is the risk/reward skewed enough, and what's the catalyst?",
    ),
    "klarman": AdvisorSpec(
        key="klarman",
        display_name="Seth Klarman",
        philosophy=(
            "You are the most patient investor alive. You demand a 30%+ margin of safety "
            "and always model the bear case with specific price targets. You'd rather miss "
            "an opportunity than overpay. Cash is a perfectly acceptable position. "
            "You focus on absolute value, not relative value."
        ),
        data_focus=(
            "Downside scenarios with specific prices, margin of safety calculation, "
            "liquidation value, free cash flow yield, insider alignment, "
            "catalyst for value realization, historical valuation range."
        ),
        evaluation_criteria=(
            "What is the bear case price? Is the margin of safety at least 30%? "
            "What is the downside if the thesis is completely wrong? "
            "Is there a catalyst to close the value gap, or is this a value trap?"
        ),
        bias_warning=(
            "You can be too conservative and miss multi-baggers by demanding "
            "excessive margin of safety. Your patience can look like paralysis. "
            "You may undervalue growth and quality premiums."
        ),
        vote_tendency=(
            "VETO when margin of safety is < 15%. "
            "ADJUST_DOWN when margin of safety is 15-30%. "
            "APPROVE only when margin of safety exceeds 30%."
        ),
        signature_question="How much can I lose, and is the margin of safety wide enough?",
    ),
    "munger": AdvisorSpec(
        key="munger",
        display_name="Charlie Munger",
        philosophy=(
            "You use mental models from multiple disciplines — psychology, physics, "
            "biology, mathematics. You practice inversion: 'Tell me where I'll die, "
            "so I won't go there.' You focus on avoiding stupidity over seeking "
            "brilliance. Quality businesses at fair prices beat cheap businesses every time."
        ),
        data_focus=(
            "Competitive moat durability, management quality and incentive alignment, "
            "cognitive biases in the analysis, capital allocation track record, "
            "return on equity trends, industry structure (Porter's forces)."
        ),
        evaluation_criteria=(
            "What would make this a terrible investment? (Inversion) "
            "What cognitive biases might be affecting the other agents' analysis? "
            "Is this a wonderful business at a fair price, or a fair business at a "
            "wonderful price? Is management allocating capital wisely?"
        ),
        bias_warning=(
            "You can be too focused on finding flaws and miss good opportunities. "
            "Your contrarian instinct can make you reflexively skeptical. "
            "You may over-index on qualitative factors like 'management quality.'"
        ),
        vote_tendency=(
            "VETO when you detect clear cognitive bias driving the bullish thesis. "
            "ADJUST_DOWN when you see one or two red flags worth noting. "
            "APPROVE when the thesis survives inversion analysis."
        ),
        signature_question="What would make this a terrible investment? Invert, always invert.",
    ),
    "williams": AdvisorSpec(
        key="williams",
        display_name="John Burr Williams",
        philosophy=(
            "You are the father of fundamental analysis. Every stock is worth the "
            "present value of all future cash flows, period. You insist on rigorous "
            "DCF with explicit discount rates, growth assumptions, and terminal value. "
            "Narrative is irrelevant — only the numbers matter."
        ),
        data_focus=(
            "Free cash flow history and projections, WACC components, growth rate "
            "assumptions (near-term vs terminal), reinvestment rate, return on "
            "invested capital, dividend discount model inputs, payout ratios."
        ),
        evaluation_criteria=(
            "What is the intrinsic value based on a 10-year DCF? What discount "
            "rate is appropriate? What growth rate is priced in, and is it achievable? "
            "What does the stock need to deliver to justify the current price?"
        ),
        bias_warning=(
            "You rely heavily on assumptions that may be wrong (growth rates, "
            "discount rates). You can give false precision. You may undervalue "
            "optionality and strategic value that doesn't show in cash flows."
        ),
        vote_tendency=(
            "ADJUST_UP when DCF shows 40%+ upside to intrinsic value. "
            "VETO when stock is 20%+ above intrinsic value with generous assumptions. "
            "APPROVE when current price is at or below fair value."
        ),
        signature_question=(
            "What is the intrinsic value based on discounted cash flows, "
            "and at what discount rate?"
        ),
    ),
    "soros": AdvisorSpec(
        key="soros",
        display_name="George Soros",
        philosophy=(
            "Markets are reflexive — prices change fundamentals, not just the reverse. "
            "You look for where the prevailing narrative diverges from reality, "
            "creating boom-bust dynamics. Perception shapes reality, which in turn "
            "shapes perception. The key is identifying inflection points in this cycle."
        ),
        data_focus=(
            "Market narrative vs fundamental reality, reflexive feedback loops, "
            "positioning data (COT, options flow), credit conditions, "
            "sentiment extremes, geopolitical catalysts, regime transitions."
        ),
        evaluation_criteria=(
            "Is the market narrative self-reinforcing or about to break? "
            "Are we in the early stage of a boom (buy), late stage (be cautious), "
            "or approaching the bust inflection (sell)? What could trigger the "
            "narrative reversal?"
        ),
        bias_warning=(
            "You can see reflexive dynamics everywhere, even when markets are "
            "efficiently priced. You may be too focused on short-term narrative "
            "shifts and miss long-term value creation."
        ),
        vote_tendency=(
            "VETO when narrative is clearly unsustainable and bust is imminent. "
            "ADJUST_DOWN when late-cycle dynamics are building. "
            "ADJUST_UP when early-stage boom with strong reflexive feedback."
        ),
        signature_question="Is the market narrative self-reinforcing or about to break?",
    ),
    "simons": AdvisorSpec(
        key="simons",
        display_name="Jim Simons",
        philosophy=(
            "You trust data over stories. Statistical edges, mean reversion setups, "
            "and regime-dependent patterns are what matter. Qualitative narratives are "
            "noise — only systematic, measurable signals deserve weight. "
            "The edge is in the data, not the story."
        ),
        data_focus=(
            "Price momentum and mean reversion signals, volume patterns, volatility "
            "regime, sector relative strength, statistical anomalies, "
            "correlation structure, seasonal patterns, options implied probabilities."
        ),
        evaluation_criteria=(
            "What does the statistical evidence actually say? Are the technical "
            "signals aligned with the fundamental thesis? Is there quantifiable "
            "edge, or just a compelling narrative? What is the probability of "
            "the bullish/bearish scenario based on historical analogues?"
        ),
        bias_warning=(
            "You can be too dismissive of qualitative factors that matter "
            "(management quality, competitive dynamics). Historical patterns "
            "don't always repeat. You may miss structural breaks."
        ),
        vote_tendency=(
            "ADJUST_DOWN when technicals diverge from fundamental thesis (bearish divergence). "
            "ADJUST_UP when technical and fundamental signals align strongly. "
            "APPROVE when data supports the thesis direction."
        ),
        signature_question="What does the statistical evidence actually say, stripped of narrative?",
    ),
}


# ---------------------------------------------------------------------------
# Pair Configuration — 4 pairs, 4 concurrent LLM calls
# ---------------------------------------------------------------------------

PAIR_CONFIG: list[dict] = [
    {
        "members": ("soros", "druckenmiller"),
        "theme": "Macro Conviction",
        "providers": ["remote-board-gemini", "gemini-cli", "deepseek"],  # preference order
    },
    {
        "members": ("munger", "klarman"),
        "theme": "Value Discipline",
        "providers": ["remote-board-claude", "claude-cli", "deepseek"],
    },
    {
        "members": ("dalio", "williams"),
        "theme": "Portfolio Theory & DCF",
        "providers": ["deepseek"],
    },
    {
        "members": ("lynch", "simons"),
        "theme": "Growth & Quantitative",
        "providers": ["groq"],
    },
]


# Verdict ordering for shift operations
_VERDICT_LADDER = [
    "AVOID", "DISCARD", "SELL", "REDUCE", "WATCHLIST",
    "HOLD", "ACCUMULATE", "BUY", "STRONG_BUY",
]


class AdvisoryBoard:
    """Convenes 8 advisory board members to review the L5 verdict.

    Uses paired prompts (2 advisors per LLM call, 4 calls total) for
    cost efficiency while preserving distinct perspectives.
    """

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def convene(
        self,
        verdict: VerdictResult,
        stances: list[AgentStance],
        adversarial: object | None,
        request: object,
        fundamentals: object | None = None,
    ) -> BoardResult:
        """Run the full advisory board review.

        Args:
            verdict: The L5 verdict to review.
            stances: All agent stances from L3.
            adversarial: AdversarialResult from L4 (if any).
            request: AnalysisRequest with full context.
            fundamentals: FundamentalsSnapshot for the ticker.
        """
        start_time = time.monotonic()

        # Build the shared user prompt (same for all pairs)
        user_prompt = _build_user_prompt(verdict, stances, adversarial, request, fundamentals)

        # Launch all 4 pairs concurrently
        tasks = []
        for pair_cfg in PAIR_CONFIG:
            member_a_key, member_b_key = pair_cfg["members"]
            member_a = BOARD_MEMBERS[member_a_key]
            member_b = BOARD_MEMBERS[member_b_key]
            system_prompt = _build_system_prompt(member_a, member_b, pair_cfg["theme"])
            providers = pair_cfg["providers"]
            tasks.append(
                self._call_pair(system_prompt, user_prompt, member_a, member_b, providers)
            )

        # Gather results (failures return empty lists)
        pair_results = await asyncio.gather(*tasks, return_exceptions=True)

        opinions: list[AdvisorOpinion] = []
        for i, result in enumerate(pair_results):
            if isinstance(result, Exception):
                pair_members = PAIR_CONFIG[i]["members"]
                logger.warning(
                    "Advisory pair %s failed: %s", pair_members, result,
                )
                continue
            opinions.extend(result)

        total_ms = int((time.monotonic() - start_time) * 1000)

        # Synthesize vote outcome (pure Python, deterministic)
        return _synthesize_votes(verdict.verdict.value, opinions, total_ms)

    async def _call_pair(
        self,
        system_prompt: str,
        user_prompt: str,
        member_a: AdvisorSpec,
        member_b: AdvisorSpec,
        providers: list[str],
    ) -> list[AdvisorOpinion]:
        """Call one pair of advisors via the LLM gateway.

        Tries providers in preference order until one succeeds.
        """
        last_error: Exception | None = None
        for provider in providers:
            try:
                resp = await self._gateway.call(
                    provider=provider,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=4096,
                    temperature=0.4,
                )
                return _parse_pair_response(resp, member_a, member_b)
            except Exception as e:
                last_error = e
                logger.debug(
                    "Provider %s failed for pair (%s, %s): %s",
                    provider, member_a.key, member_b.key, e,
                )

        raise RuntimeError(
            f"All providers failed for pair ({member_a.key}, {member_b.key}): {last_error}"
        )


# ---------------------------------------------------------------------------
# Prompt Builders
# ---------------------------------------------------------------------------

def _build_system_prompt(member_a: AdvisorSpec, member_b: AdvisorSpec, theme: str) -> str:
    """Build the system prompt for a paired advisory call."""
    return f"""You are two senior investment advisors on an advisory board reviewing an investment verdict. You must each provide an INDEPENDENT opinion — you may disagree with each other.

## Board Member 1: {member_a.display_name}
Philosophy: {member_a.philosophy}
Data Focus: {member_a.data_focus}
Evaluation Criteria: {member_a.evaluation_criteria}
Bias Warning: {member_a.bias_warning}
Signature Question: "{member_a.signature_question}"

## Board Member 2: {member_b.display_name}
Philosophy: {member_b.philosophy}
Data Focus: {member_b.data_focus}
Evaluation Criteria: {member_b.evaluation_criteria}
Bias Warning: {member_b.bias_warning}
Signature Question: "{member_b.signature_question}"

## Theme: {theme}

## Instructions
Review the verdict and agent analysis below. Each advisor must:
1. Answer their signature question
2. Vote: APPROVE (agree), ADJUST_UP (should be more bullish), ADJUST_DOWN (should be more bearish), or VETO (fundamentally disagree)
3. Provide confidence (0.0-1.0), a 1-sentence assessment, key concern, key endorsement, and 2-3 sentences of reasoning

You MUST reason independently for each advisor based on their distinct philosophy. They can and should disagree when their frameworks lead to different conclusions.

Respond with ONLY valid JSON (no markdown fences, no commentary):
{{
    "{member_a.key}": {{
        "vote": "APPROVE|ADJUST_UP|ADJUST_DOWN|VETO",
        "confidence": 0.75,
        "assessment": "One sentence headline",
        "key_concern": "Specific risk or null",
        "key_endorsement": "Specific positive or null",
        "reasoning": "2-3 sentences from this advisor's unique lens"
    }},
    "{member_b.key}": {{
        "vote": "APPROVE|ADJUST_UP|ADJUST_DOWN|VETO",
        "confidence": 0.75,
        "assessment": "One sentence headline",
        "key_concern": "Specific risk or null",
        "key_endorsement": "Specific positive or null",
        "reasoning": "2-3 sentences from this advisor's unique lens"
    }}
}}"""


def _build_user_prompt(
    verdict: VerdictResult,
    stances: list[AgentStance],
    adversarial: object | None,
    request: object,
    fundamentals: object | None,
) -> str:
    """Build the shared user prompt with all analysis context."""
    parts: list[str] = []

    # Ticker + Verdict
    ticker = getattr(request, "ticker", "UNKNOWN")
    parts.append(f"## Ticker: {ticker}")
    parts.append(f"## L5 Verdict: {verdict.verdict.value}")
    parts.append(f"Consensus Score: {verdict.consensus_score:.3f}")
    parts.append(f"Confidence: {float(verdict.confidence):.0%}")
    if verdict.regime_label:
        parts.append(f"Market Regime: {verdict.regime_label}")

    # Agent Stances
    parts.append("\n## Agent Stances (L3)")
    for s in stances:
        direction = "BULLISH" if s.sentiment > 0.1 else "BEARISH" if s.sentiment < -0.1 else "NEUTRAL"
        parts.append(
            f"- **{s.name.capitalize()}**: {direction} (sentiment={s.sentiment:.2f}, "
            f"confidence={float(s.confidence):.0%})"
        )
        if s.key_signals:
            parts.append(f"  Key signals: {', '.join(s.key_signals)}")
        if s.summary:
            # Truncate long summaries
            summary = s.summary[:300] + "..." if len(s.summary) > 300 else s.summary
            parts.append(f"  Summary: {summary}")

    # Adversarial Results
    if adversarial:
        parts.append("\n## Adversarial Review (Munger)")
        adv_verdict = getattr(adversarial, "verdict", None)
        if adv_verdict:
            parts.append(f"Verdict: {adv_verdict.value if hasattr(adv_verdict, 'value') else adv_verdict}")
        bias_flags = getattr(adversarial, "bias_flags", [])
        if bias_flags:
            flag_strs = [getattr(b, "bias_type", str(b)) for b in bias_flags[:5]]
            parts.append(f"Bias Flags: {', '.join(flag_strs)}")
        adv_reasoning = getattr(adversarial, "reasoning", "")
        if adv_reasoning:
            parts.append(f"Reasoning: {adv_reasoning[:400]}")

    # Risk Flags
    if verdict.risk_flags:
        parts.append(f"\n## Risk Flags: {'; '.join(verdict.risk_flags[:5])}")

    # Overrides
    if verdict.auditor_override:
        parts.append("## AUDITOR OVERRIDE ACTIVE — verdict was capped due to risk flags")
    if verdict.munger_override:
        parts.append("## MUNGER VETO ACTIVE — adversarial review vetoed the trade")

    # Fundamentals (if available)
    if fundamentals:
        parts.append("\n## Fundamentals")
        mcap = getattr(fundamentals, "market_cap", None)
        if mcap:
            parts.append(f"Market Cap: ${float(mcap):,.0f}")
        rev = getattr(fundamentals, "revenue", None)
        if rev:
            parts.append(f"Revenue: ${float(rev):,.0f}")
        ni = getattr(fundamentals, "net_income", None)
        if ni:
            parts.append(f"Net Income: ${float(ni):,.0f}")
        price = getattr(fundamentals, "price", None)
        if price:
            parts.append(f"Price: ${float(price):,.2f}")
        ey = getattr(fundamentals, "earnings_yield", None)
        if ey:
            parts.append(f"Earnings Yield: {float(ey):.1%}")
        roic = getattr(fundamentals, "roic", None)
        if roic:
            parts.append(f"ROIC: {float(roic):.1%}")

    # Thesis context (if held position)
    pos_thesis = getattr(request, "position_thesis", None)
    if pos_thesis and isinstance(pos_thesis, str):
        parts.append(f"\n## Position Context")
        parts.append(f"Original Thesis: {pos_thesis[:300]}")
        pos_type = getattr(request, "position_type", None)
        if pos_type and isinstance(pos_type, str):
            parts.append(f"Position Type: {pos_type}")
        days = getattr(request, "days_held", None)
        if isinstance(days, (int, float)):
            parts.append(f"Days Held: {days}")
        entry = getattr(request, "entry_price", None)
        if isinstance(entry, (int, float)):
            parts.append(f"Entry Price: ${entry:.2f}")
        pnl = getattr(request, "pnl_pct", None)
        if isinstance(pnl, (int, float)):
            parts.append(f"P&L: {pnl:+.1f}%")

    # Macro context
    macro = getattr(request, "macro_context", None)
    if macro and isinstance(macro, dict):
        parts.append("\n## Macro Context")
        for k, v in list(macro.items())[:8]:
            parts.append(f"- {k}: {v}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Response Parsing
# ---------------------------------------------------------------------------

def _parse_pair_response(
    resp: LLMResponse,
    member_a: AdvisorSpec,
    member_b: AdvisorSpec,
) -> list[AdvisorOpinion]:
    """Parse the paired LLM response into individual opinions."""
    raw = resp.content.strip()

    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
    raw = re.sub(r"\n?```\s*$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse advisory pair response as JSON: %s...", raw[:200])
        # Return empty — graceful degradation
        return []

    opinions = []
    for member in [member_a, member_b]:
        member_data = data.get(member.key)
        if not member_data:
            logger.warning("Missing key '%s' in advisory response", member.key)
            continue

        try:
            vote_str = member_data.get("vote", "APPROVE").upper()
            vote = BoardVote(vote_str) if vote_str in BoardVote.__members__ else BoardVote.APPROVE

            confidence_raw = member_data.get("confidence", 0.5)
            confidence = Decimal(str(min(1.0, max(0.0, float(confidence_raw)))))

            opinions.append(AdvisorOpinion(
                advisor_name=member.key,
                display_name=member.display_name,
                vote=vote,
                confidence=confidence,
                assessment=member_data.get("assessment", "No assessment provided"),
                key_concern=member_data.get("key_concern"),
                key_endorsement=member_data.get("key_endorsement"),
                reasoning=member_data.get("reasoning", ""),
                model=resp.model,
                latency_ms=resp.latency_ms,
            ))
        except Exception:
            logger.warning("Failed to parse opinion for %s", member.key, exc_info=True)

    return opinions


# ---------------------------------------------------------------------------
# Vote Synthesis (deterministic Python)
# ---------------------------------------------------------------------------

def _synthesize_votes(
    original_verdict: str,
    opinions: list[AdvisorOpinion],
    total_latency_ms: int,
) -> BoardResult:
    """Aggregate 8 advisory votes into a board decision.

    Rules:
      - 3+ VETOs → cap verdict at WATCHLIST
      - 5+ ADJUST_UP → shift verdict up one level
      - 5+ ADJUST_DOWN → shift verdict down one level
      - Otherwise → verdict stands
    """
    vote_counts: dict[str, int] = {v.value: 0 for v in BoardVote}
    for op in opinions:
        vote_counts[op.vote.value] = vote_counts.get(op.vote.value, 0) + 1

    veto_count = vote_counts.get("VETO", 0)
    adjust_up_count = vote_counts.get("ADJUST_UP", 0)
    adjust_down_count = vote_counts.get("ADJUST_DOWN", 0)

    adjusted_verdict: str | None = None

    # Hard override: 3+ VETOs
    if veto_count >= 3:
        current_idx = _verdict_index(original_verdict)
        watchlist_idx = _verdict_index("WATCHLIST")
        if current_idx > watchlist_idx:
            adjusted_verdict = "WATCHLIST"
            logger.info(
                "Board veto override: %d VETOs, capping %s → WATCHLIST",
                veto_count, original_verdict,
            )
    # Majority shift up
    elif adjust_up_count >= 5:
        shifted = _shift_verdict(original_verdict, +1)
        if shifted and shifted != original_verdict:
            adjusted_verdict = shifted
            logger.info(
                "Board shift up: %d ADJUST_UP votes, %s → %s",
                adjust_up_count, original_verdict, shifted,
            )
    # Majority shift down
    elif adjust_down_count >= 5:
        shifted = _shift_verdict(original_verdict, -1)
        if shifted and shifted != original_verdict:
            adjusted_verdict = shifted
            logger.info(
                "Board shift down: %d ADJUST_DOWN votes, %s → %s",
                adjust_down_count, original_verdict, shifted,
            )

    return BoardResult(
        opinions=opinions,
        original_verdict=original_verdict,
        adjusted_verdict=adjusted_verdict,
        vote_counts=vote_counts,
        veto_count=veto_count,
        total_latency_ms=total_latency_ms,
    )


def _verdict_index(verdict: str) -> int:
    """Get the position of a verdict in the ladder."""
    try:
        return _VERDICT_LADDER.index(verdict)
    except ValueError:
        return 4  # Default to WATCHLIST position


def _shift_verdict(verdict: str, direction: int) -> str | None:
    """Shift a verdict up (+1) or down (-1) on the ladder.

    Returns None if already at the boundary.
    """
    idx = _verdict_index(verdict)
    new_idx = idx + direction
    if 0 <= new_idx < len(_VERDICT_LADDER):
        return _VERDICT_LADDER[new_idx]
    return None
