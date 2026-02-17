from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PreMortemResult:
    narrative: str  # "It's 2028, we lost 50% on AAPL because..."
    key_risks: list[str]
    probability_estimate: str
    base_rates: str = ""  # Historical base rate context used


def build_premortem_prompt(ticker: str, thesis: str, entry_price: str) -> str:
    """Build pre-mortem prompt.

    'It is 2 years from now. Your investment in {ticker} has lost 50%.
    Write the story of what happened.'
    """
    return f"""It is 2 years from now. Your investment in {ticker} at ${entry_price} has LOST 50%.

Original thesis:
{thesis}

Write the story of what happened. Be specific and realistic.

Then provide:
1. The top 3-5 key risks that led to this outcome
2. An overall probability estimate for this loss scenario: "unlikely" (<20%), "possible" (20-40%), "plausible" (40-60%), "likely" (>60%)

Respond in JSON format:
```json
{{
  "narrative": "It's [date]. Here's what happened to {ticker}...",
  "key_risks": ["risk 1", "risk 2", "risk 3"],
  "probability_estimate": "unlikely|possible|plausible|likely"
}}
```

Be brutally honest. Don't sugarcoat the failure scenario."""


def parse_premortem(raw: str) -> PreMortemResult:
    """Parse pre-mortem narrative from LLM."""
    # Try to extract JSON from the response
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not json_match:
        logger.warning("Could not find JSON in premortem response, using raw text")
        return PreMortemResult(
            narrative=raw.strip(),
            key_risks=[],
            probability_estimate="unknown",
        )

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        logger.warning("Failed to parse premortem JSON, using raw text")
        return PreMortemResult(
            narrative=raw.strip(),
            key_risks=[],
            probability_estimate="unknown",
        )

    return PreMortemResult(
        narrative=data.get("narrative", ""),
        key_risks=data.get("key_risks", []),
        probability_estimate=data.get("probability_estimate", "unknown"),
    )
