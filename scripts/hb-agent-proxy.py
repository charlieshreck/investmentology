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

AGENT_CONFIG = {
    "soros": {"cli": "gemini", "model": "gemini-2.5-pro", "timeout": 300},
    "auditor": {"cli": "claude", "model": "claude-opus-4-6", "timeout": 300},
}

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


@app.get("/health")
async def health():
    return {"status": "ok", "agents": list(AGENT_CONFIG.keys())}


@app.post("/agent/{agent_name}", response_model=AgentResponse)
async def run_agent(agent_name: str, body: AgentRequest, request: Request):
    _verify_token(request)

    if agent_name not in AGENT_CONFIG:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_name}")

    cfg = AGENT_CONFIG[agent_name]
    combined_prompt = f"{body.system_prompt}\n\n{body.user_prompt}"

    # Build command as a list — no shell involved (asyncio.create_subprocess_exec)
    if cfg["cli"] == "claude":
        cmd = ["claude", "-p", combined_prompt, "--output-format", "json"]
    elif cfg["cli"] == "gemini":
        cmd = ["gemini", "-p", combined_prompt, "-o", "json", "--yolo"]
    else:
        raise HTTPException(status_code=500, detail=f"Bad CLI config: {cfg['cli']}")

    logger.info("Running %s via %s CLI", agent_name, cfg["cli"])
    start = time.monotonic()

    # Safe: create_subprocess_exec uses execvp (no shell), combined_prompt
    # is a single argument — no injection risk
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

    latency_ms = int((time.monotonic() - start) * 1000)
    logger.info("%s completed in %dms (exit=%d)", agent_name, latency_ms, proc.returncode)

    if proc.returncode != 0:
        stderr_text = stderr_bytes.decode(errors="replace")[:500]
        raise HTTPException(status_code=502, detail=f"{agent_name} CLI failed: {stderr_text}")

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
