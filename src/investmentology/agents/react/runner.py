"""ReAct Runner — AgentRunner subclass that uses tool-use loops.

Overrides the single-shot ``analyze()`` with a multi-turn ReAct loop
where the LLM can call data tools to gather information iteratively.
Falls back to standard single-shot on any failure.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from investmentology.agents.base import AnalysisRequest, AnalysisResponse
from investmentology.agents.gateway import LLMGateway
from investmentology.agents.react.executor import ReActExecutor
from investmentology.agents.react.tools import ToolCatalog
from investmentology.agents.runner import AgentRunner
from investmentology.agents.skills import AgentSkill

logger = logging.getLogger(__name__)


class ReActRunner(AgentRunner):
    """Agent runner that uses ReAct tool-use loop instead of single-shot."""

    def __init__(
        self,
        skill: AgentSkill,
        gateway: LLMGateway,
        tool_catalog: ToolCatalog,
    ) -> None:
        super().__init__(skill, gateway)
        self.tool_catalog = tool_catalog
        self.executor = ReActExecutor()

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """Run ReAct analysis with tool access. Falls back to single-shot."""
        try:
            return await self._react_analyze(request)
        except Exception:
            logger.warning(
                "ReAct failed for %s/%s, falling back to single-shot",
                self.skill.name, request.ticker,
                exc_info=True,
            )
            return await super().analyze(request)

    async def _react_analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """Execute the ReAct loop and parse the result."""
        system_prompt = self.build_system_prompt()
        user_prompt = self._build_react_prompt(request)
        tools_schema = self.tool_catalog.openai_schema()

        provider = self._resolve_provider()

        raw = await self.executor.run(
            gateway=self.gateway,
            provider=provider,
            model=self.skill.default_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            tool_catalog=self.tool_catalog,
            tools_schema=tools_schema,
        )

        signal_set = self.parse_response(raw, request)

        return AnalysisResponse(
            agent_name=self.skill.name,
            model=self.skill.default_model,
            ticker=request.ticker,
            signal_set=signal_set,
            summary=signal_set.reasoning,
            target_price=signal_set.target_price,
            timestamp=datetime.now(),
        )

    def _build_react_prompt(self, request: AnalysisRequest) -> str:
        """Build a lighter prompt for ReAct — let the LLM fetch what it needs.

        Provides essential context (ticker, sector, position info) but tells
        the agent to use tools for technical indicators, news, etc.
        """
        parts: list[str] = []

        # Opening
        parts.append(
            f"Analyze {request.ticker} ({request.sector} / {request.industry})."
        )
        parts.append("")
        parts.append(
            "You have access to data tools. Use them to gather the technical "
            "indicators, price history, news, earnings, and any other data "
            "you need for your analysis. Start by getting technical indicators "
            "and price history, then decide what else to investigate."
        )

        # Basic fundamentals (always available, gives price context)
        f = request.fundamentals
        parts.extend([
            "",
            "BASIC CONTEXT:",
            f"  Price: ${f.price}",
            f"  Market Cap: ${float(f.market_cap):,.0f}",
            f"  Revenue: ${float(f.revenue):,.0f}",
        ])

        # Position context if held
        if request.portfolio_context:
            pc = request.portfolio_context
            parts.extend([
                "",
                "POSITION CONTEXT:",
                f"  Currently held: YES",
            ])
            if pc.get("avg_cost"):
                parts.append(f"  Avg cost: ${pc['avg_cost']:.2f}")
            if pc.get("thesis_health"):
                parts.append(f"  Thesis health: {pc['thesis_health']}")

        # Previous verdict if available
        if request.previous_verdict:
            pv = request.previous_verdict
            parts.extend([
                "",
                f"PREVIOUS VERDICT: {pv.get('verdict')} "
                f"(confidence: {pv.get('confidence')})",
            ])

        # Closing instruction
        parts.extend([
            "",
            "After gathering data via tools, provide your analysis in the "
            "required JSON format. Focus on technical setup, momentum, and "
            "risk signals.",
        ])

        if self.skill.signature_question:
            parts.append("")
            parts.append(self.skill.signature_question)

        return "\n".join(parts)
