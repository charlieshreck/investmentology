from __future__ import annotations

import json
import logging
from decimal import Decimal

from investmentology.agents.base import AnalysisRequest, AnalysisResponse, BaseAgent
from investmentology.agents.gateway import LLMGateway
from investmentology.compatibility.taxonomy import ACTION_TAGS, MACRO_TAGS
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag

logger = logging.getLogger(__name__)

_VALID_TAGS = MACRO_TAGS | ACTION_TAGS

_SYSTEM_PROMPT = """\
You are a macro/cycle analyst modeled on George Soros's investment philosophy.

Your task: Assess the macro regime, sector rotation dynamics, credit conditions, \
geopolitical risks, and reflexivity patterns affecting the given stock.

Return your analysis as JSON with this exact structure:
{
    "signals": [
        {"tag": "REGIME_BULL", "strength": "moderate", "detail": "Expansion phase with easing monetary policy"},
        {"tag": "SECTOR_ROTATION_INTO", "strength": "strong", "detail": "Capital flowing into tech from defensives"}
    ],
    "confidence": 0.72,
    "target_price": null,
    "summary": "Brief summary of your macro assessment..."
}

Rules:
- "strength" must be one of: "strong", "moderate", "weak"
- "confidence" is a float between 0.0 and 1.0
- "target_price" is optional for macro analysis (use null if not applicable)
- Use ONLY these signal tags for your analysis:
  Macro: REGIME_BULL, REGIME_BEAR, REGIME_NEUTRAL, REGIME_TRANSITION, SECTOR_ROTATION_INTO, \
SECTOR_ROTATION_OUT, CREDIT_TIGHTENING, CREDIT_EASING, RATE_RISING, RATE_FALLING, \
INFLATION_HIGH, INFLATION_LOW, DOLLAR_STRONG, DOLLAR_WEAK, GEOPOLITICAL_RISK, \
SUPPLY_CHAIN_DISRUPTION, FISCAL_STIMULUS, FISCAL_CONTRACTION, LIQUIDITY_ABUNDANT, \
LIQUIDITY_TIGHT, REFLEXIVITY_DETECTED
  Action: BUY_NEW, BUY_ADD, TRIM, SELL_FULL, SELL_PARTIAL, HOLD, HOLD_STRONG, \
WATCHLIST_ADD, WATCHLIST_REMOVE, WATCHLIST_PROMOTE, REJECT, REJECT_HARD, NO_ACTION
- Return ONLY valid JSON. No markdown, no code fences, no commentary outside the JSON."""


