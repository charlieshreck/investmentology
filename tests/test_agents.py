from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from investmentology.agents.base import AnalysisRequest, AnalysisResponse, BaseAgent
from investmentology.agents.gateway import (
    CLIProviderConfig,
    LLMGateway,
    LLMResponse,
    ProviderConfig,
    _RateLimiter,
)
from investmentology.models.signal import AgentSignalSet, Signal, SignalSet, SignalTag
from investmentology.models.stock import FundamentalsSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(**overrides) -> FundamentalsSnapshot:
    defaults = dict(
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
    defaults.update(overrides)
    return FundamentalsSnapshot(**defaults)


def _make_signal_set() -> AgentSignalSet:
    return AgentSignalSet(
        agent_name="test_agent",
        model="test-model",
        signals=SignalSet(
            signals=[Signal(tag=SignalTag.UNDERVALUED, strength="strong", detail="cheap")]
        ),
        confidence=Decimal("0.80"),
        reasoning="Test reasoning",
    )


class ConcreteAgent(BaseAgent):
    """Minimal concrete subclass for testing."""

    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        return AnalysisResponse(
            agent_name=self.name,
            model=self.model,
            ticker=request.ticker,
            signal_set=_make_signal_set(),
            summary="Test summary",
        )

    def build_system_prompt(self) -> str:
        return "You are a test agent."

    def build_user_prompt(self, request: AnalysisRequest) -> str:
        return f"Analyze {request.ticker}"

    def parse_response(self, raw: str, request: AnalysisRequest) -> AgentSignalSet:
        return _make_signal_set()


# ---------------------------------------------------------------------------
# AnalysisRequest
# ---------------------------------------------------------------------------


class TestAnalysisRequest:
    def test_minimal_creation(self):
        snap = _make_snapshot()
        req = AnalysisRequest(
            ticker="AAPL",
            fundamentals=snap,
            sector="Technology",
            industry="Consumer Electronics",
        )
        assert req.ticker == "AAPL"
        assert req.fundamentals is snap
        assert req.quant_gate_rank is None
        assert req.piotroski_score is None
        assert req.altman_z_score is None
        assert req.price_history is None
        assert req.macro_context is None
        assert req.portfolio_context is None
        assert req.technical_indicators is None

    def test_full_creation(self):
        snap = _make_snapshot()
        req = AnalysisRequest(
            ticker="MSFT",
            fundamentals=snap,
            sector="Technology",
            industry="Software",
            quant_gate_rank=5,
            piotroski_score=8,
            altman_z_score=Decimal("3.5"),
            price_history={"close": [100, 105, 110]},
            macro_context={"cpi": 3.2},
            portfolio_context={"current_weight": 0.05},
            technical_indicators={"rsi": 45},
        )
        assert req.quant_gate_rank == 5
        assert req.piotroski_score == 8
        assert req.altman_z_score == Decimal("3.5")
        assert req.price_history == {"close": [100, 105, 110]}
        assert req.macro_context == {"cpi": 3.2}
        assert req.portfolio_context == {"current_weight": 0.05}
        assert req.technical_indicators == {"rsi": 45}


# ---------------------------------------------------------------------------
# AnalysisResponse
# ---------------------------------------------------------------------------


class TestAnalysisResponse:
    def test_creation(self):
        sig_set = _make_signal_set()
        resp = AnalysisResponse(
            agent_name="warren",
            model="deepseek-reasoner",
            ticker="AAPL",
            signal_set=sig_set,
            summary="Strong buy candidate",
            target_price=Decimal("200"),
            token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            latency_ms=1500,
        )
        assert resp.agent_name == "warren"
        assert resp.model == "deepseek-reasoner"
        assert resp.ticker == "AAPL"
        assert resp.signal_set is sig_set
        assert resp.target_price == Decimal("200")
        assert resp.latency_ms == 1500
        assert isinstance(resp.timestamp, datetime)

    def test_defaults(self):
        sig_set = _make_signal_set()
        resp = AnalysisResponse(
            agent_name="soros",
            model="grok-3",
            ticker="TSLA",
            signal_set=sig_set,
            summary="Macro headwinds",
        )
        assert resp.target_price is None
        assert resp.token_usage is None
        assert resp.latency_ms == 0


# ---------------------------------------------------------------------------
# BaseAgent
# ---------------------------------------------------------------------------


class TestBaseAgent:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseAgent("test", "model")  # type: ignore[abstract]

    def test_concrete_subclass(self):
        agent = ConcreteAgent("warren", "deepseek-reasoner")
        assert agent.name == "warren"
        assert agent.model == "deepseek-reasoner"

    def test_build_system_prompt(self):
        agent = ConcreteAgent("test", "model")
        assert agent.build_system_prompt() == "You are a test agent."

    def test_build_user_prompt(self):
        agent = ConcreteAgent("test", "model")
        snap = _make_snapshot()
        req = AnalysisRequest(
            ticker="GOOG", fundamentals=snap, sector="Tech", industry="Search"
        )
        assert agent.build_user_prompt(req) == "Analyze GOOG"

    def test_parse_response(self):
        agent = ConcreteAgent("test", "model")
        snap = _make_snapshot()
        req = AnalysisRequest(
            ticker="GOOG", fundamentals=snap, sector="Tech", industry="Search"
        )
        result = agent.parse_response("raw text", req)
        assert isinstance(result, AgentSignalSet)
        assert result.agent_name == "test_agent"

    def test_analyze(self):
        async def _run():
            agent = ConcreteAgent("warren", "deepseek-reasoner")
            snap = _make_snapshot()
            req = AnalysisRequest(
                ticker="AAPL", fundamentals=snap, sector="Tech", industry="Hardware"
            )
            resp = await agent.analyze(req)
            assert isinstance(resp, AnalysisResponse)
            assert resp.agent_name == "warren"
            assert resp.ticker == "AAPL"
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# ProviderConfig
# ---------------------------------------------------------------------------


class TestProviderConfig:
    def test_defaults(self):
        cfg = ProviderConfig(
            name="test",
            base_url="https://api.test.com/v1",
            api_key="sk-test",
            default_model="test-model",
        )
        assert cfg.rpm_limit == 60
        assert cfg.timeout_seconds == 30
        assert cfg.max_retries == 3

    def test_custom_values(self):
        cfg = ProviderConfig(
            name="groq",
            base_url="https://api.groq.com/openai/v1",
            api_key="sk-groq",
            default_model="llama-3.3-70b-versatile",
            rpm_limit=30,
            timeout_seconds=15,
            max_retries=5,
        )
        assert cfg.rpm_limit == 30
        assert cfg.timeout_seconds == 15
        assert cfg.max_retries == 5


# ---------------------------------------------------------------------------
# _RateLimiter
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_acquire_tracks_timestamps(self):
        async def _run():
            limiter = _RateLimiter(rpm_limit=60)
            assert len(limiter._timestamps) == 0
            await limiter.acquire()
            assert len(limiter._timestamps) == 1
            await limiter.acquire()
            assert len(limiter._timestamps) == 2
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# LLMGateway
# ---------------------------------------------------------------------------


class TestLLMGateway:
    def test_register_provider(self):
        gw = LLMGateway()
        cfg = ProviderConfig(
            name="deepseek",
            base_url="https://api.deepseek.com/v1",
            api_key="sk-test",
            default_model="deepseek-reasoner",
        )
        gw.register_provider(cfg)
        assert "deepseek" in gw._providers
        assert "deepseek" in gw._limiters
        assert gw._providers["deepseek"] is cfg

    def test_call_unknown_provider(self):
        async def _run():
            gw = LLMGateway()
            with pytest.raises(ValueError, match="Unknown provider"):
                await gw.call("nonexistent", "sys", "user")
        asyncio.run(_run())

    def test_call_success(self):
        async def _run():
            gw = LLMGateway()
            gw.register_provider(
                ProviderConfig(
                    name="test",
                    base_url="https://api.test.com/v1",
                    api_key="sk-test",
                    default_model="test-model",
                    max_retries=1,
                )
            )

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {"content": "Analysis result"},
                        "finish_reason": "stop",
                    }
                ],
                "model": "test-model",
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }

            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.post.return_value = mock_response
            gw._client = mock_client

            result = await gw.call("test", "You are helpful.", "Analyze AAPL")

            assert isinstance(result, LLMResponse)
            assert result.content == "Analysis result"
            assert result.model == "test-model"
            assert result.provider == "test"
            assert result.token_usage["prompt_tokens"] == 100
            assert result.token_usage["completion_tokens"] == 50
            assert result.token_usage["total_tokens"] == 150
            assert result.finish_reason == "stop"
            assert result.latency_ms >= 0

            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args
            assert "chat/completions" in call_kwargs.args[0]
        asyncio.run(_run())

    def test_call_uses_custom_model(self):
        async def _run():
            gw = LLMGateway()
            gw.register_provider(
                ProviderConfig(
                    name="test",
                    base_url="https://api.test.com/v1",
                    api_key="sk-test",
                    default_model="default-model",
                    max_retries=1,
                )
            )

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "model": "custom-model",
                "usage": {},
            }

            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.post.return_value = mock_response
            gw._client = mock_client

            result = await gw.call(
                "test", "sys", "user", model="custom-model"
            )
            assert result.model == "custom-model"

            call_body = mock_client.post.call_args.kwargs["json"]
            assert call_body["model"] == "custom-model"
        asyncio.run(_run())

    def test_call_retry_on_failure(self):
        async def _run():
            gw = LLMGateway()
            gw.register_provider(
                ProviderConfig(
                    name="test",
                    base_url="https://api.test.com/v1",
                    api_key="sk-test",
                    default_model="test-model",
                    max_retries=3,
                )
            )

            # First two calls fail, third succeeds
            fail_response = MagicMock()
            fail_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500 Internal Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )

            ok_response = MagicMock()
            ok_response.raise_for_status = MagicMock()
            ok_response.json.return_value = {
                "choices": [{"message": {"content": "recovered"}, "finish_reason": "stop"}],
                "model": "test-model",
                "usage": {},
            }

            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.post.side_effect = [fail_response, fail_response, ok_response]
            gw._client = mock_client

            with patch("investmentology.agents.gateway.asyncio.sleep", new_callable=AsyncMock):
                result = await gw.call("test", "sys", "user")

            assert result.content == "recovered"
            assert mock_client.post.call_count == 3
        asyncio.run(_run())

    def test_call_raises_after_max_retries(self):
        async def _run():
            gw = LLMGateway()
            gw.register_provider(
                ProviderConfig(
                    name="test",
                    base_url="https://api.test.com/v1",
                    api_key="sk-test",
                    default_model="test-model",
                    max_retries=2,
                )
            )

            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.post.side_effect = httpx.RequestError("connection failed")
            gw._client = mock_client

            with patch("investmentology.agents.gateway.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(RuntimeError, match="failed after 2 retries"):
                    await gw.call("test", "sys", "user")

            assert mock_client.post.call_count == 2
        asyncio.run(_run())

    def test_call_anthropic_format(self):
        async def _run():
            gw = LLMGateway()
            gw.register_provider(
                ProviderConfig(
                    name="anthropic",
                    base_url="https://api.anthropic.com/v1",
                    api_key="sk-ant",
                    default_model="claude-sonnet-4-5-20250929",
                )
            )

            ok_response = MagicMock()
            ok_response.raise_for_status = MagicMock()
            ok_response.json.return_value = {
                "content": [{"type": "text", "text": '{"signals": [], "confidence": 0.7}'}],
                "model": "claude-sonnet-4-5-20250929",
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "stop_reason": "end_turn",
            }

            mock_client = AsyncMock(spec=httpx.AsyncClient)
            mock_client.post.return_value = ok_response
            gw._client = mock_client

            result = await gw.call("anthropic", "You are a risk analyst.", "Analyze AAPL")

            assert result.content == '{"signals": [], "confidence": 0.7}'
            assert result.provider == "anthropic"
            assert result.token_usage["prompt_tokens"] == 100
            assert result.token_usage["completion_tokens"] == 50
            assert result.token_usage["total_tokens"] == 150

            # Verify Anthropic-specific request format
            call_args = mock_client.post.call_args
            url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
            assert "/messages" in url
            call_body = call_args.kwargs["json"]
            assert "system" in call_body
            assert call_body["system"] == "You are a risk analyst."
            call_headers = call_args.kwargs["headers"]
            assert "x-api-key" in call_headers
            assert "anthropic-version" in call_headers
        asyncio.run(_run())

    def test_start_creates_client(self):
        async def _run():
            gw = LLMGateway()
            assert gw._client is None
            await gw.start()
            assert gw._client is not None
            await gw.close()
        asyncio.run(_run())

    def test_close_cleans_up(self):
        async def _run():
            gw = LLMGateway()
            await gw.start()
            assert gw._client is not None
            await gw.close()
            assert gw._client is None
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# LLMGateway.from_config
# ---------------------------------------------------------------------------


class TestLLMGatewayFromConfig:
    def test_all_keys_set(self):
        config = MagicMock()
        config.deepseek_api_key = "sk-ds"
        config.grok_api_key = "sk-grok"
        config.groq_api_key = "sk-groq"
        config.anthropic_api_key = "sk-ant"
        config.use_claude_cli = False
        config.use_gemini_cli = False

        gw = LLMGateway.from_config(config)
        assert "deepseek" in gw._providers
        assert "xai" in gw._providers
        assert "groq" in gw._providers
        assert "anthropic" in gw._providers
        assert len(gw._providers) == 4

    def test_no_keys_set(self):
        config = MagicMock()
        config.deepseek_api_key = ""
        config.grok_api_key = ""
        config.groq_api_key = ""
        config.anthropic_api_key = ""
        config.use_claude_cli = False
        config.use_gemini_cli = False

        gw = LLMGateway.from_config(config)
        assert len(gw._providers) == 0
        assert len(gw._cli_providers) == 0

    def test_partial_keys(self):
        config = MagicMock()
        config.deepseek_api_key = "sk-ds"
        config.grok_api_key = ""
        config.groq_api_key = "sk-groq"
        config.anthropic_api_key = ""
        config.use_claude_cli = False
        config.use_gemini_cli = False

        gw = LLMGateway.from_config(config)
        assert "deepseek" in gw._providers
        assert "xai" not in gw._providers
        assert "groq" in gw._providers
        assert "anthropic" not in gw._providers
        assert len(gw._providers) == 2

    def test_cli_providers(self):
        config = MagicMock()
        config.deepseek_api_key = "sk-ds"
        config.grok_api_key = ""
        config.groq_api_key = "sk-groq"
        config.anthropic_api_key = ""
        config.use_claude_cli = True
        config.use_gemini_cli = True

        gw = LLMGateway.from_config(config)
        assert "claude-cli" in gw._cli_providers
        assert "gemini-cli" in gw._cli_providers
        assert gw._cli_providers["claude-cli"].cli_command == "claude"
        assert gw._cli_providers["gemini-cli"].cli_command == "gemini"
        # HTTP API providers still registered
        assert "deepseek" in gw._providers
        assert "groq" in gw._providers

    def test_provider_configs_correct(self):
        config = MagicMock()
        config.deepseek_api_key = "sk-ds"
        config.grok_api_key = "sk-grok"
        config.groq_api_key = "sk-groq"
        config.anthropic_api_key = ""
        config.use_claude_cli = False
        config.use_gemini_cli = False

        gw = LLMGateway.from_config(config)

        ds = gw._providers["deepseek"]
        assert ds.api_key == "sk-ds"
        assert ds.default_model == "deepseek-reasoner"
        assert ds.timeout_seconds == 120

        xai = gw._providers["xai"]
        assert xai.api_key == "sk-grok"
        assert xai.default_model == "grok-3"

        groq = gw._providers["groq"]
        assert groq.api_key == "sk-groq"
        assert groq.default_model == "llama-3.3-70b-versatile"
        assert groq.rpm_limit == 30


# ---------------------------------------------------------------------------
# CLI Provider
# ---------------------------------------------------------------------------


class TestCLIProviderConfig:
    def test_defaults(self):
        cfg = CLIProviderConfig(name="claude-cli", cli_command="claude")
        assert cfg.timeout_seconds == 300
        assert cfg.default_model == ""

    def test_custom(self):
        cfg = CLIProviderConfig(
            name="gemini-cli",
            cli_command="gemini",
            default_model="gemini-2.5-pro",
            timeout_seconds=600,
        )
        assert cfg.cli_command == "gemini"
        assert cfg.default_model == "gemini-2.5-pro"


class TestCLIProviderRegistration:
    def test_register_cli_provider(self):
        gw = LLMGateway()
        cfg = CLIProviderConfig(name="claude-cli", cli_command="claude")
        gw.register_cli_provider(cfg)
        assert "claude-cli" in gw._cli_providers
        assert gw._cli_providers["claude-cli"] is cfg

    def test_call_dispatches_to_cli(self):
        """CLI providers are dispatched before HTTP provider lookup."""
        import json as json_mod

        async def _run():
            gw = LLMGateway()
            gw.register_cli_provider(
                CLIProviderConfig(
                    name="claude-cli",
                    cli_command="claude",
                    default_model="claude-opus-4-6",
                )
            )

            claude_output = json_mod.dumps({
                "type": "result",
                "subtype": "success",
                "result": '{"signals": [], "confidence": 0.8, "summary": "test"}',
                "cost_usd": 0.05,
                "session_id": "test-session",
            })

            mock_proc = AsyncMock()
            mock_proc.communicate.return_value = (
                claude_output.encode(),
                b"",
            )
            mock_proc.returncode = 0

            with patch("investmentology.agents.gateway.asyncio.create_subprocess_exec", return_value=mock_proc):
                with patch("investmentology.agents.gateway.asyncio.wait_for", return_value=mock_proc.communicate.return_value):
                    result = await gw._call_cli("claude-cli", "system", "user")

            assert isinstance(result, LLMResponse)
            assert result.provider == "claude-cli"
            assert '"signals"' in result.content

        asyncio.run(_run())


class TestCLIResponseParsers:
    def test_parse_claude_cli_success(self):
        import json as json_mod

        output = json_mod.dumps({
            "type": "result",
            "subtype": "success",
            "result": '{"signals": [{"tag": "LEVERAGE_HIGH"}], "confidence": 0.9}',
            "cost_usd": 0.03,
        })
        config = CLIProviderConfig(
            name="claude-cli", cli_command="claude", default_model="claude-opus-4-6"
        )
        result = LLMGateway._parse_claude_cli_output(output, "claude-cli", config, 5000)

        assert result.content == '{"signals": [{"tag": "LEVERAGE_HIGH"}], "confidence": 0.9}'
        assert result.model == "claude-opus-4-6"
        assert result.provider == "claude-cli"
        assert result.token_usage["cost_usd"] == 0.03
        assert result.latency_ms == 5000
        assert result.finish_reason == "stop"

    def test_parse_claude_cli_error(self):
        import json as json_mod

        output = json_mod.dumps({
            "type": "result",
            "subtype": "error",
            "result": "Something went wrong",
        })
        config = CLIProviderConfig(name="claude-cli", cli_command="claude")
        result = LLMGateway._parse_claude_cli_output(output, "claude-cli", config, 1000)
        assert result.finish_reason == "error"

    def test_parse_claude_cli_invalid_json(self):
        config = CLIProviderConfig(name="claude-cli", cli_command="claude")
        result = LLMGateway._parse_claude_cli_output(
            "not json at all", "claude-cli", config, 100
        )
        assert result.content == "not json at all"

    def test_parse_gemini_cli_success(self):
        import json as json_mod

        output = json_mod.dumps({
            "session_id": "test-123",
            "response": '{"signals": [{"tag": "REGIME_BULL"}], "confidence": 0.75}',
            "stats": {"input_tokens": 200, "output_tokens": 100},
        })
        config = CLIProviderConfig(
            name="gemini-cli", cli_command="gemini", default_model="gemini-2.5-pro"
        )
        result = LLMGateway._parse_gemini_cli_output(output, "gemini-cli", config, 3000)

        assert '{"signals"' in result.content
        assert result.model == "gemini-2.5-pro"
        assert result.token_usage["prompt_tokens"] == 200
        assert result.token_usage["completion_tokens"] == 100
        assert result.latency_ms == 3000

    def test_parse_gemini_cli_markdown_fenced(self):
        import json as json_mod

        output = json_mod.dumps({
            "session_id": "test-456",
            "response": '```json\n{"signals": [], "confidence": 0.6}\n```',
            "stats": {},
        })
        config = CLIProviderConfig(name="gemini-cli", cli_command="gemini")
        result = LLMGateway._parse_gemini_cli_output(output, "gemini-cli", config, 2000)

        # Markdown fences should be stripped
        assert "```" not in result.content
        assert '"signals"' in result.content

    def test_parse_gemini_cli_invalid_json(self):
        config = CLIProviderConfig(name="gemini-cli", cli_command="gemini")
        result = LLMGateway._parse_gemini_cli_output(
            "not json", "gemini-cli", config, 100
        )
        assert result.content == "not json"


# ---------------------------------------------------------------------------
# Agent Provider Resolution
# ---------------------------------------------------------------------------


class TestAgentProviderResolution:
    def test_auditor_prefers_claude_cli(self):
        from investmentology.agents.auditor import AuditorAgent

        gw = LLMGateway()
        gw.register_cli_provider(
            CLIProviderConfig(name="claude-cli", cli_command="claude", default_model="claude-opus-4-6")
        )
        gw.register_provider(
            ProviderConfig(name="anthropic", base_url="https://api.anthropic.com/v1",
                           api_key="sk-ant", default_model="claude-sonnet-4-5-20250929")
        )
        agent = AuditorAgent(gw)
        assert agent._provider == "claude-cli"
        assert agent.model == "claude-opus-4-6"

    def test_auditor_falls_back_to_anthropic(self):
        from investmentology.agents.auditor import AuditorAgent

        gw = LLMGateway()
        gw.register_provider(
            ProviderConfig(name="anthropic", base_url="https://api.anthropic.com/v1",
                           api_key="sk-ant", default_model="claude-sonnet-4-5-20250929")
        )
        agent = AuditorAgent(gw)
        assert agent._provider == "anthropic"
        assert agent.model == "claude-sonnet-4-5-20250929"

    def test_auditor_no_provider_raises(self):
        from investmentology.agents.auditor import AuditorAgent

        gw = LLMGateway()
        with pytest.raises(ValueError, match="Auditor requires"):
            AuditorAgent(gw)

    def test_soros_prefers_gemini_cli(self):
        from investmentology.agents.soros import SorosAgent

        gw = LLMGateway()
        gw.register_cli_provider(
            CLIProviderConfig(name="gemini-cli", cli_command="gemini", default_model="gemini-2.5-pro")
        )
        gw.register_provider(
            ProviderConfig(name="xai", base_url="https://api.x.ai/v1",
                           api_key="sk-grok", default_model="grok-3")
        )
        agent = SorosAgent(gw)
        assert agent._provider == "gemini-cli"
        assert agent.model == "gemini-2.5-pro"

    def test_soros_falls_back_to_xai(self):
        from investmentology.agents.soros import SorosAgent

        gw = LLMGateway()
        gw.register_provider(
            ProviderConfig(name="xai", base_url="https://api.x.ai/v1",
                           api_key="sk-grok", default_model="grok-3")
        )
        agent = SorosAgent(gw)
        assert agent._provider == "xai"
        assert agent.model == "grok-3"

    def test_soros_no_provider_raises(self):
        from investmentology.agents.soros import SorosAgent

        gw = LLMGateway()
        with pytest.raises(ValueError, match="Soros requires"):
            SorosAgent(gw)
