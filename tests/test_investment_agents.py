"""Tests for the AgentRunner + AgentSkill framework.

Validates that the generic AgentRunner correctly builds prompts, parses
responses, and routes calls via AgentSkill definitions — replacing the
individual agent class tests.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from investmentology.agents.base import AnalysisRequest, AnalysisResponse
from investmentology.agents.gateway import (
    LLMGateway,
    LLMResponse,
    ProviderConfig,
    RemoteCLIProviderConfig,
)
from investmentology.agents.runner import AgentRunner
from investmentology.agents.skills import SKILLS
from investmentology.models.signal import AgentSignalSet, SignalTag
from investmentology.models.stock import FundamentalsSnapshot


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def snapshot() -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        ticker="AAPL",
        fetched_at=datetime(2025, 1, 15, 12, 0, 0),
        operating_income=Decimal("100000"),
        market_cap=Decimal("500000"),
        total_debt=Decimal("50000"),
        cash=Decimal("30000"),
        current_assets=Decimal("80000"),
        current_liabilities=Decimal("40000"),
        net_ppe=Decimal("60000"),
        revenue=Decimal("400000"),
        net_income=Decimal("80000"),
        total_assets=Decimal("300000"),
        total_liabilities=Decimal("150000"),
        shares_outstanding=1000,
        price=Decimal("500"),
    )


@pytest.fixture
def basic_request(snapshot: FundamentalsSnapshot) -> AnalysisRequest:
    return AnalysisRequest(
        ticker="AAPL",
        fundamentals=snapshot,
        sector="Technology",
        industry="Consumer Electronics",
        quant_gate_rank=5,
        piotroski_score=8,
        altman_z_score=Decimal("3.5"),
    )


@pytest.fixture
def request_with_macro(basic_request: AnalysisRequest) -> AnalysisRequest:
    basic_request.macro_context = {
        "cpi": 3.2,
        "fed_rate": 5.25,
        "regime": "late_cycle",
    }
    return basic_request


@pytest.fixture
def request_with_technicals(basic_request: AnalysisRequest) -> AnalysisRequest:
    basic_request.technical_indicators = {
        "sma_50": 180.5,
        "sma_200": 170.2,
        "rsi_14": 62,
        "macd": 2.3,
        "macd_signal": 1.8,
        "obv": 1500000,
        "bb_upper": 195.0,
        "bb_lower": 165.0,
        "relative_strength_vs_spy": 1.05,
    }
    return basic_request


@pytest.fixture
def request_with_portfolio(basic_request: AnalysisRequest) -> AnalysisRequest:
    basic_request.portfolio_context = {
        "total_value": 1000000,
        "position_count": 15,
        "held_tickers": ["MSFT", "GOOG", "AMZN"],
        "sector_exposure": {"Technology": 25},
    }
    return basic_request


@pytest.fixture
def mock_gateway() -> LLMGateway:
    gw = LLMGateway()
    # Register remote CLI providers matching skill preferences
    for name in [
        "remote-warren", "remote-soros", "remote-auditor",
        "remote-dalio", "remote-druckenmiller", "remote-klarman",
        "remote-simons", "remote-lynch", "remote-data-analyst",
    ]:
        gw.register_remote_cli_provider(
            RemoteCLIProviderConfig(
                name=name,
                remote_url="http://test:9100",
                agent_name=name.replace("remote-", ""),
                auth_token="test-token",
            )
        )
    # Register API providers as fallbacks
    gw.register_provider(
        ProviderConfig(name="groq", base_url="http://test", api_key="test", default_model="llama-3.3-70b-versatile")
    )
    gw.register_provider(
        ProviderConfig(name="deepseek", base_url="http://test", api_key="test", default_model="deepseek-reasoner")
    )
    gw.call = AsyncMock()
    return gw


def _make_llm_response(content: str, provider: str = "test", model: str = "test-model") -> LLMResponse:
    return LLMResponse(
        content=content,
        model=model,
        provider=provider,
        token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        latency_ms=500,
    )


# ---------------------------------------------------------------------------
# Valid JSON responses for each agent type
# ---------------------------------------------------------------------------

WARREN_RESPONSE = json.dumps({
    "signals": [
        {"tag": "UNDERVALUED", "strength": "strong", "detail": "Trading at 60% of intrinsic value"},
        {"tag": "MOAT_WIDENING", "strength": "moderate", "detail": "Services ecosystem growing"},
        {"tag": "BUY_NEW", "strength": "strong", "detail": "Strong fundamental case"},
    ],
    "confidence": 0.78,
    "target_price": 215,
    "summary": "Apple shows strong fundamental value with widening moat.",
})

SOROS_RESPONSE = json.dumps({
    "signals": [
        {"tag": "REGIME_BULL", "strength": "moderate", "detail": "Expansion phase"},
        {"tag": "SECTOR_ROTATION_INTO", "strength": "strong", "detail": "Tech inflows"},
        {"tag": "HOLD", "strength": "moderate", "detail": "Macro favorable"},
    ],
    "confidence": 0.72,
    "target_price": None,
    "summary": "Macro conditions supportive for tech sector.",
})

SIMONS_RESPONSE = json.dumps({
    "signals": [
        {"tag": "TREND_UPTREND", "strength": "strong", "detail": "Above SMA 50 and 200"},
        {"tag": "MOMENTUM_STRONG", "strength": "moderate", "detail": "RSI at 62, MACD positive"},
        {"tag": "RELATIVE_STRENGTH_HIGH", "strength": "weak", "detail": "Slightly outperforming SPY"},
    ],
    "confidence": 0.75,
    "target_price": None,
    "summary": "Bullish technical setup with strong trend and momentum.",
})

AUDITOR_RESPONSE = json.dumps({
    "signals": [
        {"tag": "LEVERAGE_OK", "strength": "moderate", "detail": "Manageable debt levels"},
        {"tag": "LIQUIDITY_OK", "strength": "strong", "detail": "Current ratio above 2"},
        {"tag": "VOLATILITY_LOW", "strength": "weak", "detail": "30-day vol below average"},
    ],
    "confidence": 0.82,
    "target_price": None,
    "summary": "Low risk profile with strong balance sheet.",
})

# Map agent names to their test responses
AGENT_RESPONSES = {
    "warren": WARREN_RESPONSE,
    "soros": SOROS_RESPONSE,
    "simons": SIMONS_RESPONSE,
    "auditor": AUDITOR_RESPONSE,
}


# ===========================================================================
# AgentRunner Core Tests (parameterized across agents)
# ===========================================================================


class TestAgentRunnerProperties:
    """Test that AgentRunner exposes correct properties from AgentSkill."""

    @pytest.fixture(params=["warren", "soros", "simons", "auditor"])
    def runner(self, request, mock_gateway: LLMGateway) -> AgentRunner:
        return AgentRunner(SKILLS[request.param], mock_gateway)

    def test_name(self, runner: AgentRunner) -> None:
        assert runner.name == runner.skill.name

    def test_model(self, runner: AgentRunner) -> None:
        assert runner.model == runner.skill.default_model


class TestAgentRunnerSystemPrompt:
    """Test system prompt construction from skill fields."""

    @pytest.fixture(params=["warren", "soros", "simons", "auditor"])
    def runner(self, request, mock_gateway: LLMGateway) -> AgentRunner:
        return AgentRunner(SKILLS[request.param], mock_gateway)

    def test_includes_display_name(self, runner: AgentRunner) -> None:
        prompt = runner.build_system_prompt()
        assert runner.skill.display_name in prompt

    def test_includes_philosophy(self, runner: AgentRunner) -> None:
        prompt = runner.build_system_prompt()
        # Check philosophy content (first 50 chars to be safe with line wrapping)
        assert runner.skill.philosophy[:50] in prompt

    def test_includes_allowed_tags(self, runner: AgentRunner) -> None:
        prompt = runner.build_system_prompt()
        if runner.skill.allowed_tags:
            assert any(tag in prompt for tag in runner.skill.allowed_tags[:3])

    def test_includes_output_format(self, runner: AgentRunner) -> None:
        prompt = runner.build_system_prompt()
        assert "signals" in prompt
        assert "confidence" in prompt


# ===========================================================================
# Warren-specific Tests
# ===========================================================================


class TestWarrenRunner:
    @pytest.fixture
    def runner(self, mock_gateway: LLMGateway) -> AgentRunner:
        return AgentRunner(SKILLS["warren"], mock_gateway)

    def test_init(self, runner: AgentRunner) -> None:
        assert runner.name == "warren"
        assert runner.model == "claude-opus-4-6"

    def test_system_prompt_content(self, runner: AgentRunner) -> None:
        prompt = runner.build_system_prompt()
        assert "intrinsic value" in prompt.lower()
        assert "UNDERVALUED" in prompt

    def test_user_prompt_includes_fundamentals(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        prompt = runner.build_user_prompt(basic_request)
        assert "AAPL" in prompt
        assert "Technology" in prompt
        assert "Consumer Electronics" in prompt

    def test_user_prompt_includes_optional_data(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        prompt = runner.build_user_prompt(basic_request)
        assert "Quant Gate Rank: 5" in prompt
        assert "Piotroski F-Score: 8" in prompt
        assert "Altman Z-Score: 3.5" in prompt

    def test_user_prompt_omits_none_fields(
        self, runner: AgentRunner, snapshot: FundamentalsSnapshot,
    ) -> None:
        req = AnalysisRequest(
            ticker="MSFT",
            fundamentals=snapshot,
            sector="Technology",
            industry="Software",
        )
        prompt = runner.build_user_prompt(req)
        assert "Quant Gate Rank" not in prompt
        assert "Piotroski" not in prompt
        assert "Altman" not in prompt

    def test_parse_response_valid_json(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        result = runner.parse_response(WARREN_RESPONSE, basic_request)
        assert isinstance(result, AgentSignalSet)
        assert result.agent_name == "warren"
        assert result.model == "claude-opus-4-6"
        assert result.confidence == Decimal("0.78")
        assert result.target_price == Decimal("215")
        assert len(result.signals.signals) == 3
        assert result.signals.has(SignalTag.UNDERVALUED)
        assert result.signals.has(SignalTag.MOAT_WIDENING)
        assert result.signals.has(SignalTag.BUY_NEW)

    def test_analyze_calls_gateway(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        async def _run():
            runner.gateway.call.return_value = _make_llm_response(
                WARREN_RESPONSE, provider="remote-warren", model="claude-opus-4-6",
            )
            result = await runner.analyze(basic_request)

            assert isinstance(result, AnalysisResponse)
            assert result.agent_name == "warren"
            assert result.ticker == "AAPL"
            assert result.target_price == Decimal("215")
            assert result.latency_ms == 500
            assert result.token_usage is not None
            runner.gateway.call.assert_called_once()

        asyncio.run(_run())


# ===========================================================================
# Soros-specific Tests
# ===========================================================================


class TestSorosRunner:
    @pytest.fixture
    def runner(self, mock_gateway: LLMGateway) -> AgentRunner:
        return AgentRunner(SKILLS["soros"], mock_gateway)

    def test_init(self, runner: AgentRunner) -> None:
        assert runner.name == "soros"
        assert runner.model == "gemini-2.5-pro"

    def test_system_prompt_content(self, runner: AgentRunner) -> None:
        prompt = runner.build_system_prompt()
        assert "macro" in prompt.lower()
        assert "reflexivity" in prompt.lower()
        assert "REGIME_BULL" in prompt

    def test_user_prompt_with_macro(
        self, runner: AgentRunner, request_with_macro: AnalysisRequest,
    ) -> None:
        prompt = runner.build_user_prompt(request_with_macro)
        assert "AAPL" in prompt
        assert "cpi" in prompt
        assert "fed_rate" in prompt

    def test_user_prompt_no_macro(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        prompt = runner.build_user_prompt(basic_request)
        assert "AAPL" in prompt
        # macro_context is in optional_data but not set on basic_request

    def test_parse_response_valid_json(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        result = runner.parse_response(SOROS_RESPONSE, basic_request)
        assert isinstance(result, AgentSignalSet)
        assert result.agent_name == "soros"
        assert result.confidence == Decimal("0.72")
        assert len(result.signals.signals) == 3
        assert result.signals.has(SignalTag.REGIME_BULL)
        assert result.signals.has(SignalTag.SECTOR_ROTATION_INTO)

    def test_analyze_calls_gateway(
        self, runner: AgentRunner, request_with_macro: AnalysisRequest,
    ) -> None:
        async def _run():
            runner.gateway.call.return_value = _make_llm_response(
                SOROS_RESPONSE, provider="remote-soros", model="gemini-2.5-pro",
            )
            result = await runner.analyze(request_with_macro)

            assert isinstance(result, AnalysisResponse)
            assert result.agent_name == "soros"
            assert result.ticker == "AAPL"
            runner.gateway.call.assert_called_once()

        asyncio.run(_run())


# ===========================================================================
# Simons-specific Tests
# ===========================================================================


class TestSimonsRunner:
    @pytest.fixture
    def runner(self, mock_gateway: LLMGateway) -> AgentRunner:
        return AgentRunner(SKILLS["simons"], mock_gateway)

    def test_init(self, runner: AgentRunner) -> None:
        assert runner.name == "simons"
        assert runner.model == "llama-3.3-70b-versatile"

    def test_system_prompt_content(self, runner: AgentRunner) -> None:
        prompt = runner.build_system_prompt()
        assert "technical" in prompt.lower() or "quantitative" in prompt.lower()
        assert "TREND_UPTREND" in prompt

    def test_user_prompt_with_technicals(
        self, runner: AgentRunner, request_with_technicals: AnalysisRequest,
    ) -> None:
        prompt = runner.build_user_prompt(request_with_technicals)
        assert "AAPL" in prompt
        assert "sma_50" in prompt
        assert "rsi_14" in prompt
        assert "macd" in prompt

    def test_user_prompt_no_technicals_warns(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        prompt = runner.build_user_prompt(basic_request)
        assert "AAPL" in prompt
        assert "WARNING" in prompt or "No pre-computed" in prompt

    def test_parse_response_valid_json(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        # Use request_with_technicals would be better but basic_request still parses
        result = runner.parse_response(SIMONS_RESPONSE, basic_request)
        assert isinstance(result, AgentSignalSet)
        assert result.agent_name == "simons"
        # Without technicals, confidence is capped at 0.15
        assert result.confidence <= Decimal("0.15")

    def test_parse_response_with_technicals(
        self, runner: AgentRunner, request_with_technicals: AnalysisRequest,
    ) -> None:
        result = runner.parse_response(SIMONS_RESPONSE, request_with_technicals)
        assert result.confidence == Decimal("0.75")
        assert len(result.signals.signals) == 3
        assert result.signals.has(SignalTag.TREND_UPTREND)
        assert result.signals.has(SignalTag.MOMENTUM_STRONG)
        assert result.signals.has(SignalTag.RELATIVE_STRENGTH_HIGH)

    def test_analyze_calls_gateway(
        self, runner: AgentRunner, request_with_technicals: AnalysisRequest,
    ) -> None:
        async def _run():
            runner.gateway.call.return_value = _make_llm_response(
                SIMONS_RESPONSE, provider="groq", model="llama-3.3-70b-versatile",
            )
            result = await runner.analyze(request_with_technicals)

            assert isinstance(result, AnalysisResponse)
            assert result.agent_name == "simons"
            assert result.ticker == "AAPL"
            runner.gateway.call.assert_called_once()

        asyncio.run(_run())


# ===========================================================================
# Auditor-specific Tests
# ===========================================================================


class TestAuditorRunner:
    @pytest.fixture
    def runner(self, mock_gateway: LLMGateway) -> AgentRunner:
        return AgentRunner(SKILLS["auditor"], mock_gateway)

    def test_init(self, runner: AgentRunner) -> None:
        assert runner.name == "auditor"
        assert runner.model == "claude-opus-4-6"

    def test_system_prompt_content(self, runner: AgentRunner) -> None:
        prompt = runner.build_system_prompt()
        assert "risk" in prompt.lower()
        assert "LEVERAGE_HIGH" in prompt

    def test_user_prompt_with_portfolio(
        self, runner: AgentRunner, request_with_portfolio: AnalysisRequest,
    ) -> None:
        prompt = runner.build_user_prompt(request_with_portfolio)
        assert "AAPL" in prompt
        assert "Technology" in prompt

    def test_user_prompt_no_portfolio(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        prompt = runner.build_user_prompt(basic_request)
        assert "AAPL" in prompt

    def test_parse_response_valid_json(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        result = runner.parse_response(AUDITOR_RESPONSE, basic_request)
        assert isinstance(result, AgentSignalSet)
        assert result.agent_name == "auditor"
        assert result.confidence == Decimal("0.82")
        assert len(result.signals.signals) == 3
        assert result.signals.has(SignalTag.LEVERAGE_OK)
        assert result.signals.has(SignalTag.LIQUIDITY_OK)
        assert result.signals.has(SignalTag.VOLATILITY_LOW)

    def test_analyze_calls_gateway(
        self, runner: AgentRunner, request_with_portfolio: AnalysisRequest,
    ) -> None:
        async def _run():
            runner.gateway.call.return_value = _make_llm_response(
                AUDITOR_RESPONSE, provider="remote-auditor", model="claude-opus-4-6",
            )
            result = await runner.analyze(request_with_portfolio)

            assert isinstance(result, AnalysisResponse)
            assert result.agent_name == "auditor"
            assert result.ticker == "AAPL"
            runner.gateway.call.assert_called_once()

        asyncio.run(_run())


# ===========================================================================
# Cross-agent tests
# ===========================================================================


class TestSkillsRegistry:
    """Verify all expected skills exist in the SKILLS registry."""

    def test_all_agents_present(self) -> None:
        expected = {
            "warren", "soros", "simons", "auditor",
            "dalio", "druckenmiller", "klarman", "lynch",
            "data_analyst",
        }
        assert expected == set(SKILLS.keys())

    def test_all_skills_have_required_fields(self) -> None:
        for name, skill in SKILLS.items():
            assert skill.name == name
            assert skill.display_name
            assert skill.philosophy
            assert skill.role in ("primary", "scout", "validator")
            assert skill.provider_preference
            assert skill.default_model
            assert skill.methodology
            assert skill.output_format


class TestResponseParsing:
    """Cross-agent response parsing edge cases."""

    @pytest.fixture(params=["warren", "soros", "simons", "auditor"])
    def runner(self, request, mock_gateway: LLMGateway) -> AgentRunner:
        return AgentRunner(SKILLS[request.param], mock_gateway)

    def test_malformed_json_returns_empty(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        result = runner.parse_response("this is not json", basic_request)
        assert isinstance(result, AgentSignalSet)
        assert result.agent_name == runner.name
        assert len(result.signals.signals) == 0
        assert result.confidence == Decimal("0")

    def test_json_in_code_fence(
        self, runner: AgentRunner, basic_request: AnalysisRequest,
    ) -> None:
        response = AGENT_RESPONSES[runner.name]
        fenced = f"```json\n{response}\n```"
        result = runner.parse_response(fenced, basic_request)
        assert result.confidence > Decimal("0")

    def test_confidence_clamped_high(
        self, runner: AgentRunner, request_with_technicals: AnalysisRequest,
    ) -> None:
        # Use request_with_technicals to bypass Simons data gate (caps at 0.15 without technicals)
        data = {"signals": [], "confidence": 1.5, "target_price": None, "summary": "test"}
        result = runner.parse_response(json.dumps(data), request_with_technicals)
        assert result.confidence == Decimal("1")

    def test_confidence_clamped_low(
        self, runner: AgentRunner, request_with_technicals: AnalysisRequest,
    ) -> None:
        data = {"signals": [], "confidence": -0.5, "target_price": None, "summary": "test"}
        result = runner.parse_response(json.dumps(data), request_with_technicals)
        assert result.confidence == Decimal("0")


class TestStrengthNormalization:
    """All agents should normalize invalid strength values to 'moderate'."""

    AGENT_TAGS = {
        "warren": "UNDERVALUED",
        "soros": "REGIME_BULL",
        "simons": "TREND_UPTREND",
        "auditor": "LEVERAGE_HIGH",
    }

    @pytest.fixture(params=["warren", "soros", "simons", "auditor"])
    def runner_and_tag(self, request, mock_gateway: LLMGateway):
        name = request.param
        runner = AgentRunner(SKILLS[name], mock_gateway)
        return runner, self.AGENT_TAGS[name]

    def test_invalid_strength_normalized(
        self, runner_and_tag, request_with_technicals: AnalysisRequest,
    ) -> None:
        # Use request_with_technicals to bypass Simons data gate (adds NO_ACTION without technicals)
        runner, tag = runner_and_tag
        data = {
            "signals": [{"tag": tag, "strength": "INVALID", "detail": "test"}],
            "confidence": 0.5,
            "target_price": None,
            "summary": "test",
        }
        result = runner.parse_response(json.dumps(data), request_with_technicals)
        assert len(result.signals.signals) == 1
        assert result.signals.signals[0].strength == "moderate"


class TestProviderResolution:
    """Test that AgentRunner resolves providers from skill preferences."""

    def test_warren_resolves_remote(self, mock_gateway: LLMGateway) -> None:
        runner = AgentRunner(SKILLS["warren"], mock_gateway)
        # remote-warren is registered, should be first choice
        assert runner._resolve_provider() == "remote-warren"

    def test_simons_resolves_groq(self, mock_gateway: LLMGateway) -> None:
        runner = AgentRunner(SKILLS["simons"], mock_gateway)
        assert runner._resolve_provider() == "groq"

    def test_lynch_resolves_deepseek(self, mock_gateway: LLMGateway) -> None:
        runner = AgentRunner(SKILLS["lynch"], mock_gateway)
        assert runner._resolve_provider() == "deepseek"

    def test_fallback_when_first_unavailable(self) -> None:
        gw = LLMGateway()
        # Only register deepseek, not remote-warren or claude-cli
        gw.register_provider(
            ProviderConfig(name="deepseek", base_url="http://test", api_key="test", default_model="deepseek-reasoner")
        )
        runner = AgentRunner(SKILLS["warren"], gw)
        # Warren prefers remote-warren, claude-cli, deepseek — only deepseek available
        assert runner._resolve_provider() == "deepseek"
