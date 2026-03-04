"""L2 Selection Desk — intelligent ticker prioritization.

Replaces mechanical "all qualified tickers get analysed" with a scored
ranking that focuses pipeline budget on the most worthwhile analyses.

Scoring factors (descending priority):
- Held positions with deteriorating thesis health
- Tickers near earnings or catalysts
- High quant-gate-rank newcomers (never analysed)
- Stale verdicts (>7 days since last analysis)
- Open positions (need monitoring even if stable)
- Remaining watchlist candidates (fill remaining budget)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from investmentology.registry.db import Database

logger = logging.getLogger(__name__)

# Maximum tickers to analyse per cycle (controls cost)
MAX_TICKERS_PER_CYCLE = 20


@dataclass
class ScoredTicker:
    ticker: str
    score: float
    reasons: list[str]


def select_tickers(
    db: Database,
    candidates: list[str],
    max_tickers: int = MAX_TICKERS_PER_CYCLE,
) -> list[str]:
    """Score and rank candidates, return top N tickers for analysis.

    Always includes all held positions (they need monitoring regardless).
    Remaining budget is filled by highest-scoring watchlist/QG candidates.
    """
    if len(candidates) <= max_tickers:
        return candidates  # No need to select if under budget

    scored = _score_all(db, candidates)
    scored.sort(key=lambda s: s.score, reverse=True)

    selected = scored[:max_tickers]

    if selected:
        logger.info(
            "Selection Desk: %d/%d candidates selected (top: %s %.1f, cutoff: %s %.1f)",
            len(selected), len(scored),
            selected[0].ticker, selected[0].score,
            selected[-1].ticker, selected[-1].score,
        )
        for s in selected[:5]:
            logger.debug("  %s: %.1f — %s", s.ticker, s.score, ", ".join(s.reasons))

    return [s.ticker for s in selected]


def _score_all(db: Database, candidates: list[str]) -> list[ScoredTicker]:
    """Score all candidates based on multiple urgency factors."""
    # Pre-fetch data in bulk to avoid N+1 queries
    position_data = _get_position_data(db, candidates)
    verdict_data = _get_latest_verdicts(db, candidates)
    qg_data = _get_quant_gate_ranks(db, candidates)
    earnings_data = _get_upcoming_earnings(db, candidates)

    results = []
    for ticker in candidates:
        score = 0.0
        reasons: list[str] = []

        pos = position_data.get(ticker)
        verdict = verdict_data.get(ticker)
        qg_rank = qg_data.get(ticker)
        has_earnings_soon = earnings_data.get(ticker, False)

        # Factor 1: Held position with health issues (50 pts max)
        if pos:
            score += 20  # Base score for held positions
            reasons.append("held_position")

            health = pos.get("thesis_health", "INTACT")
            if health == "BROKEN":
                score += 50
                reasons.append("thesis_BROKEN")
            elif health == "CHALLENGED":
                score += 35
                reasons.append("thesis_CHALLENGED")
            elif health == "UNDER_REVIEW":
                score += 20
                reasons.append("thesis_UNDER_REVIEW")

            # Drawdown urgency
            pnl = pos.get("pnl_pct", 0) or 0
            if pnl < -15:
                score += 15
                reasons.append(f"drawdown_{pnl:.0f}%")
            elif pnl < -10:
                score += 8
                reasons.append(f"drawdown_{pnl:.0f}%")

        # Factor 2: Earnings proximity (25 pts)
        if has_earnings_soon:
            score += 25
            reasons.append("earnings_soon")

        # Factor 3: Never analysed (20 pts) or stale verdict (up to 15 pts)
        if verdict is None:
            score += 20
            reasons.append("never_analysed")
        else:
            days_since = verdict.get("days_since", 0)
            if days_since > 14:
                score += 15
                reasons.append(f"stale_{days_since}d")
            elif days_since > 7:
                score += 10
                reasons.append(f"stale_{days_since}d")
            elif days_since > 3:
                score += 5
                reasons.append(f"aging_{days_since}d")

        # Factor 4: Quant gate rank (up to 10 pts — higher rank = more promising)
        if qg_rank is not None:
            # Rank 1 = 10 pts, rank 50 = 5 pts, rank 100 = 0 pts
            rank_score = max(0, 10 - (qg_rank / 10))
            score += rank_score
            if qg_rank <= 20:
                reasons.append(f"qg_top20(#{qg_rank})")

        results.append(ScoredTicker(ticker=ticker, score=score, reasons=reasons))

    return results


def _get_position_data(
    db: Database, tickers: list[str],
) -> dict[str, dict]:
    """Fetch position data for held tickers."""
    if not tickers:
        return {}
    try:
        rows = db.execute(
            "SELECT ticker, thesis_health, pnl_pct, position_type, entry_price, "
            "current_price, days_held "
            "FROM invest.portfolio_positions "
            "WHERE is_closed = FALSE AND ticker = ANY(%s)",
            (tickers,),
        )
        return {r["ticker"]: dict(r) for r in rows}
    except Exception:
        logger.debug("Position data query failed")
        return {}


def _get_latest_verdicts(
    db: Database, tickers: list[str],
) -> dict[str, dict]:
    """Get most recent verdict date for each ticker."""
    if not tickers:
        return {}
    try:
        rows = db.execute(
            "SELECT DISTINCT ON (ticker) ticker, created_at, verdict "
            "FROM invest.decisions "
            "WHERE ticker = ANY(%s) "
            "ORDER BY ticker, created_at DESC",
            (tickers,),
        )
        now = datetime.now()
        result = {}
        for r in rows:
            created = r["created_at"]
            if hasattr(created, "replace"):
                # Make naive if needed for subtraction
                if created.tzinfo is not None:
                    from datetime import timezone
                    now_tz = datetime.now(timezone.utc)
                    days_since = (now_tz - created).days
                else:
                    days_since = (now - created).days
            else:
                days_since = 999
            result[r["ticker"]] = {
                "verdict": r["verdict"],
                "days_since": days_since,
            }
        return result
    except Exception:
        logger.debug("Verdict data query failed")
        return {}


def _get_quant_gate_ranks(
    db: Database, tickers: list[str],
) -> dict[str, int]:
    """Get quant gate combined_rank for tickers from latest run."""
    if not tickers:
        return {}
    try:
        rows = db.execute(
            "SELECT r.ticker, r.combined_rank "
            "FROM invest.quant_gate_results r "
            "WHERE r.run_id = ("
            "  SELECT id FROM invest.quant_gate_runs ORDER BY id DESC LIMIT 1"
            ") AND r.ticker = ANY(%s)",
            (tickers,),
        )
        return {r["ticker"]: r["combined_rank"] for r in rows}
    except Exception:
        logger.debug("Quant gate rank query failed")
        return {}


def _get_upcoming_earnings(
    db: Database, tickers: list[str],
) -> dict[str, bool]:
    """Check which tickers have earnings within the next 14 days."""
    if not tickers:
        return {}
    try:
        # Check Finnhub earnings data cached in pipeline_data_cache
        rows = db.execute(
            "SELECT ticker FROM invest.pipeline_data_cache "
            "WHERE ticker = ANY(%s) AND data_type = 'earnings' "
            "AND (data->>'earnings_date') IS NOT NULL",
            (tickers,),
        )
        now = datetime.now().date()
        result = {}
        for r in rows:
            result[r["ticker"]] = True
        return result
    except Exception:
        logger.debug("Earnings proximity query failed")
        return {}
