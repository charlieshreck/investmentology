"""Watchlist enrichment — extract structured metadata from synthesis results.

When a ticker receives a WATCHLIST verdict, this module extracts:
- Why it isn't cutting it (blocking factors from agent signals)
- What it needs to graduate (mapped graduation criteria)
- Conservative target entry price (from agent target prices)
- QG rank snapshot
"""

from __future__ import annotations

import json
import logging

from investmentology.registry.db import Database

logger = logging.getLogger(__name__)

# Signal tag → (human-readable blocking factor, graduation criteria)
BLOCKING_FACTOR_MAP: dict[str, tuple[str, str]] = {
    "OVERVALUED": (
        "Valuation too high",
        "Price decline to fair value or earnings growth to justify current price",
    ),
    "MOAT_NARROWING": (
        "Competitive moat weakening",
        "Evidence of pricing power or market share gains",
    ),
    "NO_MOAT": (
        "Competitive moat insufficient",
        "Evidence of pricing power or market share gains",
    ),
    "ACCOUNTING_RED_FLAG": (
        "Financial transparency concerns",
        "Clean audit report or improved disclosure",
    ),
    "GOVERNANCE_CONCERN": (
        "Corporate governance issues",
        "Board improvement or shareholder-friendly actions",
    ),
    "LEVERAGE_HIGH": (
        "Excessive debt burden",
        "Debt-to-equity below 1.5x or clear deleveraging path",
    ),
    "GEOPOLITICAL_RISK": (
        "Unfavorable macro environment",
        "Regime change: rates/growth/inflation shift favorably",
    ),
    "MARGIN_COMPRESSING": (
        "Deteriorating margins",
        "Operating margin stabilization or expansion",
    ),
    "REVENUE_DECELERATING": (
        "Revenue trajectory concerning",
        "Return to positive revenue growth",
    ),
    "MOMENTUM_WEAK": (
        "Weak price momentum",
        "Trend reversal with volume confirmation",
    ),
    "BREAKDOWN_CONFIRMED": (
        "Technical breakdown confirmed",
        "Price reclaims key support level with volume",
    ),
    "RESISTANCE_NEAR": (
        "Near major resistance level",
        "Clean breakout above resistance with volume",
    ),
    "RSI_OVERBOUGHT": (
        "Overbought on technicals",
        "RSI pullback below 70 and base formation",
    ),
    "DEATH_CROSS": (
        "Death cross pattern (bearish)",
        "Golden cross reversal or sustained price recovery",
    ),
    "VOLATILITY_HIGH": (
        "Elevated volatility",
        "Volatility compression below sector average",
    ),
    "DRAWDOWN_RISK": (
        "Significant drawdown risk",
        "Drawdown recovery or risk/reward improvement",
    ),
    "LIQUIDITY_LOW": (
        "Low trading liquidity",
        "Improved daily volume or institutional accumulation",
    ),
    "CONCENTRATION": (
        "Portfolio concentration risk",
        "Position sizing within risk limits",
    ),
    "SECTOR_ROTATION_OUT": (
        "Sector rotation headwinds",
        "Sector rotation reversal or relative strength improvement",
    ),
    "EARNINGS_QUALITY_LOW": (
        "Earnings quality concerns",
        "Improved cash flow conversion and earnings consistency",
    ),
    "TREND_DOWNTREND": (
        "Downtrend in progress",
        "Trend reversal with higher highs and higher lows",
    ),
    "BALANCE_SHEET_WEAK": (
        "Weak balance sheet",
        "Balance sheet improvement: debt reduction or asset growth",
    ),
    "CAPITAL_ALLOCATION_POOR": (
        "Poor capital allocation",
        "Improved ROIC or shareholder-friendly capital decisions",
    ),
}


