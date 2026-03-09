"""Recommendations endpoints — stocks that have met all criteria, ready for portfolio action."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends

from investmentology.api.deps import get_registry
from investmentology.advisory.portfolio_fit import PortfolioFitScorer
from investmentology.advisory.prediction_card import (
    AgentTarget,
    PredictionCard,
    PredictionCardInputs,
    build_prediction_card,
)
from investmentology.api.routes.shared import (
    consensus_tier as _consensus_tier,
    get_dividend_data,
    success_probability as _success_probability,
    verdict_stability as _verdict_stability,
)
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

router = APIRouter()

# Positive verdicts indicating the stock passed all criteria
POSITIVE_VERDICTS = {"STRONG_BUY", "BUY", "ACCUMULATE"}
VERDICT_ORDER = ["STRONG_BUY", "BUY", "ACCUMULATE"]


def _build_price_history(row: dict, registry: Registry) -> list[dict]:
    """Build price history for a recommendation from verdict history."""
    ticker = row.get("ticker")
    if not ticker or not registry:
        return []

    try:
        rows = registry._db.execute(
            """SELECT v.verdict, v.confidence, v.created_at
               FROM invest.verdicts v
               WHERE v.ticker = %s
               ORDER BY v.created_at DESC
               LIMIT 10""",
            (ticker,),
        )
        if not rows:
            return []

        return [
            {
                "date": str(r["created_at"])[:10] if r.get("created_at") else None,
                "verdict": r.get("verdict"),
                "confidence": float(r["confidence"]) if r.get("confidence") else None,
            }
            for r in rows
        ]
    except Exception:
        return []

def _build_prediction_cards(
    registry: Registry, tickers: list[str],
) -> dict[str, PredictionCard]:
    """Batch-build prediction cards for recommendation tickers."""
    if not tickers:
        return {}

    db = registry._db
    result: dict[str, PredictionCard] = {}

    # 1. Batch-fetch agent signal rows (target prices)
    signal_map: dict[str, list[dict]] = {}
    try:
        placeholders = ",".join(["%s"] * len(tickers))
        rows = db.execute(
            "SELECT DISTINCT ON (ticker, agent_name) ticker, agent_name, signals "
            "FROM invest.agent_signals "
            f"WHERE ticker IN ({placeholders}) "
            "ORDER BY ticker, agent_name, created_at DESC",
            tuple(tickers),
        )
        for r in (rows or []):
            signal_map.setdefault(r["ticker"], []).append(r)
    except Exception:
        logger.debug("Could not fetch agent signals for prediction cards")

    # 2. Batch-fetch quant gate data
    qg_map: dict[str, dict] = {}
    try:
        placeholders = ",".join(["%s"] * len(tickers))
        rows = db.execute(
            "SELECT ticker, combined_rank, piotroski_score, altman_zone "
            "FROM invest.quant_gate_results "
            "WHERE run_id = ("
            "  SELECT id FROM invest.quant_gate_runs ORDER BY id DESC LIMIT 1"
            f") AND ticker IN ({placeholders})",
            tuple(tickers),
        )
        for r in (rows or []):
            qg_map[r["ticker"]] = r
    except Exception:
        logger.debug("Could not fetch quant gate data for prediction cards")

    # 3. Batch-fetch earnings context
    earnings_map: dict[str, str | None] = {}
    try:
        from investmentology.advisory.earnings_calendar import (
            classify_earnings_proximity,
            format_earnings_alert,
        )
        placeholders = ",".join(["%s"] * len(tickers))
        rows = db.execute(
            "SELECT DISTINCT ON (ticker) ticker, data_value "
            "FROM invest.pipeline_data_cache "
            f"WHERE ticker IN ({placeholders}) AND data_key = 'earnings_context' "
            "ORDER BY ticker, created_at DESC",
            tuple(tickers),
        )
        for r in (rows or []):
            if r.get("data_value"):
                try:
                    proximity = classify_earnings_proximity(r["ticker"], r["data_value"])
                    warning = format_earnings_alert(proximity)
                    if warning is None and proximity.days_to_earnings is not None:
                        warning = f"Earnings in {proximity.days_to_earnings}d"
                    earnings_map[r["ticker"]] = warning
                except Exception:
                    pass
    except Exception:
        logger.debug("Could not fetch earnings context for prediction cards")

    # 4. SPY benchmark
    spy_price = None
    try:
        spy_rows = db.execute(
            "SELECT spy_price FROM invest.market_snapshots "
            "ORDER BY snapshot_date DESC LIMIT 1",
        )
        if spy_rows:
            spy_price = float(spy_rows[0]["spy_price"])
    except Exception:
        pass

    # 5. Skill weights
    try:
        from investmentology.agents.skills import SKILLS
    except Exception:
        SKILLS = {}

    # Build card for each ticker
    for ticker in tickers:
        try:
            signals = signal_map.get(ticker, [])
            if not signals:
                continue

            # Extract agent target prices
            pc_targets: list[AgentTarget] = []
            for r in signals:
                sigs = r.get("signals")
                if sigs and isinstance(sigs, str):
                    sigs = json.loads(sigs)
                if sigs and isinstance(sigs, dict):
                    tp = sigs.get("target_price")
                    if tp and isinstance(tp, (int, float)) and tp > 0:
                        agent_name = r["agent_name"]
                        weight = SKILLS[agent_name].base_weight if agent_name in SKILLS else 0.05
                        pc_targets.append(AgentTarget(
                            agent=agent_name, target_price=float(tp), weight=weight,
                        ))

            if not pc_targets:
                continue

            # Bear case from Klarman
            bear_case = None
            for r in signals:
                if r["agent_name"] == "klarman":
                    sigs = r.get("signals")
                    if sigs and isinstance(sigs, str):
                        sigs = json.loads(sigs)
                    if sigs and isinstance(sigs, dict):
                        bc = sigs.get("bear_case_price") or sigs.get("bear_case")
                        if bc and isinstance(bc, (int, float)) and bc > 0:
                            bear_case = float(bc)

            qg = qg_map.get(ticker) or {}

            inputs = PredictionCardInputs(
                ticker=ticker,
                current_price=0,  # Will be set from row data
                verdict="",       # Will be set from row data
                confidence=0,     # Will be set from row data
                agent_targets=pc_targets,
                bear_case_price=bear_case,
                quant_gate_rank=qg.get("combined_rank"),
                piotroski_score=qg.get("piotroski_score"),
                altman_zone=qg.get("altman_zone"),
                earnings_warning=earnings_map.get(ticker),
                spy_price=spy_price,
            )
            result[ticker] = inputs  # Store inputs; finalize with row data later
        except Exception:
            logger.debug("Could not build prediction card for %s", ticker)

    return result


def _finalize_prediction_card(
    inputs: PredictionCardInputs,
    row: dict,
) -> PredictionCard | None:
    """Finalize prediction card with row-specific data (price, verdict, confidence)."""
    try:
        price = float(row.get("current_price") or 0)
        if price <= 0:
            return None
        inputs.current_price = price
        inputs.verdict = row.get("verdict", "")
        inputs.confidence = float(row.get("confidence") or 0)

        # Compute consensus % from agent stances
        stances = row.get("agent_stances") or []
        if isinstance(stances, str):
            stances = json.loads(stances)
        bullish = sum(1 for s in stances if s.get("sentiment", 0) > 0)
        inputs.agent_consensus_pct = (bullish / len(stances) * 100) if stances else 0.0

        return build_prediction_card(inputs)
    except Exception:
        return None


def _format_recommendation(row: dict, registry: Registry | None = None) -> dict:
    entry_price = float(row["entry_price"]) if row.get("entry_price") else 0.0
    current_price = float(row["current_price"]) if row.get("current_price") else 0.0
    change_pct = (
        ((current_price - entry_price) / entry_price * 100)
        if entry_price > 0 else 0.0
    )

    # Compute verdict stability and consensus tier
    cons_score = float(row["consensus_score"]) if row.get("consensus_score") else None
    stability = row.get("_stability")  # Pre-computed if registry available
    cons_tier = _consensus_tier(cons_score)

    result = {
        "ticker": row["ticker"],
        "name": row.get("name") or row["ticker"],
        "sector": row.get("sector") or "",
        "industry": row.get("industry") or "",
        "currentPrice": current_price,
        "marketCap": float(row["market_cap"]) if row.get("market_cap") else 0,
        "watchlistState": row.get("watchlist_state"),
        "verdict": row["verdict"],
        "confidence": float(row["confidence"]) if row.get("confidence") else None,
        "consensusScore": cons_score,
        "consensusTier": cons_tier,
        "reasoning": row.get("reasoning"),
        "agentStances": row.get("agent_stances"),
        "riskFlags": row.get("risk_flags"),
        "auditorOverride": row.get("auditor_override", False),
        "mungerOverride": row.get("munger_override", False),
        "advisoryOpinions": row.get("advisory_opinions"),
        "boardNarrative": row.get("board_narrative"),
        "boardAdjustedVerdict": row.get("board_adjusted_verdict"),
        "adversarialResult": row.get("adversarial_result"),
        "analysisDate": str(row["created_at"]) if row.get("created_at") else None,
        "successProbability": _success_probability(row),
        "changePct": round(change_pct, 2),
        "priceHistory": _build_price_history(row, registry) if registry else row.get("price_history") or [],
    }

    if stability:
        result["stabilityScore"] = stability[0]
        result["stabilityLabel"] = stability[1]

    # Add portfolio fit if scorer is available
    fit = row.get("_portfolio_fit")
    if fit:
        result["portfolioFit"] = {
            "score": fit.score,
            "reasoning": fit.reasoning,
            "diversificationScore": fit.diversification_score,
            "balanceScore": fit.balance_score,
            "capacityScore": fit.capacity_score,
            "alreadyHeld": fit.already_held,
        }

    # Add dividend data if available
    div_data = row.get("_dividend_data")
    if div_data:
        result["dividendYield"] = div_data["yield"]
        result["annualDividend"] = div_data["annual"]
        result["dividendFrequency"] = div_data["frequency"]

    # Add buzz score
    buzz = row.get("_buzz")
    if buzz:
        result["buzzScore"] = buzz["buzz_score"]
        result["buzzLabel"] = buzz["buzz_label"]
        result["headlineSentiment"] = buzz["headline_sentiment"]
        result["contrarianFlag"] = buzz.get("contrarian_flag", False)

    # Add earnings momentum
    earnings_m = row.get("_earnings_momentum")
    if earnings_m:
        result["earningsMomentum"] = {
            "score": earnings_m["momentum_score"],
            "label": earnings_m["momentum_label"],
            "upwardRevisions": earnings_m["upward_revisions"],
            "downwardRevisions": earnings_m["downward_revisions"],
            "beatStreak": earnings_m["beat_streak"],
        }

    # Suggest position category with richer labels
    core_signals = 0
    tactical_signals = 0
    income_signals = 0
    verdict = row.get("verdict", "")
    if verdict == "STRONG_BUY":
        core_signals += 2
    elif verdict == "ACCUMULATE":
        core_signals += 1
    conf = float(row["confidence"]) if row.get("confidence") else 0
    if conf >= 0.75:
        core_signals += 1
    elif conf < 0.55:
        tactical_signals += 1
    if stability and stability[1] == "STABLE":
        core_signals += 1
    elif stability and stability[1] == "UNSTABLE":
        tactical_signals += 1
    if cons_tier == "HIGH_CONVICTION":
        core_signals += 1
    elif cons_tier == "CONTRARIAN":
        tactical_signals += 1
    div_yield = result.get("dividendYield", 0) or 0
    if div_yield >= 3.0:
        income_signals += 2
    elif div_yield >= 1.5:
        income_signals += 1
        core_signals += 1
    buzz_label = result.get("buzzLabel")
    if buzz_label == "HIGH":
        tactical_signals += 1

    # Determine category and label
    if income_signals >= 2 and core_signals >= 1:
        suggested_type = "income"
        suggested_label = "Income Builder"
    elif result.get("contrarianFlag") and tactical_signals > core_signals:
        suggested_type = "contrarian"
        suggested_label = "Contrarian Bet"
    elif core_signals > tactical_signals:
        if conf >= 0.8 and stability and stability[1] == "STABLE":
            suggested_type = "core"
            suggested_label = "Strong Conviction"
        else:
            suggested_type = "core"
            suggested_label = "Core Hold"
    else:
        suggested_type = "tactical"
        suggested_label = "Momentum Play"

    result["suggestedType"] = suggested_type
    result["suggestedLabel"] = suggested_label

    # Thesis data for held positions
    held_info = row.get("_held_info")
    if held_info:
        result["heldPosition"] = held_info

    # Verdict math (Batch 8 enrichment)
    verdict_margin = row.get("verdict_margin")
    conviction_gap = row.get("conviction_gap")
    headcount_summary = row.get("headcount_summary")
    if verdict_margin is not None or conviction_gap is not None:
        result["verdictMath"] = {
            "sentiment": cons_score,
            "confidence": float(row["confidence"]) if row.get("confidence") else None,
            "marginToBoundary": float(verdict_margin) if verdict_margin is not None else None,
            "convictionGap": conviction_gap,
            "headcountSummary": headcount_summary,
        }

    # Agent contributions (weight x confidence per agent)
    agent_contribs = row.get("agent_contributions")
    if agent_contribs and isinstance(agent_contribs, list):
        result["agentContributions"] = agent_contribs

    # Position type classification
    pos_type = row.get("position_type") or (held_info or {}).get("positionType")
    if pos_type:
        result["positionType"] = {
            "type": pos_type,
            "classificationSource": "portfolio" if held_info else "inferred",
        }

    # Regime context
    regime = row.get("regime_label")
    if regime:
        result["regimeContext"] = {
            "currentRegime": regime,
        }

    # Watchlist metadata
    watchlist_reason = row.get("watchlist_reason")
    if watchlist_reason:
        result["watchlistMeta"] = {
            "reason": watchlist_reason,
            "graduationTrigger": row.get("watchlist_graduation_trigger"),
        }

    # Data source coverage
    dsc = row.get("_data_source_count")
    if dsc is not None:
        result["dataSourceCount"] = dsc
        result["dataSourceTotal"] = row.get("_data_source_total", 12)

    # Prediction card
    pc = row.get("_prediction_card")
    if pc:
        result["predictionCard"] = pc.to_dict()

    # Adversarial result (already in row, now surfaced)
    adv = row.get("adversarial_result")
    if adv:
        result["adversarialResult"] = adv

    return result


@router.get("/recommendations")
def get_recommendations(registry: Registry = Depends(get_registry)) -> dict:
    """Stocks that have met all criteria — ready for portfolio action.

    Filtered to STRONG_BUY, BUY, ACCUMULATE verdicts only.
    Each item includes a blended success probability and portfolio-fit score.
    """
    rows = registry.get_all_actionable_verdicts()

    # Filter to positive verdicts only
    positive_rows = [r for r in rows if r.get("verdict") in POSITIVE_VERDICTS]

    # Fast enrichment (DB only — sub-millisecond per ticker)
    for row in positive_rows:
        ticker = row.get("ticker", "")
        if ticker:
            try:
                row["_stability"] = _verdict_stability(ticker, registry)
            except Exception:
                pass

    try:
        scorer = PortfolioFitScorer(registry)
        for row in positive_rows:
            row["_portfolio_fit"] = scorer.score(row.get("ticker", ""), row.get("sector"))
    except Exception:
        pass

    # Enrich held positions with thesis lifecycle data
    try:
        from investmentology.advisory.thesis_health import assess_thesis_health
        from datetime import date

        positions = registry.get_open_positions()
        held_map = {p.ticker: p for p in positions}

        for row in positive_rows:
            ticker = row.get("ticker", "")
            pos = held_map.get(ticker)
            if not pos:
                continue
            assessment = assess_thesis_health(ticker, registry, pos.position_type)
            days_held = (date.today() - pos.entry_date).days if pos.entry_date else 0
            pnl_pct = float(pos.pnl_pct * 100) if pos.entry_price else 0

            # Get entry thesis
            entry_thesis = pos.thesis
            try:
                et_rows = registry._db.execute(
                    "SELECT entry_thesis FROM invest.portfolio_positions "
                    "WHERE ticker = %s AND is_closed = false LIMIT 1",
                    (ticker,),
                )
                if et_rows and et_rows[0].get("entry_thesis"):
                    entry_thesis = et_rows[0]["entry_thesis"]
            except Exception:
                pass

            row["_held_info"] = {
                "positionType": pos.position_type,
                "daysHeld": days_held,
                "pnlPct": round(pnl_pct, 2),
                "entryPrice": float(pos.entry_price),
                "thesisHealth": assessment.health.value,
                "convictionTrend": assessment.conviction_trend,
                "entryThesis": (entry_thesis or "")[:200],
                "reasoning": assessment.reasoning,
            }
    except Exception:
        logger.debug("Could not enrich held positions with thesis data")

    # Enrichment from DB (populated by daily monitor cronjob — no external API calls)
    rec_tickers = [r.get("ticker", "") for r in positive_rows if r.get("ticker")]

    # Batch-fetch buzz scores from DB
    buzz_results: dict = {}
    if rec_tickers:
        try:
            placeholders = ",".join(["%s"] * len(rec_tickers))
            buzz_rows = registry._db.execute(
                f"SELECT DISTINCT ON (ticker) ticker, buzz_score, buzz_label, "
                f"headline_sentiment, news_count_7d, news_count_30d, contrarian_flag "
                f"FROM invest.buzz_scores WHERE ticker IN ({placeholders}) "
                f"ORDER BY ticker, scored_at DESC",
                tuple(rec_tickers),
            )
            for b in (buzz_rows or []):
                buzz_results[b["ticker"]] = b
        except Exception:
            logger.debug("Could not fetch buzz scores from DB")

    # Batch-fetch earnings momentum from DB
    earnings_results: dict = {}
    if rec_tickers:
        try:
            placeholders = ",".join(["%s"] * len(rec_tickers))
            em_rows = registry._db.execute(
                f"SELECT DISTINCT ON (ticker) ticker, momentum_score, momentum_label, "
                f"upward_revisions, downward_revisions, beat_streak "
                f"FROM invest.earnings_momentum WHERE ticker IN ({placeholders}) "
                f"ORDER BY ticker, computed_at DESC",
                tuple(rec_tickers),
            )
            for em in (em_rows or []):
                earnings_results[em["ticker"]] = em
        except Exception:
            logger.debug("Could not fetch earnings momentum from DB")

    # Dividends: yfinance with in-memory cache (fast after first load)
    div_data: dict = {}
    try:
        div_data = get_dividend_data(rec_tickers)
    except Exception:
        logger.debug("Dividend enrichment failed")

    # Batch-fetch data source coverage from pipeline_data_cache
    data_coverage: dict[str, int] = {}
    _DATA_KEYS_TOTAL = 12  # fundamentals through research_briefing
    if rec_tickers:
        try:
            placeholders = ",".join(["%s"] * len(rec_tickers))
            cov_rows = registry._db.execute(
                f"SELECT ticker, COUNT(DISTINCT data_key) AS cnt "
                f"FROM invest.pipeline_data_cache "
                f"WHERE ticker IN ({placeholders}) "
                f"GROUP BY ticker",
                tuple(rec_tickers),
            )
            for cr in (cov_rows or []):
                data_coverage[cr["ticker"]] = cr["cnt"]
        except Exception:
            logger.debug("Could not fetch data coverage counts")

    # Build prediction cards (batch — 4 queries total)
    pc_inputs: dict = {}
    try:
        pc_inputs = _build_prediction_cards(registry, rec_tickers)
    except Exception:
        logger.debug("Could not build prediction cards")

    # Apply enrichment results
    for row in positive_rows:
        ticker = row.get("ticker", "")
        # Data coverage
        row["_data_source_count"] = data_coverage.get(ticker, 0)
        row["_data_source_total"] = _DATA_KEYS_TOTAL
        # Buzz
        buzz = buzz_results.get(ticker)
        if buzz:
            row["_buzz"] = buzz
        # Dividends
        dd = div_data.get(ticker)
        if dd and dd.get("annual_div", 0) > 0:
            price = float(row.get("current_price") or 0)
            div_yield = (dd["annual_div"] / price * 100) if price > 0 else 0.0
            row["_dividend_data"] = {
                "yield": round(div_yield, 2),
                "annual": round(dd["annual_div"], 2),
                "frequency": dd.get("frequency", "none"),
            }
        # Earnings
        em = earnings_results.get(ticker)
        if em:
            row["_earnings_momentum"] = em
        # Prediction card
        pc_input = pc_inputs.get(ticker)
        if pc_input:
            card = _finalize_prediction_card(pc_input, row)
            if card:
                row["_prediction_card"] = card

    items = [_format_recommendation(r, registry) for r in positive_rows]

    grouped: dict[str, list[dict]] = {}
    for item in items:
        verdict = item["verdict"]
        if verdict not in grouped:
            grouped[verdict] = []
        grouped[verdict].append(item)

    # Sort groups by verdict strength
    ordered_grouped: dict[str, list[dict]] = {}
    for v in VERDICT_ORDER:
        if v in grouped:
            ordered_grouped[v] = grouped[v]

    return {
        "items": items,
        "groupedByVerdict": ordered_grouped,
        "totalCount": len(items),
    }
