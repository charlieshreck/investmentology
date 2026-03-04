"""Portfolio endpoints."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from investmentology.api.deps import get_registry
from investmentology.api.services.portfolio_service import PortfolioService
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


class IncomeTargetRequest(BaseModel):
    monthly_target: float


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
        result = {"id": position_id, "ticker": ticker, "status": "created"}

    return result


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


@router.get("/portfolio/closed")
def get_closed_positions(registry: Registry = Depends(get_registry)) -> dict:
    """Return closed positions with realized P&L."""
    return PortfolioService(registry).get_closed()


@router.get("/portfolio/balance")
def get_portfolio_balance(registry: Registry = Depends(get_registry)) -> dict:
    """Portfolio balance: sector allocation, risk spectrum, and soft-band health."""
    return PortfolioService(registry).get_balance()


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
