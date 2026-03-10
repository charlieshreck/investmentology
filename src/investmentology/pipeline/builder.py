"""Pipeline request builder — shared functions extracted from controller.

These module-level functions are used by both the controller (overnight cycle)
and the API trigger endpoints (manual re-runs, board re-eval, etc.).
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from investmentology.agents.base import AnalysisRequest
from investmentology.pipeline import state
from investmentology.registry.db import Database

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FundamentalsSnapshot helpers
# ---------------------------------------------------------------------------

def dict_to_snapshot(ticker: str, raw: dict):
    """Convert a raw yfinance/cache dict to a FundamentalsSnapshot."""
    from datetime import datetime as dt

    from investmentology.models.stock import FundamentalsSnapshot

    def _dec(v) -> Decimal:
        if v is None:
            return Decimal(0)
        return Decimal(str(v))

    fetched = raw.get("fetched_at")
    if isinstance(fetched, str):
        try:
            fetched = dt.fromisoformat(fetched)
        except (ValueError, TypeError):
            fetched = dt.now()
    elif fetched is None:
        fetched = dt.now()

    return FundamentalsSnapshot(
        ticker=ticker,
        fetched_at=fetched,
        operating_income=_dec(raw.get("operating_income")),
        market_cap=_dec(raw.get("market_cap")),
        total_debt=_dec(raw.get("total_debt")),
        cash=_dec(raw.get("cash")),
        current_assets=_dec(raw.get("current_assets")),
        current_liabilities=_dec(raw.get("current_liabilities")),
        net_ppe=_dec(raw.get("net_ppe") or raw.get("net_tangible_assets")),
        revenue=_dec(raw.get("revenue")),
        net_income=_dec(raw.get("net_income")),
        total_assets=_dec(raw.get("total_assets")),
        total_liabilities=_dec(raw.get("total_liabilities")),
        shares_outstanding=int(raw.get("shares_outstanding") or 0),
        price=_dec(raw.get("price")),
        gross_profit=_dec(raw.get("gross_profit")),
        receivables=_dec(raw.get("receivables")),
        depreciation=_dec(raw.get("depreciation")),
        sga=_dec(raw.get("sga")),
        dividends_paid=_dec(raw.get("dividends_paid")),
        shares_repurchased=_dec(raw.get("shares_repurchased")),
    )


def snapshot_to_dict(snap) -> dict:
    """Convert a FundamentalsSnapshot back to a dict."""
    return {
        "ticker": snap.ticker,
        "fetched_at": str(snap.fetched_at),
        "operating_income": float(snap.operating_income),
        "market_cap": float(snap.market_cap),
        "total_debt": float(snap.total_debt),
        "cash": float(snap.cash),
        "current_assets": float(snap.current_assets),
        "current_liabilities": float(snap.current_liabilities),
        "net_ppe": float(snap.net_ppe),
        "revenue": float(snap.revenue),
        "net_income": float(snap.net_income),
        "total_assets": float(snap.total_assets),
        "total_liabilities": float(snap.total_liabilities),
        "shares_outstanding": snap.shares_outstanding,
        "price": float(snap.price),
    }


def empty_snapshot(ticker: str):
    """Create a zero-filled FundamentalsSnapshot."""
    from datetime import datetime as dt

    from investmentology.models.stock import FundamentalsSnapshot
    return FundamentalsSnapshot(
        ticker=ticker,
        fetched_at=dt.now(),
        operating_income=Decimal(0),
        market_cap=Decimal(0),
        total_debt=Decimal(0),
        cash=Decimal(0),
        current_assets=Decimal(0),
        current_liabilities=Decimal(0),
        net_ppe=Decimal(0),
        revenue=Decimal(0),
        net_income=Decimal(0),
        total_assets=Decimal(0),
        total_liabilities=Decimal(0),
        shares_outstanding=0,
        price=Decimal(0),
    )


# ---------------------------------------------------------------------------
# Signal reconstruction
# ---------------------------------------------------------------------------

def reconstruct_signal_sets(signal_rows: list[dict]) -> list:
    """Reconstruct AgentSignalSet objects from DB rows."""
    from investmentology.models.signal import (
        AgentSignalSet,
        Signal,
        SignalSet,
        SignalTag,
    )

    results = []
    for row in signal_rows:
        signals_data = row["signals"]
        if isinstance(signals_data, str):
            signals_data = json.loads(signals_data)

        signal_list = []
        for s in signals_data.get("signals", []):
            try:
                tag = SignalTag(s["tag"])
                signal_list.append(Signal(
                    tag=tag,
                    strength=s.get("strength", "moderate"),
                    detail=s.get("detail", ""),
                ))
            except (ValueError, KeyError):
                continue

        target_price = signals_data.get("target_price")
        results.append(AgentSignalSet(
            agent_name=row["agent_name"],
            model=row["model"],
            signals=SignalSet(signals=signal_list),
            confidence=Decimal(str(row["confidence"])),
            reasoning=row["reasoning"] or "",
            target_price=(
                Decimal(str(target_price)) if target_price else None
            ),
        ))
    return results


# ---------------------------------------------------------------------------
# Portfolio context
# ---------------------------------------------------------------------------

def get_portfolio_context(db: Database, ticker: str) -> dict | None:
    """Get portfolio context for a ticker if it's a held position."""
    try:
        rows = db.execute(
            "SELECT id, shares, avg_cost, entry_date, entry_thesis, "
            "thesis_type, thesis_health, current_price, "
            "highest_price_since_entry, position_type, stop_loss "
            "FROM invest.portfolio_positions "
            "WHERE ticker = %s AND is_closed = FALSE "
            "ORDER BY entry_date DESC LIMIT 1",
            (ticker,),
        )
        if rows:
            r = rows[0]
            entry_date = r.get("entry_date")
            days_held = None
            if entry_date:
                from datetime import date, datetime
                if isinstance(entry_date, str):
                    entry_date = datetime.fromisoformat(entry_date).date()
                elif isinstance(entry_date, datetime):
                    entry_date = entry_date.date()
                if isinstance(entry_date, date):
                    days_held = (date.today() - entry_date).days

            avg_cost = float(r["avg_cost"]) if r["avg_cost"] else None
            current_price = float(r["current_price"]) if r.get("current_price") else None
            pnl_pct = None
            if avg_cost and avg_cost > 0 and current_price:
                pnl_pct = round((current_price - avg_cost) / avg_cost * 100, 2)

            return {
                "position_id": r.get("id"),
                "shares": float(r["shares"]) if r["shares"] else None,
                "avg_cost": avg_cost,
                "entry_date": str(r.get("entry_date")) if r.get("entry_date") else None,
                "entry_thesis": r.get("entry_thesis"),
                "thesis_type": r.get("thesis_type"),
                "thesis_health": r.get("thesis_health"),
                "current_price": current_price,
                "highest_price": float(r["highest_price_since_entry"]) if r.get("highest_price_since_entry") else None,
                "position_type": r.get("position_type"),
                "stop_loss": float(r["stop_loss"]) if r.get("stop_loss") else None,
                "days_held": days_held,
                "pnl_pct": pnl_pct,
            }
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Full AnalysisRequest builder
# ---------------------------------------------------------------------------

