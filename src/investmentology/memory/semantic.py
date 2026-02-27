"""Qdrant semantic memory for thesis lifecycle.

Phase 4: "What happened in similar situations?" pattern matching.

Stores analysis snapshots as vectors in Qdrant. Enables:
- Finding similar past situations (same position type, market regime, thesis health)
- Learning from outcomes of past similar decisions
- Pattern matching across the portfolio's history
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# Qdrant collection for thesis memory
COLLECTION_NAME = "investmentology_thesis"
QDRANT_URL = "http://knowledge-mcp.agentic.kernow.io"
EMBED_URL = "http://knowledge-mcp.agentic.kernow.io"

# Direct Qdrant access (knowledge MCP manages Qdrant)
QDRANT_DIRECT_URL = "http://qdrant.ai-platform.svc.cluster.local:6333"


@dataclass
class SimilarSituation:
    """A past situation similar to the current one."""
    ticker: str
    verdict: str
    position_type: str
    thesis_health: str
    market_regime: str
    confidence: float
    reasoning: str
    outcome: str | None  # Filled later when settled
    similarity_score: float
    date: str


def _build_embedding_text(
    ticker: str,
    verdict: str,
    reasoning: str,
    position_type: str | None,
    thesis_health: str | None,
    market_context: dict | None,
    agent_stances: list[dict] | None,
) -> str:
    """Build text representation for embedding."""
    parts = [
        f"Stock: {ticker}",
        f"Verdict: {verdict}",
        f"Position type: {position_type or 'none'}",
        f"Thesis health: {thesis_health or 'unknown'}",
    ]

    if market_context:
        vix = market_context.get("vix")
        spy = market_context.get("spy_price")
        if vix:
            parts.append(f"VIX: {vix}")
        if spy:
            parts.append(f"SPY: {spy}")

    if agent_stances:
        stance_parts = []
        for s in agent_stances[:4]:
            name = s.get("name", "unknown")
            sent = s.get("sentiment", 0)
            direction = "bullish" if sent > 0.1 else "bearish" if sent < -0.1 else "neutral"
            stance_parts.append(f"{name}={direction}")
        parts.append(f"Agent stances: {', '.join(stance_parts)}")

    if reasoning:
        parts.append(f"Reasoning: {reasoning[:500]}")

    return " | ".join(parts)


async def store_analysis_memory(
    ticker: str,
    verdict: str,
    confidence: float,
    reasoning: str,
    position_type: str | None = None,
    thesis_health: str | None = None,
    market_snapshot: dict | None = None,
    agent_stances: list[dict] | None = None,
    days_held: int | None = None,
    pnl_pct: float | None = None,
) -> bool:
    """Store an analysis snapshot in Qdrant for future similarity search.

    Uses the knowledge MCP's Qdrant integration to store vectors.
    Returns True on success.
    """
    text = _build_embedding_text(
        ticker, verdict, reasoning, position_type,
        thesis_health, market_snapshot, agent_stances,
    )

    payload = {
        "ticker": ticker,
        "verdict": verdict,
        "confidence": confidence,
        "position_type": position_type or "none",
        "thesis_health": thesis_health or "unknown",
        "reasoning": reasoning[:1000],
        "market_snapshot": {
            k: str(v) for k, v in (market_snapshot or {}).items() if v is not None
        },
        "agent_stances": agent_stances or [],
        "days_held": days_held,
        "pnl_pct": pnl_pct,
        "outcome": None,  # Filled later when settled
        "timestamp": datetime.now().isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Use knowledge MCP's vector_add_document endpoint
            resp = await client.post(
                f"{QDRANT_DIRECT_URL}/collections/{COLLECTION_NAME}/points",
                json={
                    "points": [{
                        "id": int(datetime.now().timestamp() * 1000),
                        "payload": payload,
                        "vector": None,  # Will be computed by Qdrant if configured
                    }]
                },
            )
            if resp.status_code in (200, 201):
                logger.debug("Stored analysis memory for %s in Qdrant", ticker)
                return True
            logger.debug("Qdrant store failed: %s %s", resp.status_code, resp.text[:200])
    except Exception:
        logger.debug("Could not store analysis memory for %s in Qdrant", ticker)

    return False


async def find_similar_situations(
    ticker: str,
    verdict: str,
    reasoning: str,
    position_type: str | None = None,
    thesis_health: str | None = None,
    market_snapshot: dict | None = None,
    limit: int = 5,
) -> list[SimilarSituation]:
    """Find past situations similar to the current analysis.

    Searches Qdrant for semantically similar analysis snapshots.
    Returns list of similar past situations with their outcomes.
    """
    text = _build_embedding_text(
        ticker, verdict, reasoning, position_type,
        thesis_health, market_snapshot, None,
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{QDRANT_DIRECT_URL}/collections/{COLLECTION_NAME}/points/search",
                json={
                    "query": text,
                    "limit": limit,
                    "with_payload": True,
                },
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []
            for hit in data.get("result", []):
                payload = hit.get("payload", {})
                results.append(SimilarSituation(
                    ticker=payload.get("ticker", "?"),
                    verdict=payload.get("verdict", "?"),
                    position_type=payload.get("position_type", "unknown"),
                    thesis_health=payload.get("thesis_health", "unknown"),
                    market_regime=payload.get("market_snapshot", {}).get("regime", "unknown"),
                    confidence=payload.get("confidence", 0),
                    reasoning=payload.get("reasoning", "")[:200],
                    outcome=payload.get("outcome"),
                    similarity_score=hit.get("score", 0),
                    date=payload.get("timestamp", ""),
                ))
            return results
    except Exception:
        logger.debug("Could not search similar situations in Qdrant for %s", ticker)
        return []


async def ensure_collection_exists() -> bool:
    """Create the Qdrant collection if it doesn't exist."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Check if collection exists
            resp = await client.get(f"{QDRANT_DIRECT_URL}/collections/{COLLECTION_NAME}")
            if resp.status_code == 200:
                return True

            # Create collection with 768-dim vectors (nomic-embed-text)
            resp = await client.put(
                f"{QDRANT_DIRECT_URL}/collections/{COLLECTION_NAME}",
                json={
                    "vectors": {
                        "size": 768,
                        "distance": "Cosine",
                    },
                },
            )
            return resp.status_code in (200, 201)
    except Exception:
        logger.debug("Could not ensure Qdrant collection %s exists", COLLECTION_NAME)
        return False
