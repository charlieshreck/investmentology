"""ReAct Executor — multi-turn tool-use loop for LLM agents.

Manages the conversation between an LLM and a set of tools, allowing
the model to iteratively request data, reason about results, and
produce a final analysis.
"""

from __future__ import annotations

import logging
import time

from investmentology.agents.react.tools import ToolCatalog

logger = logging.getLogger(__name__)

# Safety limits
MAX_TURNS = 8
TIMEOUT_S = 120


class ReActExecutor:
    """Execute a ReAct loop: LLM calls tools, reasons, repeats until done."""

    def __init__(
        self,
        max_turns: int = MAX_TURNS,
        timeout_s: int = TIMEOUT_S,
    ) -> None:
        self.max_turns = max_turns
        self.timeout_s = timeout_s

    async def run(
        self,
        gateway,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        tool_catalog: ToolCatalog,
        tools_schema: list[dict],
    ) -> str:
        """Run the ReAct loop. Returns the final text response.

        Raises on timeout or if the LLM never produces a final answer.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        start = time.monotonic()
        tool_calls_made = 0

        for turn in range(self.max_turns):
            # Check overall timeout
            elapsed = time.monotonic() - start
            if elapsed > self.timeout_s:
                logger.warning(
                    "ReAct timeout after %.1fs (%d turns, %d tool calls)",
                    elapsed, turn, tool_calls_made,
                )
                break

            # Call LLM with tools
            response = await gateway.call_with_tools(
                provider=provider,
                model=model,
                messages=messages,
                tools=tools_schema,
            )

            # If no tool calls, we have the final answer
            if not response.tool_calls:
                logger.info(
                    "ReAct completed in %d turns, %d tool calls, %.1fs",
                    turn + 1, tool_calls_made, time.monotonic() - start,
                )
                return response.content or ""

            # Append assistant message with tool calls
            messages.append(response.to_assistant_message())

            # Execute each tool call
            for tc in response.tool_calls:
                tool_calls_made += 1
                logger.debug(
                    "ReAct tool call #%d: %s(%s)",
                    tool_calls_made, tc["name"], tc["arguments"],
                )
                result = await tool_catalog.execute(
                    tc["name"], tc["arguments"],
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

        # Max turns exhausted — request final answer without tools
        logger.info(
            "ReAct max turns reached (%d), requesting final answer",
            self.max_turns,
        )
        messages.append({
            "role": "user",
            "content": (
                "You have used all available tool calls. "
                "Provide your final analysis now based on the data gathered."
            ),
        })
        final = await gateway.call_with_tools(
            provider=provider,
            model=model,
            messages=messages,
            tools=[],  # No tools — force text response
        )
        return final.content or ""
