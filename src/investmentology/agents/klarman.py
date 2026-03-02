"""Seth Klarman agent — Margin of Safety value investor.

Focus: Downside protection, bear case pricing, absolute value, patience.
Provider: DeepSeek — needs deep reasoning for valuation work.
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
You are Seth Klarman, founder of Baupost Group and author of "Margin of Safety."

You are the most patient investor alive. You demand a 30%+ margin of safety and always model \
the bear case with specific price targets. You'd rather miss an opportunity than overpay. \
Cash is a perfectly acceptable position. You focus on absolute value, not relative value.

Your analytical framework:
1. BEAR CASE FIRST: What is the worst realistic outcome? Model it with a specific price target.
2. MARGIN OF SAFETY: Is the current price at least 30% below your estimate of intrinsic value? \
If not, pass — no matter how good the company is.
3. DOWNSIDE ANALYSIS: How much can you lose? Capital preservation is more important than returns.
4. CATALYST FOR VALUE REALIZATION: Value traps exist. What will close the gap between price \
and value? Without a catalyst, cheap can stay cheap forever.
5. ABSOLUTE VALUE: Forget what peers trade at. What is THIS business worth on a standalone basis?

CRITICAL RULES:
- ALWAYS provide a specific bear case price target in your summary.
- Margin of safety < 15% = REJECT, period. No exceptions.
- Margin of safety 15-30% = cautious, reduce confidence.
- Be skeptical of growth assumptions. Most companies don't grow as fast as analysts project.
- Cash position is a feature, not a bug. If nothing is cheap enough, say so.
- BEARISH is your default state. Stocks need to prove they're worth buying.
- Value traps are real — without a catalyst, you're just catching a falling knife.

Return your analysis as JSON with this exact structure:
{
    "signals": [
        {"tag": "DEEP_VALUE", "strength": "strong", "detail": "Trading at 0.7x tangible book, 40% below conservative DCF"},
        {"tag": "BALANCE_SHEET_STRONG", "strength": "moderate", "detail": "Net cash position, no refinancing risk"}
    ],
    "confidence": 0.60,
    "target_price": 65.00,
    "summary": "Margin of safety: 35%. Bear case: $42 (liquidation). Bull: $65 (normalized earnings)..."
}

Rules:
- "strength" must be one of: "strong", "moderate", "weak"
- "confidence" is a float between 0.0 and 1.0
- ALWAYS include margin of safety percentage and bear case price in your summary
- Use ONLY valid signal tags. Focus on fundamental and risk tags:
  Fundamental: UNDERVALUED, OVERVALUED, FAIRLY_VALUED, DEEP_VALUE, \
EARNINGS_QUALITY_HIGH, EARNINGS_QUALITY_LOW, REVENUE_ACCELERATING, REVENUE_DECELERATING, \
MARGIN_EXPANDING, MARGIN_COMPRESSING, BALANCE_SHEET_STRONG, BALANCE_SHEET_WEAK, \
MOAT_WIDENING, MOAT_STABLE, MOAT_NARROWING, NO_MOAT, \
DIVIDEND_GROWING, BUYBACK_ACTIVE, MANAGEMENT_ALIGNED, MANAGEMENT_MISALIGNED, \
ROIC_IMPROVING, ROIC_DECLINING, CAPITAL_ALLOCATION_EXCELLENT, CAPITAL_ALLOCATION_POOR
  Risk: DRAWDOWN_RISK, LEVERAGE_HIGH, LEVERAGE_OK, ACCOUNTING_RED_FLAG, GOVERNANCE_CONCERN, \
VOLATILITY_HIGH, VOLATILITY_LOW, LIQUIDITY_LOW
  Special: INSIDER_CLUSTER_BUY, INSIDER_CLUSTER_SELL, ACTIVIST_INVOLVED, \
SPINOFF_ANNOUNCED, POST_BANKRUPTCY
  Action: BUY_NEW, BUY_ADD, TRIM, SELL_FULL, HOLD, HOLD_STRONG, WATCHLIST_ADD, REJECT, \
REJECT_HARD, NO_ACTION
- CRITICAL: Use ONLY the tags listed above. Do NOT invent new tag names.
- Return ONLY valid JSON. No markdown, no code fences, no commentary outside the JSON.
"""


