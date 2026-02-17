from __future__ import annotations

import asyncio
import json
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from investmentology.agents.auditor import AuditorAgent
from investmentology.agents.base import AnalysisRequest, AnalysisResponse
from investmentology.agents.gateway import LLMGateway, LLMResponse
from investmentology.agents.simons import SimonsAgent
from investmentology.agents.soros import SorosAgent
from investmentology.agents.warren import WarrenAgent
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
        "current_weight": 0.05,
        "sector_weight": 0.25,
        "top_holdings": ["MSFT", "GOOG", "AMZN"],
        "total_positions": 15,
    }
    return basic_request


@pytest.fixture
def mock_gateway() -> LLMGateway:
    from investmentology.agents.gateway import CLIProviderConfig, ProviderConfig

    gw = LLMGateway()
    # Register providers so agent constructors can resolve their provider
    gw.register_provider(
        ProviderConfig(name="deepseek", base_url="http://test", api_key="test", default_model="deepseek-reasoner")
    )
    gw.register_provider(
        ProviderConfig(name="groq", base_url="http://test", api_key="test", default_model="llama-3.3-70b-versatile")
    )
    gw.register_provider(
        ProviderConfig(name="xai", base_url="http://test", api_key="test", default_model="grok-3")
    )
    gw.register_provider(
        ProviderConfig(name="anthropic", base_url="http://test", api_key="test", default_model="claude-sonnet-4-5-20250929")
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


# ===========================================================================
# Warren Agent Tests
# ===========================================================================


class TestWarrenAgent:
    def test_init(self, mock_gateway: LLMGateway) -> None:
        agent = WarrenAgent(mock_gateway)
        assert agent.name == "warren"
        assert agent.model == "deepseek-reasoner"
        assert agent.gateway is mock_gateway

    def test_build_system_prompt(self, mock_gateway: LLMGateway) -> None:
        agent = WarrenAgent(mock_gateway)
        prompt = agent.build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "fundamental" in prompt.lower()
        assert "intrinsic value" in prompt.lower()
        assert "UNDERVALUED" in prompt

    def test_build_user_prompt_includes_key_data(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = WarrenAgent(mock_gateway)
        prompt = agent.build_user_prompt(basic_request)
        assert "AAPL" in prompt
        assert "Technology" in prompt
        assert "Consumer Electronics" in prompt
        assert "Earnings Yield" in prompt
        assert "ROIC" in prompt
        assert "Quant Gate Rank: 5" in prompt
        assert "Piotroski F-Score: 8" in prompt
        assert "Altman Z-Score: 3.5" in prompt

    def test_build_user_prompt_omits_none_fields(
        self, mock_gateway: LLMGateway, snapshot: FundamentalsSnapshot
    ) -> None:
        agent = WarrenAgent(mock_gateway)
        req = AnalysisRequest(
            ticker="MSFT",
            fundamentals=snapshot,
            sector="Technology",
            industry="Software",
        )
        prompt = agent.build_user_prompt(req)
        assert "Quant Gate Rank" not in prompt
        assert "Piotroski" not in prompt
        assert "Altman" not in prompt

    def test_parse_response_valid_json(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = WarrenAgent(mock_gateway)
        result = agent.parse_response(WARREN_RESPONSE, basic_request)
        assert isinstance(result, AgentSignalSet)
        assert result.agent_name == "warren"
        assert result.model == "deepseek-reasoner"
        assert result.confidence == Decimal("0.78")
        assert result.target_price == Decimal("215")
        assert len(result.signals.signals) == 3
        assert result.signals.has(SignalTag.UNDERVALUED)
        assert result.signals.has(SignalTag.MOAT_WIDENING)
        assert result.signals.has(SignalTag.BUY_NEW)

    def test_parse_response_malformed_json(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = WarrenAgent(mock_gateway)
        result = agent.parse_response("this is not json", basic_request)
        assert isinstance(result, AgentSignalSet)
        assert result.agent_name == "warren"
        assert len(result.signals.signals) == 0
        assert result.confidence == Decimal("0")

    def test_parse_response_json_in_code_fence(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = WarrenAgent(mock_gateway)
        fenced = f"```json\n{WARREN_RESPONSE}\n```"
        result = agent.parse_response(fenced, basic_request)
        assert len(result.signals.signals) == 3
        assert result.confidence == Decimal("0.78")

    def test_parse_response_filters_invalid_tags(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = WarrenAgent(mock_gateway)
        data = {
            "signals": [
                {"tag": "UNDERVALUED", "strength": "strong", "detail": "cheap"},
                {"tag": "TREND_UPTREND", "strength": "strong", "detail": "wrong category"},
                {"tag": "TOTALLY_FAKE", "strength": "strong", "detail": "invalid tag"},
            ],
            "confidence": 0.5,
            "target_price": None,
            "summary": "test",
        }
        result = agent.parse_response(json.dumps(data), basic_request)
        assert len(result.signals.signals) == 1
        assert result.signals.has(SignalTag.UNDERVALUED)

    def test_parse_response_clamps_confidence(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = WarrenAgent(mock_gateway)
        data = {"signals": [], "confidence": 1.5, "target_price": None, "summary": "test"}
        result = agent.parse_response(json.dumps(data), basic_request)
        assert result.confidence == Decimal("1")

        data["confidence"] = -0.5
        result = agent.parse_response(json.dumps(data), basic_request)
        assert result.confidence == Decimal("0")

    def test_analyze_calls_gateway(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        async def _run():
            mock_gateway.call.return_value = _make_llm_response(
                WARREN_RESPONSE, provider="deepseek", model="deepseek-reasoner"
            )
            agent = WarrenAgent(mock_gateway)
            result = await agent.analyze(basic_request)

            assert isinstance(result, AnalysisResponse)
            assert result.agent_name == "warren"
            assert result.ticker == "AAPL"
            assert result.target_price == Decimal("215")
            assert result.latency_ms == 500
            assert result.token_usage is not None

            mock_gateway.call.assert_called_once()
            call_kwargs = mock_gateway.call.call_args.kwargs
            assert call_kwargs["provider"] == "deepseek"
            assert call_kwargs["model"] == "deepseek-reasoner"
        asyncio.run(_run())


# ===========================================================================
# Soros Agent Tests
# ===========================================================================


class TestSorosAgent:
    def test_init(self, mock_gateway: LLMGateway) -> None:
        agent = SorosAgent(mock_gateway)
        assert agent.name == "soros"
        assert agent.model == "grok-3"

    def test_build_system_prompt(self, mock_gateway: LLMGateway) -> None:
        agent = SorosAgent(mock_gateway)
        prompt = agent.build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "macro" in prompt.lower()
        assert "reflexivity" in prompt.lower()
        assert "REGIME_BULL" in prompt

    def test_build_user_prompt_includes_key_data(
        self, mock_gateway: LLMGateway, request_with_macro: AnalysisRequest
    ) -> None:
        agent = SorosAgent(mock_gateway)
        prompt = agent.build_user_prompt(request_with_macro)
        assert "AAPL" in prompt
        assert "Technology" in prompt
        assert "Macro Context" in prompt
        assert "cpi" in prompt
        assert "fed_rate" in prompt

    def test_build_user_prompt_no_macro_context(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = SorosAgent(mock_gateway)
        prompt = agent.build_user_prompt(basic_request)
        assert "AAPL" in prompt
        assert "Macro Context" not in prompt

    def test_parse_response_valid_json(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = SorosAgent(mock_gateway)
        result = agent.parse_response(SOROS_RESPONSE, basic_request)
        assert isinstance(result, AgentSignalSet)
        assert result.agent_name == "soros"
        assert result.confidence == Decimal("0.72")
        assert len(result.signals.signals) == 3
        assert result.signals.has(SignalTag.REGIME_BULL)
        assert result.signals.has(SignalTag.SECTOR_ROTATION_INTO)

    def test_parse_response_malformed_json(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = SorosAgent(mock_gateway)
        result = agent.parse_response("{invalid json!!!", basic_request)
        assert isinstance(result, AgentSignalSet)
        assert len(result.signals.signals) == 0
        assert result.confidence == Decimal("0")

    def test_parse_response_filters_non_macro_tags(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = SorosAgent(mock_gateway)
        data = {
            "signals": [
                {"tag": "REGIME_BULL", "strength": "strong", "detail": "expansion"},
                {"tag": "UNDERVALUED", "strength": "strong", "detail": "wrong category"},
            ],
            "confidence": 0.6,
            "target_price": None,
            "summary": "test",
        }
        result = agent.parse_response(json.dumps(data), basic_request)
        assert len(result.signals.signals) == 1
        assert result.signals.has(SignalTag.REGIME_BULL)

    def test_analyze_calls_gateway(
        self, mock_gateway: LLMGateway, request_with_macro: AnalysisRequest
    ) -> None:
        async def _run():
            mock_gateway.call.return_value = _make_llm_response(
                SOROS_RESPONSE, provider="xai", model="grok-3"
            )
            agent = SorosAgent(mock_gateway)
            result = await agent.analyze(request_with_macro)

            assert isinstance(result, AnalysisResponse)
            assert result.agent_name == "soros"
            assert result.ticker == "AAPL"

            call_kwargs = mock_gateway.call.call_args.kwargs
            assert call_kwargs["provider"] == "xai"
            assert call_kwargs["model"] == "grok-3"
        asyncio.run(_run())


# ===========================================================================
# Simons Agent Tests
# ===========================================================================


class TestSimonsAgent:
    def test_init(self, mock_gateway: LLMGateway) -> None:
        agent = SimonsAgent(mock_gateway)
        assert agent.name == "simons"
        assert agent.model == "llama-3.3-70b-versatile"

    def test_build_system_prompt(self, mock_gateway: LLMGateway) -> None:
        agent = SimonsAgent(mock_gateway)
        prompt = agent.build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "technical" in prompt.lower()
        assert "Do NOT calculate" in prompt
        assert "TREND_UPTREND" in prompt

    def test_build_user_prompt_includes_indicators(
        self, mock_gateway: LLMGateway, request_with_technicals: AnalysisRequest
    ) -> None:
        agent = SimonsAgent(mock_gateway)
        prompt = agent.build_user_prompt(request_with_technicals)
        assert "AAPL" in prompt
        assert "Pre-Computed Technical Indicators" in prompt
        assert "sma_50" in prompt
        assert "rsi_14" in prompt
        assert "macd" in prompt

    def test_build_user_prompt_no_indicators(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = SimonsAgent(mock_gateway)
        prompt = agent.build_user_prompt(basic_request)
        assert "AAPL" in prompt
        assert "Pre-Computed Technical Indicators" not in prompt

    def test_parse_response_valid_json(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = SimonsAgent(mock_gateway)
        result = agent.parse_response(SIMONS_RESPONSE, basic_request)
        assert isinstance(result, AgentSignalSet)
        assert result.agent_name == "simons"
        assert result.confidence == Decimal("0.75")
        assert len(result.signals.signals) == 3
        assert result.signals.has(SignalTag.TREND_UPTREND)
        assert result.signals.has(SignalTag.MOMENTUM_STRONG)
        assert result.signals.has(SignalTag.RELATIVE_STRENGTH_HIGH)

    def test_parse_response_malformed_json(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = SimonsAgent(mock_gateway)
        result = agent.parse_response("completely broken", basic_request)
        assert isinstance(result, AgentSignalSet)
        assert len(result.signals.signals) == 0
        assert result.confidence == Decimal("0")

    def test_parse_response_filters_non_technical_tags(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = SimonsAgent(mock_gateway)
        data = {
            "signals": [
                {"tag": "TREND_UPTREND", "strength": "strong", "detail": "bullish"},
                {"tag": "LEVERAGE_HIGH", "strength": "strong", "detail": "wrong category"},
            ],
            "confidence": 0.7,
            "target_price": None,
            "summary": "test",
        }
        result = agent.parse_response(json.dumps(data), basic_request)
        assert len(result.signals.signals) == 1
        assert result.signals.has(SignalTag.TREND_UPTREND)

    def test_analyze_calls_gateway(
        self, mock_gateway: LLMGateway, request_with_technicals: AnalysisRequest
    ) -> None:
        async def _run():
            mock_gateway.call.return_value = _make_llm_response(
                SIMONS_RESPONSE, provider="groq", model="llama-3.3-70b-versatile"
            )
            agent = SimonsAgent(mock_gateway)
            result = await agent.analyze(request_with_technicals)

            assert isinstance(result, AnalysisResponse)
            assert result.agent_name == "simons"
            assert result.ticker == "AAPL"

            call_kwargs = mock_gateway.call.call_args.kwargs
            assert call_kwargs["provider"] == "groq"
            assert call_kwargs["model"] == "llama-3.3-70b-versatile"
        asyncio.run(_run())


# ===========================================================================
# Auditor Agent Tests
# ===========================================================================


class TestAuditorAgent:
    def test_init(self, mock_gateway: LLMGateway) -> None:
        agent = AuditorAgent(mock_gateway)
        assert agent.name == "auditor"
        assert agent.model == "claude-sonnet-4-5-20250929"

    def test_build_system_prompt(self, mock_gateway: LLMGateway) -> None:
        agent = AuditorAgent(mock_gateway)
        prompt = agent.build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "risk" in prompt.lower()
        assert "independently" in prompt.lower()
        assert "LEVERAGE_HIGH" in prompt

    def test_build_user_prompt_includes_key_data(
        self, mock_gateway: LLMGateway, request_with_portfolio: AnalysisRequest
    ) -> None:
        agent = AuditorAgent(mock_gateway)
        prompt = agent.build_user_prompt(request_with_portfolio)
        assert "AAPL" in prompt
        assert "Technology" in prompt
        assert "Total Debt" in prompt
        assert "Portfolio Context" in prompt
        assert "current_weight" in prompt

    def test_build_user_prompt_no_portfolio_context(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = AuditorAgent(mock_gateway)
        prompt = agent.build_user_prompt(basic_request)
        assert "AAPL" in prompt
        assert "Portfolio Context" not in prompt

    def test_parse_response_valid_json(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = AuditorAgent(mock_gateway)
        result = agent.parse_response(AUDITOR_RESPONSE, basic_request)
        assert isinstance(result, AgentSignalSet)
        assert result.agent_name == "auditor"
        assert result.confidence == Decimal("0.82")
        assert len(result.signals.signals) == 3
        assert result.signals.has(SignalTag.LEVERAGE_OK)
        assert result.signals.has(SignalTag.LIQUIDITY_OK)
        assert result.signals.has(SignalTag.VOLATILITY_LOW)

    def test_parse_response_malformed_json(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = AuditorAgent(mock_gateway)
        result = agent.parse_response("not valid {json", basic_request)
        assert isinstance(result, AgentSignalSet)
        assert len(result.signals.signals) == 0
        assert result.confidence == Decimal("0")

    def test_parse_response_filters_non_risk_tags(
        self, mock_gateway: LLMGateway, basic_request: AnalysisRequest
    ) -> None:
        agent = AuditorAgent(mock_gateway)
        data = {
            "signals": [
                {"tag": "LEVERAGE_HIGH", "strength": "strong", "detail": "high debt"},
                {"tag": "UNDERVALUED", "strength": "strong", "detail": "wrong category"},
                {"tag": "REVIEW_REQUIRED", "strength": "moderate", "detail": "needs review"},
            ],
            "confidence": 0.6,
            "target_price": None,
            "summary": "test",
        }
        result = agent.parse_response(json.dumps(data), basic_request)
        assert len(result.signals.signals) == 2
        assert result.signals.has(SignalTag.LEVERAGE_HIGH)
        assert result.signals.has(SignalTag.REVIEW_REQUIRED)

    def test_analyze_calls_gateway(
        self, mock_gateway: LLMGateway, request_with_portfolio: AnalysisRequest
    ) -> None:
        async def _run():
            mock_gateway.call.return_value = _make_llm_response(
                AUDITOR_RESPONSE, provider="anthropic", model="claude-sonnet-4-5-20250929"
            )
            agent = AuditorAgent(mock_gateway)
            result = await agent.analyze(request_with_portfolio)

            assert isinstance(result, AnalysisResponse)
            assert result.agent_name == "auditor"
            assert result.ticker == "AAPL"

            call_kwargs = mock_gateway.call.call_args.kwargs
            assert call_kwargs["provider"] == "anthropic"
            assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
        asyncio.run(_run())


# ===========================================================================
# Cross-agent tests
# ===========================================================================


class TestAgentExports:
    """Verify all agents are exported from the package."""

    def test_imports(self) -> None:
        from investmentology.agents import (
            AuditorAgent,
            SimonsAgent,
            SorosAgent,
            WarrenAgent,
        )

        assert AuditorAgent is not None
        assert SimonsAgent is not None
        assert SorosAgent is not None
        assert WarrenAgent is not None


class TestStrengthNormalization:
    """All agents should normalize invalid strength values to 'moderate'."""

    @pytest.fixture(params=["warren", "soros", "simons", "auditor"])
    def agent_and_tag(self, request, mock_gateway: LLMGateway):
        agents = {
            "warren": (WarrenAgent(mock_gateway), "UNDERVALUED"),
            "soros": (SorosAgent(mock_gateway), "REGIME_BULL"),
            "simons": (SimonsAgent(mock_gateway), "TREND_UPTREND"),
            "auditor": (AuditorAgent(mock_gateway), "LEVERAGE_HIGH"),
        }
        return agents[request.param]

    def test_invalid_strength_normalized(
        self, agent_and_tag, basic_request: AnalysisRequest
    ) -> None:
        agent, tag = agent_and_tag
        data = {
            "signals": [{"tag": tag, "strength": "INVALID", "detail": "test"}],
            "confidence": 0.5,
            "target_price": None,
            "summary": "test",
        }
        result = agent.parse_response(json.dumps(data), basic_request)
        assert len(result.signals.signals) == 1
        assert result.signals.signals[0].strength == "moderate"
