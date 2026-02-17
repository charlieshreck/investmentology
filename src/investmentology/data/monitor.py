from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from investmentology.data.alerts import Alert, AlertEngine
from investmentology.data.snapshots import fetch_market_snapshot
from investmentology.data.yfinance_client import YFinanceClient
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)


@dataclass
class MonitorResult:
    alerts: list[Alert] = field(default_factory=list)
    positions_updated: int = 0
    predictions_settled: int = 0
    market_snapshot_id: int | None = None
    cron_run_id: int = 0
    duration_seconds: float = 0.0


class DailyMonitor:
    """Daily monitoring loop -- runs at 4:15 PM ET and 8:00 AM ET."""

    JOB_NAME = "daily_monitor"
    JOB_NAME_PREMARKET = "premarket_monitor"

    def __init__(
        self,
        registry: Registry,
        yf_client: YFinanceClient,
        alert_engine: AlertEngine,
    ) -> None:
        self._registry = registry
        self._yf_client = yf_client
        self._alert_engine = alert_engine

    def run(self) -> MonitorResult:
        """Execute the daily monitoring cycle:

        1. Log cron start
        2. Fetch current prices for all open positions
        3. Update position current_price in registry
        4. Fetch market snapshot (SPY, VIX, etc.)
        5. Insert market snapshot to registry
        6. Run alert engine on all positions
        7. Settle predictions where settlement_date <= today
        8. Log cron finish
        9. Return MonitorResult with alerts and settled predictions
        """
        start = time.monotonic()
        result = MonitorResult()
        cron_id = self._registry.log_cron_start(self.JOB_NAME)
        result.cron_run_id = cron_id

        try:
            # Step 2: Fetch prices and update positions
            positions = self._registry.get_open_positions()
            if positions:
                tickers = [p.ticker for p in positions]
                prices = self._yf_client.get_prices_batch(tickers)
                for pos in positions:
                    if pos.ticker in prices:
                        pos.current_price = prices[pos.ticker]
                        self._registry.upsert_position(pos)
                        result.positions_updated += 1

            # Step 4-5: Market snapshot
            snapshot = fetch_market_snapshot()
            snapshot_id = self._registry.insert_market_snapshot(snapshot)
            result.market_snapshot_id = snapshot_id

            # Step 6: Run alerts
            vix = Decimal(str(snapshot.get("vix") or 0))
            # SPY drawdown would be calculated from recent high; use 0 as default
            spy_drawdown = Decimal("0")
            sector_map = self._build_sector_map(positions)
            # Re-fetch positions with updated prices
            positions = self._registry.get_open_positions()
            result.alerts = self._alert_engine.evaluate_all(
                positions, sector_map, vix, spy_drawdown,
            )

            # Step 7: Settle predictions
            unsettled = self._registry.get_unsettled_predictions(as_of=date.today())
            for pred in unsettled:
                actual = self._yf_client.get_price(pred.ticker)
                if actual is not None:
                    self._registry.settle_prediction(pred.id, actual)
                    result.predictions_settled += 1

            self._registry.log_cron_finish(cron_id, "success")

        except Exception as exc:
            logger.exception("Daily monitor failed")
            self._registry.log_cron_finish(cron_id, "error", str(exc))
            raise

        result.duration_seconds = time.monotonic() - start
        return result

    def run_premarket(self) -> MonitorResult:
        """Pre-market check (8:00 AM ET) -- lighter version.

        Only checks circuit breakers and stop losses, no settlement.
        """
        start = time.monotonic()
        result = MonitorResult()
        cron_id = self._registry.log_cron_start(self.JOB_NAME_PREMARKET)
        result.cron_run_id = cron_id

        try:
            positions = self._registry.get_open_positions()

            # Check stop losses with current prices (from registry, no live fetch)
            stop_alerts = self._alert_engine.check_stop_losses(positions)

            # Check circuit breakers with live VIX
            vix_price = self._yf_client.get_price("^VIX")
            vix = vix_price if vix_price is not None else Decimal("0")
            breaker_alerts = self._alert_engine.check_circuit_breakers(
                vix, Decimal("0"),
            )

            result.alerts = breaker_alerts + stop_alerts
            self._registry.log_cron_finish(cron_id, "success")

        except Exception as exc:
            logger.exception("Premarket monitor failed")
            self._registry.log_cron_finish(cron_id, "error", str(exc))
            raise

        result.duration_seconds = time.monotonic() - start
        return result

    @staticmethod
    def _build_sector_map(positions: list) -> dict[str, str]:
        """Build a ticker -> sector map. Placeholder until sector data is in registry."""
        # In Phase 1, sector data comes from the stocks table.
        # For now, return empty map; the alert engine handles missing sectors gracefully.
        return {}
