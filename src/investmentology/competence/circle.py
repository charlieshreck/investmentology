from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from decimal import Decimal

from investmentology.agents.gateway import LLMGateway

logger = logging.getLogger(__name__)


@dataclass
class CompetenceResult:
    in_circle: bool
    confidence: Decimal
    reasoning: str
    sector_familiarity: str  # "high", "medium", "low"


class CompetenceFilter:
    """Layer 2: Is this business within our circle of competence?

    Assesses whether a business model is comprehensible enough for
    us to make sound investment judgments about it.
    """

    PROVIDER = "deepseek"
    MODEL = "deepseek-chat"

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def assess(
        self,
        ticker: str,
        sector: str,
        industry: str,
        business_description: str,
    ) -> CompetenceResult:
        """Assess if the business is within our circle of competence."""
        prompt = self._build_prompt(ticker, sector, industry, business_description)
        response = await self._gateway.call(
            provider=self.PROVIDER,
            system_prompt=(
                "You are Warren Buffett's competence filter. "
                "Your job is to determine if a business is simple enough to understand "
                "and evaluate with confidence. Be honest about what you don't know."
            ),
            user_prompt=prompt,
            model=self.MODEL,
        )
        return self._parse_response(response.content)

    def _build_prompt(
        self,
        ticker: str,
        sector: str,
        industry: str,
        business_description: str,
    ) -> str:
        return f"""Evaluate whether {ticker} is within our circle of competence.

Sector: {sector}
Industry: {industry}
Business: {business_description}

Assess:
1. Is the business model simple and understandable?
2. Can we reasonably predict what the business looks like in 10 years?
3. Do we understand the key drivers of revenue and profitability?
4. How familiar are we with this sector?

Respond in JSON:
```json
{{
  "in_circle": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "explanation",
  "sector_familiarity": "high|medium|low"
}}
```"""

    def _parse_response(self, raw: str) -> CompetenceResult:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            logger.warning("Could not parse competence response, defaulting to out of circle")
            return CompetenceResult(
                in_circle=False,
                confidence=Decimal("0.3"),
                reasoning="Failed to parse LLM response",
                sector_familiarity="low",
            )

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            logger.warning("JSON decode error in competence response")
            return CompetenceResult(
                in_circle=False,
                confidence=Decimal("0.3"),
                reasoning="Failed to parse LLM response",
                sector_familiarity="low",
            )

        return CompetenceResult(
            in_circle=bool(data.get("in_circle", False)),
            confidence=Decimal(str(data.get("confidence", 0.5))),
            reasoning=data.get("reasoning", ""),
            sector_familiarity=data.get("sector_familiarity", "low"),
        )
