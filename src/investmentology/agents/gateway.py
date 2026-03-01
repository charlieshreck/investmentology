from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    token_usage: dict  # {"prompt_tokens": N, "completion_tokens": M, "total_tokens": T}
    latency_ms: int
    finish_reason: str = "stop"


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_key: str
    default_model: str
    rpm_limit: int = 60
    timeout_seconds: int = 30
    max_retries: int = 3


@dataclass
class CLIProviderConfig:
    """Configuration for a CLI-based LLM provider (claude, gemini)."""

    name: str  # e.g. "claude-cli", "gemini-cli"
    cli_command: str  # "claude" or "gemini"
    default_model: str = ""  # For tracking; actual model determined by subscription
    timeout_seconds: int = 300  # CLI calls can be slow


@dataclass
class RemoteCLIProviderConfig:
    """Configuration for a remote CLI provider proxied via HTTP."""

    name: str  # e.g. "remote-soros", "remote-auditor"
    remote_url: str  # e.g. "http://10.10.0.101:9100"
    agent_name: str  # "soros" or "auditor"
    auth_token: str
    default_model: str = ""
    timeout_seconds: int = 300


@dataclass
class _RateLimiter:
    """Simple sliding window rate limiter."""

    rpm_limit: int
    _timestamps: list[float] = field(default_factory=list)

    async def acquire(self) -> None:
        """Wait until rate limit allows a request."""
        now = time.monotonic()
        # Remove timestamps older than 60s
        self._timestamps = [t for t in self._timestamps if now - t < 60]
        if len(self._timestamps) >= self.rpm_limit:
            wait = 60 - (now - self._timestamps[0])
            if wait > 0:
                logger.info("Rate limit: waiting %.1fs", wait)
                await asyncio.sleep(wait)
        self._timestamps.append(time.monotonic())


