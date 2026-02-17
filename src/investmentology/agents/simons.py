from __future__ import annotations

import json
import logging
from decimal import Decimal

from investmentology.agents.base import AnalysisRequest, AnalysisResponse, BaseAgent
from investmentology.agents.gateway import LLMGateway
from investmentology.compatibility.taxonomy import ACTION_TAGS, TECHNICAL_TAGS
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag

logger = logging.getLogger(__name__)

_VALID_TAGS = TECHNICAL_TAGS | ACTION_TAGS

_SYSTEM_PROMPT = """\
You are a quantitative technical analyst modeled on Jim Simons's approach.

Your task: Interpret the pre-computed technical indicators provided for the given stock. \
Assess trend, momentum, volume patterns, support/resistance, and relative strength.

IMPORTANT: Do NOT calculate any indicators yourself. All indicators are pre-computed and \
provided in the data. Your job is to INTERPRET them and produce actionable signals.

Return your analysis as JSON with this exact structure:
{
    "signals": [
        {"tag": "TREND_UPTREND", "strength": "strong", "detail": "Price above SMA 50 and SMA 200"},
        {"tag": "MOMENTUM_STRONG", "strength": "moderate", "detail": "RSI at 62, MACD positive"}
    ],
    "confidence": 0.75,
    "target_price": null,
    "summary": "Brief summary of your technical assessment..."
}

Rules:
- "strength" must be one of: "strong", "moderate", "weak"
- "confidence" is a float between 0.0 and 1.0
- "target_price" is optional for technical analysis (use null if not applicable)
- Use ONLY these signal tags for your analysis:
  Technical: TREND_UPTREND, TREND_DOWNTREND, TREND_SIDEWAYS, MOMENTUM_STRONG, MOMENTUM_WEAK, \
MOMENTUM_DIVERGENCE, BREAKOUT_CONFIRMED, BREAKDOWN_CONFIRMED, SUPPORT_NEAR, RESISTANCE_NEAR, \
VOLUME_SURGE, VOLUME_DRY, VOLUME_CLIMAX, RSI_OVERSOLD, RSI_OVERBOUGHT, GOLDEN_CROSS, \
DEATH_CROSS, RELATIVE_STRENGTH_HIGH, RELATIVE_STRENGTH_LOW
  Action: BUY_NEW, BUY_ADD, TRIM, SELL_FULL, SELL_PARTIAL, HOLD, HOLD_STRONG, \
WATCHLIST_ADD, WATCHLIST_REMOVE, WATCHLIST_PROMOTE, REJECT, REJECT_HARD, NO_ACTION
- Return ONLY valid JSON. No markdown, no code fences, no commentary outside the JSON."""


class SimonsAgent(BaseAgent):
    """Technical analyst modeled on Jim Simons.

    Provider: Groq + Llama. Focus: technicals, momentum, timing.
    Signal category: Technical/Timing (19 tags).
    IMPORTANT: Pre-computed indicators passed in, LLM interprets, does NOT calculate.
    """

    def __init__(self, gateway: LLMGateway) -> None:
        super().__init__(name="simons", model="llama-3.3-70b-versatile")
        self.gateway = gateway

    def build_system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def build_user_prompt(self, request: AnalysisRequest) -> str:
        f = request.fundamentals
        parts = [
            f"Interpret technical indicators for {request.ticker} ({request.sector} / {request.industry})",
            "",
            f"Current Price: ${f.price}",
        ]

        if request.technical_indicators:
            parts.append("")
            parts.append("Pre-Computed Technical Indicators:")
            for k, v in request.technical_indicators.items():
                parts.append(f"  {k}: {v}")

        # Social sentiment as a momentum signal
        if request.social_sentiment:
            agg = request.social_sentiment.get("aggregate", {})
            if agg:
                parts.append("")
                parts.append("Social Momentum:")
                parts.append(f"  Bias: {agg.get('bias', 'unknown')}")
                parts.append(f"  Total mentions: {agg.get('total_mentions', 0)}")
                parts.append(f"  Positive ratio: {agg.get('positive_ratio', 'N/A')}")

        if request.previous_verdict:
            pv = request.previous_verdict
            parts.append("")
            parts.append("Previous Analysis Context:")
            parts.append(f"  Last verdict: {pv.get('verdict')} on {pv.get('date', 'unknown date')}")
            parts.append(f"  Confidence: {pv.get('confidence')}, Consensus: {pv.get('consensus_score')}")
            if pv.get("reasoning"):
                parts.append(f"  Reasoning: {pv['reasoning'][:200]}")
            parts.append("  Consider: Have technical conditions changed since the last analysis?")

        return "\n".join(parts)

    def parse_response(self, raw: str, request: AnalysisRequest) -> AgentSignalSet:
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
                    logger.warning(
                        "Simons: failed to parse JSON from %s response for %s",
                        self.model,
                        request.ticker,
                    )
                    return self._empty_signal_set()
            else:
                logger.warning(
                    "Simons: failed to parse JSON from %s response for %s",
                    self.model,
                    request.ticker,
                )
                return self._empty_signal_set()

        signals: list[Signal] = []
        for s in data.get("signals", []):
            tag_str = s.get("tag", "")
            try:
                tag = SignalTag(tag_str)
            except ValueError:
                logger.warning("Simons: unknown signal tag %r, skipping", tag_str)
                continue
            if tag not in _VALID_TAGS:
                logger.warning("Simons: tag %s not in technical/action set, skipping", tag)
                continue
            strength = s.get("strength", "moderate")
            if strength not in ("strong", "moderate", "weak"):
                strength = "moderate"
            signals.append(Signal(tag=tag, strength=strength, detail=s.get("detail", "")))

        confidence = Decimal(str(data.get("confidence", 0.5)))
        confidence = max(Decimal("0"), min(Decimal("1"), confidence))

        target_price = data.get("target_price")
        if target_price is not None:
            target_price = Decimal(str(target_price))

        return AgentSignalSet(
            agent_name=self.name,
            model=self.model,
            signals=SignalSet(signals=signals),
            confidence=confidence,
            reasoning=data.get("summary", ""),
            target_price=target_price,
        )

    def _empty_signal_set(self) -> AgentSignalSet:
        return AgentSignalSet(
            agent_name=self.name,
            model=self.model,
            signals=SignalSet(signals=[]),
            confidence=Decimal("0"),
            reasoning="Failed to parse LLM response",
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
            agent_name=self.name,
            model=self.model,
            ticker=request.ticker,
            signal_set=signal_set,
            summary=signal_set.reasoning,
            target_price=signal_set.target_price,
            token_usage=llm_response.token_usage,
            latency_ms=llm_response.latency_ms,
        )
