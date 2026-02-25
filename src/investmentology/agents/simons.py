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
You are a quantitative technical analyst modeled on Jim Simons's Renaissance Technologies approach.

Your task: Interpret the pre-computed technical indicators provided for the given stock. \
Assess trend, momentum, volume patterns, support/resistance, and relative strength.

CRITICAL RULES:
1. If NO pre-computed technical indicators are provided, you MUST return LOW confidence \
(0.0-0.15) and use the NO_ACTION tag. Do NOT guess or fabricate technical analysis. \
Without data, you cannot assess technicals.

2. BEARISH signals are equally valid as bullish ones. Most stocks at any given time are NOT \
in strong uptrends. Be rigorous:
   - RSI > 70 = RSI_OVERBOUGHT (not bullish)
   - MACD histogram negative = MOMENTUM_WEAK
   - Price below SMA 200 = TREND_DOWNTREND
   - Volume declining = VOLUME_DRY
   - ATR expanding with price decline = BREAKDOWN_CONFIRMED

3. Your confidence should reflect the STRENGTH of the technical setup, not a general \
optimism level. A stock with mixed signals should get 0.3-0.5 confidence, not 0.7+.

4. Cross-validate: If RSI says overbought but MACD says bullish crossover, that's a \
CONFLICT — lower your confidence and note it.

Return your analysis as JSON with this exact structure:
{
    "signals": [
        {"tag": "TREND_UPTREND", "strength": "strong", "detail": "Price above SMA 50 and SMA 200"},
        {"tag": "RSI_OVERBOUGHT", "strength": "moderate", "detail": "RSI at 74, approaching resistance"}
    ],
    "confidence": 0.55,
    "target_price": null,
    "summary": "Brief summary including both bullish AND bearish factors..."
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
- Return ONLY valid JSON. No markdown, no code fences, no commentary outside the JSON.
- You MUST include at least one bearish/cautionary signal if ANY indicator suggests weakness."""


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

            # Add explicit interpretation hints based on the data
            ti = request.technical_indicators
            parts.append("")
            parts.append("Key thresholds to evaluate:")
            if ti.get("rsi_14"):
                rsi = float(ti["rsi_14"])
                if rsi > 70:
                    parts.append(f"  - RSI is {rsi:.1f} (ABOVE 70 = OVERBOUGHT territory)")
                elif rsi < 30:
                    parts.append(f"  - RSI is {rsi:.1f} (BELOW 30 = OVERSOLD territory)")
            if ti.get("macd_histogram"):
                macd_h = float(ti["macd_histogram"])
                if macd_h < 0:
                    parts.append(f"  - MACD histogram is NEGATIVE ({macd_h:.4f}) = bearish momentum")
            if ti.get("price_vs_sma200") == "below":
                parts.append("  - Price is BELOW 200-day SMA = bearish trend")
            if ti.get("pct_from_52w_high"):
                pct = float(ti["pct_from_52w_high"])
                if pct < -20:
                    parts.append(f"  - Stock is {abs(pct):.1f}% below 52-week high = significant drawdown")
        else:
            parts.append("")
            parts.append("WARNING: No pre-computed technical indicators available.")
            parts.append("Without technical data, you CANNOT perform meaningful technical analysis.")
            parts.append("Set confidence to 0.0-0.15 and use NO_ACTION tag.")

        # Social sentiment as a momentum signal
        if request.social_sentiment:
            agg = request.social_sentiment.get("aggregate", {})
            if agg:
                parts.append("")
                parts.append("Social Momentum:")
                parts.append(f"  Bias: {agg.get('bias', 'unknown')}")
                parts.append(f"  Total mentions: {agg.get('total_mentions', 0)}")
                parts.append(f"  Positive ratio: {agg.get('positive_ratio', 'N/A')}")

        # Portfolio context — timing relative to existing holdings
        if request.portfolio_context:
            pc = request.portfolio_context
            parts.append("")
            parts.append("Portfolio Timing Context:")
            held = pc.get("held_tickers", [])
            if request.ticker in held:
                parts.append(f"  Already holding {request.ticker}")
                for pos in pc.get("positions", []):
                    if pos.get("ticker") == request.ticker:
                        pnl = pos.get("pnl_pct", 0)
                        parts.append(f"    Position P&L: {pnl:+.1f}%")
                        if pnl > 20:
                            parts.append("    Consider: Is this extended? Technical target for profit-taking?")
                        elif pnl < -15:
                            parts.append("    Consider: Is this breaking down? Support levels for stop-loss?")
                        break
            else:
                parts.append(f"  New position — timing entry is critical")
                parts.append(f"  Portfolio has {pc.get('position_count', 0)} positions")

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

        # Data gate: if no technical indicators were provided, cap confidence
        if not request.technical_indicators:
            confidence = min(confidence, Decimal("0.15"))
            if not any(s.tag == SignalTag.NO_ACTION for s in signals):
                signals.append(Signal(
                    tag=SignalTag.NO_ACTION,
                    strength="strong",
                    detail="No technical indicators available — cannot assess",
                ))

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
            parse_failed=True,
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
