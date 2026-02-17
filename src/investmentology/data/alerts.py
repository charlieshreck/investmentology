from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from investmentology.models.position import PortfolioPosition

logger = logging.getLogger(__name__)


class AlertSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Severity ordering for sorting (higher = more severe)
_SEVERITY_ORDER = {
    AlertSeverity.INFO: 0,
    AlertSeverity.WARNING: 1,
    AlertSeverity.ERROR: 2,
    AlertSeverity.CRITICAL: 3,
}


class AlertType(StrEnum):
    STOP_LOSS_APPROACHING = "STOP_LOSS_APPROACHING"
    STOP_LOSS_TRIGGERED = "STOP_LOSS_TRIGGERED"
    TRIPWIRE_TRIGGERED = "TRIPWIRE_TRIGGERED"
    CIRCUIT_BREAKER_L1 = "CIRCUIT_BREAKER_L1"
    CIRCUIT_BREAKER_L2 = "CIRCUIT_BREAKER_L2"
    CIRCUIT_BREAKER_L3 = "CIRCUIT_BREAKER_L3"
    PREDICTION_SETTLED = "PREDICTION_SETTLED"
    POSITION_CONCENTRATION = "POSITION_CONCENTRATION"
    SECTOR_CONCENTRATION = "SECTOR_CONCENTRATION"


@dataclass
class Alert:
    alert_type: AlertType
    severity: AlertSeverity
    ticker: str | None
    message: str
    detail: dict | None = None
    timestamp: datetime = field(default_factory=datetime.now)


