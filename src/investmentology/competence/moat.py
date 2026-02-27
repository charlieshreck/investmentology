from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal

from investmentology.agents.gateway import LLMGateway
from investmentology.models.stock import FundamentalsSnapshot

logger = logging.getLogger(__name__)


@dataclass
class MoatAssessment:
    moat_type: str  # "wide", "narrow", "none"
    sources: list[str]  # e.g., ["network_effects", "brand", "switching_costs"]
    trajectory: str  # "widening", "stable", "narrowing"
    durability_years: int  # Estimated years moat persists
    confidence: Decimal
    reasoning: str


class MoatAnalyzer:
    """Analyze competitive moat depth and durability."""

    PROVIDER = "deepseek"
    MODEL = "deepseek-chat"

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def analyze(
        self,
        ticker: str,
        sector: str,
        fundamentals: FundamentalsSnapshot,
    ) -> MoatAssessment:
        """Assess moat type, sources, trajectory."""
        prompt = self._build_prompt(ticker, sector, fundamentals)
        response = await self._gateway.call(
            provider=self.PROVIDER,
            system_prompt=(
                "You are a competitive strategy analyst specializing in economic moats. "
                "Assess moat depth using the Morningstar framework: "
                "network effects, intangible assets (brand/patents), "
                "cost advantages, switching costs, efficient scale."
            ),
            user_prompt=prompt,
            model=self.MODEL,
        )
        return self._parse_response(response.content)

    def _build_prompt(
        self,
        ticker: str,
        sector: str,
        fundamentals: FundamentalsSnapshot,
    ) -> str:
        roic = fundamentals.roic
        roic_str = f"{roic:.2%}" if roic is not None else "N/A"
        margin = (
            fundamentals.net_income / fundamentals.revenue
            if fundamentals.revenue > 0
            else Decimal("0")
        )

        debt_ratio = (
            fundamentals.total_liabilities / fundamentals.total_assets
            if fundamentals.total_assets > 0
            else Decimal("0")
        )

        return f"""Analyze the competitive moat for {ticker} (sector: {sector}).

Key financials:
- ROIC: {roic_str}
- Net margin: {margin:.2%}
- Market cap: ${fundamentals.market_cap:,.0f}
- Revenue: ${fundamentals.revenue:,.0f}
- Debt/Assets: {debt_ratio:.2%}

Assess:
1. Moat type: "wide" (durable 10+ year advantage), "narrow" (5-10 year), or "none"
2. Moat sources: network_effects, brand, patents, switching_costs, cost_advantages, efficient_scale
3. Trajectory: is the moat "widening", "stable", or "narrowing"?
4. Estimated durability in years
5. Confidence in assessment (0.0-1.0)

Respond in JSON:
```json
{{
  "moat_type": "wide|narrow|none",
  "sources": ["source1", "source2"],
  "trajectory": "widening|stable|narrowing",
  "durability_years": 10,
  "confidence": 0.7,
  "reasoning": "explanation"
}}
```"""

    def _parse_response(self, raw: str) -> MoatAssessment:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            logger.warning("Could not parse moat response, defaulting to no moat")
            return MoatAssessment(
                moat_type="none",
                sources=[],
                trajectory="stable",
                durability_years=0,
                confidence=Decimal("0.3"),
                reasoning="Failed to parse LLM response",
            )

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            logger.warning("JSON decode error in moat response")
            return MoatAssessment(
                moat_type="none",
                sources=[],
                trajectory="stable",
                durability_years=0,
                confidence=Decimal("0.3"),
                reasoning="Failed to parse LLM response",
            )

        return MoatAssessment(
            moat_type=data.get("moat_type", "none"),
            sources=data.get("sources", []),
            trajectory=data.get("trajectory", "stable"),
            durability_years=int(data.get("durability_years", 0)),
            confidence=Decimal(str(data.get("confidence", 0.5))),
            reasoning=data.get("reasoning", ""),
        )
