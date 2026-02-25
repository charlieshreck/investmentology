from __future__ import annotations

import json
import logging
from decimal import Decimal

from investmentology.agents.base import AnalysisRequest, AnalysisResponse, BaseAgent
from investmentology.agents.gateway import LLMGateway
from investmentology.compatibility.taxonomy import ACTION_TAGS, RISK_TAGS
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag

logger = logging.getLogger(__name__)

_VALID_TAGS = RISK_TAGS | ACTION_TAGS

_SYSTEM_PROMPT = """\
You are a risk analyst — the portfolio's devil's advocate.

Your task: Independently assess the risk profile of the given stock. Check concentration risk, \
correlation with existing holdings, accounting quality, leverage, liquidity, and governance.

IMPORTANT: You run independently of other analysts. You have NOT seen any other agents' \
analysis. Provide your own unbiased risk assessment.

Return your analysis as JSON with this exact structure:
{
    "signals": [
        {"tag": "LEVERAGE_HIGH", "strength": "strong", "detail": "Debt/equity ratio of 3.2x"},
        {"tag": "ACCOUNTING_RED_FLAG", "strength": "moderate", "detail": "Receivables growing faster than revenue"}
    ],
    "confidence": 0.82,
    "target_price": null,
    "summary": "Brief summary of your risk assessment..."
}

Rules:
- "strength" must be one of: "strong", "moderate", "weak"
- "confidence" is a float between 0.0 and 1.0
- "target_price" is optional for risk analysis (use null if not applicable)
- Use ONLY these signal tags for your analysis:
  Risk: CONCENTRATION, CORRELATION_HIGH, CORRELATION_LOW, LIQUIDITY_LOW, LIQUIDITY_OK, \
DRAWDOWN_RISK, ACCOUNTING_RED_FLAG, GOVERNANCE_CONCERN, LEVERAGE_HIGH, LEVERAGE_OK, \
VOLATILITY_HIGH, VOLATILITY_LOW, SECTOR_OVERWEIGHT, SECTOR_UNDERWEIGHT
  Action: BUY_NEW, BUY_ADD, TRIM, SELL_FULL, SELL_PARTIAL, HOLD, HOLD_STRONG, \
WATCHLIST_ADD, WATCHLIST_REMOVE, WATCHLIST_PROMOTE, REJECT, REJECT_HARD, NO_ACTION, \
REVIEW_REQUIRED, CONFLICT_FLAG
- Return ONLY valid JSON. No markdown, no code fences, no commentary outside the JSON."""


