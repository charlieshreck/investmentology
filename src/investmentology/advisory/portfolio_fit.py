"""Portfolio-fit scoring and macro regime allocation guidance.

For each candidate, computes:
  - Sector diversification impact (does it add diversity or increase concentration?)
  - Risk category balance impact (growth/defensive/cyclical balance)
  - Position count impact (are we near max positions?)
  - Overlap check (do we already hold this stock?)

Cash regime rule: translates MacroRegimeResult into allocation guidance.

Output: fit_score (0.0-1.0) and fit_reasoning string.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

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


# ---------------------------------------------------------------------------
# Cash Regime Rule — Macro → Portfolio Allocation Guidance
# ---------------------------------------------------------------------------

class AllocationStance(StrEnum):
    AGGRESSIVE = "aggressive"  # Recovery: 80-90% equity
    STANDARD = "standard"  # Expansion: 70-85% equity
    CAUTIOUS = "cautious"  # Late-cycle: 60-70% equity
    DEFENSIVE = "defensive"  # Contraction: 40-50% equity


@dataclass
class CashRegimeGuidance:
    regime: str
    stance: AllocationStance
    equity_min_pct: int
    equity_max_pct: int
    cash_min_pct: int
    cash_max_pct: int
    entry_criteria: str  # How strict entry should be
    summary: str


# Regime → allocation mapping (from Phase 2 definitive plan)
_REGIME_RULES: dict[str, dict] = {
    "expansion": {
        "stance": AllocationStance.STANDARD,
        "equity_min": 70, "equity_max": 85,
        "cash_min": 15, "cash_max": 30,
        "entry": "Standard entry criteria. Full and core positions permitted.",
    },
    "late_cycle": {
        "stance": AllocationStance.CAUTIOUS,
        "equity_min": 60, "equity_max": 70,
        "cash_min": 30, "cash_max": 40,
        "entry": "Tightened entry: require ALL SIGNALS ALIGNED tier for new positions.",
    },
    "contraction": {
        "stance": AllocationStance.DEFENSIVE,
        "equity_min": 40, "equity_max": 50,
        "cash_min": 50, "cash_max": 60,
        "entry": "Only highest conviction with counter-cyclical thesis. Starter positions only.",
    },
    "recovery": {
        "stance": AllocationStance.AGGRESSIVE,
        "equity_min": 80, "equity_max": 90,
        "cash_min": 10, "cash_max": 20,
        "entry": "Broader entry criteria. Aggressive allocation to quality at distressed prices.",
    },
}

# Default for unknown regime
_DEFAULT_RULE = {
    "stance": AllocationStance.STANDARD,
    "equity_min": 70, "equity_max": 85,
    "cash_min": 15, "cash_max": 30,
    "entry": "Standard entry criteria (regime unknown).",
}


@dataclass
class PortfolioGapAnalysis:
    """Current portfolio allocation vs ideal targets, with gap identification."""

    total_value: float
    position_count: int
    risk_allocations: dict[str, dict]  # category → {current_pct, ideal_pct, gap_pct, status}
    sector_allocations: dict[str, float]  # sector → current_pct
    underweight_categories: list[str]  # Risk categories needing more exposure
    overweight_categories: list[str]   # Risk categories that are too concentrated
    concentration_warnings: list[str]  # Specific warnings (sector > 40%, single pos > 10%)


def compute_portfolio_gaps(registry: Registry) -> PortfolioGapAnalysis:
    """Compute current vs ideal portfolio allocation by risk category.

    Returns gap analysis showing where the portfolio is under/overweight
    relative to IDEAL_RISK_TARGETS.
    """
    positions = registry.get_open_positions()
    if not positions:
        return PortfolioGapAnalysis(
            total_value=0,
            position_count=0,
            risk_allocations={
                cat: {"current_pct": 0.0, "ideal_pct": ideal, "gap_pct": ideal, "status": "empty"}
                for cat, ideal in IDEAL_RISK_TARGETS.items()
            },
            sector_allocations={},
            underweight_categories=list(IDEAL_RISK_TARGETS.keys()),
            overweight_categories=[],
            concentration_warnings=["Portfolio is empty"],
        )

    # Fetch sectors for held tickers
    tickers = [p.ticker for p in positions]
    sector_map: dict[str, str] = {}
    try:
        rows = registry._db.execute(
            "SELECT ticker, sector FROM invest.stocks WHERE ticker = ANY(%s)",
            [tickers],
        )
        for r in rows:
            sector_map[r["ticker"]] = r.get("sector") or "Unknown"
    except Exception:
        pass

    total_value = sum(float(p.current_price * p.shares) for p in positions)
    if total_value <= 0:
        total_value = 1.0  # Avoid division by zero

    # Compute sector allocations
    sector_values: dict[str, float] = {}
    for p in positions:
        sector = sector_map.get(p.ticker, "Unknown")
        mv = float(p.current_price * p.shares)
        sector_values[sector] = sector_values.get(sector, 0) + mv

    sector_pcts = {s: round(v / total_value * 100, 1) for s, v in sector_values.items()}

    # Compute risk category allocations
    risk_values: dict[str, float] = {}
    for p in positions:
        sector = sector_map.get(p.ticker, "Unknown")
        cat = SECTOR_RISK_MAP.get(sector, "mixed")
        mv = float(p.current_price * p.shares)
        risk_values[cat] = risk_values.get(cat, 0) + mv

    risk_allocations: dict[str, dict] = {}
    underweight: list[str] = []
    overweight: list[str] = []

    for cat, ideal_pct in IDEAL_RISK_TARGETS.items():
        current_pct = round(risk_values.get(cat, 0) / total_value * 100, 1)
        gap_pct = round(ideal_pct - current_pct, 1)

        if gap_pct > 5:
            status = "underweight"
            underweight.append(cat)
        elif gap_pct < -10:
            status = "overweight"
            overweight.append(cat)
        elif gap_pct < -5:
            status = "slightly_overweight"
        elif gap_pct > 0:
            status = "slightly_underweight"
        else:
            status = "balanced"

        risk_allocations[cat] = {
            "current_pct": current_pct,
            "ideal_pct": ideal_pct,
            "gap_pct": gap_pct,
            "status": status,
        }

    # Concentration warnings
    warnings: list[str] = []
    for sector, pct in sector_pcts.items():
        if pct > MAX_SINGLE_SECTOR_PCT:
            warnings.append(f"{sector} at {pct}% exceeds {MAX_SINGLE_SECTOR_PCT}% limit")

    for p in positions:
        pos_pct = float(p.current_price * p.shares) / total_value * 100
        if pos_pct > MAX_SINGLE_POSITION_PCT:
            warnings.append(f"{p.ticker} at {pos_pct:.1f}% exceeds {MAX_SINGLE_POSITION_PCT}% position limit")

    return PortfolioGapAnalysis(
        total_value=round(total_value, 2),
        position_count=len(positions),
        risk_allocations=risk_allocations,
        sector_allocations=sector_pcts,
        underweight_categories=underweight,
        overweight_categories=overweight,
        concentration_warnings=warnings,
    )


def get_cash_regime_guidance(macro_regime: dict | None) -> CashRegimeGuidance:
    """Translate a MacroRegimeResult dict into portfolio allocation guidance.

    Args:
        macro_regime: Dict from MacroRegimeResult (with 'regime', 'confidence', 'summary')
                     or None if macro data is unavailable.

    Returns:
        CashRegimeGuidance with allocation ranges and entry criteria.
    """
    if macro_regime is None:
        regime_name = "unknown"
    else:
        regime_name = macro_regime.get("regime", "unknown")

    rule = _REGIME_RULES.get(regime_name, _DEFAULT_RULE)
    stance = rule["stance"]

    confidence = 0.0
    if macro_regime:
        confidence = macro_regime.get("confidence", 0.0)

    # Low confidence → soften toward standard stance
    if confidence < 0.35 and regime_name != "unknown":
        summary = (
            f"Macro regime: {regime_name} (low confidence {confidence:.0%}). "
            f"Defaulting to standard allocation. {rule['entry']}"
        )
        rule = _DEFAULT_RULE
        stance = AllocationStance.STANDARD
    else:
        regime_summary = macro_regime.get("summary", "") if macro_regime else ""
        summary = (
            f"Macro regime: {regime_name} ({confidence:.0%} confidence). "
            f"Target equity: {rule['equity_min']}-{rule['equity_max']}%. "
            f"{rule['entry']}"
            + (f" ({regime_summary})" if regime_summary else "")
        )

    return CashRegimeGuidance(
        regime=regime_name,
        stance=stance,
        equity_min_pct=rule["equity_min"],
        equity_max_pct=rule["equity_max"],
        cash_min_pct=rule["cash_min"],
        cash_max_pct=rule["cash_max"],
        entry_criteria=rule["entry"],
        summary=summary,
    )
