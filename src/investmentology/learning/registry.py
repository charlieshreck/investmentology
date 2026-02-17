from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from investmentology.models.decision import Decision, DecisionType
from investmentology.registry.queries import Registry


class DecisionLogger:
    """Convenience wrapper around Registry for structured decision logging."""

    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    # Map action strings to DecisionType
    _ACTION_MAP: dict[str, DecisionType] = {
        "BUY": DecisionType.BUY,
        "SELL": DecisionType.SELL,
        "TRIM": DecisionType.TRIM,
        "HOLD": DecisionType.HOLD,
        "REJECT": DecisionType.REJECT,
    }

    def log_screen_decision(
        self, run_id: int, universe_size: int, passed_count: int
    ) -> int:
        """Log a L1 screening batch decision."""
        decision = Decision(
            ticker="__BATCH__",
            decision_type=DecisionType.SCREEN,
            layer_source="L1_QUANT_GATE",
            confidence=None,
            reasoning=f"Screened {universe_size} stocks, {passed_count} passed",
            metadata={
                "run_id": run_id,
                "universe_size": universe_size,
                "passed_count": passed_count,
            },
        )
        return self._registry.log_decision(decision)

    def log_competence_decision(
        self, ticker: str, passed: bool, reasoning: str, confidence: Decimal,
        signals: dict | None = None,
    ) -> int:
        """Log a L2 competence filter decision."""
        decision = Decision(
            ticker=ticker,
            decision_type=DecisionType.COMPETENCE_PASS if passed else DecisionType.COMPETENCE_FAIL,
            layer_source="L2_COMPETENCE",
            confidence=confidence,
            reasoning=reasoning,
            signals=signals,
        )
        return self._registry.log_decision(decision)

    def log_analysis_decision(
        self,
        ticker: str,
        decision_type: DecisionType,
        layer_source: str,
        confidence: Decimal,
        reasoning: str,
        signals: dict | None = None,
    ) -> int:
        """Log an agent analysis or pattern match decision."""
        decision = Decision(
            ticker=ticker,
            decision_type=decision_type,
            layer_source=layer_source,
            confidence=confidence,
            reasoning=reasoning,
            signals=signals,
        )
        return self._registry.log_decision(decision)

    def log_trade_decision(
        self,
        ticker: str,
        action: str,
        reasoning: str,
        confidence: Decimal | None = None,
        metadata: dict | None = None,
    ) -> int:
        """Log a trade decision (BUY, SELL, TRIM, HOLD)."""
        action_upper = action.upper()
        decision_type = self._ACTION_MAP.get(action_upper)
        if decision_type is None:
            raise ValueError(
                f"Unknown action '{action}'. Must be one of: {', '.join(self._ACTION_MAP)}"
            )

        layer_source = "MANUAL" if (metadata or {}).get("manual") else "AUTOMATED"

        decision = Decision(
            ticker=ticker,
            decision_type=decision_type,
            layer_source=layer_source,
            confidence=confidence,
            reasoning=reasoning,
            metadata=metadata,
        )
        return self._registry.log_decision(decision)

    def get_decision_count(self, ticker: str | None = None) -> int:
        """Get total decision count, optionally for a ticker."""
        decisions = self._registry.get_decisions(ticker=ticker, limit=100_000)
        return len(decisions)

    def get_recent_decisions(self, limit: int = 50) -> list[Decision]:
        """Get most recent decisions."""
        return self._registry.get_decisions(limit=limit)
