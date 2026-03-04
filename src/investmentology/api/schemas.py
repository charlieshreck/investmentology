"""Pydantic response models for typed API responses."""

from __future__ import annotations

from pydantic import BaseModel


# ── System ──


class SystemHealthResponse(BaseModel):
    status: str
    database: bool
    apiKeys: dict[str, bool]
    lastQuantRun: str | None
    decisionsLogged: int
    uptime: int


# ── Portfolio ──


class PositionResponse(BaseModel):
    id: int | None = None
    ticker: str
    name: str | None = None
    shares: float
    avgCost: float
    currentPrice: float | None = None
    marketValue: float
    unrealizedPnl: float
    unrealizedPnlPct: float
    weight: float
    positionType: str | None = None
    entryDate: str | None = None
    stopLoss: float | None = None
    fairValueEstimate: float | None = None
    thesis: str | None = None
    dayChange: float | None = None
    dayChangePct: float | None = None
    dividendYield: float | None = None
    monthlyDividend: float | None = None
    annualDividend: float | None = None


class AlertResponse(BaseModel):
    id: int | None = None
    ticker: str
    type: str
    severity: str
    message: str
    detail: str | None = None
    createdAt: str | None = None


class ClosedPositionResponse(BaseModel):
    id: int | None = None
    ticker: str
    shares: float
    entryPrice: float
    exitPrice: float | None = None
    realizedPnl: float
    realizedPnlPct: float
    holdingDays: int | None = None
    closedAt: str | None = None


class PortfolioResponse(BaseModel):
    positions: list[PositionResponse]
    totalValue: float
    totalPnl: float
    totalPnlPct: float
    cash: float
    dayPnl: float
    dayPnlPct: float
    alerts: list[AlertResponse]
    closedPositions: list[ClosedPositionResponse]
    totalRealizedPnl: float


class PortfolioBalanceResponse(BaseModel):
    sectors: list[dict]
    riskCategories: list[dict]
    positionCount: int
    sectorCount: int
    health: str
    insights: list[str]


# ── Quant Gate ──


class QuantGateResultResponse(BaseModel):
    ticker: str
    name: str | None = None
    compositeScore: float | None = None
    earningsYield: float | None = None
    roic: float | None = None
    greenblattRank: int | None = None
    piotroskiScore: int | None = None
    altmanZone: str | None = None
    marketCap: float | None = None
    sector: str | None = None


class QuantGateRunResponse(BaseModel):
    runDate: str
    totalScreened: int
    results: list[QuantGateResultResponse]
