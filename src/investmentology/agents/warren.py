from __future__ import annotations

import json
import logging
from decimal import Decimal

from investmentology.agents.base import AnalysisRequest, AnalysisResponse, BaseAgent
from investmentology.agents.gateway import LLMGateway
from investmentology.compatibility.taxonomy import ACTION_TAGS, FUNDAMENTAL_TAGS
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag

logger = logging.getLogger(__name__)

_VALID_TAGS = FUNDAMENTAL_TAGS | ACTION_TAGS

_SYSTEM_PROMPT = """\
You are a fundamental equity analyst modeled on Warren Buffett's investment philosophy.

Your task: Assess the intrinsic value, moat quality, earnings quality, and balance sheet \
strength of the given stock.

Return your analysis as JSON with this exact structure:
{
    "signals": [
        {"tag": "UNDERVALUED", "strength": "strong", "detail": "Trading at 60% of intrinsic value"},
        {"tag": "MOAT_WIDENING", "strength": "moderate", "detail": "Services ecosystem growing"}
    ],
    "confidence": 0.78,
    "target_price": 215,
    "summary": "Brief summary of your fundamental assessment..."
}

Rules:
- "strength" must be one of: "strong", "moderate", "weak"
- "confidence" is a float between 0.0 and 1.0
- "target_price" is your estimate of fair value per share (number or null)
- Use ONLY these signal tags for your analysis:
  Fundamental: UNDERVALUED, OVERVALUED, FAIRLY_VALUED, DEEP_VALUE, MOAT_WIDENING, MOAT_STABLE, \
MOAT_NARROWING, NO_MOAT, EARNINGS_QUALITY_HIGH, EARNINGS_QUALITY_LOW, REVENUE_ACCELERATING, \
REVENUE_DECELERATING, MARGIN_EXPANDING, MARGIN_COMPRESSING, BALANCE_SHEET_STRONG, \
BALANCE_SHEET_WEAK, DIVIDEND_GROWING, BUYBACK_ACTIVE, MANAGEMENT_ALIGNED
  Action: BUY_NEW, BUY_ADD, TRIM, SELL_FULL, SELL_PARTIAL, HOLD, HOLD_STRONG, \
WATCHLIST_ADD, WATCHLIST_REMOVE, WATCHLIST_PROMOTE, REJECT, REJECT_HARD, NO_ACTION
- Return ONLY valid JSON. No markdown, no code fences, no commentary outside the JSON."""


