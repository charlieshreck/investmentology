"""Drawdown engine with high-water mark tracking.

Computes portfolio drawdown from HWM and persists daily snapshots to
the portfolio_risk_snapshots table (migration 009).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from investmentology.models.position import PortfolioPosition
from investmentology.registry.db import Database

logger = logging.getLogger(__name__)


@dataclass
class RiskSnapshot:
    """Point-in-time portfolio risk state."""

    snapshot_date: date
    total_value: Decimal
    position_count: int
    drawdown_pct: Decimal
    high_water_mark: Decimal
    sector_concentration: dict[str, float]
    top_position_weight: Decimal
    risk_level: str  # NORMAL, ELEVATED, HIGH, CRITICAL
    details: dict = field(default_factory=dict)


def _classify_risk(drawdown_pct: float) -> str:
    """Map drawdown percentage to risk level."""
    if drawdown_pct < 10:
        return "NORMAL"
    if drawdown_pct < 15:
        return "ELEVATED"
    if drawdown_pct < 20:
        return "HIGH"
    return "CRITICAL"


class DrawdownEngine:
    """Track portfolio drawdown from high-water mark (HWM).

    Called on-demand from /portfolio/risk endpoint and daily by overnight pipeline.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def compute_snapshot(
        self,
        positions: list[PortfolioPosition],
        cash: Decimal,
    ) -> RiskSnapshot:
        """Compute current drawdown from stored HWM."""
        total_value = sum(p.market_value for p in positions) + cash

        # Fetch previous HWM
        rows = self._db.execute(
            "SELECT COALESCE(MAX(high_water_mark), 0) AS hwm "
            "FROM invest.portfolio_risk_snapshots"
        )
        prev_hwm = Decimal(str(rows[0]["hwm"])) if rows else Decimal(0)
        hwm = max(total_value, prev_hwm)

        # Drawdown from HWM
        if hwm > 0:
            drawdown_pct = (hwm - total_value) / hwm * 100
        else:
            drawdown_pct = Decimal(0)

        # Sector concentration
        sector_map: dict[str, Decimal] = {}
        for p in positions:
            try:
                s_rows = self._db.execute(
                    "SELECT sector FROM invest.stocks WHERE ticker = %s",
                    (p.ticker,),
                )
                sector = s_rows[0]["sector"] if s_rows else "Unknown"
            except Exception:
                sector = "Unknown"
            sector_map[sector] = sector_map.get(sector, Decimal(0)) + p.market_value

        sector_concentration: dict[str, float] = {}
        if total_value > 0:
            for sector, val in sector_map.items():
                sector_concentration[sector] = round(
                    float(val / total_value * 100), 1
                )

        # Top position weight
        top_weight = Decimal(0)
        if total_value > 0 and positions:
            top_weight = max(p.market_value for p in positions) / total_value * 100

        risk_level = _classify_risk(float(drawdown_pct))

        return RiskSnapshot(
            snapshot_date=date.today(),
            total_value=total_value,
            position_count=len(positions),
            drawdown_pct=drawdown_pct,
            high_water_mark=hwm,
            sector_concentration=sector_concentration,
            top_position_weight=top_weight,
            risk_level=risk_level,
        )

    def save_snapshot(self, snapshot: RiskSnapshot) -> None:
        """Upsert into portfolio_risk_snapshots (unique on snapshot_date)."""
        self._db.execute(
            """
            INSERT INTO invest.portfolio_risk_snapshots
                (snapshot_date, total_value, position_count,
                 portfolio_drawdown_pct, high_water_mark,
                 sector_concentration, top_position_weight,
                 risk_level, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (snapshot_date) DO UPDATE SET
                total_value = EXCLUDED.total_value,
                position_count = EXCLUDED.position_count,
                portfolio_drawdown_pct = EXCLUDED.portfolio_drawdown_pct,
                high_water_mark = EXCLUDED.high_water_mark,
                sector_concentration = EXCLUDED.sector_concentration,
                top_position_weight = EXCLUDED.top_position_weight,
                risk_level = EXCLUDED.risk_level,
                details = EXCLUDED.details
            """,
            (
                snapshot.snapshot_date,
                snapshot.total_value,
                snapshot.position_count,
                snapshot.drawdown_pct,
                snapshot.high_water_mark,
                snapshot.sector_concentration,
                snapshot.top_position_weight,
                snapshot.risk_level,
                snapshot.details,
            ),
        )

    def get_max_drawdown(self, days: int = 252) -> Decimal:
        """Max drawdown over trailing period from saved snapshots."""
        rows = self._db.execute(
            "SELECT COALESCE(MAX(portfolio_drawdown_pct), 0) AS max_dd "
            "FROM invest.portfolio_risk_snapshots "
            "WHERE snapshot_date >= CURRENT_DATE - %s",
            (days,),
        )
        return Decimal(str(rows[0]["max_dd"])) if rows else Decimal(0)

    def get_history(self, days: int = 90) -> list[dict]:
        """Return recent risk snapshot history."""
        rows = self._db.execute(
            "SELECT snapshot_date, total_value, portfolio_drawdown_pct, "
            "high_water_mark, risk_level, sector_concentration, top_position_weight "
            "FROM invest.portfolio_risk_snapshots "
            "WHERE snapshot_date >= CURRENT_DATE - %s "
            "ORDER BY snapshot_date DESC",
            (days,),
        )
        return [
            {
                "date": str(r["snapshot_date"]),
                "totalValue": float(r["total_value"]),
                "drawdownPct": float(r["portfolio_drawdown_pct"]),
                "highWaterMark": float(r["high_water_mark"]),
                "riskLevel": r["risk_level"],
                "sectorConcentration": r.get("sector_concentration", {}),
                "topPositionWeight": float(r["top_position_weight"]),
            }
            for r in rows
        ]
