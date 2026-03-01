"""L3.5 Agent Debate: Cross-pollination round where agents review peer positions.

After initial L3 analysis, each agent sees a summary of all 4 stances and can
revise their confidence, signals, or target price (but NOT their sentiment
direction). Research shows this improves accuracy by ~13% (AI Hedge Fund).
"""

from __future__ import annotations

import logging

from investmentology.agents.base import AnalysisRequest, AnalysisResponse, BaseAgent
from investmentology.agents.gateway import LLMGateway

logger = logging.getLogger(__name__)

_DEBATE_SYSTEM = """\
You are participating in an investment debate. You have already provided your initial analysis.

Now you will see the positions of your peer analysts. Review their arguments, consider whether \
they raise valid points you missed, and provide a REVISED assessment.

Rules:
- You CANNOT change your overall direction (bullish/bearish/neutral)
- You CAN adjust your confidence level up or down
- You CAN add or remove signal tags based on peer arguments
- You CAN revise your target price
- Explain what changed and why in your summary

Return your revised analysis as JSON with the same structure as before:
{
    "signals": [{"tag": "...", "strength": "...", "detail": "..."}],
    "confidence": 0.XX,
    "target_price": NNN,
    "summary": "Revised assessment after peer review..."
}

Return ONLY valid JSON. No markdown, no code fences."""


def _format_stance(resp: AnalysisResponse) -> str:
    """Format an agent's stance as a readable summary for peers."""
    signals = resp.signal_set.signals.signals
    signal_tags = ", ".join(f"{s.tag.value}({s.strength})" for s in signals[:8])
    target = f"${resp.target_price}" if resp.target_price else "N/A"

    return (
        f"[{resp.agent_name.upper()}] (model: {resp.model})\n"
        f"  Confidence: {resp.signal_set.confidence}\n"
        f"  Target Price: {target}\n"
        f"  Key Signals: {signal_tags}\n"
        f"  Summary: {resp.summary[:300]}"
    )


class DebateOrchestrator:
    """Runs a debate round where agents review each other's positions."""

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def debate(
        self,
        agents: list[BaseAgent],
        responses: list[AnalysisResponse],
        request: AnalysisRequest,
    ) -> list[AnalysisResponse]:
        """Run one debate round. Returns revised responses.

        Args:
            agents: The agent instances (same order as responses).
            responses: Initial L3 responses from each agent.
            request: Original analysis request for context.

        Returns:
            List of revised AnalysisResponse objects. If an agent's
            debate call fails, the original response is kept.
        """
        if len(agents) != len(responses):
            logger.warning("Agent/response count mismatch, skipping debate")
            return responses

        # Format all stances for peer review
        all_stances = "\n\n".join(_format_stance(r) for r in responses)

        import asyncio
        tasks = [
            self._debate_single(agent, resp, all_stances, request)
            for agent, resp in zip(agents, responses)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        revised: list[AnalysisResponse] = []
        for i, result in enumerate(results):
            if isinstance(result, AnalysisResponse):
                revised.append(result)
                # Log confidence delta
                orig_conf = responses[i].signal_set.confidence
                new_conf = result.signal_set.confidence
                delta = new_conf - orig_conf
                if delta != 0:
                    logger.info(
                        "Debate: %s revised confidence %s -> %s (delta: %+.2f)",
                        result.agent_name, orig_conf, new_conf, delta,
                    )
            else:
                if isinstance(result, Exception):
                    logger.warning(
                        "Debate failed for %s: %s, keeping original",
                        responses[i].agent_name, result,
                    )
                revised.append(responses[i])

        return revised

    async def _debate_single(
        self,
        agent: BaseAgent,
        original: AnalysisResponse,
        all_stances: str,
        request: AnalysisRequest,
    ) -> AnalysisResponse:
        """Run debate for a single agent."""
        user_prompt = (
            f"Your initial analysis for {request.ticker}:\n"
            f"{_format_stance(original)}\n\n"
            f"Peer analyst positions:\n{all_stances}\n\n"
            f"Based on the peer positions above, provide your REVISED assessment. "
            f"Remember: you cannot change your overall direction, but you can adjust "
            f"confidence, signals, and target price."
        )

        # Determine provider for this agent
        provider = getattr(agent, "_provider", None)
        if provider is None:
            # Default provider resolution: check agent type
            if hasattr(agent, "gateway"):
                provider = _resolve_provider(agent)
            else:
                provider = "deepseek"

        model = agent.model

        llm_response = await self._gateway.call(
            provider=provider,
            system_prompt=_DEBATE_SYSTEM,
            user_prompt=user_prompt,
            model=model,
        )

        # Parse the revised response using the agent's own parser
        revised_signals = agent.parse_response(llm_response.content, request)
        revised_signals.token_usage = llm_response.token_usage
        revised_signals.latency_ms = llm_response.latency_ms

        return AnalysisResponse(
            agent_name=original.agent_name,
            model=original.model,
            ticker=original.ticker,
            signal_set=revised_signals,
            summary=revised_signals.reasoning,
            target_price=revised_signals.target_price,
            token_usage=llm_response.token_usage,
            latency_ms=llm_response.latency_ms,
        )


def _resolve_provider(agent: BaseAgent) -> str:
    """Resolve the LLM provider for an agent based on its type."""
    name = agent.name.lower()
    provider_map = {
        "warren": "deepseek",
        "soros": "gemini-cli",
        "simons": "groq",
        "auditor": "claude-cli",
    }
    return provider_map.get(name, "deepseek")
