"""Portfolio endpoints."""

from __future__ import annotations

import csv
import io
import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from investmentology.api.deps import get_registry
from investmentology.api.schemas import PortfolioBalanceResponse
from investmentology.api.services.portfolio_service import PortfolioService
from investmentology.registry.queries import Registry
from investmentology.timing.sizing import PositionSizer, SizingConfig

logger = logging.getLogger(__name__)


class InvalidationCriterion(BaseModel):
    criteria_type: str  # roic_floor, fscore_floor, revenue_growth_floor, debt_ceiling, dividend_cut, custom_quantitative, custom_qualitative
    threshold_value: float | None = None  # numeric threshold (required for quantitative)
    qualitative_text: str | None = None  # description (required for qualitative)
    is_quantitative: bool = True


class CreatePositionRequest(BaseModel):
    ticker: str
    entry_price: float
    shares: float
    position_type: str = "core"
    weight: float = 0.0
    stop_loss: float | None = None
    fair_value_estimate: float | None = None
    thesis: str = ""
    invalidation_criteria: list[InvalidationCriterion] = []


class ClosePositionRequest(BaseModel):
    exit_price: float
    exit_date: str | None = None


class IncomeTargetRequest(BaseModel):
    monthly_target: float


class ScenarioRequest(BaseModel):
    action: str  # "add", "remove", "resize"
    ticker: str
    shares: float
    price: float | None = None


router = APIRouter()


@router.get("/portfolio")
def get_portfolio(registry: Registry = Depends(get_registry)) -> dict:
    """Return positions list with P&L, sector exposure summary, total value."""
    return PortfolioService(registry).get_portfolio()


@router.get("/portfolio/alerts")
def get_portfolio_alerts(registry: Registry = Depends(get_registry)) -> dict:
    """Portfolio alerts: stop-loss breaches, drawdowns, sell engine signals."""
    return PortfolioService(registry).get_alerts()


