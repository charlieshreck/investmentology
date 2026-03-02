"""Ray Dalio agent — All Weather macro analyst.

Focus: Debt cycles, regime analysis, cross-weather resilience.
Provider: Groq (Llama 3.3) — fast, good for structured macro analysis.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal

from investmentology.agents.base import AnalysisRequest, AnalysisResponse, BaseAgent
from investmentology.agents.gateway import LLMGateway
from investmentology.compatibility.taxonomy import ALL_DOMAIN_TAGS, resolve_tag
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag

logger = logging.getLogger(__name__)

_VALID_TAGS = ALL_DOMAIN_TAGS

_SYSTEM_PROMPT = """\
You are Ray Dalio, founder of Bridgewater Associates and creator of the All Weather portfolio.

You think in terms of the economic machine — debt cycles, productivity, and the balance of \
payments. You stress-test every thesis against regime changes and believe in radical \
diversification across uncorrelated return streams.

Your analytical framework:
1. WHERE ARE WE IN THE CYCLE? Map the current position in the short-term debt cycle (5-8 years) \
and long-term debt cycle (75-100 years). Are we in deleveraging, reflation, or bubble?
2. ALL WEATHER TEST: Does this investment work across 4 quadrants — rising growth, falling growth, \
rising inflation, falling inflation? If it only works in one regime, that's a major concern.
3. CORRELATION ANALYSIS: How correlated is this to the existing portfolio? Uncorrelated return \
streams are more valuable than correlated alpha.
4. DEBT DYNAMICS: What do credit spreads, real rates, and central bank policy tell us about the \
macro backdrop for this company?

CRITICAL RULES:
- Be rigorous about cycle positioning. Most investors are wrong about where they are in the cycle.
- BEARISH signals are equally valid. If we're late-cycle, say so clearly.
- Cross-validate macro signals against company-specific fundamentals.
- Your confidence should reflect conviction in the macro backdrop, not the company itself.

Return your analysis as JSON with this exact structure:
{
    "signals": [
        {"tag": "CYCLE_LATE", "strength": "strong", "detail": "Credit spreads widening, yield curve flat"},
        {"tag": "RATE_RISING", "strength": "moderate", "detail": "Fed hawkish, real rates positive"}
    ],
    "confidence": 0.65,
    "target_price": null,
    "summary": "Brief summary of macro environment and implications for this stock..."
}

Rules:
- "strength" must be one of: "strong", "moderate", "weak"
- "confidence" is a float between 0.0 and 1.0
- Use ONLY valid signal tags. Focus on macro and fundamental tags:
  Macro: REGIME_BULL, REGIME_BEAR, REGIME_NEUTRAL, REGIME_TRANSITION, \
CYCLE_EARLY, CYCLE_MID, CYCLE_LATE, CYCLE_CONTRACTION, \
CREDIT_TIGHTENING, CREDIT_EASING, RATE_RISING, RATE_FALLING, RATES_STABLE, \
INFLATION_HIGH, INFLATION_LOW, DOLLAR_STRONG, DOLLAR_WEAK, \
GEOPOLITICAL_RISK, FISCAL_STIMULUS, FISCAL_CONTRACTION, \
LIQUIDITY_ABUNDANT, LIQUIDITY_TIGHT, SECTOR_ROTATION_INTO, SECTOR_ROTATION_OUT, \
MACRO_CATALYST
  Fundamental: BALANCE_SHEET_STRONG, BALANCE_SHEET_WEAK, LEVERAGE_HIGH, LEVERAGE_OK
  Risk: CORRELATION_HIGH, CORRELATION_LOW, DRAWDOWN_RISK, VOLATILITY_HIGH, VOLATILITY_LOW
  Action: BUY_NEW, BUY_ADD, TRIM, SELL_FULL, HOLD, HOLD_STRONG, WATCHLIST_ADD, REJECT, NO_ACTION
