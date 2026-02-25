"""Shared utilities for API route handlers."""

from __future__ import annotations


def success_probability(row: dict) -> float | None:
    """Blended success probability (0.0-1.0) from agent analysis signals.

    Components (weights renormalized when data is missing):
        35% verdict confidence
        25% consensus score (normalized -1..+1 to 0..1)
        20% agent alignment (fraction of agents with positive sentiment)
        20% risk-adjusted (penalized by risk flag count)
    """
    components: list[tuple[float, float]] = []

    vc = row.get("confidence")
    if vc is not None:
        components.append((float(vc), 0.35))

    cons = row.get("consensus_score")
    if cons is not None:
        components.append(((float(cons) + 1) / 2, 0.25))

    stances = row.get("agent_stances")
    if stances and isinstance(stances, list) and len(stances) > 0:
        pos_count = sum(
            1 for s in stances
            if isinstance(s, dict) and s.get("sentiment", 0) > 0
        )
        alignment = pos_count / len(stances)
        components.append((alignment, 0.20))

    # Risk-adjusted component: start at 1.0, deduct per risk flag
    risk_flags = row.get("risk_flags")
    risk_score = 1.0
    if risk_flags and isinstance(risk_flags, list):
        risk_score = max(0.0, 1.0 - len(risk_flags) * 0.15)
    components.append((risk_score, 0.20))

    if not components:
        return None

    total_weight = sum(w for _, w in components)
    return round(sum(v * w for v, w in components) / total_weight, 4)