class AlertEngine:
    """Evaluates alert rules against current portfolio state."""

    def __init__(
        self,
        max_position_pct: Decimal = Decimal("0.05"),
        max_sector_pct: Decimal = Decimal("0.30"),
        stop_loss_warning_pct: Decimal = Decimal("0.02"),
    ) -> None:
        self.max_position_pct = max_position_pct
        self.max_sector_pct = max_sector_pct
        self.stop_loss_warning_pct = stop_loss_warning_pct

    def check_stop_losses(self, positions: list[PortfolioPosition]) -> list[Alert]:
        """Check positions against stop losses.

        - APPROACHING: within stop_loss_warning_pct of stop (WARNING)
        - TRIGGERED: at or below stop loss (ERROR)
        """
        alerts: list[Alert] = []
        for pos in positions:
            if pos.stop_loss is None or pos.current_price <= 0:
                continue

            if pos.current_price <= pos.stop_loss:
                alerts.append(Alert(
                    alert_type=AlertType.STOP_LOSS_TRIGGERED,
                    severity=AlertSeverity.ERROR,
                    ticker=pos.ticker,
                    message=(
                        f"{pos.ticker} stop loss TRIGGERED: "
                        f"price ${pos.current_price} <= stop ${pos.stop_loss}"
                    ),
                    detail={
                        "current_price": str(pos.current_price),
                        "stop_loss": str(pos.stop_loss),
                        "entry_price": str(pos.entry_price),
                        "pnl_pct": str(pos.pnl_pct),
                    },
                ))
            else:
                # Check if approaching: price within warning threshold of stop
                warning_threshold = pos.stop_loss * (1 + self.stop_loss_warning_pct)
                if pos.current_price <= warning_threshold:
                    distance_pct = (pos.current_price - pos.stop_loss) / pos.stop_loss
                    alerts.append(Alert(
                        alert_type=AlertType.STOP_LOSS_APPROACHING,
                        severity=AlertSeverity.WARNING,
                        ticker=pos.ticker,
                        message=(
                            f"{pos.ticker} approaching stop loss: "
                            f"price ${pos.current_price}, stop ${pos.stop_loss} "
                            f"({distance_pct:.2%} away)"
                        ),
                        detail={
                            "current_price": str(pos.current_price),
                            "stop_loss": str(pos.stop_loss),
                            "distance_pct": str(distance_pct),
                        },
                    ))
        return alerts

    def check_concentration(self, positions: list[PortfolioPosition]) -> list[Alert]:
        """Check position concentration limits.

        Single position > max_position_pct triggers WARNING.
        """
        alerts: list[Alert] = []
        total_value = sum(pos.market_value for pos in positions)
        if total_value <= 0:
            return alerts

        for pos in positions:
            weight = pos.market_value / total_value
            if weight > self.max_position_pct:
                alerts.append(Alert(
                    alert_type=AlertType.POSITION_CONCENTRATION,
                    severity=AlertSeverity.WARNING,
                    ticker=pos.ticker,
                    message=(
                        f"{pos.ticker} concentration {weight:.1%} "
                        f"exceeds limit {self.max_position_pct:.1%}"
                    ),
                    detail={
                        "weight": str(weight),
                        "limit": str(self.max_position_pct),
                        "market_value": str(pos.market_value),
                        "total_portfolio": str(total_value),
                    },
                ))
        return alerts

    def check_sector_concentration(
        self,
        positions: list[PortfolioPosition],
        sector_map: dict[str, str],
    ) -> list[Alert]:
        """Check sector exposure. Any sector > max_sector_pct triggers WARNING."""
        alerts: list[Alert] = []
        total_value = sum(pos.market_value for pos in positions)
        if total_value <= 0:
            return alerts

        sector_values: dict[str, Decimal] = {}
        for pos in positions:
            sector = sector_map.get(pos.ticker, "Unknown")
            sector_values[sector] = sector_values.get(sector, Decimal(0)) + pos.market_value

        for sector, value in sector_values.items():
            weight = value / total_value
            if weight > self.max_sector_pct:
                alerts.append(Alert(
                    alert_type=AlertType.SECTOR_CONCENTRATION,
                    severity=AlertSeverity.WARNING,
                    ticker=None,
                    message=(
                        f"Sector '{sector}' concentration {weight:.1%} "
                        f"exceeds limit {self.max_sector_pct:.1%}"
                    ),
                    detail={
                        "sector": sector,
                        "weight": str(weight),
                        "limit": str(self.max_sector_pct),
                        "sector_value": str(value),
                        "total_portfolio": str(total_value),
                    },
                ))
        return alerts

    def check_circuit_breakers(
        self,
        vix: Decimal,
        spy_drawdown_pct: Decimal,
    ) -> list[Alert]:
        """Check market-wide circuit breakers.

        L1: VIX > 25 or SPY drawdown > 5% (WARNING)
        L2: VIX > 35 or SPY drawdown > 10% (ERROR)
        L3: VIX > 45 or SPY drawdown > 15% (CRITICAL)
        """
        alerts: list[Alert] = []

        # Check from most severe to least, but emit all triggered levels
        if vix > 45 or spy_drawdown_pct > 15:
            alerts.append(Alert(
                alert_type=AlertType.CIRCUIT_BREAKER_L3,
                severity=AlertSeverity.CRITICAL,
                ticker=None,
                message=(
                    f"CIRCUIT BREAKER L3: VIX={vix}, SPY drawdown={spy_drawdown_pct}%. "
                    f"HALT all new positions."
                ),
                detail={"vix": str(vix), "spy_drawdown_pct": str(spy_drawdown_pct)},
            ))
        elif vix > 35 or spy_drawdown_pct > 10:
            alerts.append(Alert(
                alert_type=AlertType.CIRCUIT_BREAKER_L2,
                severity=AlertSeverity.ERROR,
                ticker=None,
                message=(
                    f"CIRCUIT BREAKER L2: VIX={vix}, SPY drawdown={spy_drawdown_pct}%. "
                    f"Reduce position sizes by 50%."
                ),
                detail={"vix": str(vix), "spy_drawdown_pct": str(spy_drawdown_pct)},
            ))
        elif vix > 25 or spy_drawdown_pct > 5:
            alerts.append(Alert(
                alert_type=AlertType.CIRCUIT_BREAKER_L1,
                severity=AlertSeverity.WARNING,
                ticker=None,
                message=(
                    f"CIRCUIT BREAKER L1: VIX={vix}, SPY drawdown={spy_drawdown_pct}%. "
                    f"Elevated caution."
                ),
                detail={"vix": str(vix), "spy_drawdown_pct": str(spy_drawdown_pct)},
            ))

        return alerts

    def evaluate_all(
        self,
        positions: list[PortfolioPosition],
        sector_map: dict[str, str],
        vix: Decimal,
        spy_drawdown_pct: Decimal,
    ) -> list[Alert]:
        """Run all alert checks. Returns sorted by severity (critical first)."""
        alerts: list[Alert] = []
        alerts.extend(self.check_stop_losses(positions))
        alerts.extend(self.check_concentration(positions))
        alerts.extend(self.check_sector_concentration(positions, sector_map))
        alerts.extend(self.check_circuit_breakers(vix, spy_drawdown_pct))

        # Sort by severity descending (critical first)
        alerts.sort(key=lambda a: _SEVERITY_ORDER.get(a.severity, 0), reverse=True)
        return alerts
