"""Stock endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from investmentology.api.deps import get_registry
from investmentology.api.services.report_service import ReportService
from investmentology.api.services.stock_service import StockService
from investmentology.data.profile import fetch_news_from_yfinance
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stock/{ticker}")
def get_stock(ticker: str, registry: Registry = Depends(get_registry)) -> dict:
    """Full deep dive: profile, fundamentals, signals, decisions, watchlist state."""
    return StockService(registry).get_stock(ticker)


@router.get("/stock/{ticker}/news")
def get_stock_news(ticker: str) -> dict:
    """Fetch recent news articles for a ticker."""
    ticker = ticker.upper()
    articles = fetch_news_from_yfinance(ticker, limit=12)
    return {"ticker": ticker, "articles": articles}


@router.get("/stock/{ticker}/signals")
def get_stock_signals(ticker: str, registry: Registry = Depends(get_registry)) -> dict:
    """Agent signal sets for a ticker."""
    ticker = ticker.upper()
    rows = registry._db.execute(
        "SELECT id, agent_name, model, signals, confidence, reasoning, "
        "token_usage, latency_ms, created_at "
        "FROM invest.agent_signals WHERE ticker = %s ORDER BY created_at DESC",
        (ticker,),
    )
    return {
        "ticker": ticker,
        "signals": [
            {
                "id": r["id"],
                "agent_name": r["agent_name"],
                "model": r["model"],
                "signals": r["signals"],
                "confidence": float(r["confidence"]) if r["confidence"] else None,
                "reasoning": r["reasoning"],
                "token_usage": r["token_usage"],
                "latency_ms": r["latency_ms"],
                "created_at": str(r["created_at"]) if r["created_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/stock/{ticker}/decisions")
def get_stock_decisions(ticker: str, registry: Registry = Depends(get_registry)) -> dict:
    """Decision history for a ticker."""
    ticker = ticker.upper()
    decisions = registry.get_decisions(ticker=ticker, limit=100)
    return {
        "ticker": ticker,
        "decisions": [
            {
                "id": d.id,
                "decision_type": d.decision_type.value,
                "layer_source": d.layer_source,
                "confidence": float(d.confidence) if d.confidence else None,
                "reasoning": d.reasoning,
                "signals": d.signals,
                "metadata": d.metadata,
                "created_at": str(d.created_at) if d.created_at else None,
            }
            for d in decisions
        ],
    }


# Period map: query param -> yfinance period/interval
_CHART_PERIODS = {
    "1w": ("5d", "15m"),
    "1mo": ("1mo", "1d"),
    "3mo": ("3mo", "1d"),
    "6mo": ("6mo", "1d"),
    "1y": ("1y", "1wk"),
    "ytd": ("ytd", "1d"),
}


@router.get("/stock/{ticker}/chart")
def get_stock_chart(
    ticker: str,
    period: str = Query("1mo", regex="^(1w|1mo|3mo|6mo|1y|ytd)$"),
) -> dict:
    """Price chart data from yfinance. Returns OHLCV time series."""
    import yfinance as yf

    ticker = ticker.upper()
    yf_period, yf_interval = _CHART_PERIODS.get(period, ("1mo", "1d"))

    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=yf_period, interval=yf_interval)
        if hist.empty:
            return {"ticker": ticker, "period": period, "data": []}

        data = []
        for dt, row in hist.iterrows():
            ts = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
            data.append({
                "date": ts,
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        return {"ticker": ticker, "period": period, "data": data}
    except Exception as exc:
        logger.warning("Chart fetch failed for %s: %s", ticker, exc)
        return {"ticker": ticker, "period": period, "data": [], "error": str(exc)}


@router.get("/stock/{ticker}/report")
def get_stock_report(
    ticker: str,
    registry: Registry = Depends(get_registry),
) -> dict:
    """Full AI research report assembled from all DB sources."""
    report = ReportService(registry).generate(ticker)
    if report is None:
        return {"error": "Insufficient data for report", "ticker": ticker.upper()}
    return report