class AuditorAgent(BaseAgent):
    """Risk analyst -- the portfolio's devil's advocate.

    Provider: Claude (via CLI subscription or Anthropic API).
    Focus: risk, correlation, portfolio impact.
    IMPORTANT: Runs INDEPENDENTLY -- never sees other agents' outputs.
    Signal category: Risk/Portfolio (14 tags).
    """

    # Provider preference: claude-cli (subscription) > anthropic (API)
    PROVIDER_PREFERENCE = ["claude-cli", "anthropic"]

    def __init__(self, gateway: LLMGateway) -> None:
        self.gateway = gateway
        provider, model = self._resolve_provider(gateway)
        super().__init__(name="auditor", model=model)
        self._provider = provider

    @classmethod
    def _resolve_provider(cls, gateway: LLMGateway) -> tuple[str, str]:
        """Pick best available provider for the Auditor."""
        if "claude-cli" in gateway._cli_providers:
            cfg = gateway._cli_providers["claude-cli"]
            return "claude-cli", cfg.default_model or "claude-opus-4-6"
        if "anthropic" in gateway._providers:
            cfg = gateway._providers["anthropic"]
            return "anthropic", cfg.default_model
        raise ValueError(
            "Auditor requires claude-cli (USE_CLAUDE_CLI=1) or anthropic API key"
        )

    def build_system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def build_user_prompt(self, request: AnalysisRequest) -> str:
        f = request.fundamentals
        parts = [
            f"Assess risk profile for {request.ticker} ({request.sector} / {request.industry})",
            "",
            "Key Fundamentals:",
            f"  Price: ${f.price}",
            f"  Market Cap: ${f.market_cap:,}",
            f"  Revenue: ${f.revenue:,}",
            f"  Net Income: ${f.net_income:,}",
            f"  Total Debt: ${f.total_debt:,}",
            f"  Cash: ${f.cash:,}",
            f"  Total Assets: ${f.total_assets:,}",
            f"  Total Liabilities: ${f.total_liabilities:,}",
            f"  Current Assets: ${f.current_assets:,}",
            f"  Current Liabilities: ${f.current_liabilities:,}",
        ]

        if request.portfolio_context:
            pc = request.portfolio_context
            parts.append("")
            parts.append("Portfolio Risk Context:")
            parts.append(f"  Total portfolio value: ${pc.get('total_value', 0):,.0f}")
            parts.append(f"  Number of positions: {pc.get('position_count', 0)}")
            # Concentration analysis
            held = pc.get("held_tickers", [])
            if request.ticker in held:
                parts.append(f"  ALREADY HOLDS {request.ticker}:")
                for pos in pc.get("positions", []):
                    if pos.get("ticker") == request.ticker:
                        parts.append(f"    Current weight: {pos.get('weight_pct', 0):.1f}%")
                        parts.append(f"    P&L: {pos.get('pnl_pct', 0):+.1f}%")
                        if pos.get("weight_pct", 0) > 10:
                            parts.append("    WARNING: Position >10% of portfolio — concentration risk")
                        break
                parts.append("  Assess: Does adding more increase concentration risk unacceptably?")
            # Sector concentration
            se = pc.get("sector_exposure", {})
            if se:
                candidate_pct = se.get(request.sector, 0)
                parts.append(f"  Sector exposure ({request.sector}): {candidate_pct:.0f}%")
                if candidate_pct > 30:
                    parts.append(f"  WARNING: {request.sector} at {candidate_pct:.0f}% — sector overweight risk")
                # Show all sector weights for full picture
                sorted_se = sorted(se.items(), key=lambda x: x[1], reverse=True)
                if len(sorted_se) > 1:
                    parts.append("  Full sector exposure:")
                    for sector, pct in sorted_se:
                        marker = " <<" if sector == request.sector else ""
                        parts.append(f"    {sector}: {pct:.0f}%{marker}")
            # Position-level risks
            positions = pc.get("positions", [])
            losers = [p for p in positions if p.get("pnl_pct", 0) < -10]
            if losers:
                parts.append(f"  Portfolio has {len(losers)} position(s) down >10%:")
                for l in losers[:3]:
                    parts.append(f"    {l['ticker']}: {l['pnl_pct']:+.1f}%")

        # Social sentiment — risk signal (extreme sentiment = risk)
        if request.social_sentiment:
            agg = request.social_sentiment.get("aggregate", {})
            if agg:
                parts.append("")
                parts.append("Social Sentiment Risk:")
                bias = agg.get("bias", "unknown")
                pos_ratio = agg.get("positive_ratio", "N/A")
                mentions = agg.get("total_mentions", 0)
                parts.append(f"  Bias: {bias}, Positive ratio: {pos_ratio}, Mentions: {mentions}")
                if mentions > 100:
                    parts.append("  HIGH social attention — potential for sentiment-driven volatility")
                if pos_ratio and (float(pos_ratio) > 0.85 or float(pos_ratio) < 0.15):
                    parts.append("  EXTREME sentiment reading — elevated risk of mean-reversion")

                # Insider transactions (governance/alignment signal)
        if request.insider_context:
            parts.append("")
            parts.append("Insider Transactions (recent):")
            for t in request.insider_context[:5]:
                name = t.get("name", "Unknown")[:30]
                tx_type = t.get("transaction_type", "other")
                change = t.get("change", 0)
                tx_date = t.get("transaction_date", "")[:10]
                parts.append(f"  {tx_date} {name}: {tx_type} ({change:+,} shares)")

        # Earnings surprises (accounting quality signal)
        if request.earnings_context:
            ec = request.earnings_context
            surprises = ec.get("recent_surprises", [])
            if surprises:
                parts.append("")
                parts.append("Recent Earnings Surprises:")
                for s in surprises:
                    period = s.get("period", "?")
                    actual = s.get("actual_eps")
                    est = s.get("estimated_eps")
                    pct = s.get("surprise_pct")
                    if actual is not None and est is not None:
                        parts.append(f"  {period}: actual={actual} vs est={est} ({pct:+.1f}%)" if pct else f"  {period}: actual={actual} vs est={est}")

        # Recent news (headline risk)
        if request.news_context:
            parts.append("")
            parts.append("Recent News (check for risk signals):")
            for item in request.news_context[:3]:
                headline = item.get("headline", "")[:100]
                parts.append(f"  - {headline}")

        # 10-K risk factors (red flag detection)
        if request.filing_context and request.filing_context.get("risk_factors"):
            parts.append("")
            parts.append(f"10-K Risk Factors ({request.filing_context.get('filing_date', 'recent')}):")
            parts.append(f"  {request.filing_context['risk_factors'][:2000]}")

        # Institutional holders (ownership concentration)
        if request.institutional_context:
            parts.append("")
            parts.append("Institutional Ownership (13F):")
            for h in request.institutional_context[:5]:
                name = h.get("name", "Unknown")[:40]
                shares = h.get("shares", 0)
                parts.append(f"  {name}: {shares:,} shares")

        if request.previous_verdict:
            pv = request.previous_verdict
            parts.append("")
            parts.append("Previous Analysis Context:")
            parts.append(f"  Last verdict: {pv.get('verdict')} on {pv.get('date', 'unknown date')}")
            parts.append(f"  Confidence: {pv.get('confidence')}, Consensus: {pv.get('consensus_score')}")
            if pv.get("reasoning"):
                parts.append(f"  Reasoning: {pv['reasoning'][:200]}")
            parts.append("  Consider: Have risk factors changed since the last analysis?")

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
                        "Auditor: failed to parse JSON from %s response for %s",
                        self.model,
                        request.ticker,
                    )
                    return self._empty_signal_set()
            else:
                logger.warning(
                    "Auditor: failed to parse JSON from %s response for %s",
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
                logger.warning("Auditor: unknown signal tag %r, skipping", tag_str)
                continue
            if tag not in _VALID_TAGS:
                logger.warning("Auditor: tag %s not in risk/action set, skipping", tag)
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
