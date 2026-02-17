from __future__ import annotations

from decimal import Decimal

from investmentology.learning.registry import DecisionLogger
from investmentology.models.decision import DecisionType
from investmentology.models.lifecycle import WatchlistState, validate_transition
from investmentology.registry.queries import Registry


class StockLifecycleManager:
    """Wraps watchlist operations with full decision audit trail."""

    def __init__(self, registry: Registry, decision_logger: DecisionLogger) -> None:
        self._registry = registry
        self._decision_logger = decision_logger

    def transition(
        self,
        ticker: str,
        new_state: WatchlistState,
        reason: str,
        layer_source: str,
        confidence: Decimal | None = None,
    ) -> None:
        """Transition a stock to a new lifecycle state.

        1. Update watchlist state via registry (validates transition internally)
        2. Log a Decision recording the transition
        """
        # This will raise ValueError if the transition is invalid or ticker not found
        self._registry.update_watchlist_state(ticker, new_state)

        self._decision_logger.log_analysis_decision(
            ticker=ticker,
            decision_type=DecisionType.WATCHLIST,
            layer_source=layer_source,
            confidence=confidence or Decimal("0"),
            reasoning=f"Transition to {new_state.value}: {reason}",
            signals={"new_state": new_state.value},
        )

    def promote_candidates(self, tickers: list[str], source_run_id: int) -> int:
        """Add new stocks from QG as CANDIDATE state. Returns count added."""
        count = 0
        for ticker in tickers:
            self._registry.add_to_watchlist(
                ticker=ticker,
                state=WatchlistState.CANDIDATE,
                source_run_id=source_run_id,
            )
            count += 1
        return count

    def get_pipeline_summary(self) -> dict[str, int]:
        """Get count of stocks in each lifecycle state."""
        summary: dict[str, int] = {}
        for state in WatchlistState:
            items = self._registry.get_watchlist_by_state(state)
            summary[state.value] = len(items)
        return summary
