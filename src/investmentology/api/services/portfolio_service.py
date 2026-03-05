"""Business logic for portfolio endpoints."""

from __future__ import annotations

import logging
import math
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from investmentology.advisory.performance import PerformanceCalculator
from investmentology.api.routes.shared import get_dividend_data
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)


def _safe_decimal(v: Decimal | None) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


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

RISK_BANDS: dict[str, tuple[float, float, float]] = {
    "growth": (15, 45, 55),
    "cyclical": (10, 35, 45),
    "defensive": (10, 30, 40),
    "mixed": (0, 25, 35),
    "income": (0, 20, 30),
}

SECTOR_BAND_MAX = 30.0
SECTOR_WARN_MAX = 40.0

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


# In-memory cache: (timestamp, data)
_correlation_cache: dict[str, tuple[float, dict]] = {}
_CORR_CACHE_TTL = 86400  # 24 hours


def _lookup_sectors(db, tickers: list[str]) -> dict[str, str]:
    if not tickers:
        return {}
    placeholders = ",".join(["%s"] * len(tickers))
    rows = db.execute(
        f"SELECT ticker, sector FROM invest.stocks WHERE ticker IN ({placeholders})",
        tuple(tickers),
    )
    mapping = {r["ticker"]: r["sector"] for r in rows if r["sector"]}

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


