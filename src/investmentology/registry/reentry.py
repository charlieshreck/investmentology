"""Re-entry qualification gate.

When agents reject a stock (AVOID/DISCARD verdict), we extract structured
block conditions from their consensus signal tags and store them with a
baseline metric snapshot.  Before re-queuing any ticker for analysis we
check whether those conditions have materially changed.

Block types:
  quantitative  — clears when a measurable metric crosses a threshold
  time_gated    — clears after a cooldown period
  permanent     — requires manual override
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Signal tag → block condition mapping
# ---------------------------------------------------------------------------
# Each entry: (block_type, condition_key, threshold)
#   condition_key tells the checker *what* to compare
#   threshold is the magnitude of change required to clear

BLOCK_CONDITIONS: dict[str, tuple[str, str, float]] = {
    # Valuation — need price drop to clear
    "OVERVALUED":           ("quantitative", "price_drop_pct",       10.0),
    "FAIRLY_VALUED":        ("quantitative", "price_drop_pct",        5.0),

    # Fundamental deterioration — need metric improvement
    "MARGIN_COMPRESSING":   ("quantitative", "margin_recovery",       0.02),
    "EARNINGS_QUALITY_LOW": ("quantitative", "earnings_improvement",  0.01),
    "LEVERAGE_HIGH":        ("quantitative", "leverage_reduction",    0.05),
    "BALANCE_SHEET_WEAK":   ("quantitative", "leverage_reduction",    0.05),
    "REVENUE_DECELERATING": ("quantitative", "revenue_growth",        0.0),
    "ROIC_DECLINING":       ("quantitative", "roic_improvement",      0.01),

    # Technical — need price recovery
    "BREAKDOWN_CONFIRMED":  ("quantitative", "price_recovery_pct",    5.0),
    "DEATH_CROSS":          ("quantitative", "price_recovery_pct",   10.0),
    "RSI_OVERBOUGHT":       ("quantitative", "price_drop_pct",        5.0),
    "TREND_DOWNTREND":      ("quantitative", "price_recovery_pct",    5.0),

    # Qualitative — time-gated cooldown (days)
    "ACCOUNTING_RED_FLAG":        ("time_gated", "cooldown_days", 90),
    "GOVERNANCE_CONCERN":         ("time_gated", "cooldown_days", 90),
    "RISK_LITIGATION":            ("time_gated", "cooldown_days", 90),
    "RISK_KEY_PERSON":            ("time_gated", "cooldown_days", 60),
    "REGULATORY_CHANGE":          ("time_gated", "cooldown_days", 60),
    "GEOPOLITICAL_RISK":          ("time_gated", "cooldown_days", 30),
    "SUPPLY_CHAIN_DISRUPTION":    ("time_gated", "cooldown_days", 30),

    # Hard rejections — permanent until manual override
    "REJECT_HARD":  ("permanent", "manual_override", 0),
    "MUNGER_VETO":  ("permanent", "manual_override", 0),
}

# Minimum number of agents that must agree on a signal for it to create a block
CONSENSUS_THRESHOLD = 2


def _safe_div(numerator, denominator) -> float | None:
    """Safe division returning None on zero/None denominator."""
    try:
        n = float(numerator or 0)
        d = float(denominator or 0)
        if d == 0:
            return None
        return n / d
    except (TypeError, ValueError):
        return None


def _snapshot_baseline(condition_key: str, fundamentals: dict | None) -> float | None:
    """Capture the baseline metric value at rejection time.

    Args:
        condition_key: What metric this block tracks.
        fundamentals: Latest fundamentals_cache row as dict (or object with attrs).

    Returns:
        The baseline value to store, or None if unavailable.
    """
    if fundamentals is None:
        return None

    # Support both dict and object access
    def _get(key: str):
        if isinstance(fundamentals, dict):
            return fundamentals.get(key)
        return getattr(fundamentals, key, None)

    if condition_key in ("price_drop_pct", "price_recovery_pct"):
        p = _get("price")
        return float(p) if p and float(p) > 0 else None

    if condition_key == "margin_recovery":
        return _safe_div(_get("operating_income"), _get("revenue"))

    if condition_key == "earnings_improvement":
        return _safe_div(_get("net_income"), _get("revenue"))

    if condition_key == "leverage_reduction":
        return _safe_div(_get("total_debt"), _get("total_assets"))

    if condition_key == "revenue_growth":
        rev = _get("revenue")
        return float(rev) if rev else None

    if condition_key == "roic_improvement":
        roic = _get("roic")
        if roic is not None:
            return float(roic)
        # Compute from raw fields: operating_income / (NWC + net_ppe)
        oi = _get("operating_income")
        ca = _get("current_assets")
        cl = _get("current_liabilities")
        ppe = _get("net_ppe")
        if oi and ca and cl and ppe:
            invested = (float(ca) - float(cl)) + float(ppe)
            if invested > 0:
                return float(oi) / invested
        return None

    # time_gated and permanent don't need baselines
    return None


# ---------------------------------------------------------------------------
# Block extraction — called after saving a negative verdict
# ---------------------------------------------------------------------------

def extract_and_save_blocks(
    registry,
    verdict_id: int,
    ticker: str,
    agent_signal_tags: list[list[str]],
    fundamentals: dict | None,
) -> int:
    """Extract block conditions from agent consensus and persist them.

    Args:
        registry: Registry instance (has ._db for raw SQL).
        verdict_id: The verdict row id.
        ticker: Stock ticker.
        agent_signal_tags: List of tag-lists, one per agent.
            e.g. [["OVERVALUED","REJECT"], ["OVERVALUED","LEVERAGE_HIGH"], ...]
        fundamentals: Latest fundamentals snapshot (dict or FundamentalsSnapshot).

    Returns:
        Number of blocks created.
    """
    # Count how many agents emitted each blockable tag
    tag_counts: Counter[str] = Counter()
    for tags in agent_signal_tags:
        # Deduplicate per-agent (an agent shouldn't double-count)
        seen = set()
        for tag in tags:
            tag_str = tag.value if hasattr(tag, "value") else str(tag)
            if tag_str in BLOCK_CONDITIONS and tag_str not in seen:
                tag_counts[tag_str] += 1
                seen.add(tag_str)

    # Only create blocks for tags with sufficient consensus
    blocks_created = 0
    for tag_str, count in tag_counts.items():
        if count < CONSENSUS_THRESHOLD:
            continue

        block_type, condition_key, threshold = BLOCK_CONDITIONS[tag_str]
        baseline = _snapshot_baseline(condition_key, fundamentals)

        # For quantitative blocks, skip if we can't capture a baseline
        if block_type == "quantitative" and baseline is None:
            logger.debug(
                "Skipping quantitative block %s for %s: no baseline available",
                tag_str, ticker,
            )
            continue

        try:
            registry._db.execute(
                "INSERT INTO invest.reentry_blocks "
                "(ticker, verdict_id, block_type, signal_tag, condition_key, "
                "threshold, baseline_value, agent_count) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (ticker, verdict_id, block_type, tag_str, condition_key,
                 Decimal(str(threshold)), Decimal(str(baseline)) if baseline is not None else None,
                 count),
            )
            blocks_created += 1
            logger.info(
                "Block created: %s %s (%s, key=%s, baseline=%s, threshold=%s, agents=%d)",
                ticker, tag_str, block_type, condition_key, baseline, threshold, count,
            )
        except Exception:
            logger.exception("Failed to insert reentry block for %s/%s", ticker, tag_str)

    if blocks_created:
        logger.info("Created %d reentry blocks for %s (verdict_id=%d)", blocks_created, ticker, verdict_id)

    return blocks_created


# ---------------------------------------------------------------------------
# Block clearing — called before building the analysis queue
# ---------------------------------------------------------------------------

def _check_quantitative(condition_key: str, threshold: float,
                        baseline: float, fundamentals: dict | None) -> bool:
    """Check if a quantitative condition has cleared.

    Returns True if the condition is satisfied (block should clear).
    """
    if fundamentals is None or baseline is None:
        return False

    def _get(key: str):
        if isinstance(fundamentals, dict):
            return fundamentals.get(key)
        return getattr(fundamentals, key, None)

    current: float | None = None

    if condition_key == "price_drop_pct":
        p = _get("price")
        if p and float(p) > 0 and baseline > 0:
            drop = (baseline - float(p)) / baseline * 100
            return drop >= threshold
        return False

    if condition_key == "price_recovery_pct":
        p = _get("price")
        if p and float(p) > 0 and baseline > 0:
            recovery = (float(p) - baseline) / baseline * 100
            return recovery >= threshold
        return False

    if condition_key == "margin_recovery":
        current = _safe_div(_get("operating_income"), _get("revenue"))
        if current is not None:
            return (current - baseline) >= threshold
        return False

    if condition_key == "earnings_improvement":
        current = _safe_div(_get("net_income"), _get("revenue"))
        if current is not None:
            return (current - baseline) >= threshold
        return False

    if condition_key == "leverage_reduction":
        current = _safe_div(_get("total_debt"), _get("total_assets"))
        if current is not None:
            return (baseline - current) >= threshold  # Lower is better
        return False

    if condition_key == "revenue_growth":
        rev = _get("revenue")
        if rev and baseline:
            return float(rev) > baseline  # Any positive growth
        return False

    if condition_key == "roic_improvement":
        roic = _get("roic")
        if roic is None:
            oi = _get("operating_income")
            ca = _get("current_assets")
            cl = _get("current_liabilities")
            ppe = _get("net_ppe")
            if oi and ca and cl and ppe:
                invested = (float(ca) - float(cl)) + float(ppe)
                if invested > 0:
                    roic = float(oi) / invested
        if roic is not None:
            return (float(roic) - baseline) >= threshold
        return False

    return False


def check_and_clear_blocks(db, fundamentals_by_ticker: dict[str, dict]) -> int:
    """Check all active blocks and clear those whose conditions are satisfied.

    Args:
        db: Database instance.
        fundamentals_by_ticker: {ticker: fundamentals_dict} for current data.

    Returns:
        Number of blocks cleared.
    """
    rows = db.execute(
        "SELECT id, ticker, block_type, condition_key, threshold, "
        "baseline_value, created_at "
        "FROM invest.reentry_blocks "
        "WHERE is_cleared = FALSE"
    )

    cleared = 0
    for row in rows:
        block_id = row["id"]
        ticker = row["ticker"]
        block_type = row["block_type"]
        condition_key = row["condition_key"]
        threshold = float(row["threshold"]) if row["threshold"] is not None else 0
        baseline = float(row["baseline_value"]) if row["baseline_value"] is not None else None

        should_clear = False
        reason = ""

        if block_type == "quantitative":
            fund = fundamentals_by_ticker.get(ticker)
            if fund and _check_quantitative(condition_key, threshold, baseline, fund):
                should_clear = True
                reason = f"{condition_key} threshold met"

        elif block_type == "time_gated":
            created = row["created_at"]
            if created:
                if hasattr(created, "tzinfo") and created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                elapsed_days = (datetime.now(timezone.utc) - created).total_seconds() / 86400
                if elapsed_days >= threshold:
                    should_clear = True
                    reason = f"Cooldown elapsed ({elapsed_days:.0f} >= {threshold:.0f} days)"

        elif block_type == "permanent":
            # Permanent blocks only cleared manually
            continue

        if should_clear:
            try:
                db.execute(
                    "UPDATE invest.reentry_blocks "
                    "SET is_cleared = TRUE, cleared_at = NOW(), cleared_reason = %s "
                    "WHERE id = %s",
                    (reason, block_id),
                )
                cleared += 1
                logger.info("Block cleared: %s #%d (%s)", ticker, block_id, reason)
            except Exception:
                logger.exception("Failed to clear block %d", block_id)

    if cleared:
        logger.info("Cleared %d reentry blocks", cleared)
    return cleared


def get_blocked_tickers(db) -> set[str]:
    """Return the set of tickers that have any active (un-cleared) blocks."""
    rows = db.execute(
        "SELECT DISTINCT ticker FROM invest.reentry_blocks WHERE is_cleared = FALSE"
    )
    return {r["ticker"] for r in rows}


def clear_blocks_for_ticker(db, ticker: str, reason: str = "positive_verdict") -> int:
    """Clear all active blocks for a ticker (e.g. when it gets a positive verdict).

    Returns number of blocks cleared.
    """
    rows = db.execute(
        "UPDATE invest.reentry_blocks "
        "SET is_cleared = TRUE, cleared_at = NOW(), cleared_reason = %s "
        "WHERE ticker = %s AND is_cleared = FALSE "
        "RETURNING id",
        (reason, ticker),
    )
    count = len(rows)
    if count:
        logger.info("Cleared %d blocks for %s (reason: %s)", count, ticker, reason)
    return count


def manual_clear_blocks(db, ticker: str, reason: str = "manual_override") -> int:
    """Admin override: clear all blocks for a ticker including permanent ones."""
    return clear_blocks_for_ticker(db, ticker, reason=reason)


def create_gate_blocks(
    db,
    ticker: str,
    screener_signal_tags: list[list[str]],
    fundamentals: dict | None,
) -> int:
    """Create reentry blocks from scout gate rejection (no verdict required).

    Called when a screener rejects a ticker at the gate. Creates blocks using
    the same BLOCK_CONDITIONS mapping so they auto-clear when fundamentals change.

    Args:
        db: Database instance.
        ticker: Stock ticker.
        screener_signal_tags: List of tag-lists, one per screener.
        fundamentals: Latest fundamentals snapshot.

    Returns:
        Number of blocks created.
    """
    # Count how many screeners emitted each blockable tag
    tag_counts: Counter[str] = Counter()
    for tags in screener_signal_tags:
        seen = set()
        for tag in tags:
            tag_str = tag.value if hasattr(tag, "value") else str(tag)
            if tag_str in BLOCK_CONDITIONS and tag_str not in seen:
                tag_counts[tag_str] += 1
                seen.add(tag_str)

    blocks_created = 0
    for tag_str, count in tag_counts.items():
        # With 4 screeners, require at least 2 to agree on a blocking signal
        if count < 2:
            continue

        block_type, condition_key, threshold = BLOCK_CONDITIONS[tag_str]
        baseline = _snapshot_baseline(condition_key, fundamentals)

        if block_type == "quantitative" and baseline is None:
            logger.debug(
                "Skipping gate block %s for %s: no baseline available",
                tag_str, ticker,
            )
            continue

        try:
            db.execute(
                "INSERT INTO invest.reentry_blocks "
                "(ticker, verdict_id, block_type, signal_tag, condition_key, "
                "threshold, baseline_value, agent_count) "
                "VALUES (%s, NULL, %s, %s, %s, %s, %s, %s)",
                (ticker, block_type, tag_str, condition_key,
                 Decimal(str(threshold)),
                 Decimal(str(baseline)) if baseline is not None else None,
                 count),
            )
            blocks_created += 1
            logger.info(
                "Gate block: %s %s (%s, key=%s, baseline=%s, screeners=%d)",
                ticker, tag_str, block_type, condition_key, baseline, count,
            )
        except Exception:
            logger.exception("Failed to insert gate block for %s/%s", ticker, tag_str)

    if blocks_created:
        logger.info(
            "Created %d gate blocks for %s (screener consensus)",
            blocks_created, ticker,
        )
    return blocks_created