class LLMGateway:
    """Multi-provider LLM gateway supporting both HTTP APIs and CLI tools.

    HTTP providers use OpenAI-compatible chat completions format, with
    Anthropic's Messages API handled transparently.

    CLI providers invoke local CLI tools (claude, gemini) via subprocess
    for subscription-based usage.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderConfig] = {}
        self._cli_providers: dict[str, CLIProviderConfig] = {}
        self._remote_cli_providers: dict[str, RemoteCLIProviderConfig] = {}
        self._limiters: dict[str, _RateLimiter] = {}
        self._client: httpx.AsyncClient | None = None

    def register_provider(self, config: ProviderConfig) -> None:
        """Register an HTTP API provider."""
        self._providers[config.name] = config
        self._limiters[config.name] = _RateLimiter(rpm_limit=config.rpm_limit)

    def register_cli_provider(self, config: CLIProviderConfig) -> None:
        """Register a CLI-based provider (claude, gemini)."""
        self._cli_providers[config.name] = config

    def register_remote_cli_provider(self, config: RemoteCLIProviderConfig) -> None:
        """Register a remote CLI provider (proxied via HTTP to HB LXC)."""
        self._remote_cli_providers[config.name] = config

    async def start(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def call(
        self,
        provider: str,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Call an LLM provider (HTTP API, CLI subprocess, or remote CLI proxy)."""
        # Dispatch CLI providers (local)
        if provider in self._cli_providers:
            return await self._call_cli(provider, system_prompt, user_prompt)

        # Dispatch remote CLI providers (HB LXC proxy)
        if provider in self._remote_cli_providers:
            return await self._call_remote_cli(provider, system_prompt, user_prompt)

        if provider not in self._providers:
            raise ValueError(f"Unknown provider: {provider}")

        config = self._providers[provider]
        limiter = self._limiters[provider]
        target_model = model or config.default_model

        if not self._client:
            await self.start()

        # Rate limit
        await limiter.acquire()

        is_anthropic = provider == "anthropic"

        # Build request (Anthropic uses a different format)
        if is_anthropic:
            url = f"{config.base_url}/messages"
            headers = {
                "x-api-key": config.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            body = {
                "model": target_model,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        else:
            url = f"{config.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": target_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

        # Retry loop
        last_error: Exception | None = None
        for attempt in range(config.max_retries):
            try:
                start_time = time.monotonic()
                response = await self._client.post(
                    url,
                    json=body,
                    headers=headers,
                    timeout=config.timeout_seconds,
                )
                latency_ms = int((time.monotonic() - start_time) * 1000)

                response.raise_for_status()
                data = response.json()

                # Parse response (Anthropic format differs from OpenAI)
                if is_anthropic:
                    content = ""
                    for block in data.get("content", []):
                        if block.get("type") == "text":
                            content += block.get("text", "")
                    usage = data.get("usage", {})
                    return LLMResponse(
                        content=content,
                        model=data.get("model", target_model),
                        provider=provider,
                        token_usage={
                            "prompt_tokens": usage.get("input_tokens", 0),
                            "completion_tokens": usage.get("output_tokens", 0),
                            "total_tokens": usage.get("input_tokens", 0)
                            + usage.get("output_tokens", 0),
                        },
                        latency_ms=latency_ms,
                        finish_reason=data.get("stop_reason", "end_turn"),
                    )

                choice = data["choices"][0]
                usage = data.get("usage", {})

                return LLMResponse(
                    content=choice["message"]["content"],
                    model=data.get("model", target_model),
                    provider=provider,
                    token_usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                    latency_ms=latency_ms,
                    finish_reason=choice.get("finish_reason", "stop"),
                )
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                last_error = e
                if attempt < config.max_retries - 1:
                    wait = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        "Provider %s attempt %d failed: %s. Retrying in %ds",
                        provider,
                        attempt + 1,
                        e,
                        wait,
                    )
                    await asyncio.sleep(wait)

        raise RuntimeError(
            f"Provider {provider} failed after {config.max_retries} retries: {last_error}"
        )

    async def _call_cli(
        self, provider: str, system_prompt: str, user_prompt: str
    ) -> LLMResponse:
        """Call a CLI-based provider via async subprocess."""
        config = self._cli_providers[provider]
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"

        if config.cli_command == "claude":
            cmd = ["claude", "-p", combined_prompt, "--output-format", "json"]
        elif config.cli_command == "gemini":
            cmd = [
                "gemini",
                "-p",
                combined_prompt,
                "-o",
                "json",
                "--yolo",
            ]
        else:
            raise ValueError(f"Unsupported CLI command: {config.cli_command}")

        logger.info("CLI provider %s: invoking %s", provider, config.cli_command)
        start_time = time.monotonic()

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=config.timeout_seconds
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(
                f"CLI provider {provider} timed out after {config.timeout_seconds}s"
            )

        latency_ms = int((time.monotonic() - start_time) * 1000)
        logger.info("CLI provider %s: completed in %dms", provider, latency_ms)

        if proc.returncode != 0:
            stderr_text = stderr_bytes.decode(errors="replace")
            raise RuntimeError(f"CLI provider {provider} failed: {stderr_text}")

        output = stdout_bytes.decode(errors="replace")

        if config.cli_command == "claude":
            return self._parse_claude_cli_output(output, provider, config, latency_ms)
        return self._parse_gemini_cli_output(output, provider, config, latency_ms)

    async def _call_remote_cli(
        self, provider: str, system_prompt: str, user_prompt: str
    ) -> LLMResponse:
        """Call a remote CLI provider via HTTP proxy (HB LXC)."""
        config = self._remote_cli_providers[provider]

        if not self._client:
            await self.start()

        url = f"{config.remote_url}/agent/{config.agent_name}"
        logger.info("Remote CLI provider %s: calling %s", provider, url)
        start_time = time.monotonic()

        try:
            resp = await self._client.post(  # type: ignore[union-attr]
                url,
                json={"system_prompt": system_prompt, "user_prompt": user_prompt},
                headers={"Authorization": f"Bearer {config.auth_token}"},
                timeout=httpx.Timeout(float(config.timeout_seconds)),
            )
        except httpx.TimeoutException:
            raise RuntimeError(
                f"Remote CLI provider {provider} timed out after {config.timeout_seconds}s"
            )
        except httpx.ConnectError:
            raise RuntimeError(
                f"Remote CLI provider {provider}: cannot connect to {config.remote_url}"
            )

        latency_ms = int((time.monotonic() - start_time) * 1000)

        if resp.status_code != 200:
            detail = resp.text[:300]
            raise RuntimeError(
                f"Remote CLI provider {provider} returned {resp.status_code}: {detail}"
            )

        data = resp.json()
        logger.info("Remote CLI provider %s: completed in %dms", provider, latency_ms)

        return LLMResponse(
            content=data["content"],
            model=data.get("model", config.default_model),
            provider=provider,
            token_usage=data.get("token_usage", {}),
            latency_ms=latency_ms,
        )

    @staticmethod
    def _parse_claude_cli_output(
        output: str, provider: str, config: CLIProviderConfig, latency_ms: int
    ) -> LLMResponse:
        """Parse Claude Code CLI JSON output.

        Claude CLI with --output-format json returns:
        {"type":"result","subtype":"success","result":"...","cost_usd":0.01,...}
        """
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            # Fall back to treating entire output as content
            return LLMResponse(
                content=output,
                model=config.default_model or "claude-cli",
                provider=provider,
                token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                latency_ms=latency_ms,
            )

        content = data.get("result", "")
        cost = data.get("cost_usd", 0)
        model = config.default_model or "claude-cli"

        return LLMResponse(
            content=content,
            model=model,
            provider=provider,
            token_usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": cost,
            },
            latency_ms=latency_ms,
            finish_reason="stop" if data.get("subtype") == "success" else "error",
        )

    @staticmethod
    def _parse_gemini_cli_output(
        output: str, provider: str, config: CLIProviderConfig, latency_ms: int
    ) -> LLMResponse:
        """Parse Gemini CLI JSON output.

        Gemini CLI with -o json returns:
        {"session_id":"...","response":"...","stats":{...}}
        The response field is a string containing the LLM's actual output.
        """
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return LLMResponse(
                content=output,
                model=config.default_model or "gemini-cli",
                provider=provider,
                token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                latency_ms=latency_ms,
            )

        # Extract the response string from the envelope
        content = data.get("response", "")
        if isinstance(content, str):
            # Strip markdown code fences if the LLM wrapped its JSON output
            content = re.sub(r"```(?:json)?\s*\n?", "", content).strip()

        model = config.default_model or "gemini-cli"
        stats = data.get("stats", {})

        return LLMResponse(
            content=content,
            model=model,
            provider=provider,
            token_usage={
                "prompt_tokens": stats.get("input_tokens", 0),
                "completion_tokens": stats.get("output_tokens", 0),
                "total_tokens": stats.get("input_tokens", 0)
                + stats.get("output_tokens", 0),
            },
            latency_ms=latency_ms,
        )

    @classmethod
    def from_config(cls, config) -> LLMGateway:
        """Create gateway from AppConfig, registering all configured providers."""
        gw = cls()

        # Register HTTP API providers based on which API keys are set
        if config.deepseek_api_key:
            gw.register_provider(
                ProviderConfig(
                    name="deepseek",
                    base_url="https://api.deepseek.com/v1",
                    api_key=config.deepseek_api_key,
                    default_model="deepseek-reasoner",
                    rpm_limit=60,
                    timeout_seconds=120,
                )
            )
        if config.groq_api_key:
            gw.register_provider(
                ProviderConfig(
                    name="groq",
                    base_url="https://api.groq.com/openai/v1",
                    api_key=config.groq_api_key,
                    default_model="llama-3.3-70b-versatile",
                    rpm_limit=30,
                    timeout_seconds=15,
                )
            )

        # Register CLI providers (subscription-based, no API key needed)
        if config.use_claude_cli:
            gw.register_cli_provider(
                CLIProviderConfig(
                    name="claude-cli",
                    cli_command="claude",
                    default_model="claude-opus-4-6",
                    timeout_seconds=300,
                )
            )
        if config.use_gemini_cli:
            gw.register_cli_provider(
                CLIProviderConfig(
                    name="gemini-cli",
                    cli_command="gemini",
                    default_model="gemini-2.5-pro",
                    timeout_seconds=300,
                )
            )

        # Legacy HTTP API providers (fallback if CLI not configured)
        if config.grok_api_key:
            gw.register_provider(
                ProviderConfig(
                    name="xai",
                    base_url="https://api.x.ai/v1",
                    api_key=config.grok_api_key,
                    default_model="grok-3",
                    rpm_limit=60,
                    timeout_seconds=30,
                )
            )
        if config.anthropic_api_key:
            gw.register_provider(
                ProviderConfig(
                    name="anthropic",
                    base_url="https://api.anthropic.com/v1",
                    api_key=config.anthropic_api_key,
                    default_model="claude-sonnet-4-5-20250929",
                    rpm_limit=60,
                    timeout_seconds=60,
                )
            )

        # Register remote CLI providers (K8s pod delegates to HB LXC)
        if config.hb_proxy_url and config.hb_proxy_token:
            gw.register_remote_cli_provider(
                RemoteCLIProviderConfig(
                    name="remote-soros",
                    remote_url=config.hb_proxy_url,
                    agent_name="soros",
                    auth_token=config.hb_proxy_token,
                    default_model="gemini-2.5-pro",
                    timeout_seconds=300,
                )
            )
            gw.register_remote_cli_provider(
                RemoteCLIProviderConfig(
                    name="remote-auditor",
                    remote_url=config.hb_proxy_url,
                    agent_name="auditor",
                    auth_token=config.hb_proxy_token,
                    default_model="claude-opus-4-6",
                    timeout_seconds=300,
                )
            )

        return gw
