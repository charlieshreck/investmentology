"""Agent accuracy tracking — measures per-agent signal accuracy over time.

Records each agent's directional signals and settles them against actual
price movements at 30d and 90d horizons. Provides accuracy stats by agent
and by regime for dynamic weight adjustment.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


def record_agent_signal(
    db,
    agent_name: str,
    ticker: str,
    signal_type: str,
    confidence: float | None,
    price_at_signal: float | None,
    regime: str | None = None,
) -> None:
    """Record an agent signal for future accuracy tracking."""
    db.execute(
        "INSERT INTO invest.agent_accuracy "
        "(agent_name, ticker, signal_date, signal_type, confidence, "
        "price_at_signal, regime) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (agent_name, ticker, date.today(), signal_type, confidence,
         price_at_signal, regime),
    )


def settle_accuracy(db) -> int:
    """Settle unsettled agent signals by checking current prices.

    Called periodically (e.g., daily). Looks up current price for each
    unsettled signal and computes whether the directional call was correct.

    Returns number of signals settled.
    """
    import yfinance as yf

    settled = 0
    today = date.today()

    # Find unsettled signals that are old enough
    unsettled = db.execute(
        "SELECT id, ticker, signal_date, signal_type, price_at_signal "
        "FROM invest.agent_accuracy "
        "WHERE (settled_30d = FALSE AND signal_date <= %s) "
        "   OR (settled_90d = FALSE AND signal_date <= %s)",
        (today - timedelta(days=30), today - timedelta(days=90)),
    )

    if not unsettled:
        return 0

    # Batch fetch current prices
    tickers = list(set(r["ticker"] for r in unsettled))
    prices: dict[str, float] = {}
    try:
        for chunk_start in range(0, len(tickers), 50):
            chunk = tickers[chunk_start:chunk_start + 50]
            data = yf.download(chunk, period="1d", progress=False)
            if data is not None and not data.empty:
                close = data["Close"]
                if len(chunk) == 1:
                    if not close.empty:
                        prices[chunk[0]] = float(close.iloc[-1])
                else:
                    for t in chunk:
                        if t in close.columns:
                            series = close[t].dropna()
                            if not series.empty:
                                prices[t] = float(series.iloc[-1])
    except Exception:
        logger.warning("Failed to fetch prices for accuracy settlement", exc_info=True)
        return 0

    for row in unsettled:
        ticker = row["ticker"]
        if ticker not in prices or not row["price_at_signal"]:
            continue

        current_price = prices[ticker]
        entry_price = float(row["price_at_signal"])
        signal_date = row["signal_date"]
        signal_type = row["signal_type"]
        days_since = (today - signal_date).days

        ret = (current_price - entry_price) / entry_price if entry_price > 0 else 0

        updates = {}

        # Settle 30d
        if not row.get("settled_30d", True) and days_since >= 30:
            correct = _is_correct(signal_type, ret)
            updates["price_30d"] = current_price
            updates["return_30d"] = round(ret, 4)
            updates["correct_30d"] = correct
            updates["settled_30d"] = True

        # Settle 90d
        if not row.get("settled_90d", True) and days_since >= 90:
            correct = _is_correct(signal_type, ret)
            updates["price_90d"] = current_price
            updates["return_90d"] = round(ret, 4)
            updates["correct_90d"] = correct
            updates["settled_90d"] = True

        if updates:
            set_clauses = ", ".join(f"{k} = %s" for k in updates)
            values = list(updates.values()) + [row["id"]]
            db.execute(
                f"UPDATE invest.agent_accuracy SET {set_clauses} WHERE id = %s",  # noqa: S608
                values,
            )
            settled += 1

    # Refresh materialized view
    if settled > 0:
        try:
            db.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY invest.agent_accuracy_stats")
        except Exception:
            logger.debug("Could not refresh agent_accuracy_stats view", exc_info=True)

    logger.info("Settled %d agent accuracy records", settled)
    return settled


def get_agent_accuracy_stats(db) -> list[dict]:
    """Get per-agent accuracy stats from the materialized view."""
    try:
        rows = db.execute(
            "SELECT agent_name, regime, total_signals, settled_30d, settled_90d, "
            "accuracy_30d, accuracy_90d, avg_confidence, avg_return_30d, avg_return_90d "
            "FROM invest.agent_accuracy_stats "
            "ORDER BY agent_name, regime"
        )
        return [dict(r) for r in rows]
    except Exception:
        logger.debug("agent_accuracy_stats not available", exc_info=True)
        return []


def get_dynamic_weights(db) -> dict[str, float]:
    """Compute dynamic agent weights based on accuracy.

    Agents with higher accuracy at 90d get proportionally more weight.
    Falls back to base weights if insufficient data.
    """
    try:
        from investmentology.agents.skills import SKILLS

        stats = db.execute(
            "SELECT agent_name, "
            "AVG(CASE WHEN correct_90d THEN 1.0 ELSE 0.0 END) AS accuracy, "
            "COUNT(*) FILTER (WHERE settled_90d) AS n_settled "
            "FROM invest.agent_accuracy "
            "WHERE settled_90d = TRUE "
            "GROUP BY agent_name "
            "HAVING COUNT(*) FILTER (WHERE settled_90d) >= 10"
        )

        if not stats:
            return {name: skill.base_weight for name, skill in SKILLS.items()}

        # Compute accuracy-weighted adjustment
        accuracy_map = {r["agent_name"]: float(r["accuracy"]) for r in stats}
        base_weights = {name: skill.base_weight for name, skill in SKILLS.items()}

        # Blend: 70% base weight + 30% accuracy adjustment
        adjusted = {}
        for name, base in base_weights.items():
            if name in accuracy_map:
                acc = accuracy_map[name]
                adjusted[name] = base * 0.7 + acc * base * 0.3
            else:
                adjusted[name] = base

        # Normalize to sum to 1.0
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted
    except Exception:
        logger.debug("Dynamic weight computation failed", exc_info=True)
        from investmentology.agents.skills import SKILLS
        return {name: skill.base_weight for name, skill in SKILLS.items()}


def _is_correct(signal_type: str, actual_return: float) -> bool:
    """Determine if a signal was directionally correct."""
    if signal_type == "BUY":
        return actual_return > 0
    elif signal_type == "SELL":
        return actual_return < 0
    else:  # HOLD
        return abs(actual_return) < 0.10  # Within 10% is "correct" for hold
