from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from investmentology.models.signal import AgentSignalSet, SignalTag
from investmentology.models.stock import FundamentalsSnapshot


@dataclass
class AnalysisRequest:
    """Input to an agent for analysis."""

    ticker: str
    fundamentals: FundamentalsSnapshot
    sector: str
    industry: str
    quant_gate_rank: int | None = None
    piotroski_score: int | None = None
    altman_z_score: Decimal | None = None
    # Additional context (agents may use some or all)
    price_history: dict | None = None  # For Simons
    macro_context: dict | None = None  # For Soros
    portfolio_context: dict | None = None  # For Auditor
    technical_indicators: dict | None = None  # Pre-computed for Simons
    # Enriched data from external sources
    news_context: list[dict] | None = None  # Recent headlines + sentiment
    earnings_context: dict | None = None  # Upcoming earnings, surprises
    insider_context: list[dict] | None = None  # Recent insider transactions
    social_sentiment: dict | None = None  # Reddit/Twitter sentiment
    # SEC filing text (10-K risk factors, MD&A)
    filing_context: dict | None = None
    # Institutional holders (13F data)
    institutional_context: list[dict] | None = None
    # Previous analysis context for history-aware re-analysis
    previous_verdict: dict | None = None
    previous_signals: list[dict] | None = None
    # Thesis lifecycle context (Phase 0+1)
    market_snapshot: dict | None = None  # SPY, VIX, yields at analysis time
    position_thesis: str | None = None  # Original buy thesis (immutable)
    position_type: str | None = None  # permanent, core, tactical
    days_held: int | None = None  # Days since entry
    thesis_health: str | None = None  # INTACT, UNDER_REVIEW, CHALLENGED, BROKEN
    thesis_type: str | None = None  # growth, income, value, momentum
    entry_price: float | None = None  # Original entry price
    pnl_pct: float | None = None  # Current unrealized P&L %


@dataclass
class AnalysisResponse:
    """Output from an agent."""

    agent_name: str
    model: str
    ticker: str
    signal_set: AgentSignalSet
    summary: str
    target_price: Decimal | None = None
    token_usage: dict | None = None
    latency_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class BaseAgent(abc.ABC):
    """Abstract base class for investment analysis agents."""

    def __init__(self, name: str, model: str) -> None:
        self.name = name
        self.model = model

    @abc.abstractmethod
    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """Analyze a stock and return signals with reasoning."""
        ...

    @abc.abstractmethod
    def build_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        ...

    @abc.abstractmethod
    def build_user_prompt(self, request: AnalysisRequest) -> str:
        """Build the user prompt from the analysis request."""
        ...

    @abc.abstractmethod
    def parse_response(self, raw: str, request: AnalysisRequest) -> AgentSignalSet:
        """Parse LLM response text into structured signals."""
        ...
