from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class KillScenario:
    scenario: str
    likelihood: str  # "low", "medium", "high"
    impact: str  # "moderate", "severe", "fatal"
    timeframe: str  # "1-2 years", "3-5 years", etc.


def build_kill_company_prompt(ticker: str, sector: str, fundamentals_summary: str) -> str:
    """Build the 'Kill the Company' prompt.

    Ask LLM: 'You are trying to destroy {ticker}. What are the top 5 ways
    this business could fail in the next 3-5 years?'
    """
    return f"""You are a ruthless competitor trying to destroy {ticker} (sector: {sector}).

Fundamentals:
{fundamentals_summary}

Your task: Identify the top 5 most realistic ways this business could FAIL in the next 3-5 years. Think like a short seller, a disruptive competitor, or a hostile regulator.

For each scenario, provide:
1. The specific scenario / threat
2. Likelihood: "low", "medium", or "high"
3. Impact if it occurs: "moderate", "severe", or "fatal"
4. Timeframe: when this could realistically happen

Respond in JSON format:
```json
[
  {{
    "scenario": "description of how the company fails",
    "likelihood": "low|medium|high",
    "impact": "moderate|severe|fatal",
    "timeframe": "1-2 years|3-5 years|5+ years"
  }}
]
```

Be specific and realistic. No generic risks -- focus on threats unique to {ticker} and its {sector} position."""


def parse_kill_scenarios(raw: str) -> list[KillScenario]:
    """Parse LLM response into structured kill scenarios."""
    # Try to extract JSON from the response
    # Look for JSON array in the text (possibly wrapped in ```json blocks)
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not json_match:
        logger.warning("Could not find JSON array in kill company response")
        return []

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        logger.warning("Failed to parse kill company JSON response")
        return []

    scenarios: list[KillScenario] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        scenarios.append(
            KillScenario(
                scenario=item.get("scenario", ""),
                likelihood=item.get("likelihood", "medium"),
                impact=item.get("impact", "moderate"),
                timeframe=item.get("timeframe", "3-5 years"),
            )
        )

    return scenarios