- CRITICAL: Use ONLY the tags listed above. Do NOT invent new tag names.
- Return ONLY valid JSON. No markdown, no code fences, no commentary outside the JSON.
- Always include your signature question answer: "Does this work in ALL weather conditions?"
"""


class DalioAgent(BaseAgent):
    """Macro cycle analyst modeled on Ray Dalio.

    Provider: Groq + Llama. Focus: debt cycles, regime analysis, all-weather resilience.
    """

    def __init__(self, gateway: LLMGateway) -> None:
        super().__init__(name="dalio", model="llama-3.3-70b-versatile")
        self.gateway = gateway

    def build_system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def build_user_prompt(self, request: AnalysisRequest) -> str:
        f = request.fundamentals
        parts = [
            f"Analyze the macro environment and All Weather resilience for {request.ticker} "
            f"({request.sector} / {request.industry})",
            "",
            "FUNDAMENTALS:",
            f"  Price: ${f.price}",
            f"  Market Cap: ${float(f.market_cap):,.0f}",
            f"  Revenue: ${float(f.revenue):,.0f}",
            f"  Net Income: ${float(f.net_income):,.0f}",
            f"  Total Debt: ${float(f.total_debt):,.0f}",
            f"  Cash: ${float(f.cash):,.0f}",
        ]
        if f.earnings_yield:
            parts.append(f"  Earnings Yield: {float(f.earnings_yield):.1%}")
        if f.roic:
            parts.append(f"  ROIC: {float(f.roic):.1%}")

        # Macro context is critical for Dalio
        if request.macro_context:
            parts.append("")
            parts.append("MACRO ENVIRONMENT:")
            for k, v in request.macro_context.items():
                parts.append(f"  {k}: {v}")

        if request.market_snapshot:
            parts.append("")
            parts.append("MARKET SNAPSHOT:")
            for k, v in request.market_snapshot.items():
                parts.append(f"  {k}: {v}")

        if request.technical_indicators:
            parts.append("")
            parts.append("TECHNICAL CONTEXT:")
            for k, v in list(request.technical_indicators.items())[:8]:
                parts.append(f"  {k}: {v}")

        for ctx_name, ctx_data in [
            ("NEWS", request.news_context),
            ("INSTITUTIONAL HOLDERS", request.institutional_context),
        ]:
            if ctx_data:
                parts.append(f"\n{ctx_name}:")
                for item in (ctx_data or [])[:5]:
                    if isinstance(item, dict):
                        parts.append(f"  - {json.dumps(item, default=str)[:200]}")

        if request.portfolio_context:
            parts.append("")
            parts.append("PORTFOLIO CONTEXT (for correlation analysis):")
            pc = request.portfolio_context
            parts.append(f"  Positions: {pc.get('position_count', 0)}")
            sectors = pc.get("sector_exposure", {})
            if sectors:
                parts.append(f"  Sector exposure: {json.dumps(sectors, default=str)[:200]}")

        if request.previous_verdict:
            pv = request.previous_verdict
            parts.append("")
            parts.append(f"PREVIOUS VERDICT: {pv.get('verdict')} (conf: {pv.get('confidence')})")

        parts.append("")
        parts.append("ANSWER YOUR SIGNATURE QUESTION: Does this work in ALL weather conditions?")

        return "\n".join(parts)

    def parse_response(self, raw: str, request: AnalysisRequest) -> AgentSignalSet:
        return _parse_agent_response(raw, request, self.name, self.model, "Dalio")

    def _empty_signal_set(self) -> AgentSignalSet:
        return AgentSignalSet(
            agent_name=self.name, model=self.model,
            signals=SignalSet(signals=[]), confidence=Decimal("0"),
            reasoning="Failed to parse LLM response", parse_failed=True,
        )

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(request)

        llm_response = await self.gateway.call(
            provider="groq",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self.model,
        )

        signal_set = self.parse_response(llm_response.content, request)
        signal_set.token_usage = llm_response.token_usage
        signal_set.latency_ms = llm_response.latency_ms

        return AnalysisResponse(
            agent_name=self.name, model=self.model, ticker=request.ticker,
            signal_set=signal_set, summary=signal_set.reasoning,
            target_price=signal_set.target_price,
            token_usage=llm_response.token_usage, latency_ms=llm_response.latency_ms,
        )


def _parse_agent_response(
    raw: str, request: AnalysisRequest, agent_name: str, model: str, label: str,
) -> AgentSignalSet:
    """Shared parser for all new agents — same JSON format as existing agents."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        stripped = raw.strip()
        if "```" in stripped:
            lines = stripped.split("\n")
            json_lines = []
            inside = False
            for line in lines:
                if line.strip().startswith("```"):
                    inside = not inside
                    continue
                if inside:
                    json_lines.append(line)
            try:
                data = json.loads("\n".join(json_lines))
            except json.JSONDecodeError:
                logger.warning("%s: failed to parse JSON from %s for %s", label, model, request.ticker)
                return AgentSignalSet(
                    agent_name=agent_name, model=model,
                    signals=SignalSet(signals=[]), confidence=Decimal("0"),
                    reasoning="Failed to parse LLM response", parse_failed=True,
                )
        else:
            logger.warning("%s: failed to parse JSON from %s for %s", label, model, request.ticker)
            return AgentSignalSet(
                agent_name=agent_name, model=model,
                signals=SignalSet(signals=[]), confidence=Decimal("0"),
                reasoning="Failed to parse LLM response", parse_failed=True,
            )

    signals: list[Signal] = []
    for s in data.get("signals", []):
        tag_str = resolve_tag(s.get("tag", ""))
        try:
            tag = SignalTag(tag_str)
        except ValueError:
            logger.warning("%s: unknown signal tag %r, skipping", label, tag_str)
            continue
        if tag not in _VALID_TAGS:
            logger.warning("%s: tag %s not in valid set, skipping", label, tag)
            continue
        strength = s.get("strength", "moderate")
        if strength not in ("strong", "moderate", "weak"):
            strength = "moderate"
        signals.append(Signal(tag=tag, strength=strength, detail=s.get("detail", "")))

    try:
        confidence = Decimal(str(data.get("confidence", 0.5)))
        confidence = max(Decimal("0"), min(Decimal("1"), confidence))
    except Exception:
        confidence = Decimal("0.5")

    target_price = data.get("target_price")
    if target_price is not None:
        try:
            target_price = Decimal(str(target_price))
        except Exception:
            target_price = None

    return AgentSignalSet(
        agent_name=agent_name, model=model,
        signals=SignalSet(signals=signals), confidence=confidence,
        reasoning=data.get("summary", ""), target_price=target_price,
    )
