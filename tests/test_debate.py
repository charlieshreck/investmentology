"""Tests for the L3.5 Agent Debate round."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from investmentology.agents.base import AnalysisRequest, AnalysisResponse
from investmentology.agents.debate import DebateOrchestrator, _format_stance, _resolve_provider
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag
from investmentology.models.stock import FundamentalsSnapshot
from datetime import datetime


def _make_fundamentals() -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        ticker="AAPL",
        fetched_at=datetime.now(),
        price=Decimal("180"),
        market_cap=Decimal("2800000000000"),
        revenue=Decimal("380000000000"),
        net_income=Decimal("95000000000"),
        operating_income=Decimal("110000000000"),
        total_debt=Decimal("110000000000"),
        cash=Decimal("60000000000"),
        total_assets=Decimal("350000000000"),
        total_liabilities=Decimal("280000000000"),
        current_assets=Decimal("140000000000"),
        current_liabilities=Decimal("150000000000"),
        net_ppe=Decimal("40000000000"),
        shares_outstanding=15000000000,
    )


def _make_request() -> AnalysisRequest:
    return AnalysisRequest(
        ticker="AAPL",
        fundamentals=_make_fundamentals(),
        sector="Technology",
        industry="Consumer Electronics",
    )


def _make_signal_set(agent_name: str, confidence: float = 0.7) -> AgentSignalSet:
    return AgentSignalSet(
        agent_name=agent_name,
        model="test-model",
        signals=SignalSet(signals=[
            Signal(tag=SignalTag.UNDERVALUED, strength="moderate", detail="test"),
        ]),
        confidence=Decimal(str(confidence)),
        reasoning=f"{agent_name} thinks AAPL is undervalued",
    )


def _make_response(agent_name: str, confidence: float = 0.7) -> AnalysisResponse:
    signal_set = _make_signal_set(agent_name, confidence)
    return AnalysisResponse(
        agent_name=agent_name,
        model="test-model",
        ticker="AAPL",
        signal_set=signal_set,
        summary=signal_set.reasoning,
        target_price=Decimal("200"),
    )


def _make_agent(name: str) -> MagicMock:
    agent = MagicMock()
    agent.name = name
    agent.model = "test-model"
    agent._provider = "deepseek"
    agent.parse_response.return_value = _make_signal_set(name, 0.8)
    return agent


class TestFormatStance:
    def test_formats_agent_stance(self):
        resp = _make_response("warren")
        result = _format_stance(resp)
        assert "[WARREN]" in result
        assert "0.7" in result
        assert "$200" in result
        assert "UNDERVALUED" in result

    def test_no_target_price(self):
        resp = _make_response("auditor")
        resp.target_price = None
        result = _format_stance(resp)
        assert "N/A" in result


class TestResolveProvider:
    def test_known_agents(self):
        for name, expected in [
            ("warren", "deepseek"),
            ("soros", "gemini-cli"),
            ("simons", "groq"),
            ("auditor", "claude-cli"),
        ]:
            agent = MagicMock()
            agent.name = name
            assert _resolve_provider(agent) == expected

    def test_unknown_agent(self):
        agent = MagicMock()
        agent.name = "unknown"
        assert _resolve_provider(agent) == "deepseek"


class TestDebateOrchestrator:
    def test_debate_revises_responses(self):
        gateway = MagicMock()
        gateway.call = AsyncMock(return_value=MagicMock(
            content='{"signals": [{"tag": "UNDERVALUED", "strength": "strong", "detail": "revised"}], "confidence": 0.85, "target_price": 210, "summary": "Revised after debate"}',
            token_usage={"input": 100, "output": 50},
            latency_ms=500,
        ))

        debate = DebateOrchestrator(gateway)
        agents = [_make_agent("warren"), _make_agent("soros")]
        responses = [_make_response("warren"), _make_response("soros")]
        request = _make_request()

        result = asyncio.run(debate.debate(agents, responses, request))
        assert len(result) == 2
        # Gateway should have been called twice (once per agent)
        assert gateway.call.call_count == 2

    def test_debate_keeps_original_on_failure(self):
        gateway = MagicMock()
        gateway.call = AsyncMock(side_effect=Exception("LLM down"))

        debate = DebateOrchestrator(gateway)
        agents = [_make_agent("warren")]
        responses = [_make_response("warren", 0.65)]
        request = _make_request()

        result = asyncio.run(debate.debate(agents, responses, request))
        assert len(result) == 1
        # Should keep original response
        assert result[0].signal_set.confidence == Decimal("0.65")

    def test_debate_skips_on_mismatch(self):
        gateway = MagicMock()
        debate = DebateOrchestrator(gateway)

        agents = [_make_agent("warren")]
        responses = [_make_response("warren"), _make_response("soros")]
        request = _make_request()

        result = asyncio.run(debate.debate(agents, responses, request))
        # Should return original responses unchanged
        assert len(result) == 2
        assert result[0].agent_name == "warren"

    def test_debate_prompt_includes_peer_stances(self):
        gateway = MagicMock()
        gateway.call = AsyncMock(return_value=MagicMock(
            content='{"signals": [], "confidence": 0.7, "target_price": null, "summary": "ok"}',
            token_usage={},
            latency_ms=100,
        ))

        debate = DebateOrchestrator(gateway)
        agents = [_make_agent("warren"), _make_agent("soros")]
        responses = [_make_response("warren"), _make_response("soros")]
        request = _make_request()

        asyncio.run(debate.debate(agents, responses, request))

        # Check that the user prompt sent to LLM includes peer stances
        call_args = gateway.call.call_args_list[0]
        user_prompt = call_args.kwargs.get("user_prompt", call_args[1].get("user_prompt", ""))
        assert "SOROS" in user_prompt or "WARREN" in user_prompt

    def test_debate_with_single_agent(self):
        gateway = MagicMock()
        debate = DebateOrchestrator(gateway)

        agents = [_make_agent("warren")]
        responses = [_make_response("warren")]
        request = _make_request()

        # Single agent: len(initial_responses) < 2 in orchestrator, but debate itself works
        # The orchestrator guards this; debate.debate() handles it
        result = asyncio.run(debate.debate(agents, responses, request))
        assert len(result) == 1
