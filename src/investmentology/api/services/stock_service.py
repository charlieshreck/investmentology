"""Business logic for stock deep-dive endpoints."""

from __future__ import annotations

import logging

from investmentology.api.routes.shared import consensus_tier, verdict_stability
from investmentology.data.profile import get_or_fetch_profile
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)


class StockService:
    def __init__(self, registry: Registry) -> None:
        self._reg = registry

    def get_stock(self, ticker: str) -> dict:
        """Full deep dive: profile, fundamentals, signals, decisions, watchlist state."""
        ticker = ticker.upper()
        registry = self._reg

        # Business profile (cached, fetched from yfinance on-demand)
        profile_data = None
        try:
            profile_row = get_or_fetch_profile(registry._db, ticker)
            if profile_row:
                profile_data = _format_profile(profile_row)
        except Exception:
            logger.debug("Could not fetch profile for %s", ticker)

        # Fundamentals
        fundamentals = registry.get_latest_fundamentals(ticker)
        fund_data = None
        if fundamentals:
            def _f(v):
                """Safely convert to float, returning None for NULL/NaN."""
                if v is None:
                    return None
                fv = float(v)
                return None if fv != fv else fv  # NaN check

            fund_data = {
                "ticker": fundamentals.ticker,
                "fetched_at": str(fundamentals.fetched_at),
                "market_cap": _f(fundamentals.market_cap),
                "operating_income": _f(fundamentals.operating_income),
                "revenue": _f(fundamentals.revenue),
                "net_income": _f(fundamentals.net_income),
                "total_debt": _f(fundamentals.total_debt),
                "cash": _f(fundamentals.cash),
                "shares_outstanding": fundamentals.shares_outstanding,
                "price": _f(fundamentals.price),
                "earnings_yield": _f(fundamentals.earnings_yield),
                "roic": _f(fundamentals.roic),
                "enterprise_value": _f(fundamentals.enterprise_value),
            }

        # Signals
        signal_rows = registry._db.execute(
            "SELECT agent_name, model, signals, confidence, reasoning, created_at "
            "FROM invest.agent_signals WHERE ticker = %s ORDER BY created_at DESC LIMIT 20",
            (ticker,),
        )

        # Decisions (with outcome from decision_outcomes table)
        decision_rows = registry._db.execute(
            "SELECT d.id, d.decision_type, d.layer_source, d.confidence, "
            "d.reasoning, d.created_at, dout.outcome, dout.settled_at "
            "FROM invest.decisions d "
            "LEFT JOIN invest.decision_outcomes dout ON dout.decision_id = d.id "
            "WHERE d.ticker = %s ORDER BY d.created_at DESC LIMIT 20",
            (ticker,),
        )
        decision_data = [
            {
                "id": str(r["id"]),
                "decisionType": r["decision_type"],
                "layer": r["layer_source"],
                "confidence": float(r["confidence"]) if r["confidence"] else None,
                "reasoning": r["reasoning"],
                "createdAt": str(r["created_at"]) if r["created_at"] else None,
                "outcome": r.get("outcome"),
                "settledAt": str(r["settled_at"]) if r.get("settled_at") else None,
            }
            for r in decision_rows
        ]

        # Watchlist state
        watchlist_rows = registry._db.execute(
            "SELECT state, notes, updated_at FROM invest.watchlist "
            "WHERE ticker = %s ORDER BY updated_at DESC LIMIT 1",
            (ticker,),
        )
        watchlist = None
        if watchlist_rows:
            w = watchlist_rows[0]
            watchlist = {
                "state": w["state"],
                "notes": w["notes"],
                "updated_at": str(w["updated_at"]) if w["updated_at"] else None,
            }

        # Quant gate scoring (latest run)
        qg_rows = registry._db.execute(
            "SELECT r.combined_rank, r.ey_rank, r.roic_rank, r.piotroski_score, "
            "r.altman_z_score, r.altman_zone, r.composite_score, "
            "s.name, s.sector, s.market_cap "
            "FROM invest.quant_gate_results r "
            "LEFT JOIN invest.stocks s ON s.ticker = r.ticker "
            "WHERE r.ticker = %s ORDER BY r.run_id DESC LIMIT 1",
            (ticker,),
        )
        quant_gate = None
        if qg_rows:
            q = qg_rows[0]
            quant_gate = {
                "combinedRank": q["combined_rank"],
                "eyRank": q["ey_rank"],
                "roicRank": q["roic_rank"],
                "piotroskiScore": q["piotroski_score"],
                "altmanZScore": float(q["altman_z_score"]) if q["altman_z_score"] else None,
                "altmanZone": q["altman_zone"],
                "compositeScore": float(q["composite_score"]) if q["composite_score"] else None,
            }

        # Verdict history (latest + previous)
        verdict_history_rows = registry.get_verdict_history(ticker, limit=20)
        verdict_data = None
        verdict_history: list[dict] = []
        for vr in verdict_history_rows:
            entry = {
                "recommendation": vr["verdict"],
                "confidence": float(vr["confidence"]) if vr["confidence"] else None,
                "consensusScore": float(vr["consensus_score"]) if vr["consensus_score"] else None,
                "reasoning": vr["reasoning"],
                "agentStances": vr["agent_stances"],
                "riskFlags": vr["risk_flags"],
                "auditorOverride": vr["auditor_override"],
                "mungerOverride": vr["munger_override"],
                "advisoryOpinions": vr.get("advisory_opinions"),
                "boardNarrative": vr.get("board_narrative"),
                "boardAdjustedVerdict": vr.get("board_adjusted_verdict"),
                "adversarialResult": vr.get("adversarial_result"),
                "createdAt": str(vr["created_at"]) if vr["created_at"] else None,
            }
            verdict_history.append(entry)
        if verdict_history:
            verdict_data = verdict_history[0]

        # Competence & moat from latest L2 decision
        competence_data = None
        competence_rows = registry._db.execute(
            "SELECT decision_type, confidence, reasoning, signals "
            "FROM invest.decisions WHERE ticker = %s "
            "AND decision_type IN ('COMPETENCE_PASS', 'COMPETENCE_FAIL') "
            "ORDER BY created_at DESC LIMIT 1",
            (ticker,),
        )
        if competence_rows:
            cr = competence_rows[0]
            competence_data = {
                "passed": cr["decision_type"] == "COMPETENCE_PASS",
                "confidence": float(cr["confidence"]) if cr["confidence"] else None,
                "reasoning": cr["reasoning"],
            }
            if cr["signals"]:
                competence_data["in_circle"] = cr["signals"].get("in_circle")
                competence_data["sector_familiarity"] = cr["signals"].get("sector_familiarity")
                competence_data["moat"] = cr["signals"].get("moat")

        # Stock name — prefer profile data, fall back to stocks table
        stock_name = ticker
        stock_sector = ""
        stock_industry = ""
        if profile_data:
            stock_sector = profile_data.get("sector") or ""
            stock_industry = profile_data.get("industry") or ""
        stock_rows = registry._db.execute(
            "SELECT name, sector, industry FROM invest.stocks WHERE ticker = %s",
            (ticker,),
        )
        if stock_rows:
            stock_name = stock_rows[0]["name"] or ticker
            if not stock_sector:
                stock_sector = stock_rows[0].get("sector") or ""
            if not stock_industry:
                stock_industry = stock_rows[0].get("industry") or ""

        # Position data (if held)
        position_data = None
        positions = registry.get_open_positions()
        held = next((p for p in positions if p.ticker == ticker), None)
        if held:
            current = float(fund_data["price"]) if fund_data and fund_data.get("price") else float(held.current_price)
            entry = float(held.entry_price)
            pnl = (current - entry) * float(held.shares)
            pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
            position_data = {
                "id": held.id,
                "shares": float(held.shares),
                "entryPrice": entry,
                "currentPrice": current,
                "positionType": held.position_type,
                "weight": float(held.weight) if held.weight else None,
                "stopLoss": float(held.stop_loss) if held.stop_loss else None,
                "fairValue": float(held.fair_value_estimate) if held.fair_value_estimate else None,
                "pnl": round(pnl, 2),
                "pnlPct": round(pnl_pct, 2),
                "entryDate": str(held.entry_date) if held.entry_date else None,
                "thesis": held.thesis or None,
            }

        # Signal enrichment: buzz, earnings momentum, stability, consensus tier
        buzz_data = None
        try:
            buzz_rows = registry._db.execute(
                "SELECT buzz_score, buzz_label, headline_sentiment, "
                "news_count_7d, news_count_30d, contrarian_flag "
                "FROM invest.buzz_scores WHERE ticker = %s ORDER BY scored_at DESC LIMIT 1",
                (ticker,),
            )
            if buzz_rows:
                b = buzz_rows[0]
                buzz_data = {
                    "buzzScore": b["buzz_score"],
                    "buzzLabel": b["buzz_label"],
                    "headlineSentiment": float(b["headline_sentiment"]) if b["headline_sentiment"] else None,
                    "articleCount": (b["news_count_7d"] or 0) + (b["news_count_30d"] or 0),
                    "contrarianFlag": b.get("contrarian_flag", False),
                }
        except Exception:
            logger.debug("Could not fetch buzz for %s", ticker)

        earnings_data = None
        try:
            em_rows = registry._db.execute(
                "SELECT momentum_score, momentum_label, upward_revisions, downward_revisions, beat_streak "
                "FROM invest.earnings_momentum WHERE ticker = %s ORDER BY computed_at DESC LIMIT 1",
                (ticker,),
            )
            if em_rows:
                em = em_rows[0]
                earnings_data = {
                    "score": float(em["momentum_score"]) if em["momentum_score"] else 0,
                    "label": em["momentum_label"],
                    "upwardRevisions": em["upward_revisions"] or 0,
                    "downwardRevisions": em["downward_revisions"] or 0,
                    "beatStreak": em["beat_streak"] or 0,
                }
        except Exception:
            logger.debug("Could not fetch earnings momentum for %s", ticker)

        # Extract per-agent target prices from signals JSONB
        target_prices = []
        for r in signal_rows:
            sigs = r.get("signals")
            if sigs and isinstance(sigs, dict):
                tp = sigs.get("target_price")
                if tp and isinstance(tp, (int, float)) and tp > 0:
                    target_prices.append({"agent": r["agent_name"], "price": float(tp)})
        target_price_range = None
        if target_prices:
            prices = [p["price"] for p in target_prices]
            sorted_prices = sorted(prices)
            target_price_range = {
                "prices": target_prices,
                "low": sorted_prices[0],
                "high": sorted_prices[-1],
                "median": sorted_prices[len(sorted_prices) // 2],
            }

        # --- Prediction card assembly ---
        prediction_card = None
        if verdict_data and fund_data and fund_data.get("price"):
            try:
                from investmentology.advisory.prediction_card import (
                    AgentTarget,
                    PredictionCardInputs,
                    build_prediction_card,
                )
                from investmentology.agents.skills import SKILLS

                pc_targets = []
                for r in signal_rows:
                    sigs = r.get("signals")
                    if sigs and isinstance(sigs, dict):
                        tp = sigs.get("target_price")
                        if tp and isinstance(tp, (int, float)) and tp > 0:
                            agent_name = r["agent_name"]
                            weight = SKILLS[agent_name].base_weight if agent_name in SKILLS else 0.05
                            pc_targets.append(AgentTarget(
                                agent=agent_name, target_price=float(tp), weight=weight,
                            ))

                stances = verdict_data.get("agentStances") or []
                if isinstance(stances, str):
                    import json
                    stances = json.loads(stances)
                bullish = sum(1 for s in stances if s.get("sentiment", 0) > 0)
                consensus_pct = (bullish / len(stances) * 100) if stances else 0.0

                # Earnings proximity from cached pipeline data
                earnings_warning = None
                try:
                    from investmentology.advisory.earnings_calendar import (
                        classify_earnings_proximity,
                        format_earnings_alert,
                    )
                    ep_rows = registry._db.execute(
                        "SELECT data_value FROM invest.pipeline_data_cache "
                        "WHERE ticker = %s AND data_key = 'earnings_context' "
                        "ORDER BY created_at DESC LIMIT 1",
                        (ticker,),
                    )
                    if ep_rows and ep_rows[0].get("data_value"):
                        proximity = classify_earnings_proximity(ticker, ep_rows[0]["data_value"])
                        earnings_warning = format_earnings_alert(proximity)
                        if earnings_warning is None and proximity.days_to_earnings is not None:
                            earnings_warning = (
                                f"Earnings in {proximity.days_to_earnings}d (safe to enter)"
                            )
                except Exception:
                    pass

                # SPY benchmark
                spy_rows = registry._db.execute(
                    "SELECT spy_price FROM invest.market_snapshots "
                    "ORDER BY snapshot_date DESC LIMIT 1",
                )
                spy_price = float(spy_rows[0]["spy_price"]) if spy_rows else None

                # Bear case from Klarman agent signals
                bear_case = None
                for r in signal_rows:
                    if r["agent_name"] == "klarman":
                        sigs = r.get("signals")
                        if sigs and isinstance(sigs, dict):
                            bc = sigs.get("bear_case_price") or sigs.get("bear_case")
                            if bc and isinstance(bc, (int, float)) and bc > 0:
                                bear_case = float(bc)

                inputs = PredictionCardInputs(
                    ticker=ticker,
                    current_price=float(fund_data["price"]),
                    verdict=verdict_data.get("recommendation", ""),
                    confidence=float(verdict_data.get("confidence") or 0),
                    agent_targets=pc_targets,
                    bear_case_price=bear_case,
                    agent_consensus_pct=consensus_pct,
                    quant_gate_rank=quant_gate.get("combinedRank") if quant_gate else None,
                    piotroski_score=quant_gate.get("piotroskiScore") if quant_gate else None,
                    altman_zone=quant_gate.get("altmanZone") if quant_gate else None,
                    earnings_warning=earnings_warning,
                    spy_price=spy_price,
                )
                card = build_prediction_card(inputs)
                prediction_card = card.to_dict()
            except Exception:
                logger.debug("Could not build prediction card for %s", ticker)

        stab_score, stab_label = verdict_stability(ticker, registry)
        cons_tier = consensus_tier(
            float(verdict_data["consensusScore"]) if verdict_data and verdict_data.get("consensusScore") else None
        )

        # Research briefing from pipeline data cache (latest cycle)
        research_briefing = None
        try:
            rb_rows = registry._db.execute(
                "SELECT data_value, created_at FROM invest.pipeline_data_cache "
                "WHERE ticker = %s AND data_key = 'research_briefing' "
                "ORDER BY created_at DESC LIMIT 1",
                (ticker,),
            )
            if rb_rows and rb_rows[0].get("data_value"):
                dv = rb_rows[0]["data_value"]
                research_briefing = {
                    "content": dv.get("briefing") or "",
                    "sourceCount": dv.get("raw_sources", 0),
                    "createdAt": str(rb_rows[0]["created_at"]) if rb_rows[0].get("created_at") else None,
                }
        except Exception:
            logger.debug("Could not fetch research briefing for %s", ticker)

        # Synthesized briefing — plain English, position-aware
        briefing = _build_briefing(
            ticker, stock_name, verdict_data, position_data, positions,
            fund_data, profile_data, competence_data, quant_gate,
        )

        return {
            "ticker": ticker,
            "name": stock_name,
            "sector": stock_sector,
            "industry": stock_industry,
            "profile": profile_data,
            "fundamentals": fund_data,
            "quantGate": quant_gate,
            "competence": competence_data,
            "verdict": verdict_data,
            "verdictHistory": verdict_history,
            "position": position_data,
            "briefing": briefing,
            "signals": [
                {
                    "agentName": r["agent_name"],
                    "model": r["model"],
                    "signals": r["signals"],
                    "confidence": float(r["confidence"]) if r["confidence"] else None,
                    "reasoning": r["reasoning"],
                    "createdAt": str(r["created_at"]) if r["created_at"] else None,
                }
                for r in signal_rows
            ],
            "decisions": decision_data,
            "watchlist": watchlist,
            "buzz": buzz_data,
            "earningsMomentum": earnings_data,
            "stabilityScore": stab_score,
            "stabilityLabel": stab_label,
            "consensusTier": cons_tier,
            "targetPriceRange": target_price_range,
            "researchBriefing": research_briefing,
            "predictionCard": prediction_card,
        }


def _format_profile(p: dict) -> dict:
    """Format a stock_profiles row for JSON response."""
    return {
        "sector": p.get("sector"),
        "industry": p.get("industry"),
        "businessSummary": p.get("business_summary"),
        "website": p.get("website"),
        "employees": p.get("employees"),
        "city": p.get("city"),
        "country": p.get("country"),
        "beta": float(p["beta"]) if p.get("beta") else None,
        "dividendYield": float(p["dividend_yield"]) if p.get("dividend_yield") else None,
        "trailingPE": float(p["trailing_pe"]) if p.get("trailing_pe") else None,
        "forwardPE": float(p["forward_pe"]) if p.get("forward_pe") else None,
        "priceToBook": float(p["price_to_book"]) if p.get("price_to_book") else None,
        "priceToSales": float(p["price_to_sales"]) if p.get("price_to_sales") else None,
        "fiftyTwoWeekHigh": float(p["fifty_two_week_high"]) if p.get("fifty_two_week_high") else None,
        "fiftyTwoWeekLow": float(p["fifty_two_week_low"]) if p.get("fifty_two_week_low") else None,
        "averageVolume": p.get("average_volume"),
        "analystTarget": float(p["analyst_target"]) if p.get("analyst_target") else None,
        "analystRecommendation": p.get("analyst_recommendation"),
        "analystCount": p.get("analyst_count"),
    }


def _build_briefing(
    ticker: str,
    name: str,
    verdict: dict | None,
    position: dict | None,
    all_positions: list,
    fundamentals: dict | None,
    profile: dict | None,
    competence: dict | None,
    quant_gate: dict | None,
) -> dict | None:
    """Build a plain-English briefing synthesizing all data into actionable guidance."""
    if not verdict:
        return None

    rec = verdict.get("recommendation", "")
    conf = verdict.get("confidence")
    conf_pct = f"{conf * 100:.0f}%" if conf else "unknown"
    stances = verdict.get("agentStances") or []
    risk_flags = verdict.get("riskFlags") or []
    price = fundamentals.get("price") if fundamentals else None

    # Count bulls vs bears
    bulls = [s for s in stances if s.get("sentiment", 0) > 0.1]
    bears = [s for s in stances if s.get("sentiment", 0) < -0.1]
    bull_names = [s["name"].capitalize() for s in bulls]
    bear_names = [s["name"].capitalize() for s in bears]

    # Short company descriptor
    short_name = name.split(",")[0].split(" Inc")[0].split(" Corp")[0].strip()

    # --- Build the narrative pieces ---
    headline = ""
    situation = ""
    action = ""
    rationale_parts: list[str] = []

    # Position-aware context
    if position:
        pnl = position.get("pnl", 0)
        pnl_pct = position.get("pnlPct", 0)
        shares = position.get("shares", 0)
        entry = position.get("entryPrice", 0)
        pos_type = position.get("positionType", "tactical")
        pnl_dir = "up" if pnl >= 0 else "down"
        pnl_str = f"${abs(pnl):,.0f} ({abs(pnl_pct):.1f}%)"

        situation = (
            f"You hold {int(shares)} shares of {short_name} at ${entry:.2f}. "
            f"You're currently {pnl_dir} {pnl_str}. "
            f"This is a {pos_type} position."
        )

        fair_value = position.get("fairValue")
        stop_loss = position.get("stopLoss")
        if fair_value and price:
            upside = ((fair_value - price) / price) * 100
            if upside > 0:
                rationale_parts.append(
                    f"Our agents estimate fair value at ${fair_value:.2f}, "
                    f"suggesting {upside:.0f}% upside from here."
                )
            else:
                rationale_parts.append(
                    f"Our agents estimate fair value at ${fair_value:.2f}, "
                    f"which is {abs(upside):.0f}% below the current price."
                )
        if stop_loss:
            rationale_parts.append(f"Stop loss is set at ${stop_loss:.2f}.")

        # Action based on verdict + position
        if rec in ("STRONG_BUY", "BUY"):
            headline = "Keep holding — the thesis is intact"
            action = f"The system rates {ticker} a {rec} with {conf_pct} confidence. Consider adding to this position if you have available capital."
        elif rec == "ACCUMULATE":
            headline = "Gradually add on dips"
            action = "The fundamentals support building this position over time. Look for pullbacks to add shares at better prices."
        elif rec in ("REDUCE", "SELL"):
            headline = "Consider reducing your exposure"
            action = f"The system flags {ticker} as {rec}. Review whether your original thesis still holds and consider trimming."
        elif rec == "WATCHLIST":
            headline = "Hold but watch closely"
            action = "Mixed signals — the position is worth keeping but not adding to right now. Monitor for the risk flags to resolve."
        elif rec == "HOLD":
            headline = "No action needed right now"
            action = "The position is stable. Hold and review at the next analysis cycle."
        elif rec == "AVOID":
            headline = "This position may need exiting"
            action = f"The system rates {ticker} as AVOID. Review urgently — this may warrant selling."
        else:
            headline = "Review this position"
            action = f"Verdict: {rec} at {conf_pct} confidence."
    else:
        # Not held — should you buy?
        situation = f"{short_name} is not currently in your portfolio."

        if rec in ("STRONG_BUY", "BUY"):
            headline = "Strong candidate for purchase"
            action = f"The system rates {ticker} a {rec} with {conf_pct} confidence. This could be worth initiating a position."
        elif rec == "ACCUMULATE":
            headline = "Worth starting a small position"
            action = "Start accumulating gradually. Don't go all-in — build the position over time."
        elif rec == "WATCHLIST":
            headline = "Interesting but not ready yet"
            action = "Add to your watch list and wait for a better entry point or for risk flags to clear."
        elif rec in ("HOLD", "REDUCE", "SELL"):
            headline = "Not recommended for purchase"
            action = f"The system does not recommend initiating a new position in {ticker} right now."
        elif rec == "AVOID":
            headline = "Stay away"
            action = "Multiple agents flag significant concerns. There are better opportunities elsewhere."
        else:
            headline = f"{rec} — needs more analysis"
            action = "Run the full analysis pipeline for a clearer picture."

    # Agent consensus narrative
    if bulls and bears:
        rationale_parts.append(
            f"{', '.join(bull_names)} {'are' if len(bulls) > 1 else 'is'} bullish, "
            f"while {', '.join(bear_names)} {'raise' if len(bears) > 1 else 'raises'} concerns."
        )
    elif bulls:
        rationale_parts.append(f"All active agents ({', '.join(bull_names)}) are bullish.")
    elif bears:
        rationale_parts.append(f"All active agents ({', '.join(bear_names)}) are cautious or bearish.")

    # Risk flag narrative
    if risk_flags:
        flag_labels = []
        for f in risk_flags:
            label = f.split(":")[0].strip().replace("_", " ").lower()
            flag_labels.append(label)
        rationale_parts.append(f"Key risks: {', '.join(flag_labels)}.")

    # Portfolio context
    total_value = sum(
        float(p.current_price) * float(p.shares) for p in all_positions
    ) if all_positions else 0
    if total_value > 0 and position:
        weight = (position.get("currentPrice", 0) * position.get("shares", 0)) / total_value * 100
        rationale_parts.append(f"This position is {weight:.1f}% of your portfolio.")

    # Sector context
    if all_positions and fundamentals:
        this_sector = profile.get("sector") if profile else None
        if this_sector:
            pass

    # Quant gate summary
    if quant_gate:
        comp = quant_gate.get("compositeScore")
        piotroski = quant_gate.get("piotroskiScore")
        altman = quant_gate.get("altmanZone")
        qg_parts = []
        if comp is not None:
            qg_parts.append(f"composite score {comp:.2f}")
        if piotroski is not None:
            qg_parts.append(f"Piotroski {piotroski}/9")
        if altman:
            qg_parts.append(f"Altman {altman}")
        if qg_parts:
            rationale_parts.append(f"Quantitative health: {', '.join(qg_parts)}.")

    # Analyst target
    if profile and profile.get("analystTarget") and price:
        target = profile["analystTarget"]
        diff_pct = ((target - price) / price) * 100
        if abs(diff_pct) > 2:
            direction = "above" if diff_pct > 0 else "below"
            rationale_parts.append(
                f"Wall Street target is ${target:.0f} ({abs(diff_pct):.0f}% {direction} current price)."
            )

    return {
        "headline": headline,
        "situation": situation,
        "action": action,
        "rationale": " ".join(rationale_parts),
    }