def build_analysis_request(
    db: Database,
    ticker: str,
    cycle_id: str | None = None,
) -> AnalysisRequest:
    """Build an AnalysisRequest from cached pipeline data or DB fallback.

    Used by the controller for overnight cycles and by API endpoints for
    manual triggers (board re-eval, agent re-runs, etc.).
    """
    # 1. Load fundamentals from pipeline cache
    raw_fundamentals = None
    if cycle_id:
        raw_fundamentals = state.get_data_cache(
            db, cycle_id, ticker, "fundamentals",
        )

    # Fallback: load from fundamentals_cache DB table
    if not raw_fundamentals:
        try:
            from investmentology.registry.queries import Registry
            registry = Registry(db)
            snap = registry.get_latest_fundamentals(ticker)
            if snap:
                raw_fundamentals = snapshot_to_dict(snap)
        except Exception:
            logger.debug("No DB fundamentals for %s", ticker)

    if not raw_fundamentals:
        logger.warning("No fundamentals for %s, using minimal request", ticker)
        return AnalysisRequest(
            ticker=ticker,
            fundamentals=empty_snapshot(ticker),
            sector="Unknown",
            industry="Unknown",
        )

    # 2. Build FundamentalsSnapshot
    fundamentals = dict_to_snapshot(ticker, raw_fundamentals)

    # 3. Technical indicators from cache
    tech = None
    if cycle_id:
        tech = state.get_data_cache(
            db, cycle_id, ticker, "technical_indicators",
        )

    # 3b. Research briefing from cache
    research_briefing = None
    if cycle_id:
        rb = state.get_data_cache(
            db, cycle_id, ticker, "research_briefing",
        )
        if rb:
            research_briefing = rb.get("briefing")

    # 3c. Enrichment data from cache (FRED, Finnhub, EDGAR)
    # Try current cycle first, then fall back to latest across all cycles
    # so agents always get the best available data rather than running blind.
    cycle_cache: dict[str, dict] = {}
    if cycle_id:
        cycle_cache = state.get_all_data_cache(db, cycle_id, ticker)

    # Cross-cycle fallback — only query if current cycle is missing keys
    _ENRICH_KEYS = (
        "macro_context", "news_context", "earnings_context", "insider_context",
        "social_sentiment", "filing_context", "institutional_context",
        "analyst_ratings", "short_interest",
    )
    cross_cache: dict[str, dict] | None = None
    def _enrich(key: str) -> dict | None:
        nonlocal cross_cache
        val = cycle_cache.get(key)
        if val is not None:
            return val
        if cross_cache is None:
            cross_cache = state.get_latest_data_cache(db, ticker)
        return cross_cache.get(key)

    # Macro regime — cycle-level, stored under ticker="__cycle__"
    macro_regime = None
    if cycle_id:
        macro_regime = state.get_data_cache(
            db, cycle_id, "__cycle__", "macro_regime",
        )

    # Backtest calibration — cycle-level, stored under ticker="__cycle__"
    backtest_calibration = None
    if cycle_id:
        backtest_calibration = state.get_data_cache(
            db, cycle_id, "__cycle__", "backtest_calibration",
        )

    macro_context = _enrich("macro_context")
    news_raw = _enrich("news_context")
    news_context = news_raw.get("items") if isinstance(news_raw, dict) else news_raw
    earnings_context = _enrich("earnings_context")
    ins_raw = _enrich("insider_context")
    insider_context = ins_raw.get("items") if isinstance(ins_raw, dict) else ins_raw
    social_sentiment = _enrich("social_sentiment")
    filing_context = _enrich("filing_context")
    inst_raw = _enrich("institutional_context")
    institutional_context = inst_raw.get("items") if isinstance(inst_raw, dict) else inst_raw
    analyst_ratings = _enrich("analyst_ratings")
    short_interest = _enrich("short_interest")

    # 4. Portfolio context
    portfolio_context = get_portfolio_context(db, ticker)

    # 5. Previous verdict + verdict chain from Neo4j
    previous_verdict = None
    try:
        from investmentology.registry.queries import Registry
        registry = Registry(db)
        prev = registry.get_latest_verdict(ticker)
        if prev:
            previous_verdict = {
                "verdict": prev.get("verdict") if isinstance(prev, dict) else getattr(prev, "verdict", None),
                "confidence": float(prev.get("confidence", 0) if isinstance(prev, dict) else getattr(prev, "confidence", 0)),
            }
    except Exception:
        pass

    # 5b. Enrich with Neo4j verdict chain history
    try:
        import httpx as _httpx
        resp = _httpx.post(
            "http://knowledge-mcp.ai-platform.svc.cluster.local:8000/api/call",
            json={
                "name": "query_graph",
                "arguments": {
                    "query": (
                        f"MATCH (s:InvestStock {{ticker: '{ticker}'}})-[:HAS_VERDICT]->(v:InvestVerdict) "
                        f"RETURN v.verdict AS verdict, v.confidence AS confidence, "
                        f"v.created_at AS date "
                        f"ORDER BY v.created_at DESC LIMIT 5"
                    ),
                },
            },
            timeout=5.0,
        )
        if resp.status_code == 200:
            chain_data = resp.json().get("result", [])
            if chain_data and isinstance(chain_data, list):
                if previous_verdict is None:
                    previous_verdict = {}
                previous_verdict["verdict_chain"] = [
                    {"verdict": r.get("verdict"), "confidence": r.get("confidence"), "date": r.get("date")}
                    for r in chain_data[:5]
                ]
    except Exception:
        pass

    # 5c. Qdrant similar situations
    similar_situations = None
    try:
        from investmentology.memory.semantic import (
            COLLECTION_NAME, QDRANT_DIRECT_URL, _build_embedding_text, _get_embed_model,
        )
        model = _get_embed_model()
        if model is not None:
            text = _build_embedding_text(
                ticker,
                previous_verdict.get("verdict", "") if previous_verdict else "",
                "",
                portfolio_context.get("position_type") if portfolio_context else None,
                portfolio_context.get("thesis_health") if portfolio_context else None,
                None, None,
            )
            query_vec = model.encode(
                f"search_query: {text}", normalize_embeddings=True,
            ).tolist()
            import httpx as _httpx
            resp = _httpx.post(
                f"{QDRANT_DIRECT_URL}/collections/{COLLECTION_NAME}/points/search",
                json={"vector": query_vec, "limit": 3, "with_payload": True},
                timeout=5.0,
            )
            if resp.status_code == 200:
                hits = resp.json().get("result", [])
                if hits:
                    similar_situations = [
                        {
                            "ticker": h["payload"].get("ticker", "?"),
                            "verdict": h["payload"].get("verdict", "?"),
                            "confidence": h["payload"].get("confidence", 0),
                            "outcome": h["payload"].get("outcome"),
                            "reasoning": h["payload"].get("reasoning", "")[:200],
                            "similarity": h.get("score", 0),
                            "date": h["payload"].get("timestamp", ""),
                        }
                        for h in hits
                    ]
    except Exception:
        logger.debug("Qdrant similar situations lookup failed for %s", ticker)

    # 6. Quant gate context
    qg_rank = None
    piotroski = None
    altman_z = None
    try:
        qg_rows = db.execute(
            "SELECT combined_rank, piotroski_score, altman_z_score "
            "FROM invest.quant_gate_results "
            "WHERE ticker = %s ORDER BY id DESC LIMIT 1",
            (ticker,),
        )
        if qg_rows:
            qg_rank = qg_rows[0].get("combined_rank")
            piotroski = qg_rows[0].get("piotroski_score")
            az = qg_rows[0].get("altman_z_score")
            altman_z = Decimal(str(az)) if az is not None else None
    except Exception:
        pass

    # 7. Extract position-level fields from portfolio context
    # These drive _TYPE_GUIDANCE overlays and _fmt_thesis in the prompt builder.
    position_thesis = None
    position_type = None
    thesis_type = None
    thesis_health = None
    days_held = None
    entry_price = None
    pnl_pct = None
    if portfolio_context:
        position_thesis = portfolio_context.get("entry_thesis")
        position_type = portfolio_context.get("position_type")
        thesis_type = portfolio_context.get("thesis_type")
        thesis_health = portfolio_context.get("thesis_health")
        days_held = portfolio_context.get("days_held")
        entry_price = portfolio_context.get("avg_cost")
        pnl_pct = portfolio_context.get("pnl_pct")

    return AnalysisRequest(
        ticker=ticker,
        fundamentals=fundamentals,
        sector=raw_fundamentals.get("sector", "Unknown"),
        industry=raw_fundamentals.get("industry", "Unknown"),
        technical_indicators=tech,
        macro_regime=macro_regime,
        macro_context=macro_context,
        news_context=news_context,
        earnings_context=earnings_context,
        insider_context=insider_context,
        social_sentiment=social_sentiment,
        filing_context=filing_context,
        institutional_context=institutional_context,
        analyst_ratings=analyst_ratings,
        short_interest=short_interest,
        portfolio_context=portfolio_context,
        previous_verdict=previous_verdict,
        similar_situations=similar_situations,
        quant_gate_rank=qg_rank,
        piotroski_score=piotroski,
        altman_z_score=altman_z,
        research_briefing=research_briefing,
        backtest_calibration=backtest_calibration,
        position_thesis=position_thesis,
        position_type=position_type,
        thesis_type=thesis_type,
        thesis_health=thesis_health,
        days_held=days_held,
        entry_price=entry_price,
        pnl_pct=pnl_pct,
    )
