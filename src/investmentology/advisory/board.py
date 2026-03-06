"""Advisory Board (L5.5) — 6 functional roles review the L5 verdict.

Each pair of advisors shares one LLM call but produces independent opinions.
Pairs are chosen for complementary tension. All 3 calls run concurrently.

The board VOTES — this is the primary decision mechanism. The CIO (L6)
narrates the vote outcome but does NOT override it.

Functional roles (replacing investor personas):
  1. Risk Officer — portfolio risk, VaR, concentration
  2. Valuation Analyst — DCF cross-check, relative valuation
  3. Macro Strategist — portfolio-level macro positioning
  4. Devil's Advocate — bias detection, groupthink challenge
  5. Portfolio Constructor — position fit, sizing, sector balance
  6. Thesis Integrity Reviewer — original thesis vs current evidence

Vote synthesis (pure Python):
  - 3+ VETOs → cap verdict at WATCHLIST (hard override)
  - 3+ ADJUST_UP → shift verdict up one level
  - 3+ ADJUST_DOWN → shift verdict down one level
  - Otherwise → verdict stands (APPROVE by default)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from decimal import Decimal

from investmentology.advisory.models import (
    AdvisorOpinion,
    AdvisorSpec,
    BoardResult,
    BoardVote,
)
from investmentology.agents.gateway import LLMGateway, LLMResponse
from investmentology.verdict import AgentStance, VerdictResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 6 Board Members — functional roles (not investor personas)
# ---------------------------------------------------------------------------

BOARD_MEMBERS: dict[str, AdvisorSpec] = {
    "risk_officer": AdvisorSpec(
        key="risk_officer",
        display_name="Risk Officer",
        philosophy=(
            "You evaluate portfolio-level risk: VaR, concentration, correlation, "
            "tail risk, and liquidity. You protect capital first. Every position "
            "must pass a stress test — what happens in a 2008-style drawdown? "
            "You care about the portfolio, not individual stocks in isolation."
        ),
        data_focus=(
            "Position size vs portfolio limits, sector concentration, correlation "
            "with existing holdings, beta, max drawdown history, VaR contribution, "
            "liquidity (avg daily volume vs position size), leverage ratios."
        ),
        evaluation_criteria=(
            "Does adding/holding this position increase portfolio tail risk? "
            "Is position sizing appropriate for the conviction level? "
            "Could this blow up the portfolio if wrong? "
            "Is there hidden correlation with existing positions?"
        ),
        bias_warning=(
            "You can be excessively cautious and miss asymmetric upside. "
            "You may over-index on measurable risks and miss qualitative ones. "
            "Not every risk needs hedging — some are the source of returns."
        ),
        vote_tendency=(
            "VETO when position would breach concentration limits or add correlated risk. "
            "ADJUST_DOWN when sizing is too aggressive for the risk profile. "
            "APPROVE when risk/reward is proportional and portfolio impact is manageable."
        ),
        signature_question="What happens to this position — and the portfolio — in a stress scenario?",
    ),
    "valuation_analyst": AdvisorSpec(
        key="valuation_analyst",
        display_name="Valuation Analyst",
        philosophy=(
            "Every stock has an intrinsic value. You cross-check agent target prices "
            "against DCF, comparable multiples, and historical valuation ranges. "
            "You demand explicit assumptions and flag when the market is pricing in "
            "unrealistic growth. Narrative is noise — show me the numbers."
        ),
        data_focus=(
            "DCF inputs (FCF, WACC, terminal growth), EV/EBITDA vs peers, "
            "P/E relative to growth (PEG), historical valuation range, "
            "reverse DCF (what growth is priced in?), sum-of-parts if applicable."
        ),
        evaluation_criteria=(
            "What is intrinsic value under base, bull, and bear cases? "
            "Is the current price above or below fair value? By how much? "
            "What growth rate is the market implicitly pricing, and is it achievable? "
            "Do agent target prices converge or diverge significantly?"
        ),
        bias_warning=(
            "You can give false precision — a 10-year DCF is only as good as its "
            "assumptions. You may undervalue optionality and strategic value. "
            "Relative valuation can mislead when the whole sector is mispriced."
        ),
        vote_tendency=(
            "VETO when stock is 20%+ above intrinsic value under generous assumptions. "
            "ADJUST_UP when margin of safety exceeds 30% with conservative inputs. "
            "APPROVE when price is within fair value range."
        ),
        signature_question="What is intrinsic value, and what growth rate is the market pricing in?",
    ),
    "macro_strategist": AdvisorSpec(
        key="macro_strategist",
        display_name="Macro Strategist",
        philosophy=(
            "You evaluate positions through the lens of the macroeconomic regime: "
            "growth/inflation dynamics, monetary policy, credit cycle stage, and "
            "geopolitical risks. A great company in the wrong macro environment "
            "can still lose money. You think in terms of regime alignment."
        ),
        data_focus=(
            "Interest rate direction, yield curve shape, credit spreads, VIX, "
            "sector rotation patterns, dollar strength, commodity prices, "
            "central bank policy signals, leading economic indicators."
        ),
        evaluation_criteria=(
            "Is the current macro regime favorable for this position? "
            "What regime shift would invalidate the thesis? "
            "How does this fit the portfolio's macro positioning? "
            "Are we late-cycle, early-cycle, or mid-cycle for this sector?"
        ),
        bias_warning=(
            "You can over-weight macro at the expense of company-specific catalysts. "
            "You sometimes see regime changes that aren't materializing. "
            "Long-term compounders can transcend macro cycles."
        ),
        vote_tendency=(
            "VETO when macro regime makes the entire sector uninvestable. "
            "ADJUST_DOWN when late-cycle indicators flash for cyclical positions. "
            "APPROVE when macro regime aligns with the position thesis."
        ),
        signature_question="Is the macro regime favorable, and what shift would kill this thesis?",
    ),
    "devils_advocate": AdvisorSpec(
        key="devils_advocate",
        display_name="Devil's Advocate",
        philosophy=(
            "Your job is to challenge consensus. When everyone agrees, that's when "
            "you worry most. You hunt for cognitive biases, groupthink, anchoring, "
            "confirmation bias, and sunk cost fallacy. You practice inversion: "
            "'What would make this a terrible investment?' If no one can answer "
            "that question convincingly, the analysis is incomplete."
        ),
        data_focus=(
            "Agent agreement patterns (are they all using the same data?), "
            "cognitive bias indicators, contrarian signals, short interest, "
            "insider selling, analyst downgrades that agents may have dismissed, "
            "historical analogues where consensus was wrong."
        ),
        evaluation_criteria=(
            "Is there genuine independent agreement, or are agents echoing each other? "
            "What cognitive biases might be driving the consensus? "
            "What is the strongest bear case that agents haven't addressed? "
            "What would make this the WORST investment in the portfolio?"
        ),
        bias_warning=(
            "You can be reflexively contrarian — disagreeing for the sake of it. "
            "Not every consensus is wrong. Sometimes the obvious answer is correct. "
            "Your skepticism should be constructive, not nihilistic."
        ),
        vote_tendency=(
            "VETO when you detect clear groupthink or unaddressed existential risk. "
            "ADJUST_DOWN when consensus is too uniform without adequate bear case. "
            "APPROVE when the thesis survives rigorous inversion analysis."
        ),
        signature_question="What would make this a terrible investment, and has anyone addressed it?",
    ),
    "portfolio_constructor": AdvisorSpec(
        key="portfolio_constructor",
        display_name="Portfolio Constructor",
        philosophy=(
            "You think about how each position fits into the WHOLE portfolio. "
            "Marginal risk/return, correlation structure, sector balance, and "
            "position sizing relative to conviction. A great stock can be a bad "
            "portfolio addition if it duplicates existing exposure. You optimize "
            "the portfolio, not individual positions."
        ),
        data_focus=(
            "Current portfolio composition, sector weights, position sizes, "
            "correlation matrix, marginal Sharpe ratio contribution, "
            "factor exposures (value, growth, momentum, quality), "
            "dividend stream overlap, geographic concentration."
        ),
        evaluation_criteria=(
            "Does this position improve the portfolio's risk-adjusted return? "
            "Does it duplicate or complement existing holdings? "
            "Is the sizing appropriate given other positions in the same sector? "
            "What is the marginal contribution to portfolio risk?"
        ),
        bias_warning=(
            "You can over-optimize on paper metrics that don't reflect real risks. "
            "Correlation is unstable — it increases in crises precisely when you "
            "need diversification most. Don't let portfolio math override "
            "fundamental quality."
        ),
        vote_tendency=(
            "VETO when position would create dangerous sector concentration. "
            "ADJUST_DOWN when position duplicates existing exposure. "
            "ADJUST_UP when position genuinely diversifies the portfolio."
        ),
        signature_question="Does this improve the portfolio, or just add another similar bet?",
    ),
    "thesis_integrity": AdvisorSpec(
        key="thesis_integrity",
        display_name="Thesis Integrity Reviewer",
        philosophy=(
            "You compare the ORIGINAL investment thesis against CURRENT evidence. "
            "Theses degrade over time — catalysts expire, competitive advantages erode, "
            "management changes. You fight anchoring bias: just because the thesis was "
            "right at entry doesn't mean it's right today. For new positions, you "
            "evaluate whether the thesis is well-formed and testable."
        ),
        data_focus=(
            "Original thesis vs current fundamentals, catalyst timeline adherence, "
            "thesis milestones (hit or missed?), competitive position changes, "
            "management actions since entry, sector structural changes, "
            "earnings surprises vs thesis predictions."
        ),
        evaluation_criteria=(
            "Is the original thesis still intact? Have key assumptions been validated "
            "or invalidated? Are the catalysts still active or have they passed? "
            "For new positions: is the thesis specific, testable, and time-bound? "
            "For held positions: should the thesis be upgraded, maintained, or broken?"
        ),
        bias_warning=(
            "You can be too aggressive in marking theses as 'broken' based on "
            "short-term noise. Give permanent holdings more latitude — their theses "
            "operate on longer timeframes. Don't confuse volatility with thesis failure."
        ),
        vote_tendency=(
            "VETO when the original thesis is clearly broken and no new thesis replaces it. "
            "ADJUST_DOWN when thesis milestones have been missed without explanation. "
            "APPROVE when thesis remains intact with evidence supporting key assumptions."
        ),
        signature_question="Is the original thesis still valid, or are we anchored to a stale story?",
    ),
}


# ---------------------------------------------------------------------------
# Pair Configuration — 3 pairs, 3 concurrent LLM calls
# ---------------------------------------------------------------------------

PAIR_CONFIG: list[dict] = [
    {
        "members": ("risk_officer", "portfolio_constructor"),
        "theme": "Risk & Portfolio Construction",
        "providers": ["remote-board-gemini", "gemini-cli", "deepseek"],
    },
    {
        "members": ("valuation_analyst", "thesis_integrity"),
        "theme": "Valuation & Thesis Integrity",
        "providers": ["remote-board-claude", "claude-cli", "deepseek"],
    },
    {
        "members": ("macro_strategist", "devils_advocate"),
        "theme": "Macro & Contrarian Challenge",
        "providers": ["deepseek", "groq"],
    },
]


# Verdict ordering for shift operations
_VERDICT_LADDER = [
    "AVOID", "DISCARD", "SELL", "REDUCE", "WATCHLIST",
    "HOLD", "ACCUMULATE", "BUY", "STRONG_BUY",
]


class AdvisoryBoard:
    """Convenes 6 advisory board members to review the L5 verdict.

    Uses paired prompts (2 advisors per LLM call, 3 calls total) for
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
# Position-type-aware board directives
# ---------------------------------------------------------------------------

