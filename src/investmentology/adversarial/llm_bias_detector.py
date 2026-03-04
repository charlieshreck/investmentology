"""LLM-augmented cognitive bias detection.

Runs alongside keyword-based detection from biases.py.
Uses DeepSeek (same provider as Kill The Company) for cost efficiency.
"""

from __future__ import annotations

import json
import logging

from investmentology.adversarial.biases import COGNITIVE_BIASES, BiasResult

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a cognitive bias analyst reviewing investment reasoning.
Given agent analyses of a stock, identify any cognitive biases present.

Available biases to check (only flag those clearly present):
{bias_list}

Respond with a JSON array. Each item: {{"bias": "Bias Name", "detail": "Brief explanation of how this bias manifests in the reasoning"}}.
If no biases are found, respond with [].
Only output the JSON array, nothing else."""


async def detect_biases_llm(
    gateway,
    agent_signals: list,
    ticker: str,
) -> list[BiasResult]:
    """LLM-based bias detection across all agent reasoning.

    Args:
        gateway: LLMGateway instance.
        agent_signals: List of AgentSignalSet with reasoning.
        ticker: Stock ticker being analyzed.

    Returns:
        List of flagged BiasResult objects.
    """
    if not agent_signals:
        return []

    bias_list = "\n".join(
        f"- {b.name}: {b.description}" for b in COGNITIVE_BIASES
    )
    system = _SYSTEM_PROMPT.format(bias_list=bias_list)

    reasoning_parts = []
    for s in agent_signals:
        name = getattr(s, "agent_name", "Agent")
        reasoning = getattr(s, "reasoning", "")
        if reasoning:
            reasoning_parts.append(f"[{name}]: {reasoning[:500]}")

    if not reasoning_parts:
        return []

    user_msg = f"Ticker: {ticker}\n\nAgent analyses:\n" + "\n\n".join(reasoning_parts)

    try:
        response = await gateway.call(
            provider="deepseek",
            system_prompt=system,
            user_prompt=user_msg,
            max_tokens=1000,
        )

        # Parse JSON response
        text = response.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
        items = json.loads(text)

        results = []
        valid_names = {b.name for b in COGNITIVE_BIASES}
        for item in items:
            name = item.get("bias", "")
            detail = item.get("detail", "")
            if name in valid_names and detail:
                results.append(BiasResult(
                    bias_name=name,
                    is_flagged=True,
                    detail=f"[LLM] {detail}",
                ))
        return results

    except Exception:
        logger.warning("LLM bias detection failed, falling back to keyword-only", exc_info=True)
        return []


def merge_bias_flags(
    keyword_flags: list[BiasResult],
    llm_flags: list[BiasResult],
) -> list[BiasResult]:
    """Merge keyword and LLM bias results. LLM detail takes precedence when both flag the same bias."""
    by_name: dict[str, BiasResult] = {}

    for r in keyword_flags:
        by_name[r.bias_name] = r

    for r in llm_flags:
        if r.bias_name in by_name:
            # Both flagged — use LLM detail (more informative)
            by_name[r.bias_name] = BiasResult(
                bias_name=r.bias_name,
                is_flagged=True,
                detail=r.detail,
            )
        else:
            by_name[r.bias_name] = r

    return list(by_name.values())