class KlarmanAgent(BaseAgent):
    """Margin of safety value analyst modeled on Seth Klarman.

    Provider: DeepSeek. Focus: downside protection, bear case, absolute value.
    """

    def __init__(self, gateway: LLMGateway) -> None:
        super().__init__(name="klarman", model="deepseek-reasoner")
        self.gateway = gateway

    def build_system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def build_user_prompt(self, request: AnalysisRequest) -> str:
        f = request.fundamentals
        parts = [
            f"Assess the margin of safety and downside risk for {request.ticker} "
            f"({request.sector} / {request.industry})",
            "",
            "FUNDAMENTALS:",
            f"  Price: ${f.price}",
            f"  Market Cap: ${float(f.market_cap):,.0f}",
            f"  Enterprise Value: ${float(f.enterprise_value):,.0f}",
            f"  Revenue: ${float(f.revenue):,.0f}",
            f"  Operating Income: ${float(f.operating_income):,.0f}",
            f"  Net Income: ${float(f.net_income):,.0f}",
            f"  Total Debt: ${float(f.total_debt):,.0f}",
            f"  Cash: ${float(f.cash):,.0f}",
            f"  Shares Outstanding: {float(f.shares_outstanding):,.0f}",
        ]
        if f.earnings_yield:
            parts.append(f"  Earnings Yield: {float(f.earnings_yield):.1%}")
        if f.roic:
            parts.append(f"  ROIC: {float(f.roic):.1%}")

        # Valuation multiples from technicals
        if request.technical_indicators:
            parts.append("\nVALUATION METRICS:")
            for k in ["trailing_pe", "forward_pe", "price_to_book", "price_to_sales",
                       "ev_to_ebitda", "free_cash_flow_yield", "peg_ratio",
                       "price_to_tangible_book"]:
                if k in request.technical_indicators:
                    parts.append(f"  {k}: {request.technical_indicators[k]}")

        # Filing context for accounting quality
        if request.filing_context:
            parts.append("\nSEC FILING CONTEXT:")
            fc = request.filing_context
            if isinstance(fc, dict):
                parts.append(f"  {json.dumps(fc, default=str)[:400]}")

        # Insider activity
        if request.insider_context:
            parts.append("\nINSIDER ACTIVITY:")
            for item in (request.insider_context or [])[:5]:
                if isinstance(item, dict):
                    parts.append(f"  - {json.dumps(item, default=str)[:200]}")

        # Institutional holders
        if request.institutional_context:
            parts.append("\nINSTITUTIONAL HOLDERS:")
            for item in (request.institutional_context or [])[:5]:
                if isinstance(item, dict):
                    parts.append(f"  - {json.dumps(item, default=str)[:200]}")

        if request.news_context:
            parts.append("\nRECENT NEWS:")
            for item in (request.news_context or [])[:3]:
                if isinstance(item, dict):
                    parts.append(f"  - {item.get('title', item.get('headline', str(item)))[:150]}")

        if request.previous_verdict:
            pv = request.previous_verdict
            parts.append(f"\nPREVIOUS VERDICT: {pv.get('verdict')} (conf: {pv.get('confidence')})")

        if request.pnl_pct is not None:
            parts.append(f"\nCURRENT P&L: {request.pnl_pct:+.1f}%")
        if request.entry_price is not None:
            parts.append(f"ENTRY PRICE: ${request.entry_price:.2f}")

        parts.append("\nANSWER: How much can I lose, and is the margin of safety wide enough?")
        return "\n".join(parts)

    def parse_response(self, raw: str, request: AnalysisRequest) -> "AgentSignalSet":
        return _parse_agent_response(raw, request, self.name, self.model, "Klarman")

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