class PortfolioService:
    def __init__(self, registry: Registry) -> None:
        self._reg = registry

    def get_portfolio(self) -> dict:
        registry = self._reg
        raw_positions = registry.get_open_positions()

        aggregated: dict[str, dict] = {}
        for p in raw_positions:
            if p.ticker in aggregated:
                agg = aggregated[p.ticker]
                old_cost = agg["entry_price"] * agg["shares"]
                new_cost = p.entry_price * p.shares
                total_shares = agg["shares"] + p.shares
                agg["entry_price"] = (old_cost + new_cost) / total_shares if total_shares else Decimal("0")
                agg["shares"] = total_shares
                agg["current_price"] = p.current_price
                if p.entry_date and (not agg["entry_date"] or p.entry_date < agg["entry_date"]):
                    agg["entry_date"] = p.entry_date
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
                    "position_type": p.position_type or "core",
                    "entry_date": p.entry_date,
                }

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
            cur_price = _safe_decimal(a["current_price"])
            if cur_price is None:
                items.append({
                    "id": a["id"],
                    "ticker": a["ticker"],
                    "name": stock_names.get(a["ticker"]),
                    "shares": float(a["shares"]),
                    "avgCost": float(a["entry_price"]),
                    "currentPrice": None,
                    "marketValue": 0.0,
                    "unrealizedPnl": 0.0,
                    "unrealizedPnlPct": 0.0,
                    "dayChange": 0.0,
                    "dayChangePct": 0.0,
                    "weight": float(a["weight"]),
                    "positionType": a["position_type"],
                    "entryDate": str(a["entry_date"]) if a.get("entry_date") else None,
                    "priceUnavailable": True,
                })
                continue

            mv = a["current_price"] * a["shares"]
            total_value += mv
            entry_cost = a["entry_price"] * a["shares"]
            unrealised = float(mv - entry_cost)
            unrealised_pct = float((mv - entry_cost) / entry_cost * 100) if entry_cost else 0.0

            prev = prev_close.get(a["ticker"])
            day_change_per_share = (cur_price - prev) if prev and prev > 0 else 0.0
            day_change_pct = (day_change_per_share / prev * 100) if prev and prev > 0 else 0.0
            day_change_total = day_change_per_share * float(a["shares"])
            total_day_pnl += day_change_total

            items.append({
                "id": a["id"],
                "ticker": a["ticker"],
                "name": stock_names.get(a["ticker"]),
                "shares": float(a["shares"]),
                "avgCost": float(a["entry_price"]),
                "currentPrice": cur_price,
                "marketValue": float(mv),
                "unrealizedPnl": unrealised,
                "unrealizedPnlPct": unrealised_pct,
                "dayChange": round(day_change_total, 2),
                "dayChangePct": round(day_change_pct, 2),
                "weight": float(a["weight"]),
                "positionType": a["position_type"],
                "entryDate": str(a["entry_date"]) if a.get("entry_date") else None,
            })

        div_data: dict[str, dict] = {}
        total_annual_div = 0.0
        total_monthly_div = 0.0
        if tickers:
            try:
                div_data = get_dividend_data(tickers)
            except Exception:
                logger.debug("Failed to fetch dividend data", exc_info=True)

        for item in items:
            ticker = item["ticker"]
            dd = div_data.get(ticker, {})
            annual_per_share = dd.get("annual_div", 0.0) or 0.0
            shares = item["shares"]
            annual_total = annual_per_share * shares
            monthly_total = annual_total / 12 if annual_total > 0 else 0.0
            item["dividendPerShare"] = round(annual_per_share, 4)
            item["dividendYield"] = round((dd.get("div_yield", 0.0) or 0.0) * 100, 2) if dd.get("div_yield") else round(
                (annual_per_share / item["avgCost"] * 100) if item["avgCost"] > 0 and annual_per_share > 0 else 0.0, 2
            )
            item["annualDividend"] = round(annual_total, 2)
            item["monthlyDividend"] = round(monthly_total, 2)
            item["dividendFrequency"] = dd.get("frequency", "none")
            item["exDividendDate"] = dd.get("ex_div_date")
            total_annual_div += annual_total
            total_monthly_div += monthly_total

        positions = raw_positions

        alerts: list[dict] = []
        for p in positions:
            cur = _safe_decimal(p.current_price)
            sl = _safe_decimal(p.stop_loss)
            if cur is not None and sl is not None and cur <= sl:
                alerts.append({
                    "id": f"sl-{p.ticker}",
                    "severity": "critical",
                    "title": "Stop-loss breached",
                    "message": f"{p.ticker} at {cur:.2f} breached stop-loss {sl:.2f}",
                    "ticker": p.ticker,
                    "timestamp": "",
                    "acknowledged": False,
                })
            pnl = _safe_decimal(p.pnl_pct)
            if pnl is not None and pnl < -0.15:
                alerts.append({
                    "id": f"dd-{p.ticker}",
                    "severity": "high",
                    "title": "Significant drawdown",
                    "message": f"{p.ticker} down {pnl:.1%} from entry",
                    "ticker": p.ticker,
                    "timestamp": "",
                    "acknowledged": False,
                })

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

        performance = None
        try:
            calc = PerformanceCalculator(registry)
            perf = calc.compute()
            performance = {
                "portfolioReturnPct": perf.portfolio_return_pct,
                "spyReturnPct": perf.spy_return_pct,
                "alphaPct": perf.alpha_pct,
                "sharpeRatio": perf.sharpe_ratio,
                "sortinoRatio": perf.sortino_ratio,
                "maxDrawdownPct": perf.max_drawdown_pct,
                "winRate": perf.win_rate,
                "avgWinPct": perf.avg_win_pct,
                "avgLossPct": perf.avg_loss_pct,
                "totalTrades": perf.total_trades,
                "expectancy": perf.expectancy,
                "dispositionRatio": perf.disposition_ratio,
                "avgWinnerHoldDays": perf.avg_winner_hold_days,
                "avgLoserHoldDays": perf.avg_loser_hold_days,
                "measurementDays": perf.measurement_days,
            }
        except Exception:
            logger.debug("Performance metrics computation failed", exc_info=True)

        return {
            "positions": items,
            "totalValue": portfolio_total,
            "dayPnl": round(total_day_pnl, 2),
            "dayPnlPct": round(day_pnl_pct, 2),
            "cash": float(cash),
            "alerts": alerts,
            "performance": performance,
            "dividendSummary": {
                "totalAnnual": round(total_annual_div, 2),
                "totalMonthly": round(total_monthly_div, 2),
                "yield": round(total_annual_div / float(total_value) * 100, 2) if total_value > 0 else 0.0,
            },
        }

    def get_alerts(self) -> dict:
        registry = self._reg
        positions = registry.get_open_positions()
        alerts: list[dict] = []

        for p in positions:
            if p.stop_loss and p.current_price <= p.stop_loss:
                alerts.append({
                    "ticker": p.ticker,
                    "severity": "critical",
                    "type": "stop_loss_breach",
                    "message": f"{p.ticker} at {float(p.current_price):.2f} breached stop-loss {float(p.stop_loss):.2f}",
                })
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
            if p.fair_value_estimate and p.current_price > p.fair_value_estimate * Decimal("1.1"):
                alerts.append({
                    "ticker": p.ticker,
                    "severity": "medium",
                    "type": "above_fair_value",
                    "message": f"{p.ticker} trading above fair value estimate ({float(p.fair_value_estimate):.2f})",
                })

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

    def get_closed(self) -> dict:
        registry = self._reg
        positions = registry.get_closed_positions()

        tickers = list({p.ticker for p in positions})
        stock_info: dict[str, dict] = {}
        verdicts: dict[str, dict] = {}
        if tickers:
            try:
                stock_rows = registry._db.execute(
                    "SELECT ticker, name, sector, industry FROM invest.stocks WHERE ticker = ANY(%s)",
                    (tickers,),
                )
                stock_info = {r["ticker"]: r for r in stock_rows}
            except Exception:
                logger.warning("Failed to fetch stock info for closed positions", exc_info=True)
            for t in tickers:
                v = registry.get_latest_verdict(t)
                if v:
                    verdicts[t] = v

        items = []
        total_realized = Decimal("0")
        for p in positions:
            rpnl = float(p.realized_pnl) if p.realized_pnl else 0.0
            total_realized += p.realized_pnl or Decimal("0")
            si = stock_info.get(p.ticker, {})
            name = si.get("name", p.ticker) or p.ticker
            short_name = name.split(",")[0].split(" Inc")[0].split(" Corp")[0].strip()
            v = verdicts.get(p.ticker)
            items.append({
                "id": p.id,
                "ticker": p.ticker,
                "name": short_name,
                "sector": si.get("sector", "Unknown") or "Unknown",
                "positionType": p.position_type or "core",
                "entryDate": str(p.entry_date),
                "entryPrice": float(p.entry_price),
                "exitDate": str(p.exit_date) if p.exit_date else None,
                "exitPrice": float(p.exit_price) if p.exit_price else None,
                "shares": float(p.shares),
                "realizedPnl": rpnl,
                "realizedPnlPct": float(p.pnl_pct * 100) if p.entry_price else 0.0,
                "holdingDays": (p.exit_date - p.entry_date).days if p.exit_date else None,
                "fairValue": float(p.fair_value_estimate) if p.fair_value_estimate else None,
                "thesis": p.thesis or None,
                "verdict": v["verdict"] if v else None,
                "verdictConfidence": float(v["confidence"]) if v and v.get("confidence") else None,
                "verdictReasoning": v["reasoning"] if v else None,
                "verdictDate": str(v["created_at"]) if v and v.get("created_at") else None,
            })
        return {"closedPositions": items, "totalRealizedPnl": float(total_realized)}

    def get_balance(self) -> dict:
        registry = self._reg
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

        tickers = [p.ticker for p in positions]
        sector_map = _lookup_sectors(registry._db, tickers)

        total_value = sum(
            float(p.market_value) for p in positions
            if _safe_decimal(p.market_value) is not None
        )
        if not total_value or total_value == 0:
            return {"sectors": [], "riskCategories": [], "positionCount": 0,
                    "sectorCount": 0, "health": "empty", "insights": []}

        sector_values: dict[str, float] = {}
        sector_tickers: dict[str, list[str]] = {}
        for p in positions:
            sector = sector_map.get(p.ticker, "Unknown")
            mv = _safe_decimal(p.market_value)
            sector_values[sector] = sector_values.get(sector, 0) + (mv if mv is not None else 0)
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

    def evaluate_scenario(
        self,
        action: str,
        ticker: str,
        shares: float,
        price: float | None = None,
    ) -> dict:
        """Simulate a portfolio change and return before/after comparison."""
        ticker = ticker.upper()
        registry = self._reg
        positions = registry.get_open_positions()

        # Resolve price if not provided
        if price is None:
            try:
                import yfinance as yf
                info = yf.Ticker(ticker).fast_info
                price = float(info.get("lastPrice", 0) or info.get("last_price", 0))
            except Exception:
                price = 0.0
        if price <= 0:
            return {"error": "Could not determine price for scenario"}

        # Current state
        tickers = [p.ticker for p in positions]
        sector_map = _lookup_sectors(registry._db, tickers + [ticker])

        budget_rows = registry._db.execute(
            "SELECT cash_reserve FROM invest.portfolio_budget LIMIT 1"
        )
        cash = float(budget_rows[0]["cash_reserve"]) if budget_rows else 0.0

        current_total = sum(
            float(p.market_value) for p in positions
            if _safe_decimal(p.market_value) is not None
        )

        # Build simulated positions list
        sim_positions: list[dict] = []
        for p in positions:
            mv = _safe_decimal(p.market_value) or 0
            sim_positions.append({
                "ticker": p.ticker,
                "shares": float(p.shares),
                "price": float(p.current_price) if p.current_price else 0,
                "marketValue": mv,
                "sector": sector_map.get(p.ticker, "Unknown"),
            })

        # Apply scenario action
        scenario_value = shares * price
        warnings: list[str] = []

        if action == "add":
            existing = next((sp for sp in sim_positions if sp["ticker"] == ticker), None)
            if existing:
                existing["shares"] += shares
                existing["marketValue"] += scenario_value
            else:
                sim_positions.append({
                    "ticker": ticker,
                    "shares": shares,
                    "price": price,
                    "marketValue": scenario_value,
                    "sector": sector_map.get(ticker, "Unknown"),
                })
            sim_cash = cash - scenario_value
            if sim_cash < 0:
                warnings.append(f"Insufficient cash: need ${scenario_value:,.0f}, have ${cash:,.0f}")

        elif action == "remove":
            existing = next((sp for sp in sim_positions if sp["ticker"] == ticker), None)
            if not existing:
                return {"error": f"No position in {ticker} to remove"}
            if shares >= existing["shares"]:
                sim_positions = [sp for sp in sim_positions if sp["ticker"] != ticker]
            else:
                existing["shares"] -= shares
                existing["marketValue"] -= scenario_value
            sim_cash = cash + scenario_value

        elif action == "resize":
            existing = next((sp for sp in sim_positions if sp["ticker"] == ticker), None)
            if not existing:
                return {"error": f"No position in {ticker} to resize"}
            old_value = existing["marketValue"]
            existing["shares"] = shares
            existing["marketValue"] = shares * price
            sim_cash = cash + (old_value - existing["marketValue"])

        else:
            return {"error": f"Unknown action: {action}"}

        # Compute after-state metrics
        sim_total = sum(sp["marketValue"] for sp in sim_positions)

        # Sector exposure
        sim_sector_values: dict[str, float] = {}
        for sp in sim_positions:
            s = sp["sector"]
            sim_sector_values[s] = sim_sector_values.get(s, 0) + sp["marketValue"]

        sim_sectors = []
        for s, v in sorted(sim_sector_values.items(), key=lambda x: -x[1]):
            pct = (v / sim_total * 100) if sim_total > 0 else 0
            sim_sectors.append({
                "name": s,
                "pct": round(pct, 1),
                "value": round(v, 2),
                "color": SECTOR_COLORS.get(s, "#94a3b8"),
            })
            if pct > 25:
                warnings.append(f"{s} sector would be {pct:.1f}% (limit: 25%)")

        # Position concentration
        for sp in sim_positions:
            pos_pct = (sp["marketValue"] / sim_total * 100) if sim_total > 0 else 0
            if pos_pct > 20:
                warnings.append(f"{sp['ticker']} would be {pos_pct:.1f}% of portfolio (limit: 20%)")

        # Current sector exposure for comparison
        cur_sector_values: dict[str, float] = {}
        for sp_cur in [{
            "ticker": p.ticker,
            "marketValue": _safe_decimal(p.market_value) or 0,
            "sector": sector_map.get(p.ticker, "Unknown"),
        } for p in positions]:
            s = sp_cur["sector"]
            cur_sector_values[s] = cur_sector_values.get(s, 0) + sp_cur["marketValue"]

        cur_sectors = []
        for s, v in sorted(cur_sector_values.items(), key=lambda x: -x[1]):
            pct = (v / current_total * 100) if current_total > 0 else 0
            cur_sectors.append({
                "name": s,
                "pct": round(pct, 1),
                "value": round(v, 2),
                "color": SECTOR_COLORS.get(s, "#94a3b8"),
            })

        return {
            "ticker": ticker,
            "action": action,
            "shares": shares,
            "price": round(price, 2),
            "before": {
                "totalValue": round(current_total, 2),
                "cashReserve": round(cash, 2),
                "positionCount": len(positions),
                "sectors": cur_sectors,
            },
            "after": {
                "totalValue": round(sim_total, 2),
                "cashReserve": round(sim_cash, 2),
                "positionCount": len(sim_positions),
                "sectors": sim_sectors,
            },
            "warnings": warnings,
            "canProceed": len(warnings) == 0,
        }

    def get_briefing(self) -> dict:
        registry = self._reg
        positions = registry.get_open_positions()
        if not positions:
            return {"briefing": None}

        total_value = sum(float(p.market_value) for p in positions)
        tickers = [p.ticker for p in positions]

        verdicts: dict[str, dict] = {}
        for t in tickers:
            v = registry.get_latest_verdict(t)
            if v:
                verdicts[t] = v

        stock_rows = registry._db.execute(
            "SELECT ticker, name, sector, industry FROM invest.stocks WHERE ticker = ANY(%s)",
            (tickers,),
        )
        stock_info = {r["ticker"]: r for r in stock_rows}

        cash = 0.0
        try:
            budget_row = registry._db.execute(
                "SELECT total_capital, cash_reserve FROM invest.portfolio_budget LIMIT 1"
            )
            if budget_row:
                cash = float(budget_row[0].get("cash_reserve", 0) or 0)
        except Exception:
            pass

        _ = total_value + cash

        pos_summaries: list[dict] = []
        sectors: dict[str, float] = {}
        core_count = 0
        tactical_count = 0
        analyzed_count = 0
        bullish_count = 0
        bearish_count = 0
        total_upside_weighted = 0.0
        total_weight_for_upside = 0.0

        for p in positions:
            mv = float(p.market_value)
            weight = (mv / total_value * 100) if total_value else 0
            pnl = float(p.current_price - p.entry_price) * float(p.shares)
            pnl_pct = float(p.pnl_pct * 100) if p.pnl_pct else 0
            sector = stock_info.get(p.ticker, {}).get("sector", "Other") or "Other"
            name = stock_info.get(p.ticker, {}).get("name", p.ticker) or p.ticker
            short_name = name.split(",")[0].split(" Inc")[0].split(" Corp")[0].strip()

            sectors[sector] = sectors.get(sector, 0) + weight

            ptype = p.position_type or "core"
            if ptype == "core":
                core_count += 1
            else:
                tactical_count += 1

            v = verdicts.get(p.ticker)
            verdict_str = v["verdict"] if v else None
            conf = float(v["confidence"]) if v and v.get("confidence") else None

            if v:
                analyzed_count += 1
                if verdict_str in ("STRONG_BUY", "BUY", "ACCUMULATE"):
                    bullish_count += 1
                elif verdict_str in ("SELL", "AVOID", "REDUCE"):
                    bearish_count += 1

            fv = float(p.fair_value_estimate) if p.fair_value_estimate else None
            price = float(p.current_price)
            upside_pct = None
            if fv and price > 0:
                upside_pct = ((fv - price) / price) * 100
                total_upside_weighted += upside_pct * weight
                total_weight_for_upside += weight

            status_parts: list[str] = []
            if pnl >= 0:
                status_parts.append(f"up {pnl_pct:.1f}%")
            else:
                status_parts.append(f"down {abs(pnl_pct):.1f}%")
            if verdict_str:
                status_parts.append(f"rated {verdict_str}")
                if conf:
                    status_parts[-1] += f" ({conf * 100:.0f}%)"
            if upside_pct is not None:
                if upside_pct > 0:
                    status_parts.append(f"{upside_pct:.0f}% upside to fair value")
                else:
                    status_parts.append(f"{abs(upside_pct):.0f}% above fair value")

            action_hint = ""
            if verdict_str in ("SELL", "AVOID"):
                action_hint = "Consider selling"
            elif verdict_str == "REDUCE":
                action_hint = "Consider trimming"
            elif verdict_str in ("STRONG_BUY", "BUY") and weight < 8:
                action_hint = "Room to add more"
            elif verdict_str == "WATCHLIST":
                action_hint = "Hold and monitor"
            elif verdict_str in ("ACCUMULATE",):
                action_hint = "Add on dips"
            elif not verdict_str:
                action_hint = "Needs analysis"
            else:
                action_hint = "Hold"

            pos_summaries.append({
                "ticker": p.ticker,
                "name": short_name,
                "sector": sector,
                "positionType": ptype,
                "weight": round(weight, 1),
                "pnl": round(pnl, 2),
                "pnlPct": round(pnl_pct, 1),
                "verdict": verdict_str,
                "confidence": round(conf * 100) if conf else None,
                "fairValue": fv,
                "upsidePct": round(upside_pct, 1) if upside_pct is not None else None,
                "status": ". ".join(status_parts).capitalize(),
                "action": action_hint,
            })

        action_priority = {"Consider selling": 0, "Consider trimming": 1, "Needs analysis": 2}
        pos_summaries.sort(key=lambda s: (action_priority.get(s["action"], 5), -s["weight"]))

        n_positions = len(positions)
        n_sectors = len(sectors)
        top_sector = max(sectors, key=sectors.get) if sectors else "None"  # type: ignore[arg-type]
        top_sector_pct = sectors.get(top_sector, 0)

        if n_sectors >= 5 and top_sector_pct < 35:
            diversity = "well-diversified"
            diversity_detail = f"Spread across {n_sectors} sectors with no single sector dominating."
        elif n_sectors >= 3 and top_sector_pct < 50:
            diversity = "moderately diversified"
            diversity_detail = f"{n_sectors} sectors, but {top_sector} is heavy at {top_sector_pct:.0f}%."
        else:
            diversity = "concentrated"
            diversity_detail = f"Only {n_sectors} sector{'s' if n_sectors > 1 else ''} with {top_sector} at {top_sector_pct:.0f}%. Consider adding exposure to other sectors."

        unanalyzed = n_positions - analyzed_count
        if analyzed_count == 0:
            quality = "unknown"
            quality_detail = "No positions have been through the AI analysis pipeline. Run analysis to get buy/hold/sell guidance."
        elif bullish_count >= analyzed_count * 0.7:
            quality = "strong"
            quality_detail = f"{bullish_count} of {analyzed_count} analyzed positions rated bullish. The portfolio is aligned with AI conviction."
        elif bearish_count >= analyzed_count * 0.5:
            quality = "concerning"
            quality_detail = f"{bearish_count} of {analyzed_count} analyzed positions have sell/reduce signals. Review urgently."
        else:
            quality = "mixed"
            quality_detail = f"{bullish_count} bullish, {bearish_count} bearish, {analyzed_count - bullish_count - bearish_count} neutral out of {analyzed_count} analyzed."

        if unanalyzed > 0:
            quality_detail += f" {unanalyzed} position{'s' if unanalyzed > 1 else ''} still need{'s' if unanalyzed == 1 else ''} analysis."

        type_detail = ""
        if core_count and tactical_count:
            type_detail = f"{core_count} core (long-term) and {tactical_count} tactical (shorter-term) positions."
        elif core_count:
            type_detail = f"All {core_count} positions are core holds. Consider adding tactical positions for shorter-term opportunities."
        elif tactical_count:
            type_detail = f"All {tactical_count} positions are tactical. Consider converting winners to core for long-term compounding."

        avg_upside = (total_upside_weighted / total_weight_for_upside) if total_weight_for_upside > 0 else None
        upside_str = ""
        if avg_upside is not None:
            if avg_upside > 0:
                upside_str = f"Weighted average upside to fair value is {avg_upside:.0f}%."
            else:
                upside_str = f"The portfolio is trading {abs(avg_upside):.0f}% above aggregate fair value on average."

        urgent = [s for s in pos_summaries if s["action"] in ("Consider selling", "Consider trimming", "Needs analysis")]

        if any(s["action"] == "Consider selling" for s in pos_summaries):
            headline = "Action needed — review sell signals"
        elif unanalyzed > 0:
            headline = f"{unanalyzed} position{'s' if unanalyzed > 1 else ''} need{'s' if unanalyzed == 1 else ''} analysis"
        elif quality == "strong":
            headline = "Portfolio looks healthy"
        elif quality == "concerning":
            headline = "Review portfolio — multiple concerns flagged"
        else:
            headline = "Portfolio is stable with some mixed signals"

        return {
            "briefing": {
                "headline": headline,
                "overview": (
                    f"You hold {n_positions} positions worth ${total_value:,.0f}"
                    f"{f' with ${cash:,.0f} in cash' if cash > 0 else ''}. "
                    f"The portfolio is {diversity}."
                ),
                "diversity": {"rating": diversity, "detail": diversity_detail},
                "quality": {"rating": quality, "detail": quality_detail},
                "positionTypes": {"core": core_count, "tactical": tactical_count, "detail": type_detail},
                "upside": upside_str,
                "positions": pos_summaries,
                "urgent": urgent[:5],
                "sectors": [
                    {"name": s, "pct": round(w, 1)}
                    for s, w in sorted(sectors.items(), key=lambda x: -x[1])
                ],
            },
        }

    def get_timeline(self, limit: int = 80) -> dict:
        registry = self._reg

        portfolio_tickers: set[str] = set()
        all_positions = registry._db.execute(
            "SELECT id, ticker, entry_date, entry_price, shares, position_type, "
            "is_closed, exit_date, exit_price, realized_pnl, created_at, updated_at "
            "FROM invest.portfolio_positions ORDER BY created_at DESC"
        )
        for p in all_positions:
            portfolio_tickers.add(p["ticker"])

        events: list[dict] = []

        for p in all_positions:
            buy_ts = p["created_at"]
            if buy_ts and hasattr(buy_ts, "isoformat"):
                ts_str = buy_ts.isoformat()
            else:
                ts_str = f"{p['entry_date']}T09:30:00"
            events.append({
                "type": "BUY",
                "timestamp": ts_str,
                "ticker": p["ticker"],
                "detail": f"Bought {float(p['shares']):.0f} shares at ${float(p['entry_price']):,.2f}",
                "extra": {
                    "shares": float(p["shares"]),
                    "price": float(p["entry_price"]),
                    "positionType": p["position_type"] or "core",
                },
            })
            if p["is_closed"] and p["exit_date"]:
                rpnl = float(p["realized_pnl"]) if p["realized_pnl"] else 0.0
                sell_ts = p["updated_at"]
                if sell_ts and hasattr(sell_ts, "isoformat"):
                    sell_ts_str = sell_ts.isoformat()
                else:
                    sell_ts_str = f"{p['exit_date']}T16:00:00"
                events.append({
                    "type": "SELL",
                    "timestamp": sell_ts_str,
                    "ticker": p["ticker"],
                    "detail": (
                        f"Sold {float(p['shares']):.0f} shares at "
                        f"${float(p['exit_price']):,.2f} "
                        f"({'+'if rpnl >= 0 else ''}{rpnl:,.2f})"
                    ),
                    "extra": {
                        "shares": float(p["shares"]),
                        "price": float(p["exit_price"]) if p["exit_price"] else None,
                        "pnl": rpnl,
                    },
                })

        if portfolio_tickers:
            decisions = registry.get_decisions(limit=500)
            decision_types_to_show = {"BUY", "SELL", "HOLD", "WATCHLIST", "REJECT", "TRIM"}
            for d in decisions:
                if d.ticker in portfolio_tickers and d.decision_type.value in decision_types_to_show:
                    ts = d.created_at.isoformat() if d.created_at else ""
                    events.append({
                        "type": f"DECISION_{d.decision_type.value}",
                        "timestamp": ts,
                        "ticker": d.ticker,
                        "detail": d.reasoning[:150] if d.reasoning else f"{d.decision_type.value} decision",
                        "extra": {
                            "confidence": float(d.confidence) if d.confidence else None,
                            "layer": d.layer_source,
                        },
                    })

        if portfolio_tickers:
            ticker_list = list(portfolio_tickers)
            verdict_rows = registry._db.execute(
                "SELECT id, ticker, verdict, confidence, reasoning, created_at "
                "FROM invest.verdicts WHERE ticker = ANY(%s) "
                "ORDER BY created_at DESC LIMIT 200",
                (ticker_list,),
            )
            for v in verdict_rows:
                ts = v["created_at"].isoformat() if v["created_at"] else ""
                events.append({
                    "type": "VERDICT",
                    "timestamp": ts,
                    "ticker": v["ticker"],
                    "detail": f"Verdict: {v['verdict']} ({float(v['confidence']) * 100:.0f}% confidence)",
                    "extra": {
                        "verdict": v["verdict"],
                        "confidence": float(v["confidence"]) if v["confidence"] else None,
                        "reasoning": (v["reasoning"] or "")[:200],
                    },
                })

        events.sort(key=lambda e: e["timestamp"], reverse=True)

        event_types = sorted({e["type"] for e in events})
        tickers_in_timeline = sorted({e["ticker"] for e in events})

        grouped: OrderedDict[str, list[dict]] = OrderedDict()
        for e in events[:limit]:
            d = e["timestamp"][:10] if e["timestamp"] else "unknown"
            if d not in grouped:
                grouped[d] = []
            grouped[d].append(e)

        return {
            "timeline": [
                {"date": d, "events": evts}
                for d, evts in grouped.items()
            ],
            "totalEvents": len(events),
            "filters": {
                "types": event_types,
                "tickers": tickers_in_timeline,
            },
        }

    def get_advisor(self) -> dict:
        registry = self._reg
        positions = registry.get_open_positions()
        if not positions:
            return {"actions": []}

        actions: list[dict] = []

        pos_by_ticker = {p.ticker: p for p in positions}
        tickers = list(pos_by_ticker.keys())
        total_value = sum(
            float(p.market_value) for p in positions
            if _safe_decimal(p.market_value) is not None
        )

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
                            "current_price": _safe_decimal(p.current_price),
                            "current_weight": round(float(p.market_value) / total_value * 100, 1) if total_value and _safe_decimal(p.market_value) is not None else 0,
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
                            "current_price": _safe_decimal(p.current_price),
                            "current_weight": round(float(p.market_value) / total_value * 100, 1) if total_value and _safe_decimal(p.market_value) is not None else 0,
                            "suggested_shares": max(1, int(float(p.shares) * 0.5)),
                        })
        except Exception:
            logger.warning("Sell engine failed in advisor", exc_info=True)

        # -- 2. Verdict-based signals on held positions --
        for ticker in tickers:
            try:
                verdict = registry.get_latest_verdict(ticker)
                if not verdict:
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
                    if weight < 8:
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
            corr_data = self.get_correlations()
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

        # -- 7. Enrich with agent stances --
        enriched_tickers: dict[str, dict] = {}
        for action in actions:
            t = action.get("ticker")
            if not t or t in enriched_tickers:
                continue
            try:
                v = registry.get_latest_verdict(t)
                if v and v.get("agent_stances"):
                    stances = v["agent_stances"]
                    enriched_tickers[t] = {
                        "agent_summary": [
                            {
                                "agent": s.get("agent") or s.get("name", ""),
                                "sentiment": float(s.get("sentiment", 0)),
                                "confidence": float(s.get("confidence", 0)),
                                "summary": (s.get("summary") or "")[:80],
                            }
                            for s in stances if isinstance(s, dict)
                        ],
                        "consensus_score": float(v.get("consensus_score") or 0),
                    }
            except Exception:
                pass

        for action in actions:
            t = action.get("ticker")
            if t and t in enriched_tickers:
                action["agent_summary"] = enriched_tickers[t]["agent_summary"]
                action["consensus_score"] = enriched_tickers[t]["consensus_score"]

        # -- 8. Sort: high priority first, then medium, then low --
        priority_order = {"high": 0, "medium": 1, "low": 2}
        actions.sort(key=lambda a: priority_order.get(a["priority"], 99))

        return {"actions": actions}

    def get_correlations(self) -> dict:
        import time as _time

        positions = self._reg.get_open_positions()
        tickers = sorted(set(p.ticker for p in positions))

        if len(tickers) < 2:
            return {"tickers": tickers, "correlations": []}

        cache_key = ",".join(tickers)
        now = _time.time()
        if cache_key in _correlation_cache:
            ts, data = _correlation_cache[cache_key]
            if now - ts < _CORR_CACHE_TTL:
                return data

        try:
            import yfinance as yf

            df = yf.download(tickers, period="3mo", auto_adjust=True, progress=False)
            if df.empty:
                return {"tickers": tickers, "correlations": []}

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

    def get_income(self) -> dict:
        registry = self._reg
        positions = registry.get_open_positions()
        if not positions:
            return {"positions": [], "summary": {}, "target": None}

        target_monthly = 0.0
        try:
            budget_rows = registry._db.execute(
                "SELECT income_target_monthly FROM invest.portfolio_budget LIMIT 1"
            )
            if budget_rows:
                target_monthly = float(budget_rows[0].get("income_target_monthly") or 0)
        except Exception:
            pass

        tickers = [p.ticker for p in positions]
        stock_rows = registry._db.execute(
            "SELECT ticker, name, sector FROM invest.stocks WHERE ticker = ANY(%s)",
            (tickers,),
        )
        stock_info = {r["ticker"]: r for r in stock_rows}

        div_data = get_dividend_data(tickers)

        items: list[dict] = []
        total_annual_income = 0.0
        total_portfolio_value = 0.0
        payers = 0

        for p in positions:
            shares = float(p.shares)
            price = float(p.current_price) if p.current_price else 0.0
            position_value = shares * price
            total_portfolio_value += position_value

            dd = div_data.get(p.ticker, {})
            annual_div = dd.get("annual_div", 0.0)
            div_yield = (annual_div / price * 100) if price > 0 and annual_div > 0 else 0.0
            frequency = dd.get("frequency", "none")
            payout_ratio = dd.get("payout_ratio", 0.0)
            div_growth_5y = dd.get("div_growth_5y")
            last_div_amount = dd.get("last_div_amount", 0.0)
            last_div_date = dd.get("last_div_date")
            ex_div_date = dd.get("ex_div_date")

            position_income = annual_div * shares
            total_annual_income += position_income
            if annual_div > 0:
                payers += 1

            si = stock_info.get(p.ticker, {})
            name = si.get("name", p.ticker) or p.ticker
            short_name = name.split(",")[0].split(" Inc")[0].split(" Corp")[0].strip()

            items.append({
                "ticker": p.ticker,
                "name": short_name,
                "sector": si.get("sector", "") or "",
                "shares": shares,
                "price": price,
                "positionValue": position_value,
                "annualDividend": annual_div,
                "dividendYield": round(div_yield, 2),
                "annualIncome": round(position_income, 2),
                "monthlyIncome": round(position_income / 12, 2),
                "lastDividend": last_div_amount,
                "lastDividendDate": last_div_date,
                "exDividendDate": ex_div_date,
                "frequency": frequency,
                "payoutRatio": round(payout_ratio, 1),
                "dividendGrowth5y": round(div_growth_5y, 1) if div_growth_5y is not None else None,
                "positionType": p.position_type or "core",
            })

        items.sort(key=lambda x: x["annualIncome"], reverse=True)

        monthly_income = total_annual_income / 12
        blended_yield = (total_annual_income / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
        target_annual = target_monthly * 12
        target_pct = (monthly_income / target_monthly * 100) if target_monthly > 0 else 0

        capital_needed = 0.0
        if target_monthly > 0 and blended_yield > 0:
            capital_needed = max(0, (target_annual / (blended_yield / 100)) - total_portfolio_value)

        return {
            "positions": items,
            "summary": {
                "annualIncome": round(total_annual_income, 2),
                "monthlyIncome": round(monthly_income, 2),
                "blendedYield": round(blended_yield, 2),
                "portfolioValue": round(total_portfolio_value, 2),
                "dividendPayers": payers,
                "totalPositions": len(items),
            },
            "target": {
                "monthlyTarget": target_monthly,
                "annualTarget": target_annual,
                "progressPct": round(target_pct, 1),
                "capitalNeeded": round(capital_needed, 0),
            } if target_monthly > 0 else None,
        }

    def get_risk(self) -> dict:
        """Portfolio risk snapshot: drawdown from HWM, sector concentration, risk level."""
        from investmentology.risk.drawdown import DrawdownEngine

        positions = self._reg.get_open_positions()
        if not positions:
            return {
                "drawdownPct": 0,
                "highWaterMark": 0,
                "totalValue": 0,
                "riskLevel": "NORMAL",
                "positionCount": 0,
                "sectorConcentration": {},
                "topPositionWeight": 0,
                "maxDrawdown252d": 0,
                "history": [],
            }

        try:
            budget_rows = self._reg._db.execute(
                "SELECT cash_reserve FROM invest.portfolio_budget LIMIT 1"
            )
            cash = Decimal(str(budget_rows[0]["cash_reserve"])) if budget_rows else Decimal(0)
        except Exception:
            cash = Decimal(0)

        engine = DrawdownEngine(self._reg._db)
        snapshot = engine.compute_snapshot(positions, cash)

        try:
            engine.save_snapshot(snapshot)
        except Exception:
            logger.warning("Failed to save risk snapshot", exc_info=True)

        max_dd = engine.get_max_drawdown(days=252)
        history = engine.get_history(days=90)

        # VaR computation (may be slow — yfinance fetch)
        var_data = None
        try:
            from investmentology.risk.var import VaREngine

            var_result = VaREngine().compute_var(
                positions, float(snapshot.total_value)
            )
            if var_result:
                var_data = {
                    "var95": var_result.var_95,
                    "var99": var_result.var_99,
                    "cvar95": var_result.cvar_95,
                    "dollarVar95": var_result.dollar_var_95,
                    "horizonDays": var_result.horizon_days,
                    "observationCount": var_result.observation_count,
                }
        except Exception:
            logger.warning("VaR computation skipped", exc_info=True)

        return {
            "drawdownPct": round(float(snapshot.drawdown_pct), 2),
            "highWaterMark": round(float(snapshot.high_water_mark), 2),
            "totalValue": round(float(snapshot.total_value), 2),
            "riskLevel": snapshot.risk_level,
            "positionCount": snapshot.position_count,
            "sectorConcentration": snapshot.sector_concentration,
            "topPositionWeight": round(float(snapshot.top_position_weight), 1),
            "maxDrawdown252d": round(float(max_dd), 2),
            "var": var_data,
            "history": history,
        }

    def get_sparklines(self) -> dict:
        """Batch sparkline data for all open positions from fundamentals_cache."""
        positions = self._reg.get_open_positions()
        tickers = list({p.ticker for p in positions})
        if not tickers:
            return {"sparklines": {}}

        rows = self._reg._db.execute("""
            SELECT ticker, fetched_at::date AS dt, price
            FROM invest.fundamentals_cache
            WHERE ticker = ANY(%s) AND price > 0
            ORDER BY ticker, fetched_at::date
        """, [tickers])

        sparklines: dict[str, list[dict]] = {}
        for row in rows:
            ticker = row["ticker"]
            if ticker not in sparklines:
                sparklines[ticker] = []
            sparklines[ticker].append({
                "date": str(row["dt"]),
                "close": round(float(row["price"]), 2),
            })

        # Fallback for tickers with insufficient cache data
        missing = [t for t in tickers if len(sparklines.get(t, [])) < 10]
        if missing:
            try:
                import yfinance as yf
                data = yf.download(missing, period="3mo", progress=False, threads=True)
                if not data.empty:
                    close = data["Close"] if len(missing) > 1 else data[["Close"]]
                    for ticker in missing:
                        col = ticker if len(missing) > 1 else "Close"
                        if col in close.columns:
                            series = close[col].dropna()
                            sparklines[ticker] = [
                                {"date": str(idx.date()), "close": round(float(val), 2)}
                                for idx, val in series.items()
                            ]
            except Exception:
                logger.warning("yfinance sparkline fallback failed", exc_info=True)

        return {"sparklines": sparklines}

    def get_performance(self, period: str = "3mo") -> dict:
        """Portfolio value time series from risk snapshots."""
        from datetime import datetime, timedelta

        period_days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "all": 9999}
        days = period_days.get(period, 90)
        since = datetime.now() - timedelta(days=days)

        rows = self._reg._db.execute("""
            SELECT snapshot_date, total_value, drawdown_pct, high_water_mark
            FROM invest.portfolio_risk_snapshots
            WHERE snapshot_date >= %s
            ORDER BY snapshot_date
        """, [since.date()])

        if not rows:
            return {"dataPoints": [], "cumReturn": 0, "maxDrawdown": 0}

        data_points = []
        for r in rows:
            data_points.append({
                "date": str(r["snapshot_date"]),
                "value": round(float(r["total_value"]), 2),
                "drawdownPct": round(float(r["drawdown_pct"]), 2),
            })

        first_val = float(rows[0]["total_value"])
        last_val = float(rows[-1]["total_value"])
        cum_return = ((last_val - first_val) / first_val * 100) if first_val > 0 else 0
        max_dd = max((float(r["drawdown_pct"]) for r in rows), default=0)

        return {
            "dataPoints": data_points,
            "cumReturn": round(cum_return, 2),
            "maxDrawdown": round(max_dd, 2),
        }