class SorosAgent(BaseAgent):
    """Macro analyst modeled on George Soros.

    Provider: Gemini (via CLI subscription or xAI Grok API).
    Focus: macro cycles, geopolitics, reflexivity.
    Signal category: Macro/Cycle (21 tags).
    """

    # Provider preference: gemini-cli (subscription) > xai (API)
    PROVIDER_PREFERENCE = ["gemini-cli", "xai"]

    def __init__(self, gateway: LLMGateway) -> None:
        self.gateway = gateway
        provider, model = self._resolve_provider(gateway)
        super().__init__(name="soros", model=model)
        self._provider = provider

    @classmethod
    def _resolve_provider(cls, gateway: LLMGateway) -> tuple[str, str]:
        """Pick best available provider for Soros."""
        if "gemini-cli" in gateway._cli_providers:
            cfg = gateway._cli_providers["gemini-cli"]
            return "gemini-cli", cfg.default_model or "gemini-2.5-pro"
        if "xai" in gateway._providers:
            cfg = gateway._providers["xai"]
            return "xai", cfg.default_model
        raise ValueError(
            "Soros requires gemini-cli (USE_GEMINI_CLI=1) or xAI/Grok API key"
        )

    def build_system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def build_user_prompt(self, request: AnalysisRequest) -> str:
        f = request.fundamentals
        parts = [
            f"Analyze macro conditions for {request.ticker} ({request.sector} / {request.industry})",
            "",
            "Company Fundamentals Summary:",
            f"  Market Cap: ${f.market_cap:,}",
            f"  Revenue: ${f.revenue:,}",
            f"  Net Income: ${f.net_income:,}",
            f"  Earnings Yield: {f.earnings_yield}",
            f"  Debt/Assets: {f.total_liabilities / f.total_assets if f.total_assets else 'N/A'}",
        ]

        if request.macro_context:
            parts.append("")
            parts.append("Macro Context:")
            for k, v in request.macro_context.items():
                parts.append(f"  {k}: {v}")

        # Recent news for macro/sector narrative
        if request.news_context:
            parts.append("")
            parts.append("Recent News:")
            for item in request.news_context[:5]:
                headline = item.get("headline", "")[:100]
                dt = item.get("datetime", "")[:10]
                parts.append(f"  [{dt}] {headline}")

        # Social sentiment (Reddit/Twitter)
        if request.social_sentiment:
            parts.append("")
            parts.append("Social Sentiment:")
            agg = request.social_sentiment.get("aggregate", {})
            if agg:
                parts.append(f"  Bias: {agg.get('bias', 'unknown')}")
                parts.append(f"  Positive ratio: {agg.get('positive_ratio', 'N/A')}")
                parts.append(f"  Total mentions: {agg.get('total_mentions', 0)}")
            for source in ["reddit", "twitter"]:
                s = request.social_sentiment.get(source)
                if s:
                    parts.append(f"  {source.capitalize()}: +{s.get('positive_mention', 0)} / -{s.get('negative_mention', 0)} mentions")

        # Portfolio context — macro risk to existing exposure
        if request.portfolio_context:
            pc = request.portfolio_context
            parts.append("")
            parts.append("Portfolio Macro Risk Context:")
            se = pc.get("sector_exposure", {})
            if se:
                # Show sector tilt for macro vulnerability assessment
                sorted_sectors = sorted(se.items(), key=lambda x: x[1], reverse=True)
                top_sectors = sorted_sectors[:3]
                parts.append("  Largest sector exposures:")
                for sector, pct in top_sectors:
                    parts.append(f"    {sector}: {pct:.0f}%")
                # Classify portfolio tilt
                growth_pct = sum(se.get(s, 0) for s in ["Technology", "Communication Services", "Consumer Cyclical"])
                defensive_pct = sum(se.get(s, 0) for s in ["Consumer Defensive", "Utilities", "Healthcare"])
                cyclical_pct = sum(se.get(s, 0) for s in ["Financial Services", "Industrials", "Basic Materials", "Energy"])
                parts.append(f"  Portfolio tilt: Growth {growth_pct:.0f}% / Defensive {defensive_pct:.0f}% / Cyclical {cyclical_pct:.0f}%")
                if growth_pct > 50:
                    parts.append("  NOTE: Portfolio is growth-heavy — vulnerable to rate hikes and risk-off rotation")
                elif cyclical_pct > 40:
                    parts.append("  NOTE: Portfolio is cyclical-heavy — vulnerable to economic slowdown")
            parts.append(f"  Total value at risk: ${pc.get('total_value', 0):,.0f}")
            parts.append(f"  Consider: How does adding {request.ticker} ({request.sector}) change macro vulnerability?")

        if request.previous_verdict:
            pv = request.previous_verdict
            parts.append("")
            parts.append("Previous Analysis Context:")
            parts.append(f"  Last verdict: {pv.get('verdict')} on {pv.get('date', 'unknown date')}")
            parts.append(f"  Confidence: {pv.get('confidence')}, Consensus: {pv.get('consensus_score')}")
            if pv.get("reasoning"):
                parts.append(f"  Reasoning: {pv['reasoning'][:200]}")
            parts.append("  Consider: Have macro conditions changed since the last analysis?")

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
                        "Soros: failed to parse JSON from %s response for %s",
                        self.model,
                        request.ticker,
                    )
                    return self._empty_signal_set()
            else:
                logger.warning(
                    "Soros: failed to parse JSON from %s response for %s",
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
                logger.warning("Soros: unknown signal tag %r, skipping", tag_str)
                continue
            if tag not in _VALID_TAGS:
                logger.warning("Soros: tag %s not in macro/action set, skipping", tag)
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
            provider=self._provider,
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