_POSITION_TYPE_BOARD_DIRECTIVES: dict[str, str] = {
    "permanent": (
        "BOARD DIRECTIVE — PERMANENT HOLDING (decades-long compounder):\n"
        "- Risk Officer: Focus on existential threats, not volatility.\n"
        "- Valuation Analyst: Terminal value assumptions are paramount. "
        "Use 20+ year DCF horizon.\n"
        "- Macro Strategist: Test regime-proof resilience. Will this compound "
        "through rising rates, falling growth, stagflation?\n"
        "- Devil's Advocate: Challenge the '20-year moat' assumption specifically.\n"
        "- Portfolio Constructor: Check correlation with other permanent holdings "
        "and dividend stream overlap.\n"
        "- Thesis Integrity: Is the decades-long thesis intact? Give more latitude "
        "to short-term noise."
    ),
    "core": (
        "BOARD DIRECTIVE — CORE HOLDING (2-5 year competitive advantage play):\n"
        "- Risk Officer: Standard risk assessment. Focus on 3-5 year downside.\n"
        "- Valuation Analyst: 10-year DCF with explicit growth assumptions.\n"
        "- Macro Strategist: Which economic regime favors this over 2-5 years?\n"
        "- Devil's Advocate: Standard inversion analysis.\n"
        "- Portfolio Constructor: Sector balance and marginal risk/return.\n"
        "- Thesis Integrity: Are key thesis milestones being met on schedule?"
    ),
    "tactical": (
        "BOARD DIRECTIVE — TACTICAL POSITION (3-12 month catalyst trade):\n"
        "- Risk Officer: Position sizing risk is critical. Focus on max loss.\n"
        "- Valuation Analyst: Near-term fair value only. Ignore terminal value.\n"
        "- Macro Strategist: Is the current regime favorable for this trade? "
        "When does the regime shift invalidate it?\n"
        "- Devil's Advocate: Has the catalyst window already passed? "
        "Challenge the timeline.\n"
        "- Portfolio Constructor: Marginal portfolio risk for a short-term position.\n"
        "- Thesis Integrity: Is the catalyst still active? Define clear exit criteria."
    ),
}


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
        parts.append("\n## Adversarial Review (L4)")
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

    # Position context (held + candidates)
    pos_type = getattr(request, "position_type", None)
    if pos_type and isinstance(pos_type, str):
        parts.append(f"\n## Position Type: {pos_type.upper()}")
        _type_directives = _POSITION_TYPE_BOARD_DIRECTIVES.get(pos_type, "")
        if _type_directives:
            parts.append(_type_directives)

    pos_thesis = getattr(request, "position_thesis", None)
    if pos_thesis and isinstance(pos_thesis, str):
        parts.append("\n## Position Context")
        parts.append(f"Original Thesis: {pos_thesis[:300]}")
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

