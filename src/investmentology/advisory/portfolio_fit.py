"""Portfolio-fit scoring — evaluate how well a candidate stock fits the current portfolio.

For each candidate, computes:
  - Sector diversification impact (does it add diversity or increase concentration?)
  - Risk category balance impact (growth/defensive/cyclical balance)
  - Position count impact (are we near max positions?)
  - Overlap check (do we already hold this stock?)

Output: fit_score (0.0-1.0) and fit_reasoning string.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)


# Same mapping as briefing.py
SECTOR_RISK_MAP = {
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

IDEAL_RISK_TARGETS = {
    "growth": 35,
    "cyclical": 25,
    "defensive": 20,
    "mixed": 15,
    "income": 5,
}

MAX_POSITIONS = 25
MAX_SINGLE_SECTOR_PCT = 40.0
MAX_SINGLE_POSITION_PCT = 10.0


@dataclass
class PortfolioFitResult:
    score: float  # 0.0 to 1.0
    reasoning: str
    diversification_score: float
    balance_score: float
    capacity_score: float
    already_held: bool


class PortfolioFitScorer:
    """Score how well a candidate fits into the current portfolio."""

    def __init__(self, registry: Registry):
        self._registry = registry
        self._positions = None
        self._sectors: dict[str, str] = {}

    def _load_portfolio(self) -> None:
        if self._positions is not None:
            return

        self._positions = self._registry.get_open_positions()
        tickers = [p.ticker for p in self._positions]

        if tickers:
            try:
                rows = self._registry._db.execute(
                    "SELECT ticker, sector FROM invest.stocks WHERE ticker = ANY(%s)",
                    [tickers],
                )
                for r in rows:
                    self._sectors[r["ticker"]] = r.get("sector") or "Unknown"
            except Exception:
                pass

    def score(self, ticker: str, sector: str | None = None) -> PortfolioFitResult:
        """Score portfolio fit for a candidate stock.

        Args:
            ticker: Stock ticker symbol
            sector: Sector of the candidate (will look up if not provided)

        Returns:
            PortfolioFitResult with score and reasoning
        """
        self._load_portfolio()

        if sector is None:
            try:
                rows = self._registry._db.execute(
                    "SELECT sector FROM invest.stocks WHERE ticker = %s", (ticker,)
                )
                sector = rows[0]["sector"] if rows else "Unknown"
            except Exception:
                sector = "Unknown"

        held_tickers = {p.ticker for p in self._positions}
        already_held = ticker in held_tickers

        # 1. Diversification score (does this add diversity or increase concentration?)
        diversification_score = self._score_diversification(sector)

        # 2. Risk category balance score
        balance_score = self._score_balance(sector)

        # 3. Capacity score (room for more positions?)
        capacity_score = self._score_capacity()

        # Weighted composite
        if already_held:
            # If already held, fit score is lower (we're adding to concentration)
            score = diversification_score * 0.3 + balance_score * 0.3 + capacity_score * 0.1 + 0.3 * 0.5
        else:
            score = diversification_score * 0.4 + balance_score * 0.35 + capacity_score * 0.25

        # Build reasoning
        reasons = []
        if already_held:
            reasons.append(f"Already hold {ticker} — adding increases concentration")

        if diversification_score >= 0.8:
            reasons.append(f"{sector} adds diversification to portfolio")
        elif diversification_score <= 0.3:
            reasons.append(f"Portfolio already heavy in {sector}")

        if balance_score >= 0.8:
            risk_cat = SECTOR_RISK_MAP.get(sector, "mixed")
            reasons.append(f"Improves {risk_cat} exposure balance")
        elif balance_score <= 0.3:
            risk_cat = SECTOR_RISK_MAP.get(sector, "mixed")
            reasons.append(f"Would increase {risk_cat} overexposure")

        if capacity_score <= 0.3:
            reasons.append(f"Near maximum positions ({len(self._positions)}/{MAX_POSITIONS})")

        reasoning = ". ".join(reasons) if reasons else "Neutral portfolio fit"

        return PortfolioFitResult(
            score=round(max(0.0, min(1.0, score)), 3),
            reasoning=reasoning,
            diversification_score=round(diversification_score, 3),
            balance_score=round(balance_score, 3),
            capacity_score=round(capacity_score, 3),
            already_held=already_held,
        )

    def _score_diversification(self, candidate_sector: str) -> float:
        """How much diversification does adding this sector provide?

        High score = sector is underrepresented. Low score = sector is overweighted.
        """
        if not self._positions:
            return 1.0  # Empty portfolio — anything adds diversity

        total_value = sum(float(p.current_price * p.shares) for p in self._positions)
        if total_value <= 0:
            return 1.0

        # Current sector allocation
        sector_values: dict[str, float] = {}
        for p in self._positions:
            s = self._sectors.get(p.ticker, "Unknown")
            mv = float(p.current_price * p.shares)
            sector_values[s] = sector_values.get(s, 0) + mv

        candidate_pct = sector_values.get(candidate_sector, 0) / total_value * 100

        if candidate_pct == 0:
            return 1.0  # New sector — maximum diversification
        elif candidate_pct < 15:
            return 0.8
        elif candidate_pct < 25:
            return 0.5
        elif candidate_pct < MAX_SINGLE_SECTOR_PCT:
            return 0.3
        else:
            return 0.1  # Already above concentration limit

    def _score_balance(self, candidate_sector: str) -> float:
        """How does adding this sector's risk category affect balance?

        High score = moves toward ideal balance. Low score = increases imbalance.
        """
        if not self._positions:
            return 0.8

        total_value = sum(float(p.current_price * p.shares) for p in self._positions)
        if total_value <= 0:
            return 0.8

        # Current risk category allocations
        risk_values: dict[str, float] = {}
        for p in self._positions:
            s = self._sectors.get(p.ticker, "Unknown")
            cat = SECTOR_RISK_MAP.get(s, "mixed")
            mv = float(p.current_price * p.shares)
            risk_values[cat] = risk_values.get(cat, 0) + mv

        risk_pcts = {cat: v / total_value * 100 for cat, v in risk_values.items()}

        candidate_cat = SECTOR_RISK_MAP.get(candidate_sector, "mixed")
        current_pct = risk_pcts.get(candidate_cat, 0)
        ideal_pct = IDEAL_RISK_TARGETS.get(candidate_cat, 15)

        # If current is below ideal, adding helps balance (high score)
        if current_pct < ideal_pct:
            return min(1.0, 0.5 + (ideal_pct - current_pct) / ideal_pct * 0.5)
        else:
            # Over ideal — score decreases proportionally
            overshoot = current_pct - ideal_pct
            return max(0.1, 0.5 - overshoot / 30)

    def _score_capacity(self) -> float:
        """Is there room for another position?"""
        n = len(self._positions)
        if n == 0:
            return 1.0
        if n >= MAX_POSITIONS:
            return 0.0

        remaining_ratio = (MAX_POSITIONS - n) / MAX_POSITIONS
        return min(1.0, remaining_ratio + 0.3)  # Generous until near max