@router.post("/portfolio/positions")
def create_position(
    body: CreatePositionRequest,
    registry: Registry = Depends(get_registry),
) -> dict:
    """Create a new paper portfolio position, or add to existing position for same ticker."""
    if body.stop_loss is None:
        raise HTTPException(
            status_code=422,
            detail="stop_loss is required for every position. "
            "Set a trailing stop (core: 15-20%, permanent: 25% catastrophic).",
        )

    # Enforce thesis invalidation criteria at BUY time
    has_quant = any(c.is_quantitative for c in body.invalidation_criteria)
    has_qual = any(not c.is_quantitative for c in body.invalidation_criteria)
    if not (has_quant and has_qual):
        raise HTTPException(
            status_code=422,
            detail="At least one quantitative AND one qualitative invalidation "
            "criterion required. Examples: quantitative='ROIC floor >= 12%', "
            "qualitative='thesis breaks if they lose the DOD contract'. "
            "Send invalidation_criteria with is_quantitative=true/false.",
        )

    # Validate each criterion
    for c in body.invalidation_criteria:
        if c.is_quantitative and c.threshold_value is None:
            raise HTTPException(
                status_code=422,
                detail=f"Quantitative criterion '{c.criteria_type}' requires threshold_value.",
            )
        if not c.is_quantitative and not c.qualitative_text:
            raise HTTPException(
                status_code=422,
                detail=f"Qualitative criterion '{c.criteria_type}' requires qualitative_text.",
            )

    ticker = body.ticker.upper()
    new_shares = Decimal(str(body.shares))
    new_price = Decimal(str(body.entry_price))

    existing = registry.get_open_positions()

    # Portfolio construction limits check
    purchase_value = float(new_price * new_shares)
    total_portfolio_value = sum(float(p.current_price * p.shares) for p in existing) + purchase_value

    if total_portfolio_value > 0:
        existing_pos = next((p for p in existing if p.ticker == ticker), None)
        position_value = purchase_value
        if existing_pos:
            position_value += float(existing_pos.current_price * existing_pos.shares)
        position_pct = position_value / total_portfolio_value * 100
        if position_pct > 20:
            raise HTTPException(
                status_code=422,
                detail=f"Position would be {position_pct:.1f}% of portfolio. "
                f"Max single position is 20%.",
            )

        try:
            rows = registry._db.execute(
                "SELECT sector FROM invest.stocks WHERE ticker = %s", (ticker,)
            )
            candidate_sector = rows[0]["sector"] if rows else None
            if candidate_sector:
                sector_value = purchase_value
                for p in existing:
                    try:
                        s_rows = registry._db.execute(
                            "SELECT sector FROM invest.stocks WHERE ticker = %s",
                            (p.ticker,),
                        )
                        if s_rows and s_rows[0].get("sector") == candidate_sector:
                            sector_value += float(p.current_price * p.shares)
                    except Exception:
                        pass
                sector_pct = sector_value / total_portfolio_value * 100
                if sector_pct > 25:
                    raise HTTPException(
                        status_code=422,
                        detail=f"{candidate_sector} sector would be {sector_pct:.1f}% "
                        f"of portfolio. Max single sector is 25%.",
                    )
        except HTTPException:
            raise
        except Exception:
            logger.debug("Sector check failed for %s", ticker)

    # Correlation gate: block high-correlation additions (soft — fails open)
    if len(existing) >= 3:
        try:
            corr_data = PortfolioService(registry).get_correlations()
            if corr_data.get("correlations"):
                ticker_corrs = [
                    c["value"]
                    for c in corr_data["correlations"]
                    if ticker in (c["ticker1"], c["ticker2"])
                ]
                if ticker_corrs:
                    avg_corr = sum(ticker_corrs) / len(ticker_corrs)
                    if avg_corr > 0.75:
                        raise HTTPException(
                            status_code=422,
                            detail=f"{ticker} has {avg_corr:.2f} avg correlation "
                            f"with portfolio. Adds concentration risk (threshold: 0.75).",
                        )
        except HTTPException:
            raise
        except Exception:
            logger.debug("Correlation gate skipped for %s (data unavailable)", ticker)

    existing_pos = next((p for p in existing if p.ticker == ticker), None)
    purchase_cost = new_price * new_shares

    if existing_pos:
        old_cost = existing_pos.entry_price * existing_pos.shares
        new_cost = new_price * new_shares
        total_shares = existing_pos.shares + new_shares
        avg_price = (old_cost + new_cost) / total_shares

        with registry._db.transaction() as tx:
            tx.execute(
                "UPDATE invest.portfolio_positions "
                "SET shares = %s, entry_price = %s, current_price = %s, updated_at = NOW() "
                "WHERE id = %s AND is_closed = FALSE",
                (total_shares, avg_price, new_price, existing_pos.id),
            )
            tx.execute(
                "UPDATE invest.portfolio_budget SET cash_reserve = cash_reserve - %s",
                (purchase_cost,),
            )
        logger.info("Added to position + deducted $%.2f for %s (atomic)", float(purchase_cost), ticker)
        result = {"id": existing_pos.id, "ticker": ticker, "status": "added",
                  "totalShares": float(total_shares), "avgCost": float(avg_price)}
    else:
        position_id = registry.create_position_atomic(
            ticker=ticker,
            entry_date=date.today(),
            entry_price=new_price,
            shares=new_shares,
            position_type=body.position_type,
            weight=Decimal(str(body.weight)),
            purchase_cost=purchase_cost,
            stop_loss=Decimal(str(body.stop_loss)) if body.stop_loss else None,
            fair_value_estimate=Decimal(str(body.fair_value_estimate)) if body.fair_value_estimate else None,
            thesis=body.thesis,
        )
        logger.info("Created position + deducted $%.2f for %s (atomic)", float(purchase_cost), ticker)

        # Store thesis invalidation criteria
        if body.invalidation_criteria:
            import json
            break_conds = []
            for c in body.invalidation_criteria:
                registry._db.execute(
                    "INSERT INTO invest.thesis_criteria "
                    "(position_id, criteria_type, threshold_value, qualitative_text, "
                    " is_quantitative, monitoring_active) "
                    "VALUES (%s, %s, %s, %s, %s, TRUE)",
                    (position_id, c.criteria_type, c.threshold_value,
                     c.qualitative_text, c.is_quantitative),
                )
                break_conds.append({
                    "type": c.criteria_type,
                    "threshold": c.threshold_value,
                    "text": c.qualitative_text,
                    "quantitative": c.is_quantitative,
                })
            # Store summary on position for quick access
            registry._db.execute(
                "UPDATE invest.portfolio_positions SET break_conditions = %s WHERE id = %s",
                (json.dumps(break_conds), position_id),
            )

        result = {"id": position_id, "ticker": ticker, "status": "created"}

    # Advisory sizing suggestion (non-blocking)
    try:
        budget_rows = registry._db.execute(
            "SELECT cash_reserve FROM invest.portfolio_budget LIMIT 1"
        )
        cash = float(budget_rows[0]["cash_reserve"]) if budget_rows else 0.0
        pv = total_portfolio_value + cash
        if pv > 0:
            sizer = PositionSizer(SizingConfig())
            suggestion = sizer.calculate_size(
                portfolio_value=Decimal(str(pv)),
                price=new_price,
                current_position_count=len(existing),
                ticker=ticker,
            )
            result["sizingSuggestion"] = {
                "suggestedShares": suggestion.shares,
                "suggestedDollarAmount": float(suggestion.dollar_amount),
                "suggestedWeightPct": float(suggestion.weight_pct),
                "method": suggestion.sizing_method,
                "rationale": suggestion.rationale,
            }
    except Exception:
        logger.debug("Sizing suggestion failed for %s", ticker)

    return result


