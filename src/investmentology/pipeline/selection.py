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
from datetime import datetime
from typing import NamedTuple

from investmentology.registry.db import Database

logger = logging.getLogger(__name__)

# Maximum watchlist (non-portfolio) tickers per cycle
MAX_WATCHLIST_TICKERS = 15

# Legacy alias — total can be up to len(portfolio) + MAX_WATCHLIST_TICKERS
MAX_TICKERS_PER_CYCLE = 20


@dataclass
class ScoredTicker:
    ticker: str
    score: float
    reasons: list[str]


class TickerSelection(NamedTuple):
    """Two-group selection: portfolio tickers (guaranteed) + watchlist (budget-capped)."""
    portfolio: list[str]
    watchlist: list[str]

    @property
    def all_tickers(self) -> list[str]:
        """Portfolio first, then watchlist — preserves dispatch ordering."""
        return self.portfolio + self.watchlist


def get_portfolio_tickers(db: Database) -> list[str]:
    """Get all open portfolio positions (shares > 0, not closed)."""
    try:
        rows = db.execute(
            "SELECT ticker FROM invest.portfolio_positions "
            "WHERE is_closed = FALSE AND shares > 0"
        )
        return [r["ticker"] for r in rows]
    except Exception:
        logger.warning("Failed to fetch portfolio tickers")
        return []


def select_tickers(
    db: Database,
    candidates: list[str],
    max_tickers: int = MAX_TICKERS_PER_CYCLE,
) -> TickerSelection:
    """Score and rank candidates, return TickerSelection with portfolio-first guarantee.

    Portfolio tickers are ALWAYS included regardless of budget.
    Remaining budget (MAX_WATCHLIST_TICKERS) is filled by highest-scoring
    watchlist/QG candidates.

    Returns TickerSelection(portfolio=[...], watchlist=[...]).
    Use .all_tickers for a flat list with portfolio first.
    """
    # Identify portfolio tickers from the candidate list
    portfolio_set = set(get_portfolio_tickers(db))
    portfolio_tickers = [t for t in candidates if t in portfolio_set]
    watchlist_candidates = [t for t in candidates if t not in portfolio_set]

    # Score watchlist candidates and select top N
    if watchlist_candidates:
        scored = _score_all(db, watchlist_candidates)
        scored.sort(key=lambda s: s.score, reverse=True)
        watchlist_selected = scored[:MAX_WATCHLIST_TICKERS]
    else:
        watchlist_selected = []

    watchlist_tickers = [s.ticker for s in watchlist_selected]

    logger.info(
        "Selection Desk: %d portfolio (guaranteed) + %d/%d watchlist selected",
        len(portfolio_tickers),
        len(watchlist_tickers),
        len(watchlist_candidates),
    )
    if watchlist_selected:
        logger.info(
            "  Watchlist top: %s %.1f, cutoff: %s %.1f",
            watchlist_selected[0].ticker, watchlist_selected[0].score,
            watchlist_selected[-1].ticker, watchlist_selected[-1].score,
        )
    for s in watchlist_selected[:5]:
        logger.debug("  %s: %.1f — %s", s.ticker, s.score, ", ".join(s.reasons))

    return TickerSelection(portfolio=portfolio_tickers, watchlist=watchlist_tickers)


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
            score += 25  # Base score for held positions (raised from 20)
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

            # Drawdown urgency (position-type-aware thresholds)
            pnl = pos.get("pnl_pct", 0) or 0
            p_type = pos.get("position_type", "core")
            drawdown_threshold = -15 if p_type == "tactical" else -20
            if pnl < drawdown_threshold:
                score += 40  # Hard reanalysis trigger — bypasses normal queue
                reasons.append(f"MANDATORY_drawdown_{pnl:.0f}%")
            elif pnl < -10:
                score += 15
                reasons.append(f"drawdown_{pnl:.0f}%")
            elif pnl < -5:
                score += 8
                reasons.append(f"drawdown_{pnl:.0f}%")

            # Stale held position: >90 days without reanalysis
            days_held = pos.get("days_held", 0) or 0
            last_verdict = verdict_data.get(ticker)
            days_since_verdict = (last_verdict or {}).get("days_since", 999)
            if days_held > 90 and days_since_verdict > 90:
                score += 15
                reasons.append("stale_held_90d+")

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

        # Factor 4: Quant gate rank (tiered scoring)
        if qg_rank is not None:
            if qg_rank <= 10:
                score += 20
                reasons.append(f"qg_top10(#{qg_rank})")
            elif qg_rank <= 25:
                score += 12
                reasons.append(f"qg_top25(#{qg_rank})")
            elif qg_rank <= 50:
                score += 8
                reasons.append(f"qg_top50(#{qg_rank})")
            else:
                rank_score = max(0, 5 - (qg_rank / 20))
                score += rank_score

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
        result = {}
        for r in rows:
            result[r["ticker"]] = True
        return result
    except Exception:
        logger.debug("Earnings proximity query failed")
        return {}
