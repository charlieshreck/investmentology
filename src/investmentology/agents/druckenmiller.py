"""Stanley Druckenmiller agent — Conviction sizing and catalyst hunter.

Focus: Risk/reward asymmetry, catalysts, position sizing, macro+bottom-up.
Provider: DeepSeek — needs deep reasoning for asymmetry detection.
"""
from __future__ import annotations

import json
import logging

from investmentology.agents.base import AnalysisRequest, AnalysisResponse, BaseAgent
from investmentology.agents.dalio import _parse_agent_response
from investmentology.agents.gateway import LLMGateway
from investmentology.models.signal import AgentSignalSet

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are Stanley Druckenmiller, one of the greatest macro traders of all time.

You size positions based on conviction — when you see asymmetry, you bet big. The biggest \
mistake is not being wrong, it's being right and not betting enough. You combine top-down macro \
with bottom-up stock picking.

Your analytical framework:
1. RISK/REWARD ASYMMETRY: Is the upside at least 3:1 vs downside? What's the skew?
2. CATALYST IDENTIFICATION: What specific event in the next 3-6 months will move this stock? \
No catalyst = no urgency = no position.
3. CONVICTION SIZING: On a scale of 1-10, how convicted are you? 8+ means go big. \
4-7 means small position. Below 4 means pass.
4. MACRO ALIGNMENT: Is the broader macro environment supportive of this trade?
5. TIME HORIZON: When do you expect the trade to work? 1 month? 6 months? 1 year?

CRITICAL RULES:
- No catalyst = REJECT. You need a specific, identifiable catalyst with a timeline.
- Risk/reward below 2:1 = pass. You don't take symmetric bets.
- Be explicit about position sizing recommendation (small/standard/large/max).
- BEARISH setups with clear catalysts are equally tradeable.
- Macro must be at least neutral — don't fight the tape.
- Always provide a bear case price target alongside bull case.

Return your analysis as JSON with this exact structure:
{
    "signals": [
        {"tag": "EARNINGS_SURPRISE", "strength": "strong", "detail": "Earnings in 3 weeks, whisper number $0.20 above consensus"},
        {"tag": "REGIME_BULL", "strength": "moderate", "detail": "Macro supportive, sector rotation favoring"}
    ],
    "confidence": 0.75,
    "target_price": 125.00,
    "summary": "3:1 risk/reward with Q2 earnings catalyst in 3 weeks. Bull: $125, Bear: $90..."
}

Rules:
- "strength" must be one of: "strong", "moderate", "weak"
- "confidence" is a float between 0.0 and 1.0
- ALWAYS include both bull and bear case price in your summary
- Use ONLY valid signal tags:
  Macro: REGIME_BULL, REGIME_BEAR, REGIME_NEUTRAL, REGIME_TRANSITION, \
SECTOR_ROTATION_INTO, SECTOR_ROTATION_OUT, MACRO_CATALYST, \
CYCLE_EARLY, CYCLE_MID, CYCLE_LATE, CYCLE_CONTRACTION
  Fundamental: UNDERVALUED, OVERVALUED, FAIRLY_VALUED, DEEP_VALUE, \
REVENUE_ACCELERATING, REVENUE_DECELERATING, MARGIN_EXPANDING, MARGIN_COMPRESSING, \
EARNINGS_QUALITY_HIGH, MOAT_WIDENING, MOAT_STABLE
  Special: EARNINGS_SURPRISE, GUIDANCE_RAISED, GUIDANCE_LOWERED, \
INSIDER_CLUSTER_BUY, INSIDER_CLUSTER_SELL, ACTIVIST_INVOLVED, MANAGEMENT_CHANGE, \
SPINOFF_ANNOUNCED, MERGER_TARGET, INDEX_ADD, INDEX_DROP
  Technical: BREAKOUT_CONFIRMED, BREAKDOWN_CONFIRMED, MOMENTUM_STRONG, MOMENTUM_WEAK, \
TREND_UPTREND, TREND_DOWNTREND, VOLUME_SURGE
  Risk: DRAWDOWN_RISK, VOLATILITY_HIGH, VOLATILITY_LOW, LEVERAGE_HIGH
  Action: BUY_NEW, BUY_ADD, TRIM, SELL_FULL, HOLD, HOLD_STRONG, WATCHLIST_ADD, REJECT, NO_ACTION
- CRITICAL: Use ONLY the tags listed above. Do NOT invent new tag names.
- Return ONLY valid JSON. No markdown, no code fences, no commentary outside the JSON.
"""


class DruckenmillerAgent(BaseAgent):
    """Catalyst and conviction analyst modeled on Stanley Druckenmiller.

    Provider: DeepSeek. Focus: risk/reward asymmetry, catalysts, sizing.
    """

    def __init__(self, gateway: LLMGateway) -> None:
        super().__init__(name="druckenmiller", model="deepseek-reasoner")
        self.gateway = gateway

    def build_system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def build_user_prompt(self, request: AnalysisRequest) -> str:
        f = request.fundamentals
        parts = [
            f"Assess risk/reward asymmetry and catalysts for {request.ticker} "
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

        # Macro context — Druckenmiller combines top-down + bottom-up
        if request.macro_context:
            parts.append("\nMACRO BACKDROP:")
            for k, v in request.macro_context.items():
                parts.append(f"  {k}: {v}")

        if request.market_snapshot:
            parts.append("\nMARKET SNAPSHOT:")
            for k, v in list(request.market_snapshot.items())[:6]:
                parts.append(f"  {k}: {v}")

        # News for catalyst identification
        if request.news_context:
            parts.append("\nRECENT NEWS (look for catalysts):")
            for item in (request.news_context or [])[:5]:
                if isinstance(item, dict):
                    parts.append(f"  - {item.get('title', item.get('headline', str(item)))[:150]}")

        # Earnings context — key catalyst
        if request.earnings_context:
            parts.append("\nEARNINGS CONTEXT:")
            ec = request.earnings_context
            if isinstance(ec, dict):
                parts.append(f"  {json.dumps(ec, default=str)[:300]}")

        if request.technical_indicators:
            parts.append("\nTECHNICAL SETUP:")
            for k, v in list(request.technical_indicators.items())[:10]:
                parts.append(f"  {k}: {v}")

        if request.insider_context:
            parts.append("\nINSIDER ACTIVITY:")
            for item in (request.insider_context or [])[:3]:
                if isinstance(item, dict):
                    parts.append(f"  - {json.dumps(item, default=str)[:200]}")

        if request.portfolio_context:
            pc = request.portfolio_context
            held = pc.get("held_tickers", [])
            if request.ticker in held:
                parts.append(f"\nALREADY HOLDING {request.ticker}")
                for pos in pc.get("positions", []):
                    if pos.get("ticker") == request.ticker:
                        parts.append(f"  Entry: ${pos.get('entry_price', '?')}, P&L: {pos.get('pnl_pct', 0):+.1f}%")

        if request.previous_verdict:
            pv = request.previous_verdict
            parts.append(f"\nPREVIOUS VERDICT: {pv.get('verdict')} (conf: {pv.get('confidence')})")

        parts.append("\nANSWER: Is the risk/reward skewed at least 3:1, and what's the catalyst?")
        return "\n".join(parts)

    def parse_response(self, raw: str, request: AnalysisRequest) -> "AgentSignalSet":
        return _parse_agent_response(raw, request, self.name, self.model, "Druckenmiller")

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        llm_response = await self.gateway.call(
            provider="deepseek",
            system_prompt=self.build_system_prompt(),
            user_prompt=self.build_user_prompt(request),
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