@router.get("/portfolio/positions/{position_id}/criteria")
def get_position_criteria(
    position_id: int,
    registry: Registry = Depends(get_registry),
) -> dict:
    """Get thesis invalidation criteria for a position."""
    from investmentology.advisory.thesis_health import get_criteria_for_position

    criteria = get_criteria_for_position(position_id, registry)
    return {"position_id": position_id, "criteria": criteria}


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
    proceeds = position.shares * Decimal(str(body.exit_price))
    registry.close_position_atomic(position_id, Decimal(str(body.exit_price)), proceeds, exit_d)
    logger.info("Closed %s + credited $%.2f proceeds (atomic)", position.ticker, float(proceeds))

    return {"id": position_id, "status": "closed", "exit_price": body.exit_price, "proceeds": float(proceeds)}


@router.get("/portfolio/sizing/{ticker}")
def get_sizing_suggestion(
    ticker: str,
    price: float | None = None,
    registry: Registry = Depends(get_registry),
) -> dict:
    """Pre-trade sizing suggestion for a ticker."""
    ticker = ticker.upper()
    positions = registry.get_open_positions()
    budget_rows = registry._db.execute(
        "SELECT cash_reserve FROM invest.portfolio_budget LIMIT 1"
    )
    cash = float(budget_rows[0]["cash_reserve"]) if budget_rows else 0.0
    portfolio_value = sum(float(p.current_price * p.shares) for p in positions) + cash

    if portfolio_value <= 0:
        raise HTTPException(status_code=400, detail="Portfolio value must be positive")

    # Use provided price or try to fetch current price
    if price is None:
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).fast_info
            price = float(info.get("lastPrice", 0) or info.get("last_price", 0))
        except Exception:
            raise HTTPException(status_code=400, detail="Price required (could not fetch)")
    if price <= 0:
        raise HTTPException(status_code=400, detail="Price must be positive")

    sizer = PositionSizer(SizingConfig())
    suggestion = sizer.calculate_size(
        portfolio_value=Decimal(str(portfolio_value)),
        price=Decimal(str(price)),
        current_position_count=len(positions),
        ticker=ticker,
    )
    return {
        "ticker": ticker,
        "price": price,
        "portfolioValue": round(portfolio_value, 2),
        "cashAvailable": round(cash, 2),
        "positionCount": len(positions),
        "suggestedShares": suggestion.shares,
        "suggestedDollarAmount": float(suggestion.dollar_amount),
        "suggestedWeightPct": float(suggestion.weight_pct),
        "method": suggestion.sizing_method,
        "rationale": suggestion.rationale,
    }