def _extract_json(raw: str) -> dict | None:
    """Extract JSON from LLM output with 3 fallback strategies.

    Shared robust parser handling code fences and wrapper text.
    """
    stripped = raw.strip()

    # 1. Direct parse
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown fences
    if "```" in stripped:
        lines = stripped.split("\n")
        json_lines: list[str] = []
        inside = False
        for line in lines:
            if line.strip().startswith("```"):
                inside = not inside
                continue
            if inside:
                json_lines.append(line)
        try:
            return json.loads("\n".join(json_lines))
        except json.JSONDecodeError:
            pass

    # 3. Brace-matching: find first top-level JSON object
    first_brace = stripped.find("{")
    if first_brace >= 0:
        depth = 0
        in_string = False
        escape_next = False
        for i in range(first_brace, len(stripped)):
            c = stripped[i]
            if escape_next:
                escape_next = False
                continue
            if c == "\\":
                escape_next = True
                continue
            if c == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = stripped[first_brace: i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
    return None


def _parse_pair_response(
    resp: LLMResponse,
    member_a: AdvisorSpec,
    member_b: AdvisorSpec,
) -> list[AdvisorOpinion]:
    """Parse the paired LLM response into individual opinions."""
    data = _extract_json(resp.content)
    if data is None:
        logger.warning("Failed to parse advisory pair response as JSON: %s...", resp.content[:200])
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
    """Aggregate 6 advisory votes into a board decision.

    Rules (3/6 = 50% thresholds):
      - 3+ VETOs → cap verdict at WATCHLIST
      - 3+ ADJUST_UP → shift verdict up one level
      - 3+ ADJUST_DOWN → shift verdict down one level
      - Otherwise → verdict stands
    """
    vote_counts: dict[str, int] = {v.value: 0 for v in BoardVote}
    for op in opinions:
        vote_counts[op.vote.value] = vote_counts.get(op.vote.value, 0) + 1

    veto_count = vote_counts.get("VETO", 0)
    adjust_up_count = vote_counts.get("ADJUST_UP", 0)
    adjust_down_count = vote_counts.get("ADJUST_DOWN", 0)

    adjusted_verdict: str | None = None

    # Hard override: 3+ VETOs (50% of 6)
    if veto_count >= 3:
        current_idx = _verdict_index(original_verdict)
        watchlist_idx = _verdict_index("WATCHLIST")
        if current_idx > watchlist_idx:
            adjusted_verdict = "WATCHLIST"
            logger.info(
                "Board veto override: %d VETOs, capping %s → WATCHLIST",
                veto_count, original_verdict,
            )
    # Majority shift up: 3+ (50% of 6)
    elif adjust_up_count >= 3:
        shifted = _shift_verdict(original_verdict, +1)
        if shifted and shifted != original_verdict:
            adjusted_verdict = shifted
            logger.info(
                "Board shift up: %d ADJUST_UP votes, %s → %s",
                adjust_up_count, original_verdict, shifted,
            )
    # Majority shift down: 3+ (50% of 6)
    elif adjust_down_count >= 3:
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