class WarrenAgent(BaseAgent):
    """Fundamentals analyst modeled on Warren Buffett.

    Provider: DeepSeek R1. Focus: intrinsic value, moat, earnings quality.
    Signal category: Fundamental (19 tags).
    """

    def __init__(self, gateway: LLMGateway) -> None:
        super().__init__(name="warren", model="deepseek-reasoner")
        self.gateway = gateway

    def build_system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def build_user_prompt(self, request: AnalysisRequest) -> str:
        f = request.fundamentals
        parts = [
            f"Analyze {request.ticker} ({request.sector} / {request.industry})",
            "",
            "Key Fundamentals:",
            f"  Price: ${f.price}",
            f"  Market Cap: ${f.market_cap:,}",
            f"  Enterprise Value: ${f.enterprise_value:,}",
            f"  Revenue: ${f.revenue:,}",
            f"  Net Income: ${f.net_income:,}",
            f"  Operating Income: ${f.operating_income:,}",
            f"  Earnings Yield: {f.earnings_yield}",
            f"  ROIC: {f.roic}",
            f"  Total Debt: ${f.total_debt:,}",
            f"  Cash: ${f.cash:,}",
            f"  Total Assets: ${f.total_assets:,}",
            f"  Total Liabilities: ${f.total_liabilities:,}",
        ]

        if request.quant_gate_rank is not None:
            parts.append(f"  Quant Gate Rank: {request.quant_gate_rank}")
        if request.piotroski_score is not None:
            parts.append(f"  Piotroski F-Score: {request.piotroski_score}")
        if request.altman_z_score is not None:
            parts.append(f"  Altman Z-Score: {request.altman_z_score}")

        # Earnings context (upcoming + recent surprises)
        if request.earnings_context:
            ec = request.earnings_context
            parts.append("")
            parts.append("Earnings Context:")
            if ec.get("upcoming"):
                u = ec["upcoming"]
                parts.append(f"  Next earnings: {u.get('date', 'TBD')}")
                if u.get("eps_estimate"):
                    parts.append(f"  EPS estimate: {u['eps_estimate']}")
            beat = ec.get("beat_count", 0)
            miss = ec.get("miss_count", 0)
            if beat or miss:
                parts.append(f"  Last 4 quarters: {beat} beat, {miss} miss")

        # Recent news headlines
        if request.news_context:
            parts.append("")
            parts.append("Recent News:")
            for item in request.news_context[:5]:
                headline = item.get("headline", "")[:100]
                dt = item.get("datetime", "")[:10]
                parts.append(f"  [{dt}] {headline}")

        # Insider transactions
        if request.insider_context:
            buys = sum(1 for t in request.insider_context if t.get("transaction_type") == "buy")
            sells = sum(1 for t in request.insider_context if t.get("transaction_type") == "sell")
            if buys or sells:
                parts.append("")
                parts.append(f"Insider Activity (recent): {buys} buys, {sells} sells")

        # 10-K filing excerpts (risk factors + MD&A)
        if request.filing_context:
            fc = request.filing_context
            if fc.get("risk_factors"):
                parts.append("")
                parts.append(f"10-K Risk Factors ({fc.get('filing_date', 'recent')}):")
                parts.append(f"  {fc['risk_factors'][:1500]}")
            if fc.get("mda"):
                parts.append("")
                parts.append("Management Discussion & Analysis:")
                parts.append(f"  {fc['mda'][:1500]}")

        # Institutional holders (13F)
        if request.institutional_context:
            parts.append("")
            parts.append("Top Institutional Holders (13F):")
            for h in request.institutional_context[:10]:
                name = h.get("name", "Unknown")[:40]
                shares = h.get("shares", 0)
                parts.append(f"  {name}: {shares:,} shares")

        # Social sentiment — contrarian signal for value investing
        if request.social_sentiment:
            agg = request.social_sentiment.get("aggregate", {})
            if agg:
                parts.append("")
                parts.append("Social Sentiment (contrarian signal):")
                bias = agg.get("bias", "unknown")
                pos_ratio = agg.get("positive_ratio", "N/A")
                mentions = agg.get("total_mentions", 0)
                parts.append(f"  Overall bias: {bias}")
                parts.append(f"  Positive ratio: {pos_ratio}")
                parts.append(f"  Total mentions: {mentions}")
                if bias == "bullish" and pos_ratio and float(pos_ratio) > 0.8:
                    parts.append("  NOTE: Extreme social bullishness — Buffett would be cautious (contrarian)")
                elif bias == "bearish" and pos_ratio and float(pos_ratio) < 0.3:
                    parts.append("  NOTE: Social bearishness — potential value opportunity if fundamentals strong")

                # Portfolio context — helps assess fit and concentration
        if request.portfolio_context:
            pc = request.portfolio_context
            parts.append("")
            parts.append("Current Portfolio Context:")
            parts.append(f"  Total portfolio value: ${pc.get('total_value', 0):,.0f}")
            parts.append(f"  Number of positions: {pc.get('position_count', 0)}")
            held = pc.get("held_tickers", [])
            if request.ticker in held:
                parts.append(f"  NOTE: Already hold {request.ticker}")
                # Find this position's details
                for pos in pc.get("positions", []):
                    if pos.get("ticker") == request.ticker:
                        parts.append(f"    Current weight: {pos.get('weight_pct', 0):.1f}%")
                        parts.append(f"    P&L: {pos.get('pnl_pct', 0):+.1f}%")
                        break
                parts.append("  Consider: Is this a good add, or would it over-concentrate?")
            else:
                parts.append(f"  This would be a NEW position (currently hold {pc.get('position_count', 0)} stocks)")
            # Sector exposure
            se = pc.get("sector_exposure", {})
            if se:
                candidate_sector_pct = se.get(request.sector, 0)
                if candidate_sector_pct > 25:
                    parts.append(f"  WARNING: {request.sector} already at {candidate_sector_pct:.0f}% of portfolio")
                elif candidate_sector_pct > 0:
                    parts.append(f"  {request.sector} exposure: {candidate_sector_pct:.0f}%")
                else:
                    parts.append(f"  {request.sector} is a NEW sector for the portfolio — adds diversification")

        if request.previous_verdict:
            pv = request.previous_verdict
            parts.append("")
            parts.append("Previous Analysis Context:")
            parts.append(f"  Last verdict: {pv.get('verdict')} on {pv.get('date', 'unknown date')}")
            parts.append(f"  Confidence: {pv.get('confidence')}, Consensus: {pv.get('consensus_score')}")
            if pv.get("reasoning"):
                parts.append(f"  Reasoning: {pv['reasoning'][:200]}")
            parts.append("  Consider: Has anything materially changed since the last analysis?")

        return "\n".join(parts)

    def parse_response(self, raw: str, request: AnalysisRequest) -> AgentSignalSet:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code fences
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
                        "Warren: failed to parse JSON from %s response for %s",
                        self.model,
                        request.ticker,
                    )
                    return self._empty_signal_set()
            else:
                logger.warning(
                    "Warren: failed to parse JSON from %s response for %s",
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
                logger.warning("Warren: unknown signal tag %r, skipping", tag_str)
                continue
            if tag not in _VALID_TAGS:
                logger.warning("Warren: tag %s not in fundamental/action set, skipping", tag)
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
            provider="deepseek",
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
