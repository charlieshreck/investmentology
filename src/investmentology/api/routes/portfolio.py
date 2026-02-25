"""Portfolio endpoints."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from investmentology.api.deps import get_registry
from investmentology.registry.db import Database
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)


class CreatePositionRequest(BaseModel):
    ticker: str
    entry_price: float
    shares: float
    position_type: str = "core"
    weight: float = 0.0
    stop_loss: float | None = None
    fair_value_estimate: float | None = None
    thesis: str = ""


class ClosePositionRequest(BaseModel):
    exit_price: float
    exit_date: str | None = None

router = APIRouter()


@router.get("/portfolio")
def get_portfolio(registry: Registry = Depends(get_registry)) -> dict:
    """Return positions list with P&L, sector exposure summary, total value.

    Response shape matches PWA PortfolioResponse:
    {positions, totalValue, dayPnl, dayPnlPct, cash, alerts}

    Positions with the same ticker are aggregated into a single entry
    with weighted-average cost basis.
    """
    raw_positions = registry.get_open_positions()

    # Aggregate positions by ticker (handles legacy duplicate rows)
    aggregated: dict[str, dict] = {}
    for p in raw_positions:
        if p.ticker in aggregated:
            agg = aggregated[p.ticker]
            old_cost = agg["entry_price"] * agg["shares"]
            new_cost = p.entry_price * p.shares
            total_shares = agg["shares"] + p.shares
            agg["entry_price"] = (old_cost + new_cost) / total_shares if total_shares else Decimal("0")
            agg["shares"] = total_shares
            agg["current_price"] = p.current_price  # latest
            # Keep lowest id as canonical
        else:
            aggregated[p.ticker] = {
                "id": p.id,
                "ticker": p.ticker,
                "shares": p.shares,
                "entry_price": p.entry_price,
                "current_price": p.current_price,
                "weight": p.weight,
                "stop_loss": p.stop_loss,
                "pnl_pct": p.pnl_pct,
            }

    # Fetch stock names and previous close prices
    tickers = list(aggregated.keys())
    stock_names: dict[str, str] = {}
    prev_close: dict[str, float] = {}
    if tickers:
        try:
            name_rows = registry._db.execute(
                "SELECT ticker, name FROM invest.stocks WHERE ticker = ANY(%s)",
                [tickers],
            )
            for row in name_rows:
                if row.get("name"):
                    stock_names[row["ticker"]] = row["name"]
        except Exception:
            logger.warning("Failed to fetch stock names for portfolio", exc_info=True)
    if tickers:
        try:
            rows = registry._db.execute("""
                SELECT DISTINCT ON (fc.ticker)
                    fc.ticker, fc.price
                FROM invest.fundamentals_cache fc
                WHERE fc.ticker = ANY(%s)
                  AND fc.price > 0
                  AND fc.fetched_at::date < CURRENT_DATE
                ORDER BY fc.ticker, fc.fetched_at DESC
            """, [tickers])
            for row in rows:
                prev_close[row["ticker"]] = float(row["price"])
        except Exception:
            logger.warning("Failed to fetch previous close prices", exc_info=True)

    items = []
    total_value = Decimal("0")
    total_day_pnl = 0.0

    for a in aggregated.values():
        mv = a["current_price"] * a["shares"]
        total_value += mv
        entry_cost = a["entry_price"] * a["shares"]
        unrealised = float(mv - entry_cost)
        unrealised_pct = float((mv - entry_cost) / entry_cost * 100) if entry_cost else 0.0

        # Day change from previous close
        prev = prev_close.get(a["ticker"])
        cur = float(a["current_price"])
        day_change_per_share = (cur - prev) if prev and prev > 0 else 0.0
        day_change_pct = (day_change_per_share / prev * 100) if prev and prev > 0 else 0.0
        day_change_total = day_change_per_share * float(a["shares"])
        total_day_pnl += day_change_total

        items.append({
            "id": a["id"],
            "ticker": a["ticker"],
            "name": stock_names.get(a["ticker"]),
            "shares": float(a["shares"]),
            "avgCost": float(a["entry_price"]),
            "currentPrice": float(a["current_price"]),
            "marketValue": float(mv),
            "unrealizedPnl": unrealised,
            "unrealizedPnlPct": unrealised_pct,
            "dayChange": round(day_change_total, 2),
            "dayChangePct": round(day_change_pct, 2),
            "weight": float(a["weight"]),
        })

    positions = raw_positions  # Still need raw positions for alerts

    # Fetch alerts inline (same logic as /portfolio/alerts)
    alerts: list[dict] = []
    for p in positions:
        if p.stop_loss and p.current_price <= p.stop_loss:
            alerts.append({
                "id": f"sl-{p.ticker}",
                "severity": "critical",
                "title": "Stop-loss breached",
                "message": f"{p.ticker} at {float(p.current_price):.2f} breached stop-loss {float(p.stop_loss):.2f}",
                "ticker": p.ticker,
                "timestamp": "",
                "acknowledged": False,
            })
        pnl = float(p.pnl_pct)
        if pnl < -0.15:
            alerts.append({
                "id": f"dd-{p.ticker}",
                "severity": "high",
                "title": "Significant drawdown",
                "message": f"{p.ticker} down {pnl:.1%} from entry",
                "ticker": p.ticker,
                "timestamp": "",
                "acknowledged": False,
            })

    # Fetch cash from portfolio_budget
    cash = Decimal("0")
    try:
        budget_rows = registry._db.execute(
            "SELECT cash_reserve FROM invest.portfolio_budget LIMIT 1"
        )
        if budget_rows:
            cash = Decimal(str(budget_rows[0]["cash_reserve"] or 0))
    except Exception:
        logger.warning("Failed to fetch cash reserve from portfolio_budget", exc_info=True)

    portfolio_total = float(total_value + cash)

    day_pnl_pct = (total_day_pnl / (portfolio_total - total_day_pnl) * 100) if portfolio_total - total_day_pnl > 0 else 0.0

    return {
        "positions": items,
        "totalValue": portfolio_total,
        "dayPnl": round(total_day_pnl, 2),
        "dayPnlPct": round(day_pnl_pct, 2),
        "cash": float(cash),
        "alerts": alerts,
    }


@router.get("/portfolio/alerts")
def get_portfolio_alerts(registry: Registry = Depends(get_registry)) -> dict:
    """Return active alerts sorted by severity."""
    positions = registry.get_open_positions()
    alerts: list[dict] = []

    for p in positions:
        # Stop-loss alert
        if p.stop_loss and p.current_price <= p.stop_loss:
            alerts.append({
                "ticker": p.ticker,
                "severity": "critical",
                "type": "stop_loss_breach",
                "message": f"{p.ticker} at {float(p.current_price):.2f} breached stop-loss {float(p.stop_loss):.2f}",
            })

        # Significant drawdown
        pnl = float(p.pnl_pct)
        if pnl < -0.15:
            alerts.append({
                "ticker": p.ticker,
                "severity": "high",
                "type": "drawdown",
                "message": f"{p.ticker} down {pnl:.1%} from entry",
            })
        elif pnl < -0.10:
            alerts.append({
                "ticker": p.ticker,
                "severity": "medium",
                "type": "drawdown",
                "message": f"{p.ticker} down {pnl:.1%} from entry",
            })

        # Fair value overshoot
        if p.fair_value_estimate and p.current_price > p.fair_value_estimate * Decimal("1.1"):
            alerts.append({
                "ticker": p.ticker,
                "severity": "medium",
                "type": "above_fair_value",
                "message": f"{p.ticker} trading above fair value estimate ({float(p.fair_value_estimate):.2f})",
            })

    # Sort by severity
    # Sell engine signals
    try:
        from investmentology.sell.engine import SellEngine
        from investmentology.sell.rules import SellUrgency
        sell_engine = SellEngine()
        for p in positions:
            signals = sell_engine.evaluate_position(p)
            for sig in signals:
                severity = "critical" if sig.urgency == SellUrgency.EXECUTE else (
                    "high" if sig.urgency == SellUrgency.SIGNAL else "medium"
                )
                alerts.append({
                    "ticker": p.ticker,
                    "severity": severity,
                    "type": f"sell_{sig.reason.value.lower()}",
                    "message": sig.detail,
                })
    except Exception:
        logger.warning("Sell engine evaluation failed", exc_info=True)

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alerts.sort(key=lambda a: severity_order.get(a["severity"], 99))

    return {"alerts": alerts, "count": len(alerts)}


@router.post("/portfolio/positions")
def create_position(
    body: CreatePositionRequest,
    registry: Registry = Depends(get_registry),
) -> dict:
    """Create a new paper portfolio position, or add to existing position for same ticker."""
    ticker = body.ticker.upper()
    new_shares = Decimal(str(body.shares))
    new_price = Decimal(str(body.entry_price))

    # Check for existing open position — consolidate if found
    existing = registry.get_open_positions()
    existing_pos = next((p for p in existing if p.ticker == ticker), None)

    if existing_pos:
        # Weighted average cost basis
        old_cost = existing_pos.entry_price * existing_pos.shares
        new_cost = new_price * new_shares
        total_shares = existing_pos.shares + new_shares
        avg_price = (old_cost + new_cost) / total_shares

        registry._db.execute(
            "UPDATE invest.portfolio_positions "
            "SET shares = %s, entry_price = %s, current_price = %s, updated_at = NOW() "
            "WHERE id = %s AND is_closed = FALSE",
            (total_shares, avg_price, new_price, existing_pos.id),
        )
        return {"id": existing_pos.id, "ticker": ticker, "status": "added",
                "totalShares": float(total_shares), "avgCost": float(avg_price)}

    position_id = registry.create_position(
        ticker=ticker,
        entry_date=date.today(),
        entry_price=new_price,
        shares=new_shares,
        position_type=body.position_type,
        weight=Decimal(str(body.weight)),
        stop_loss=Decimal(str(body.stop_loss)) if body.stop_loss else None,
        fair_value_estimate=Decimal(str(body.fair_value_estimate)) if body.fair_value_estimate else None,
        thesis=body.thesis,
    )
    return {"id": position_id, "ticker": ticker, "status": "created"}


@router.post("/portfolio/positions/{position_id}/close")
def close_position(
    position_id: int,
    body: ClosePositionRequest,
    registry: Registry = Depends(get_registry),
) -> dict:
    """Close a paper portfolio position."""
    position = registry.get_position_by_id(position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    if position.is_closed:
        raise HTTPException(status_code=400, detail="Position already closed")

    exit_d = date.fromisoformat(body.exit_date) if body.exit_date else date.today()
    registry.close_position(position_id, Decimal(str(body.exit_price)), exit_d)

    return {"id": position_id, "status": "closed", "exit_price": body.exit_price}


@router.get("/portfolio/closed")
def get_closed_positions(registry: Registry = Depends(get_registry)) -> dict:
    """Return closed positions with realized P&L."""
    positions = registry.get_closed_positions()
    items = []
    total_realized = Decimal("0")
    for p in positions:
        rpnl = float(p.realized_pnl) if p.realized_pnl else 0.0
        total_realized += p.realized_pnl or Decimal("0")
        items.append({
            "id": p.id,
            "ticker": p.ticker,
            "entryDate": str(p.entry_date),
            "entryPrice": float(p.entry_price),
            "exitDate": str(p.exit_date) if p.exit_date else None,
            "exitPrice": float(p.exit_price) if p.exit_price else None,
            "shares": float(p.shares),
            "realizedPnl": rpnl,
            "realizedPnlPct": float(p.pnl_pct * 100) if p.entry_price else 0.0,
            "holdingDays": (p.exit_date - p.entry_date).days if p.exit_date else None,
        })
    return {"closedPositions": items, "totalRealizedPnl": float(total_realized)}


# --- Portfolio Balance ---

# Sector → risk category mapping
SECTOR_RISK_MAP: dict[str, str] = {
    "Technology": "growth",
    "Communication Services": "growth",
    "Consumer Cyclical": "growth",
    "Consumer Defensive": "defensive",
    "Utilities": "defensive",
    "Healthcare": "mixed",
    "Financial Services": "cyclical",
    "Industrials": "cyclical",
    "Basic Materials": "cyclical",
    "Energy": "cyclical",
    "Real Estate": "income",
}

# Soft bands for each risk category: (ideal_min, ideal_max, warn_max)
# Values are percentages of total portfolio
RISK_BANDS: dict[str, tuple[float, float, float]] = {
    "growth": (15, 45, 55),
    "cyclical": (10, 35, 45),
    "defensive": (10, 30, 40),
    "mixed": (0, 25, 35),
    "income": (0, 20, 30),
}

SECTOR_BAND_MAX = 30.0   # Soft amber above this
SECTOR_WARN_MAX = 40.0   # Red above this

SECTOR_COLORS: dict[str, str] = {
    "Technology": "#818cf8",
    "Communication Services": "#a78bfa",
    "Consumer Cyclical": "#f472b6",
    "Consumer Defensive": "#34d399",
    "Utilities": "#6ee7b7",
    "Healthcare": "#60a5fa",
    "Financial Services": "#fbbf24",
    "Industrials": "#fb923c",
    "Basic Materials": "#a3a3a3",
    "Energy": "#f87171",
    "Real Estate": "#2dd4bf",
}


def _lookup_sectors(db: Database, tickers: list[str]) -> dict[str, str]:
    """Get sector for each ticker from invest.stocks, backfill from yfinance if missing."""
    if not tickers:
        return {}
    placeholders = ",".join(["%s"] * len(tickers))
    rows = db.execute(
        f"SELECT ticker, sector FROM invest.stocks WHERE ticker IN ({placeholders})",
        tuple(tickers),
    )
    mapping = {r["ticker"]: r["sector"] for r in rows if r["sector"]}

    # Backfill missing sectors from yfinance
    missing = [t for t in tickers if t not in mapping]
    if missing:
        try:
            import yfinance as yf
            for ticker in missing:
                try:
                    info = yf.Ticker(ticker).info
                    sector = info.get("sector", "")
                    if sector:
                        mapping[ticker] = sector
                        # Cache in DB for next time
                        db.execute(
                            "INSERT INTO invest.stocks (ticker, name, sector, industry) "
                            "VALUES (%s, %s, %s, %s) "
                            "ON CONFLICT (ticker) DO UPDATE SET sector = %s, industry = %s, updated_at = NOW()",
                            (ticker, info.get("shortName", ticker), sector,
                             info.get("industry", ""), sector, info.get("industry", "")),
                        )
                except Exception:
                    pass
        except ImportError:
            pass

    return mapping


@router.get("/portfolio/balance")
def get_portfolio_balance(registry: Registry = Depends(get_registry)) -> dict:
    """Portfolio balance: sector allocation, risk spectrum, and soft-band health.

    All bands are advisory — green/amber/red zones, not hard limits.
    """
    positions = registry.get_open_positions()

    if not positions:
        return {
            "sectors": [],
            "riskCategories": [],
            "positionCount": 0,
            "sectorCount": 0,
            "health": "empty",
            "insights": ["No open positions yet. Add positions to see balance analysis."],
        }

    # Look up sectors
    tickers = [p.ticker for p in positions]
    sector_map = _lookup_sectors(registry._db, tickers)

    # Compute total portfolio value
    total_value = sum(float(p.market_value) for p in positions)
    if total_value == 0:
        return {"sectors": [], "riskCategories": [], "positionCount": 0,
                "sectorCount": 0, "health": "empty", "insights": []}

    # Sector allocation
    sector_values: dict[str, float] = {}
    sector_tickers: dict[str, list[str]] = {}
    for p in positions:
        sector = sector_map.get(p.ticker, "Unknown")
        mv = float(p.market_value)
        sector_values[sector] = sector_values.get(sector, 0) + mv
        sector_tickers.setdefault(sector, []).append(p.ticker)

    sectors = []
    for sector, value in sorted(sector_values.items(), key=lambda x: -x[1]):
        pct = (value / total_value) * 100
        risk_cat = SECTOR_RISK_MAP.get(sector, "mixed")
        if pct <= SECTOR_BAND_MAX:
            zone = "green"
        elif pct <= SECTOR_WARN_MAX:
            zone = "amber"
        else:
            zone = "red"

        sectors.append({
            "name": sector,
            "pct": round(pct, 1),
            "value": round(value, 2),
            "zone": zone,
            "riskCategory": risk_cat,
            "tickers": sector_tickers[sector],
            "color": SECTOR_COLORS.get(sector, "#94a3b8"),
            "softMax": SECTOR_BAND_MAX,
            "warnMax": SECTOR_WARN_MAX,
        })

    # Risk category allocation
    risk_values: dict[str, float] = {}
    for sector, value in sector_values.items():
        cat = SECTOR_RISK_MAP.get(sector, "mixed")
        risk_values[cat] = risk_values.get(cat, 0) + value

    risk_categories = []
    for cat in ["growth", "cyclical", "defensive", "mixed", "income"]:
        value = risk_values.get(cat, 0)
        pct = (value / total_value) * 100
        ideal_min, ideal_max, warn_max = RISK_BANDS[cat]

        if ideal_min <= pct <= ideal_max:
            zone = "green"
        elif pct < ideal_min or pct <= warn_max:
            zone = "amber"
        else:
            zone = "red"

        risk_categories.append({
            "name": cat,
            "pct": round(pct, 1),
            "value": round(value, 2),
            "zone": zone,
            "idealMin": ideal_min,
            "idealMax": ideal_max,
            "warnMax": warn_max,
        })

    # Generate insights (soft nudges, not hard errors)
    insights: list[str] = []
    unique_sectors = len([s for s in sectors if s["name"] != "Unknown"])

    if unique_sectors < 3 and len(positions) >= 3:
        insights.append(f"Only {unique_sectors} sector{'s' if unique_sectors != 1 else ''} — consider spreading across more industries.")

    for s in sectors:
        if s["zone"] == "red":
            insights.append(f"{s['name']} at {s['pct']}% — quite concentrated. Consider trimming or adding elsewhere.")
        elif s["zone"] == "amber":
            insights.append(f"{s['name']} at {s['pct']}% — getting heavy. Keep an eye on it.")

    defensive_pct = next((r["pct"] for r in risk_categories if r["name"] == "defensive"), 0)
    growth_pct = next((r["pct"] for r in risk_categories if r["name"] == "growth"), 0)

    if defensive_pct == 0 and len(positions) >= 3:
        insights.append("No defensive positions (Utilities, Staples). Consider adding some stability.")
    if growth_pct > 55:
        insights.append(f"Growth-heavy at {growth_pct:.0f}%. The portfolio may be volatile in downturns.")

    if not insights:
        insights.append("Portfolio looks well-balanced.")

    # Overall health
    red_count = sum(1 for s in sectors if s["zone"] == "red") + sum(1 for r in risk_categories if r["zone"] == "red")
    amber_count = sum(1 for s in sectors if s["zone"] == "amber") + sum(1 for r in risk_categories if r["zone"] == "amber")

    if red_count > 0:
        health = "needs_attention"
    elif amber_count > 1:
        health = "fair"
    elif amber_count == 1:
        health = "good"
    else:
        health = "excellent"

    return {
        "sectors": sectors,
        "riskCategories": risk_categories,
        "positionCount": len(positions),
        "sectorCount": unique_sectors,
        "health": health,
        "insights": insights,
    }


# --- Correlation Heatmap ---

# In-memory cache: (timestamp, data)
_correlation_cache: dict[str, tuple[float, dict]] = {}
_CORR_CACHE_TTL = 86400  # 24 hours


@router.get("/portfolio/correlations")
def get_portfolio_correlations(registry: Registry = Depends(get_registry)) -> dict:
    """90-day rolling correlation matrix for current portfolio holdings.

    Returns {tickers: [...], correlations: [{ticker1, ticker2, value}]}.
    """
    import time

    positions = registry.get_open_positions()
    tickers = sorted(set(p.ticker for p in positions))

    if len(tickers) < 2:
        return {"tickers": tickers, "correlations": []}

    cache_key = ",".join(tickers)
    now = time.time()
    if cache_key in _correlation_cache:
        ts, data = _correlation_cache[cache_key]
        if now - ts < _CORR_CACHE_TTL:
            return data

    try:
        import yfinance as yf

        df = yf.download(tickers, period="3mo", auto_adjust=True, progress=False)
        if df.empty:
            return {"tickers": tickers, "correlations": []}

        # yf.download returns MultiIndex columns for multiple tickers
        closes = df["Close"] if len(tickers) > 1 else df[["Close"]].rename(columns={"Close": tickers[0]})
        corr_matrix = closes.corr()

        correlations = []
        for i, t1 in enumerate(corr_matrix.columns):
            for j, t2 in enumerate(corr_matrix.columns):
                if j > i:
                    val = corr_matrix.iloc[i, j]
                    if not (val != val):  # skip NaN
                        correlations.append({
                            "ticker1": str(t1),
                            "ticker2": str(t2),
                            "value": round(float(val), 3),
                        })

        result = {"tickers": [str(t) for t in corr_matrix.columns], "correlations": correlations}
        _correlation_cache[cache_key] = (now, result)
        return result

    except Exception:
        logger.exception("Failed to compute correlations")
        return {"tickers": tickers, "correlations": []}


@router.get("/portfolio/advisor")
def get_portfolio_advisor(registry: Registry = Depends(get_registry)) -> dict:
    """Portfolio advisor: actionable recommendations for the whole portfolio.

    Combines sell engine signals, verdict flips, balance health, sizing guidance,
    and cash deployment into a prioritized action list.
    """
    positions = registry.get_open_positions()
    if not positions:
        return {"actions": []}

    actions: list[dict] = []

    # Lookups
    pos_by_ticker = {p.ticker: p for p in positions}
    tickers = list(pos_by_ticker.keys())
    total_value = sum(float(p.market_value) for p in positions)

    # -- 1. Sell engine signals --
    try:
        from investmentology.sell.engine import SellEngine
        from investmentology.sell.rules import SellUrgency
        sell_engine = SellEngine()
        for p in positions:
            signals = sell_engine.evaluate_position(p)
            for sig in signals:
                if sig.urgency == SellUrgency.EXECUTE:
                    actions.append({
                        "type": "SELL",
                        "ticker": p.ticker,
                        "priority": "high",
                        "title": f"Sell {p.ticker}",
                        "detail": sig.detail,
                        "reasoning": f"Sell engine: {sig.reason.value}. Urgency: EXECUTE.",
                        "position_id": p.id,
                        "current_shares": float(p.shares),
                        "current_price": float(p.current_price),
                        "current_weight": round(float(p.market_value) / total_value * 100, 1) if total_value else 0,
                    })
                elif sig.urgency == SellUrgency.SIGNAL:
                    actions.append({
                        "type": "TRIM",
                        "ticker": p.ticker,
                        "priority": "medium",
                        "title": f"Trim {p.ticker}",
                        "detail": sig.detail,
                        "reasoning": f"Sell engine: {sig.reason.value}. Consider reducing position.",
                        "position_id": p.id,
                        "current_shares": float(p.shares),
                        "current_price": float(p.current_price),
                        "current_weight": round(float(p.market_value) / total_value * 100, 1) if total_value else 0,
                        "suggested_shares": max(1, int(float(p.shares) * 0.5)),
                    })
    except Exception:
        logger.warning("Sell engine failed in advisor", exc_info=True)

    # -- 2. Verdict-based signals on held positions --
    for ticker in tickers:
        try:
            verdict = registry.get_latest_verdict(ticker)
            if not verdict:
                # No analysis yet — suggest reanalyze
                actions.append({
                    "type": "REANALYZE",
                    "ticker": ticker,
                    "priority": "medium",
                    "title": f"Analyze {ticker}",
                    "detail": f"No AI verdict exists for held position {ticker}.",
                    "reasoning": "Run the analysis pipeline to get buy/hold/sell guidance.",
                })
                continue

            v = verdict.get("verdict", "")
            conf = float(verdict.get("confidence", 0) or 0)
            reasoning = verdict.get("reasoning", "") or ""

            if v in ("SELL", "AVOID"):
                # Check we didn't already add a sell engine signal
                already_flagged = any(a["ticker"] == ticker and a["type"] in ("SELL", "TRIM") for a in actions)
                if not already_flagged:
                    p = pos_by_ticker[ticker]
                    actions.append({
                        "type": "SELL",
                        "ticker": ticker,
                        "priority": "high",
                        "title": f"AI says Sell {ticker}",
                        "detail": f"Latest verdict: {v} (confidence {conf:.0%})",
                        "reasoning": reasoning[:200],
                        "position_id": p.id,
                        "current_shares": float(p.shares),
                        "current_price": float(p.current_price),
                    })
            elif v == "REDUCE":
                already_flagged = any(a["ticker"] == ticker and a["type"] in ("SELL", "TRIM") for a in actions)
                if not already_flagged:
                    p = pos_by_ticker[ticker]
                    actions.append({
                        "type": "TRIM",
                        "ticker": ticker,
                        "priority": "medium",
                        "title": f"Reduce {ticker}",
                        "detail": f"Latest verdict: REDUCE (confidence {conf:.0%})",
                        "reasoning": reasoning[:200],
                        "position_id": p.id,
                        "current_shares": float(p.shares),
                        "current_price": float(p.current_price),
                        "suggested_shares": max(1, int(float(p.shares) * 0.66)),
                    })
            elif v in ("STRONG_BUY", "BUY", "ACCUMULATE") and conf >= 0.7:
                p = pos_by_ticker[ticker]
                weight = float(p.market_value) / total_value * 100 if total_value else 0
                if weight < 8:  # Room to add more
                    actions.append({
                        "type": "ADD_MORE",
                        "ticker": ticker,
                        "priority": "low",
                        "title": f"Add to {ticker}",
                        "detail": f"Verdict: {v} ({conf:.0%} confidence). Current weight: {weight:.1f}%",
                        "reasoning": reasoning[:200],
                        "position_id": p.id,
                        "current_shares": float(p.shares),
                        "current_price": float(p.current_price),
                        "current_weight": round(weight, 1),
                    })
        except Exception:
            logger.debug("Advisor: verdict check failed for %s", ticker, exc_info=True)

    # -- 3. Position type reclassification --
    for p in positions:
        ptype = p.position_type or "core"
        pnl_pct = float(p.pnl_pct) if p.pnl_pct else 0
        # Tactical winners graduating to core
        if ptype == "tactical" and pnl_pct > 0.20:
            actions.append({
                "type": "RECLASSIFY",
                "ticker": p.ticker,
                "priority": "low",
                "title": f"Promote {p.ticker} to Core",
                "detail": f"Tactical position up {pnl_pct:.0%}. Consider promoting to core hold.",
                "reasoning": "Strong performance suggests thesis validation — tighter stops as core.",
                "position_id": p.id,
                "current_position_type": ptype,
                "suggested_position_type": "core",
            })

    # -- 4. Concentration / diversification --
    stocks = {s["ticker"]: s for s in registry._db.execute(
        "SELECT ticker, sector FROM invest.stocks WHERE ticker = ANY(%s)", (tickers,)
    )}
    sector_weights: dict[str, float] = {}
    for p in positions:
        sector = stocks.get(p.ticker, {}).get("sector", "Other") or "Other"
        sector_weights[sector] = sector_weights.get(sector, 0) + (float(p.market_value) / total_value * 100 if total_value else 0)

    for sector, weight in sector_weights.items():
        if weight > 35:
            sector_tickers = [t for t in tickers if stocks.get(t, {}).get("sector") == sector]
            actions.append({
                "type": "DIVERSIFY",
                "ticker": None,
                "priority": "medium",
                "title": f"{sector} overweight ({weight:.0f}%)",
                "detail": f"Sector at {weight:.0f}% of portfolio. Positions: {', '.join(sector_tickers)}",
                "reasoning": "Consider trimming largest sector position or adding exposure to underweight sectors.",
            })

    # -- 5. Correlation risk --
    high_corr_pairs = []
    try:
        corr_data = get_portfolio_correlations(registry)
        for pair in corr_data.get("correlations", []):
            if pair["value"] > 0.85:
                high_corr_pairs.append(pair)
    except Exception:
        pass

    for pair in high_corr_pairs[:3]:
        actions.append({
            "type": "CORRELATION_RISK",
            "ticker": None,
            "priority": "low",
            "title": f"High correlation: {pair['ticker1']}/{pair['ticker2']}",
            "detail": f"Correlation {pair['value']:.2f} — these positions move together.",
            "reasoning": "High correlation reduces diversification benefit. Consider whether both are needed.",
        })

    # -- 6. Cash deployment --
    try:
        budget_row = registry._db.execute(
            "SELECT total_capital, cash_reserve FROM invest.portfolio_budget LIMIT 1"
        )
        if budget_row:
            cash = float(budget_row[0].get("cash_reserve", 0))
            total_capital = float(budget_row[0].get("total_capital", 0))
            if total_capital > 0:
                cash_pct = cash / total_capital * 100
                if cash_pct > 15:
                    actions.append({
                        "type": "DEPLOY_CASH",
                        "ticker": None,
                        "priority": "low",
                        "title": f"Deploy cash ({cash_pct:.0f}% idle)",
                        "detail": f"${cash:,.0f} cash available. Consider deploying into top-rated screener candidates.",
                        "reasoning": "Excess cash drag reduces returns. Review Recs tab for buy candidates.",
                    })
    except Exception:
        pass

    # -- 7. Ideal portfolio snapshot --
    # Sort: high priority first, then medium, then low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda a: priority_order.get(a["priority"], 99))

    return {"actions": actions}
