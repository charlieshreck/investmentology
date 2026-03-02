"""Peter Lynch agent — Growth at a reasonable price (GARP).

Focus: Stock classification, PEG ratio, simple story, underfollowed gems.
Provider: Groq (Llama 3.3) — fast, good for straightforward analysis.
"""
from __future__ import annotations

import json
import logging
from decimal import Decimal

from investmentology.agents.base import AnalysisRequest, AnalysisResponse, BaseAgent
from investmentology.agents.dalio import _parse_agent_response
from investmentology.agents.gateway import LLMGateway

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are Peter Lynch, legendary manager of the Magellan Fund.

You classify every company into one of six categories, and each has different buy/sell criteria:
- SLOW GROWER: 2-4% growth, bought for dividend. Sell if growth stalls or dividend cut.
- STALWART: 10-12% growth, large reliable companies. Buy on dips, sell at 30-50% gains.
- FAST GROWER: 20-25%+ growth, your favorites. The key: can they sustain it?
- CYCLICAL: Earnings tied to economic cycle. Timing is everything — buy at cycle bottom.
- TURNAROUND: Near-death companies recovering. High risk, high reward.
- ASSET PLAY: Hidden assets worth more than the stock price suggests.

Your analytical framework:
1. CLASSIFY THE COMPANY: Which of the 6 categories? This determines everything.
2. PEG RATIO: For growth companies, PEG < 1 is attractive, > 2 is expensive.
3. THE STORY TEST: Can you explain in 2 minutes why this will make money? If not, pass.
4. INSTITUTIONAL FOOTPRINT: Low institutional ownership = potential underfollowed gem.
5. INSIDER ACTIVITY: Insiders buying is one of the strongest bullish signals.

CRITICAL RULES:
- Be honest about category classification. Most stocks are Stalwarts, not Fast Growers.
- PEG > 2 for a "growth" stock is a red flag — it may be priced for perfection.
- Complexity is your enemy. If the thesis requires 5 assumptions, it's too complex.
- Low institutional ownership + insider buying = your ideal setup.
- BEARISH is valid. Not every stock has a simple, compelling story.

Return your analysis as JSON with this exact structure:
{
    "signals": [
        {"tag": "REVENUE_ACCELERATING", "strength": "strong", "detail": "Revenue growing 22% YoY"},
        {"tag": "MANAGEMENT_ALIGNED", "strength": "moderate", "detail": "CEO bought $2M in shares last quarter"}
    ],
    "confidence": 0.70,
    "target_price": 85.00,
    "summary": "FAST GROWER — 22% revenue growth with PEG of 0.8. Simple story: dominant in niche..."
}

Rules:
- "strength" must be one of: "strong", "moderate", "weak"
- "confidence" is a float between 0.0 and 1.0
- ALWAYS start your summary with the Lynch category (SLOW GROWER, STALWART, FAST GROWER, etc.)
- Use ONLY valid signal tags. Focus on fundamental and special tags:
  Fundamental: UNDERVALUED, OVERVALUED, FAIRLY_VALUED, DEEP_VALUE, \
REVENUE_ACCELERATING, REVENUE_DECELERATING, MARGIN_EXPANDING, MARGIN_COMPRESSING, \
EARNINGS_QUALITY_HIGH, EARNINGS_QUALITY_LOW, MOAT_WIDENING, MOAT_STABLE, MOAT_NARROWING, \
BALANCE_SHEET_STRONG, BALANCE_SHEET_WEAK, DIVIDEND_GROWING, BUYBACK_ACTIVE, \
MANAGEMENT_ALIGNED, MANAGEMENT_MISALIGNED, ROIC_IMPROVING, ROIC_DECLINING, \
CAPITAL_ALLOCATION_EXCELLENT, CAPITAL_ALLOCATION_POOR
  Special: INSIDER_CLUSTER_BUY, INSIDER_CLUSTER_SELL, EARNINGS_SURPRISE, \
GUIDANCE_RAISED, GUIDANCE_LOWERED, MANAGEMENT_CHANGE
  Action: BUY_NEW, BUY_ADD, TRIM, SELL_FULL, HOLD, HOLD_STRONG, WATCHLIST_ADD, REJECT, NO_ACTION
- CRITICAL: Use ONLY the tags listed above. Do NOT invent new tag names.
- Return ONLY valid JSON. No markdown, no code fences, no commentary outside the JSON.
"""


class LynchAgent(BaseAgent):
    """Growth-at-reasonable-price analyst modeled on Peter Lynch.

    Provider: Groq + Llama. Focus: PEG, stock classification, simple story.
    """

    def __init__(self, gateway: LLMGateway) -> None:
        super().__init__(name="lynch", model="llama-3.3-70b-versatile")
        self.gateway = gateway

    def build_system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def build_user_prompt(self, request: AnalysisRequest) -> str:
        f = request.fundamentals
        parts = [
            f"Classify and analyze {request.ticker} ({request.sector} / {request.industry})",
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

        # News for the "story"
        if request.news_context:
            parts.append("\nRECENT NEWS (what's the story?):")
            for item in (request.news_context or [])[:5]:
                if isinstance(item, dict):
                    parts.append(f"  - {item.get('title', item.get('headline', str(item)))[:150]}")

        # Insider activity — Lynch loves this
        if request.insider_context:
            parts.append("\nINSIDER ACTIVITY:")
            for item in (request.insider_context or [])[:5]:
                if isinstance(item, dict):
                    parts.append(f"  - {json.dumps(item, default=str)[:200]}")

        # Institutional — low = potential gem
        if request.institutional_context:
            parts.append("\nINSTITUTIONAL HOLDERS:")
            for item in (request.institutional_context or [])[:5]:
                if isinstance(item, dict):
                    parts.append(f"  - {json.dumps(item, default=str)[:200]}")

        if request.technical_indicators:
            ti = request.technical_indicators
            parts.append("\nGROWTH INDICATORS:")
            for k in ["revenue_growth_yoy", "earnings_growth_yoy", "peg_ratio",
                       "forward_pe", "trailing_pe", "price_to_sales"]:
                if k in ti:
                    parts.append(f"  {k}: {ti[k]}")

        if request.portfolio_context:
            pc = request.portfolio_context
            held = pc.get("held_tickers", [])
            if request.ticker in held:
                parts.append(f"\nALREADY HOLDING {request.ticker}")
                for pos in pc.get("positions", []):
                    if pos.get("ticker") == request.ticker:
                        parts.append(f"  P&L: {pos.get('pnl_pct', 0):+.1f}%")

        if request.previous_verdict:
            pv = request.previous_verdict
            parts.append(f"\nPREVIOUS VERDICT: {pv.get('verdict')} (conf: {pv.get('confidence')})")

        parts.append("\nANSWER: What's the story, and is it simple enough to explain in 2 minutes?")
        return "\n".join(parts)

    def parse_response(self, raw: str, request: AnalysisRequest) -> "AgentSignalSet":
        return _parse_agent_response(raw, request, self.name, self.model, "Lynch")

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        llm_response = await self.gateway.call(
            provider="groq",
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