def extract_watchlist_metadata(
    ticker: str,
    agent_signals: list[dict],
    synthesis_data: dict,
    fundamentals: dict | None,
) -> dict:
    """Extract structured watchlist metadata from synthesis results.

    Returns dict with: reason, blocking_factors, graduation_criteria,
    target_entry_price, qg_rank.
    """
    blocking_factors: list[dict] = []
    graduation_criteria: list[dict] = []
    seen_factors: set[str] = set()

    # Scan agent signals for negative tags → map to blocking factors
    for row in agent_signals:
        signals = row.get("signals")
        if not signals:
            continue
        # signals may be a JSON string or already parsed
        if isinstance(signals, str):
            try:
                signals = json.loads(signals)
            except (json.JSONDecodeError, TypeError):
                continue

        if isinstance(signals, list):
            signal_list = signals
        elif isinstance(signals, dict):
            # Support both {signals: [{tag: ...}]} and {tags: ["TAG", ...]} formats
            signal_list = signals.get("signals", []) or signals.get("tags", [])
        else:
            continue
        for sig in signal_list:
            tag = sig.get("tag", "") if isinstance(sig, dict) else str(sig)
            if tag in BLOCKING_FACTOR_MAP and tag not in seen_factors:
                seen_factors.add(tag)
                factor_label, criteria_label = BLOCKING_FACTOR_MAP[tag]
                blocking_factors.append({
                    "tag": tag,
                    "label": factor_label,
                    "source": row.get("agent_name", "unknown"),
                })
                graduation_criteria.append({
                    "tag": tag,
                    "label": criteria_label,
                    "met": False,
                })

    # Extract target entry price from agent target prices
    target_prices: list[float] = []
    for row in agent_signals:
        signals = row.get("signals")
        if not signals:
            continue
        if isinstance(signals, str):
            try:
                signals = json.loads(signals)
            except (json.JSONDecodeError, TypeError):
                continue
        # Target price may be in the signal set metadata
        tp = None
        if isinstance(signals, dict):
            tp = signals.get("target_price")
        if tp is not None:
            try:
                tp_float = float(tp)
                if tp_float > 0:
                    target_prices.append(tp_float)
            except (ValueError, TypeError):
                pass

    # Use conservative target: minimum of agent targets
    target_entry_price = min(target_prices) if target_prices else None

    # Use CIO synthesis reasoning as human-readable reason
    reason = synthesis_data.get("reasoning", "")
    if not reason:
        # Fallback to board narrative headline
        narrative = synthesis_data.get("board_narrative")
        if narrative and isinstance(narrative, dict):
            reason = narrative.get("headline", "")
    if reason:
        reason = reason[:500]

    # QG rank from latest quant gate
    qg_rank = None
    if fundamentals and isinstance(fundamentals, dict):
        qg_rank = fundamentals.get("combined_rank")
        if qg_rank is not None:
            try:
                qg_rank = int(qg_rank)
            except (ValueError, TypeError):
                qg_rank = None

    return {
        "reason": reason or None,
        "blocking_factors": blocking_factors,
        "graduation_criteria": graduation_criteria,
        "target_entry_price": target_entry_price,
        "qg_rank": qg_rank,
    }


def upsert_watchlist_entry(
    db: Database, ticker: str, metadata: dict, verdict_id: int,
) -> None:
    """Upsert structured metadata into invest.watchlist for a ticker."""
    blocking_json = json.dumps(metadata.get("blocking_factors", []))
    graduation_json = json.dumps(metadata.get("graduation_criteria", []))

    db.execute(
        """
        UPDATE invest.watchlist
        SET reason = %s,
            blocking_factors = %s,
            graduation_criteria = %s,
            target_entry_price = %s,
            qg_rank = %s,
            last_verdict_id = %s,
            updated_at = NOW()
        WHERE ticker = %s
          AND id = (
              SELECT id FROM invest.watchlist
              WHERE ticker = %s
              ORDER BY updated_at DESC LIMIT 1
          )
        """,
        (
            metadata.get("reason"),
            blocking_json,
            graduation_json,
            metadata.get("target_entry_price"),
            metadata.get("qg_rank"),
            verdict_id,
            ticker,
            ticker,
        ),
    )
    logger.info(
        "Watchlist metadata for %s: %d blocking factors, target=$%s",
        ticker,
        len(metadata.get("blocking_factors", [])),
        metadata.get("target_entry_price"),
    )
