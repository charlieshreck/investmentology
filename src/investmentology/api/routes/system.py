"""System health endpoints."""

from __future__ import annotations

import shutil
import time

from fastapi import APIRouter, Depends, Query

from investmentology.api.deps import get_gateway, get_registry
from investmentology.agents.gateway import LLMGateway
from investmentology.registry.queries import Registry

router = APIRouter()

_start_time = time.time()


def _provider_status(gateway: LLMGateway) -> dict[str, bool]:
    """Report which providers are configured and available."""
    status: dict[str, bool] = {}

    # HTTP API providers — key is set
    provider_labels = {
        "deepseek": "DeepSeek R1",
        "groq": "Groq Llama",
        "xai": "xAI Grok",
        "anthropic": "Anthropic API",
    }
    for name, label in provider_labels.items():
        if name in gateway._providers:
            status[label] = bool(gateway._providers[name].api_key)

    # CLI providers — binary exists
    cli_labels = {
        "claude-cli": "Claude CLI",
        "gemini-cli": "Gemini CLI",
    }
    for name, label in cli_labels.items():
        if name in gateway._cli_providers:
            cmd = gateway._cli_providers[name].cli_command
            status[label] = shutil.which(cmd) is not None

    return status


AGENT_PROFILES = {
    "warren": {
        "name": "Warren",
        "role": "Fundamentals Analyst",
        "philosophy": "Warren Buffett",
        "focus": "Intrinsic value, moat quality, earnings quality, balance sheet strength",
        "category": "Fundamental",
    },
    "soros": {
        "name": "Soros",
        "role": "Macro/Cycle Analyst",
        "philosophy": "George Soros",
        "focus": "Macro regime, sector rotation, credit conditions, reflexivity",
        "category": "Macro",
    },
    "simons": {
        "name": "Simons",
        "role": "Technical Analyst",
        "philosophy": "Jim Simons",
        "focus": "Trend, momentum, volume, support/resistance, relative strength",
        "category": "Technical",
    },
    "auditor": {
        "name": "Auditor",
        "role": "Risk Analyst",
        "philosophy": "Charlie Munger",
        "focus": "Concentration, correlation, leverage, liquidity, governance, accounting",
        "category": "Risk",
    },
}


@router.get("/agents/panel")
def agents_panel(
    registry: Registry = Depends(get_registry),
    gateway: LLMGateway = Depends(get_gateway),
    ticker: str | None = Query(None, description="Filter agent signals for a specific ticker"),
) -> dict:
    """Agent panel: profiles, providers, and recent activity."""
    providers = _provider_status(gateway)

    # Agent-to-provider/model mapping from gateway
    agent_providers = {}
    provider_map = {
        "warren": ("deepseek", "DeepSeek R1"),
        "simons": ("groq", "Groq Llama"),
    }
    for agent, (prov_key, label) in provider_map.items():
        if prov_key in gateway._providers:
            cfg = gateway._providers[prov_key]
            agent_providers[agent] = {"provider": label, "model": cfg.default_model}

    cli_map = {
        "auditor": ("claude-cli", "Claude CLI"),
        "soros": ("gemini-cli", "Gemini CLI"),
    }
    for agent, (cli_key, label) in cli_map.items():
        if cli_key in gateway._cli_providers:
            cfg = gateway._cli_providers[cli_key]
            agent_providers[agent] = {"provider": label, "model": cfg.default_model}

    # Fallbacks for API providers
    if "auditor" not in agent_providers and "anthropic" in gateway._providers:
        cfg = gateway._providers["anthropic"]
        agent_providers["auditor"] = {"provider": "Anthropic API", "model": cfg.default_model}
    if "soros" not in agent_providers and "xai" in gateway._providers:
        cfg = gateway._providers["xai"]
        agent_providers["soros"] = {"provider": "xAI Grok", "model": cfg.default_model}

    # Per-agent stats
    stat_rows = registry._db.execute(
        "SELECT agent_name, COUNT(*) as total, "
        "AVG(confidence) as avg_conf, AVG(latency_ms) as avg_lat, "
        "MAX(created_at) as last_active "
        "FROM invest.agent_signals GROUP BY agent_name"
    )
    stats = {r["agent_name"]: r for r in stat_rows}

    # Latest signal per agent — optionally filtered by ticker
    if ticker:
        latest_rows = registry._db.execute(
            "SELECT DISTINCT ON (agent_name) agent_name, ticker, signals, "
            "confidence, reasoning, created_at "
            "FROM invest.agent_signals WHERE ticker = %s "
            "ORDER BY agent_name, created_at DESC",
            (ticker.upper(),),
        )
    else:
        latest_rows = registry._db.execute(
            "SELECT DISTINCT ON (agent_name) agent_name, ticker, signals, "
            "confidence, reasoning, created_at "
            "FROM invest.agent_signals ORDER BY agent_name, created_at DESC"
        )
    latest = {r["agent_name"]: r for r in latest_rows}

    agents = []
    for key, profile in AGENT_PROFILES.items():
        prov = agent_providers.get(key, {})
        st = stats.get(key, {})
        lat = latest.get(key)

        agent_data = {
            **profile,
            "key": key,
            "provider": prov.get("provider", "Not configured"),
            "model": prov.get("model", ""),
            "online": prov.get("provider", "") in providers and providers.get(prov.get("provider", ""), False),
            "totalSignals": st.get("total", 0),
            "avgConfidence": float(st["avg_conf"]) if st.get("avg_conf") else None,
            "avgLatencyMs": int(st["avg_lat"]) if st.get("avg_lat") else None,
            "lastActive": str(st["last_active"]) if st.get("last_active") else None,
            "latestAnalysis": {
                "ticker": lat["ticker"],
                "confidence": float(lat["confidence"]) if lat and lat["confidence"] else None,
                "reasoning": lat["reasoning"],
                "createdAt": str(lat["created_at"]),
            } if lat else None,
        }
        agents.append(agent_data)

    return {"agents": agents}


@router.get("/system/health")
def health_check(
    registry: Registry = Depends(get_registry),
    gateway: LLMGateway = Depends(get_gateway),
) -> dict:
    """System health check.

    Response shape matches PWA SystemHealth:
    {status, database, apiKeys, lastQuantRun?, decisionsLogged, uptime}
    """
    db_ok = registry._db.health_check()

    decision_count = registry._db.execute("SELECT COUNT(*) as n FROM invest.decisions")[0]["n"]

    # Last quant gate run date
    qg_rows = registry._db.execute(
        "SELECT run_date FROM invest.quant_gate_runs ORDER BY id DESC LIMIT 1"
    )
    last_qg = str(qg_rows[0]["run_date"]) if qg_rows else None

    providers = _provider_status(gateway)

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": db_ok,
        "apiKeys": providers,
        "lastQuantRun": last_qg,
        "decisionsLogged": decision_count,
        "uptime": int(time.time() - _start_time),
    }
