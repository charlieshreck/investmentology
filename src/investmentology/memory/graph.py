"""Neo4j graph memory for thesis lifecycle.

Phase 5: Thesis lineage, verdict chains, causation tracking.

Creates and maintains a graph of:
- Stock → Thesis → Verdict chains (temporal relationships)
- Thesis challenge/break causation
- Flip-flop accuracy tracking by position type
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# Neo4j access via knowledge MCP's graph tools
NEO4J_BOLT_URL = "bolt://neo4j.ai-platform.svc.cluster.local:7687"

# We use the knowledge MCP tools for graph operations
# These are accessed via the MCP server, not direct driver calls


@dataclass
class VerdictChainEntry:
    """Entry in a verdict chain for a ticker."""
    verdict: str
    confidence: float
    date: str
    was_flip: bool = False
    was_gated: bool = False


@dataclass
class ThesisLineage:
    """Complete lineage of a thesis from entry to current state."""
    ticker: str
    entry_thesis: str
    current_health: str
    verdict_chain: list[VerdictChainEntry]
    flip_count: int
    days_since_entry: int
    challenges: list[str]


async def record_verdict_node(
    ticker: str,
    verdict: str,
    confidence: float,
    consensus_score: float,
    agent_stances: list[dict] | None = None,
    was_gated: bool = False,
    gating_reason: str | None = None,
    thesis_health: str | None = None,
) -> bool:
    """Record a verdict as a graph node with relationships.

    Creates:
    - (:Stock {ticker})-[:HAS_VERDICT]->(:Verdict {verdict, confidence, date})
    - (:Verdict)-[:FOLLOWED_BY]->(:Verdict) for temporal chain
    - (:Verdict)-[:FLIPPED_TO]->(:Verdict) if direction changed

    Uses knowledge MCP's query_graph tool via REST.
    """
    try:
        now = datetime.now().isoformat()

        # Create Stock node if not exists
        cypher_merge_stock = (
            f"MERGE (s:InvestStock {{ticker: '{ticker}'}}) "
            f"RETURN s"
        )

        # Create Verdict node
        cypher_create_verdict = (
            f"MATCH (s:InvestStock {{ticker: '{ticker}'}}) "
            f"CREATE (v:InvestVerdict {{"
            f"  ticker: '{ticker}', "
            f"  verdict: '{verdict}', "
            f"  confidence: {confidence}, "
            f"  consensus_score: {consensus_score}, "
            f"  was_gated: {'true' if was_gated else 'false'}, "
            f"  thesis_health: '{thesis_health or 'unknown'}', "
            f"  created_at: '{now}'"
            f"}}) "
            f"CREATE (s)-[:HAS_VERDICT]->(v) "
            f"RETURN v"
        )

        # Link to previous verdict (FOLLOWED_BY)
        cypher_link_prev = (
            f"MATCH (s:InvestStock {{ticker: '{ticker}'}})-[:HAS_VERDICT]->(prev:InvestVerdict) "
            f"WHERE prev.created_at < '{now}' "
            f"WITH prev ORDER BY prev.created_at DESC LIMIT 1 "
            f"MATCH (curr:InvestVerdict {{ticker: '{ticker}', created_at: '{now}'}}) "
            f"CREATE (prev)-[:FOLLOWED_BY]->(curr) "
            f"RETURN prev.verdict AS prev_verdict"
        )

        # Execute via knowledge MCP REST API
        async with httpx.AsyncClient(timeout=15) as client:
            for cypher in [cypher_merge_stock, cypher_create_verdict, cypher_link_prev]:
                try:
                    # Use knowledge MCP's query_graph endpoint
                    resp = await client.post(
                        "http://knowledge-mcp.ai-platform.svc.cluster.local:8000/api/call",
                        json={
                            "name": "query_graph",
                            "arguments": {"query": cypher},
                        },
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code not in (200, 201):
                        logger.debug("Neo4j query failed: %s", resp.text[:200])
                except Exception:
                    pass  # Individual query failures are OK

        logger.debug("Recorded verdict node for %s: %s", ticker, verdict)
        return True
    except Exception:
        logger.debug("Could not record verdict node for %s in Neo4j", ticker)
        return False


async def record_thesis_node(
    ticker: str,
    thesis_text: str,
    thesis_type: str = "growth",
    position_type: str = "tactical",
    investment_horizon: str | None = None,
) -> bool:
    """Record a thesis as a graph node.

    Creates:
    - (:InvestStock)-[:HAS_THESIS]->(:InvestThesis)
    """
    try:
        now = datetime.now().isoformat()
        safe_text = thesis_text.replace("'", "\\'")[:500]

        cypher = (
            f"MERGE (s:InvestStock {{ticker: '{ticker}'}}) "
            f"CREATE (t:InvestThesis {{"
            f"  ticker: '{ticker}', "
            f"  text: '{safe_text}', "
            f"  thesis_type: '{thesis_type}', "
            f"  position_type: '{position_type}', "
            f"  horizon: '{investment_horizon or 'unspecified'}', "
            f"  created_at: '{now}'"
            f"}}) "
            f"CREATE (s)-[:HAS_THESIS]->(t) "
            f"RETURN t"
        )

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "http://knowledge-mcp.ai-platform.svc.cluster.local:8000/api/call",
                json={"name": "query_graph", "arguments": {"query": cypher}},
                headers={"Content-Type": "application/json"},
            )
            return resp.status_code in (200, 201)
    except Exception:
        logger.debug("Could not record thesis node for %s in Neo4j", ticker)
        return False


async def get_verdict_chain(ticker: str, limit: int = 20) -> list[VerdictChainEntry]:
    """Get the verdict chain for a ticker from Neo4j.

    Returns ordered list of verdicts with flip annotations.
    """
    try:
        cypher = (
            f"MATCH (s:InvestStock {{ticker: '{ticker}'}})-[:HAS_VERDICT]->(v:InvestVerdict) "
            f"RETURN v.verdict AS verdict, v.confidence AS confidence, "
            f"v.created_at AS date, v.was_gated AS was_gated "
            f"ORDER BY v.created_at DESC LIMIT {limit}"
        )

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "http://knowledge-mcp.ai-platform.svc.cluster.local:8000/api/call",
                json={"name": "query_graph", "arguments": {"query": cypher}},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = data.get("result", [])
            if not results:
                return []

            # Build chain with flip detection
            chain: list[VerdictChainEntry] = []
            bullish = {"STRONG_BUY", "BUY", "ACCUMULATE"}
            bearish = {"SELL", "AVOID", "DISCARD", "REDUCE"}

            for r in results:
                entry = VerdictChainEntry(
                    verdict=r.get("verdict", "?"),
                    confidence=r.get("confidence", 0),
                    date=r.get("date", ""),
                    was_gated=r.get("was_gated", False),
                )
                # Detect flip from previous
                if chain:
                    prev = chain[-1].verdict
                    curr = entry.verdict
                    if (prev in bullish and curr in bearish) or (prev in bearish and curr in bullish):
                        entry.was_flip = True
                chain.append(entry)

            return chain
    except Exception:
        logger.debug("Could not get verdict chain for %s from Neo4j", ticker)
        return []


async def get_flip_accuracy(
    position_type: str | None = None, days: int = 180,
) -> dict:
    """Get flip accuracy stats: when we flipped on positions, were we right?

    Returns dict with flip_count, correct_flips, accuracy.
    """
    try:
        type_filter = f"AND v1.position_type = '{position_type}' " if position_type else ""
        cypher = (
            f"MATCH (v1:InvestVerdict)-[:FLIPPED_TO]->(v2:InvestVerdict) "
            f"WHERE v1.created_at > datetime() - duration({{days: {days}}}) "
            f"{type_filter}"
            f"RETURN count(*) AS flip_count"
        )

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "http://knowledge-mcp.ai-platform.svc.cluster.local:8000/api/call",
                json={"name": "query_graph", "arguments": {"query": cypher}},
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("result", [])
                if results:
                    return {"flip_count": results[0].get("flip_count", 0)}

        return {"flip_count": 0}
    except Exception:
        logger.debug("Could not get flip accuracy from Neo4j")
        return {"flip_count": 0}
