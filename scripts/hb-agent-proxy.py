"""HB LXC Agent Proxy — delegates CLI-based LLM calls for Soros & Auditor.

Runs on HB LXC (10.10.0.101:9100). The K8s pod calls this to access
Gemini CLI (subscription) and Claude CLI (subscription) without needing
the CLI tools installed in the container.

Usage:
    HB_PROXY_TOKEN=<token> python3 scripts/hb-agent-proxy.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROXY_TOKEN = os.environ.get("HB_PROXY_TOKEN", "")
if not PROXY_TOKEN:
    raise RuntimeError("HB_PROXY_TOKEN env var is required")

MAX_CONCURRENT_AGENTS = int(os.environ.get("MAX_CONCURRENT_AGENTS", "8"))
_agent_semaphore: asyncio.Semaphore | None = None
_active_agents = 0

# Gemini quota circuit breaker — blocks all Gemini calls until quota resets
_gemini_quota_blocked_until: float = 0.0  # monotonic timestamp

AGENT_CONFIG = {
    # Claude CLI screen agents
    "warren":       {"cli": "claude", "model": "claude-opus-4-6", "timeout": 600},
    "auditor":      {"cli": "claude", "model": "claude-opus-4-6", "timeout": 600},
    "klarman":      {"cli": "claude", "model": "claude-opus-4-6", "timeout": 600},
    "debate":       {"cli": "claude", "model": "claude-opus-4-6", "timeout": 600},
    "synthesis":    {"cli": "claude", "model": "claude-opus-4-6", "timeout": 600},
    "board-claude": {"cli": "claude", "model": "claude-opus-4-6", "timeout": 360},
    # Gemini CLI screen agents
    "soros":          {"cli": "gemini", "model": "gemini-2.5-pro", "timeout": 600},
    "druckenmiller":  {"cli": "gemini", "model": "gemini-2.5-pro", "timeout": 600},
    "dalio":          {"cli": "gemini", "model": "gemini-2.5-pro", "timeout": 600},
    "data-analyst":   {"cli": "gemini", "model": "gemini-2.5-pro", "timeout": 600},
    "board-gemini":   {"cli": "gemini", "model": "gemini-2.5-pro", "timeout": 360},
    # Research agent — deep research synthesis (large context)
    "researcher":     {"cli": "gemini", "model": "gemini-2.5-pro", "timeout": 900},
}

def _is_quota_error(text: str) -> bool:
    """Detect Gemini CLI quota exhaustion errors."""
    markers = [
        "exhausted your capacity",
        "No capacity available",
        "quota will reset",
        "RESOURCE_EXHAUSTED",
    ]
    return any(m.lower() in text.lower() for m in markers)


def _parse_quota_reset_seconds(text: str) -> int:
    """Extract reset duration from 'quota will reset after 8h18m48s' style messages."""
    m = re.search(r"reset after\s+(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", text)
    if not m:
        return 3600  # default 1 hour if we can't parse
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


app = FastAPI(title="HB Agent Proxy", docs_url=None, redoc_url=None)


class AgentRequest(BaseModel):
    system_prompt: str
    user_prompt: str


class AgentResponse(BaseModel):
    content: str
    model: str
    provider: str
    token_usage: dict
    latency_ms: int


def _verify_token(request: Request) -> None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != PROXY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


def _parse_claude_output(output: str, model: str) -> tuple[str, dict]:
    try:
        data = json.loads(output)
        content = data.get("result", output)
        cost = data.get("cost_usd", 0)
        return content, {"cost_usd": cost, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    except json.JSONDecodeError:
        return output, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _parse_gemini_output(output: str, model: str) -> tuple[str, dict]:
    try:
        data = json.loads(output)
        content = data.get("response", output)
        if isinstance(content, str):
            content = re.sub(r"```(?:json)?\s*\n?", "", content).strip()
        stats = data.get("stats", {})
        return content, {
            "prompt_tokens": stats.get("input_tokens", 0),
            "completion_tokens": stats.get("output_tokens", 0),
            "total_tokens": stats.get("input_tokens", 0) + stats.get("output_tokens", 0),
        }
    except json.JSONDecodeError:
        return output, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


@app.on_event("startup")
async def _init_semaphore():
    global _agent_semaphore
    _agent_semaphore = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)
    logger.info("Agent concurrency limit: %d", MAX_CONCURRENT_AGENTS)


@app.get("/health")
async def health():
    now = time.monotonic()
    gemini_blocked = now < _gemini_quota_blocked_until
    return {
        "status": "degraded" if gemini_blocked else "ok",
        "agents": list(AGENT_CONFIG.keys()),
        "max_concurrent": MAX_CONCURRENT_AGENTS,
        "active_agents": _active_agents,
        "gemini_quota_blocked": gemini_blocked,
        "gemini_quota_reset_seconds": max(0, int(_gemini_quota_blocked_until - now)) if gemini_blocked else 0,
    }


@app.post("/agent/{agent_name}", response_model=AgentResponse)
async def run_agent(agent_name: str, body: AgentRequest, request: Request):
    _verify_token(request)

    if agent_name not in AGENT_CONFIG:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_name}")

    cfg = AGENT_CONFIG[agent_name]
    combined_prompt = f"{body.system_prompt}\n\n{body.user_prompt}"

    # Circuit breaker: block Gemini calls while quota is exhausted
    global _gemini_quota_blocked_until
    if cfg["cli"] == "gemini" and time.monotonic() < _gemini_quota_blocked_until:
        remaining = int(_gemini_quota_blocked_until - time.monotonic())
        logger.warning("Gemini quota circuit breaker active — %s blocked (%ds remaining)", agent_name, remaining)
        raise HTTPException(
            status_code=429,
            detail=f"Gemini quota exhausted, resets in {remaining}s",
            headers={"Retry-After": str(remaining)},
        )

    # Build command as a list — no shell involved (asyncio.create_subprocess_exec)
    if cfg["cli"] == "claude":
        cmd = ["claude", "-p", combined_prompt, "--output-format", "json"]
    elif cfg["cli"] == "gemini":
        cmd = ["gemini", "-p", combined_prompt, "-o", "json", "--yolo"]
    else:
        raise HTTPException(status_code=500, detail=f"Bad CLI config: {cfg['cli']}")

    global _active_agents
    logger.info("Running %s via %s CLI (active: %d/%d)", agent_name, cfg["cli"], _active_agents, MAX_CONCURRENT_AGENTS)
    start = time.monotonic()

    assert _agent_semaphore is not None
    async with _agent_semaphore:
        _active_agents += 1
        try:
            # Safe: uses execvp (no shell), combined_prompt is a single arg
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=cfg["timeout"]
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise HTTPException(status_code=504, detail=f"{agent_name} timed out after {cfg['timeout']}s")
        finally:
            _active_agents -= 1

    latency_ms = int((time.monotonic() - start) * 1000)
    logger.info("%s completed in %dms (exit=%d)", agent_name, latency_ms, proc.returncode)

    if proc.returncode != 0:
        stderr_text = stderr_bytes.decode(errors="replace")[:1000]
        stdout_text = stdout_bytes.decode(errors="replace")[:1000]
        combined_error = f"{stderr_text} {stdout_text}"

        # Gemini quota exhaustion → activate circuit breaker, return 429
        if cfg["cli"] == "gemini" and _is_quota_error(combined_error):
            reset_secs = _parse_quota_reset_seconds(combined_error)
            _gemini_quota_blocked_until = time.monotonic() + reset_secs
            logger.error(
                "Gemini quota exhausted — circuit breaker activated for %ds (agent: %s)",
                reset_secs, agent_name,
            )
            raise HTTPException(
                status_code=429,
                detail=f"Gemini quota exhausted, resets in {reset_secs}s",
                headers={"Retry-After": str(reset_secs)},
            )

        raise HTTPException(status_code=502, detail=f"{agent_name} CLI failed: {stderr_text[:500]}")

    output = stdout_bytes.decode(errors="replace")

    if cfg["cli"] == "claude":
        content, token_usage = _parse_claude_output(output, cfg["model"])
    else:
        content, token_usage = _parse_gemini_output(output, cfg["model"])

    return AgentResponse(
        content=content,
        model=cfg["model"],
        provider=f"{cfg['cli']}-cli",
        token_usage=token_usage,
        latency_ms=latency_ms,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9100, log_level="info")