@router.get("/portfolio/closed")
def get_closed_positions(registry: Registry = Depends(get_registry)) -> dict:
    """Return closed positions with realized P&L."""
    return PortfolioService(registry).get_closed()


@router.get("/portfolio/balance", response_model=PortfolioBalanceResponse)
def get_portfolio_balance(registry: Registry = Depends(get_registry)) -> dict:
    """Portfolio balance: sector allocation, risk spectrum, and soft-band health."""
    return PortfolioService(registry).get_balance()


@router.get("/portfolio/risk")
def get_portfolio_risk(registry: Registry = Depends(get_registry)) -> dict:
    """Portfolio risk snapshot: drawdown from HWM, concentration, risk level."""
    return PortfolioService(registry).get_risk()


@router.get("/portfolio/sparklines")
def get_portfolio_sparklines(registry: Registry = Depends(get_registry)) -> dict:
    """Batch sparkline data for all portfolio positions."""
    return PortfolioService(registry).get_sparklines()


@router.get("/portfolio/performance")
def get_portfolio_performance(
    period: str = Query("3mo", pattern="^(1mo|3mo|6mo|1y|all)$"),
    registry: Registry = Depends(get_registry),
) -> dict:
    """Portfolio value time series from risk snapshots."""
    return PortfolioService(registry).get_performance(period=period)


@router.get("/portfolio/correlations")
def get_portfolio_correlations(registry: Registry = Depends(get_registry)) -> dict:
    """90-day rolling correlation matrix for current portfolio holdings."""
    return PortfolioService(registry).get_correlations()


@router.get("/portfolio/advisor")
def get_portfolio_advisor(registry: Registry = Depends(get_registry)) -> dict:
    """Portfolio advisor: actionable recommendations for the whole portfolio."""
    return PortfolioService(registry).get_advisor()


@router.get("/portfolio/briefing")
def get_portfolio_briefing(registry: Registry = Depends(get_registry)) -> dict:
    """Portfolio-level briefing: plain-English synthesis of the whole portfolio."""
    return PortfolioService(registry).get_briefing()


@router.get("/portfolio/timeline")
def get_portfolio_timeline(
    limit: int = 80,
    registry: Registry = Depends(get_registry),
) -> dict:
    """Build a unified timeline of portfolio events."""
    return PortfolioService(registry).get_timeline(limit=limit)


@router.get("/portfolio/income")
def get_portfolio_income(registry: Registry = Depends(get_registry)) -> dict:
    """Passive income projection from dividends."""
    return PortfolioService(registry).get_income()


@router.post("/portfolio/income/target")
def set_income_target(
    body: IncomeTargetRequest,
    registry: Registry = Depends(get_registry),
) -> dict:
    """Set monthly passive income target."""
    registry._db.execute(
        "UPDATE invest.portfolio_budget SET income_target_monthly = %s",
        (Decimal(str(body.monthly_target)),),
    )
    return {"monthlyTarget": body.monthly_target, "status": "updated"}


@router.post("/portfolio/scenario")
def evaluate_scenario(
    body: ScenarioRequest,
    registry: Registry = Depends(get_registry),
) -> dict:
    """What-if scenario: simulate adding, removing, or resizing a position."""
    return PortfolioService(registry).evaluate_scenario(
        action=body.action,
        ticker=body.ticker,
        shares=body.shares,
        price=body.price,
    )


@router.get("/portfolio/export")
def export_portfolio(registry: Registry = Depends(get_registry)):
    """Export portfolio positions as CSV."""
    data = PortfolioService(registry).get_portfolio()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticker", "Shares", "Avg Cost", "Current Price", "Market Value",
                      "P&L", "P&L %", "Weight", "Type", "Entry Date"])
    for p in data.get("positions", []):
        writer.writerow([
            p["ticker"], p["shares"], p["avgCost"], p.get("currentPrice", ""),
            p.get("marketValue", ""), p.get("unrealizedPnl", ""),
            p.get("unrealizedPnlPct", ""), p.get("weight", ""),
            p.get("positionType", ""), p.get("entryDate", ""),
        ])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=portfolio.csv"},
    )
