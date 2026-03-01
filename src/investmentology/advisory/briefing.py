"""Daily Advisory Briefing — comprehensive financial review after each analysis run.

Combines:
  - Market overview (pendulum, macro, sector rotation signals)
  - Portfolio snapshot (positions, P&L, sector exposure, health)
  - New recommendations (from recent analysis runs)
  - Position reviews (alerts, stop-loss proximity, fair value overshoot)
  - Risk summary (concentration, drawdown)
  - Actionable items (prioritized what-to-do list)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from investmentology.advisory.performance import PerformanceCalculator
from investmentology.registry.queries import Registry
from investmentology.timing.pendulum import PendulumReader

logger = logging.getLogger(__name__)


# ---- Data Structures ----

@dataclass
class MarketOverview:
    pendulum: dict  # score, label, sizing_multiplier, components
    macro_signals: list[str]  # human-readable macro observations
    date: str = ""


@dataclass
class PositionSnapshot:
    ticker: str
    name: str
    shares: float
    avg_cost: float
    current_price: float
    market_value: float
    pnl_pct: float
    sector: str
    weight_pct: float  # % of portfolio


@dataclass
class PortfolioSnapshot:
    positions: list[PositionSnapshot]
    total_value: float
    cash_pct: float  # estimated from unused allocation
    position_count: int
    sector_exposure: dict[str, float]  # sector -> % allocation
    risk_category_exposure: dict[str, float]  # growth/defensive/cyclical -> %
    day_pnl: float
    total_unrealized_pnl: float


@dataclass
class Recommendation:
    ticker: str
    name: str
    verdict: str
    confidence: float
    success_probability: float | None
    sector: str
    current_price: float
    reasoning: str | None


@dataclass
class PositionAlert:
    ticker: str
    severity: str  # critical, high, medium, low
    alert_type: str
    message: str


@dataclass
class RiskSummary:
    concentration_warnings: list[str]
    drawdown_alerts: list[str]
    sector_imbalances: list[str]
    overall_risk_level: str  # low, moderate, elevated, high


@dataclass
class ActionItem:
    priority: int  # 1 = highest
    category: str  # buy, sell, review, rebalance, watch
    ticker: str | None
    action: str
    reasoning: str


@dataclass
class DailyBriefing:
    date: str
    market_overview: MarketOverview
    portfolio_snapshot: PortfolioSnapshot
    new_recommendations: list[Recommendation]
    position_alerts: list[PositionAlert]
    risk_summary: RiskSummary
    action_items: list[ActionItem]
    learning_summary: dict  # calibration stats, prediction counts
    performance: dict | None = None  # benchmark comparison, Sharpe, disposition


# ---- Sector -> Risk Category Mapping ----

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

RISK_BANDS = {
    "growth": (15, 45, 55),
    "cyclical": (10, 35, 45),
    "defensive": (10, 30, 40),
    "mixed": (0, 25, 35),
    "income": (0, 20, 30),
}


# ---- Builder ----

class BriefingBuilder:
    """Builds a DailyBriefing from registry data and market signals."""

    def __init__(self, registry: Registry):
        self._registry = registry

    def build(self) -> DailyBriefing:
        """Generate the full daily briefing."""
        today = date.today().isoformat()

        market = self._build_market_overview()
        portfolio = self._build_portfolio_snapshot()
        recommendations = self._build_recommendations()
        alerts = self._build_position_alerts()
        risk = self._build_risk_summary(portfolio, alerts)
        actions = self._build_action_items(
            portfolio, recommendations, alerts, risk, market,
        )
        learning = self._build_learning_summary()

        # Performance metrics (benchmark, disposition)
        perf_data = None
        try:
            calc = PerformanceCalculator(self._registry)
            perf = calc.compute()
            perf_data = {
                "portfolioReturnPct": perf.portfolio_return_pct,
                "spyReturnPct": perf.spy_return_pct,
                "alphaPct": perf.alpha_pct,
                "sharpeRatio": perf.sharpe_ratio,
                "maxDrawdownPct": perf.max_drawdown_pct,
                "dispositionRatio": perf.disposition_ratio,
                "measurementDays": perf.measurement_days,
            }
            # Add disposition warning to action items if ratio is bad
            if perf.disposition_ratio and perf.disposition_ratio > 1.5:
                actions.append(ActionItem(
                    priority=len(actions) + 1,
                    category="review",
                    ticker=None,
                    action="Disposition effect detected — losers held longer than winners",
                    reasoning=f"Avg winner hold: {perf.avg_winner_hold_days:.0f} days, "
                    f"avg loser hold: {perf.avg_loser_hold_days:.0f} days "
                    f"(ratio: {perf.disposition_ratio:.1f}x). "
                    f"Review losing positions for thesis breaks.",
                ))
        except Exception:
            logger.debug("Performance metrics failed in briefing", exc_info=True)

        # Buzz + earnings insights for action items
        try:
            import os
            from investmentology.data.buzz_scorer import BuzzScorer

            held_tickers = [p.ticker for p in portfolio.positions]
            scorer = BuzzScorer()
            buzz_results = scorer.score_watchlist(held_tickers)

            for ticker, buzz in buzz_results.items():
                if buzz.get("contrarian_flag"):
                    actions.append(ActionItem(
                        priority=len(actions) + 1,
                        category="watch",
                        ticker=ticker,
                        action=f"Contrarian signal: {ticker} has low buzz but positive verdict",
                        reasoning=f"Buzz score {buzz['buzz_score']:.0f}/100 ({buzz['buzz_label']}) "
                        f"with sentiment {buzz['headline_sentiment']:+.2f} — "
                        f"low attention + high fundamentals may indicate mispricing",
                    ))
                if buzz.get("buzz_score", 0) >= 75:
                    actions.append(ActionItem(
                        priority=len(actions) + 1,
                        category="review",
                        ticker=ticker,
                        action=f"High buzz alert: {ticker} has elevated news coverage",
                        reasoning=f"Buzz score {buzz['buzz_score']:.0f}/100 with "
                        f"{buzz.get('news_count_7d', 0)} articles this week. "
                        f"Sentiment: {buzz['headline_sentiment']:+.2f}. "
                        f"High attention may precede volatility.",
                    ))
        except Exception:
            logger.debug("Buzz scoring failed in briefing", exc_info=True)

        try:
            import os
            from investmentology.data.earnings_tracker import EarningsTracker
            from investmentology.data.finnhub_provider import FinnhubProvider

            fh_key = os.environ.get("FINNHUB_API_KEY", "")
            if fh_key:
                fh = FinnhubProvider(fh_key)
                tracker = EarningsTracker(fh, self._registry)
                held_tickers = [p.ticker for p in portfolio.positions]
                for ticker in held_tickers:
                    try:
                        tracker.capture_snapshot(ticker)
                        momentum = tracker.compute_momentum(ticker)
                        if momentum["momentum_label"] == "STRONG_UPWARD":
                            actions.append(ActionItem(
                                priority=len(actions) + 1,
                                category="watch",
                                ticker=ticker,
                                action=f"Strong earnings momentum: {ticker} EPS estimates rising",
                                reasoning=f"{momentum['upward_revisions']} upward revisions in 90d, "
                                f"beat streak: {momentum['beat_streak']}. "
                                f"Positive revision momentum is a leading indicator.",
                            ))
                        elif momentum["momentum_label"] == "DECLINING":
                            actions.append(ActionItem(
                                priority=len(actions) + 1,
                                category="review",
                                ticker=ticker,
                                action=f"Earnings concern: {ticker} EPS estimates declining",
                                reasoning=f"{momentum['downward_revisions']} downward revisions in 90d. "
                                f"Declining estimates may signal fundamental deterioration.",
                            ))
                    except Exception:
                        pass
        except Exception:
            logger.debug("Earnings tracking failed in briefing", exc_info=True)

        return DailyBriefing(
            date=today,
            market_overview=market,
            portfolio_snapshot=portfolio,
            new_recommendations=recommendations,
            position_alerts=alerts,
            risk_summary=risk,
            action_items=actions,
            learning_summary=learning,
            performance=perf_data,
        )

    # ---- Market Overview ----

    def _build_market_overview(self) -> MarketOverview:
        try:
            reader = PendulumReader()
            reading = reader.read()
            pendulum_data = {
                "score": reading.score,
                "label": reading.label,
                "sizing_multiplier": float(reading.sizing_multiplier),
                "components": reading.components,
            }
        except Exception:
            pendulum_data = {"score": 50, "label": "neutral", "sizing_multiplier": 1.0, "components": {}}

        macro_signals = []
        score = pendulum_data["score"]
        _ = pendulum_data["label"]

        if score >= 80:
            macro_signals.append("Extreme greed — markets may be overheated, exercise caution with new positions")
        elif score >= 65:
            macro_signals.append("Greed regime — trim sizing, favour defensive names")
        elif score <= 20:
            macro_signals.append("Extreme fear — potential buying opportunity for quality names")
        elif score <= 35:
            macro_signals.append("Fear regime — increased sizing justified, look for dislocations")
        else:
            macro_signals.append("Neutral market sentiment — standard sizing applies")

        components = pendulum_data.get("components", {})
        vix = components.get("vix")
        if vix is not None:
            if vix >= 80:
                macro_signals.append(f"VIX elevated (score {vix}) — high volatility environment")
            elif vix <= 20:
                macro_signals.append(f"VIX complacent (score {vix}) — low vol may precede correction")

        return MarketOverview(
            pendulum=pendulum_data,
            macro_signals=macro_signals,
            date=date.today().isoformat(),
        )

    # ---- Portfolio Snapshot ----

    @staticmethod
    def _has_valid_price(p) -> bool:
        """Return True if position has a finite, usable current_price."""
        if p.current_price is None:
            return False
        try:
            return math.isfinite(float(p.current_price))
        except (InvalidOperation, ValueError, OverflowError):
            return False

    def _build_portfolio_snapshot(self) -> PortfolioSnapshot:
        raw_positions = [
            p for p in self._registry.get_open_positions()
            if self._has_valid_price(p)
        ]

        # Aggregate by ticker
        aggregated: dict[str, dict] = {}
        for p in raw_positions:
            if p.ticker in aggregated:
                agg = aggregated[p.ticker]
                old_cost = agg["entry_price"] * agg["shares"]
                new_cost = p.entry_price * p.shares
                total_shares = agg["shares"] + p.shares
                agg["entry_price"] = (old_cost + new_cost) / total_shares if total_shares else Decimal("0")
                agg["shares"] = total_shares
                agg["current_price"] = p.current_price
            else:
                aggregated[p.ticker] = {
                    "ticker": p.ticker,
                    "shares": p.shares,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "pnl_pct": p.pnl_pct,
                }

        # Get sector info
        tickers = list(aggregated.keys())
        sectors: dict[str, str] = {}
        names: dict[str, str] = {}
        if tickers:
            try:
                rows = self._registry._db.execute(
                    "SELECT ticker, sector, name FROM invest.stocks WHERE ticker = ANY(%s)",
                    [tickers],
                )
                for r in rows:
                    sectors[r["ticker"]] = r.get("sector") or "Unknown"
                    names[r["ticker"]] = r.get("name") or r["ticker"]
            except Exception:
                pass

        total_value = Decimal("0")
        total_unrealized = 0.0
        positions = []

        for a in aggregated.values():
            mv = a["current_price"] * a["shares"]
            total_value += mv
            entry_cost = a["entry_price"] * a["shares"]
            unrealized = float(mv - entry_cost)
            total_unrealized += unrealized

        # Second pass with weights
        for a in aggregated.values():
            mv = a["current_price"] * a["shares"]
            entry_cost = a["entry_price"] * a["shares"]
            pnl = float((mv - entry_cost) / entry_cost * 100) if entry_cost else 0.0
            weight = float(mv / total_value * 100) if total_value else 0.0

            positions.append(PositionSnapshot(
                ticker=a["ticker"],
                name=names.get(a["ticker"], a["ticker"]),
                shares=float(a["shares"]),
                avg_cost=float(a["entry_price"]),
                current_price=float(a["current_price"]),
                market_value=float(mv),
                pnl_pct=pnl,
                sector=sectors.get(a["ticker"], "Unknown"),
                weight_pct=round(weight, 1),
            ))

        # Sector exposure
        sector_exposure: dict[str, float] = {}
        for pos in positions:
            sector_exposure[pos.sector] = sector_exposure.get(pos.sector, 0) + pos.weight_pct

        # Risk category exposure
        risk_exposure: dict[str, float] = {}
        for sector, pct in sector_exposure.items():
            cat = SECTOR_RISK_MAP.get(sector, "mixed")
            risk_exposure[cat] = risk_exposure.get(cat, 0) + pct

        return PortfolioSnapshot(
            positions=sorted(positions, key=lambda p: -p.market_value),
            total_value=float(total_value),
            cash_pct=0.0,  # paper portfolio — no actual cash tracking
            position_count=len(positions),
            sector_exposure=sector_exposure,
            risk_category_exposure=risk_exposure,
            day_pnl=0.0,  # would require previous close data
            total_unrealized_pnl=total_unrealized,
        )

    # ---- New Recommendations ----

    def _build_recommendations(self) -> list[Recommendation]:
        positive_verdicts = {"STRONG_BUY", "BUY", "ACCUMULATE"}

        try:
            rows = self._registry.get_all_actionable_verdicts()
        except Exception:
            return []

        # Filter to recent (last 7 days) positive verdicts
        cutoff = date.today() - timedelta(days=7)
        recs = []

        for r in rows:
            if r.get("verdict") not in positive_verdicts:
                continue

            created = r.get("created_at")
            if created and hasattr(created, "date"):
                if created.date() < cutoff:
                    continue

            confidence = float(r.get("confidence") or 0)

            # Compute success probability
            components: list[tuple[float, float]] = []
            if r.get("confidence"):
                components.append((float(r["confidence"]), 0.35))
            cons = r.get("consensus_score")
            if cons is not None:
                components.append(((float(cons) + 1) / 2, 0.25))
            stances = r.get("agent_stances")
            if stances and isinstance(stances, list) and len(stances) > 0:
                pos_count = sum(1 for s in stances if isinstance(s, dict) and s.get("sentiment", 0) > 0)
                components.append((pos_count / len(stances), 0.20))
            risk_flags = r.get("risk_flags")
            risk_score = max(0.0, 1.0 - len(risk_flags) * 0.15) if risk_flags and isinstance(risk_flags, list) else 1.0
            components.append((risk_score, 0.20))
            total_w = sum(w for _, w in components)
            sp = round(sum(v * w for v, w in components) / total_w, 4) if components else None

            recs.append(Recommendation(
                ticker=r["ticker"],
                name=r.get("name") or r["ticker"],
                verdict=r["verdict"],
                confidence=confidence,
                success_probability=sp,
                sector=r.get("sector") or "",
                current_price=float(r.get("current_price") or 0),
                reasoning=r.get("reasoning"),
            ))

        # Sort by success probability descending
        recs.sort(key=lambda r: r.success_probability or 0, reverse=True)
        return recs

    # ---- Position Alerts ----

    def _build_position_alerts(self) -> list[PositionAlert]:
        positions = self._registry.get_open_positions()
        alerts = []

        def _safe_float(v: Decimal | None) -> float | None:
            if v is None:
                return None
            try:
                f = float(v)
                return f if math.isfinite(f) else None
            except (InvalidOperation, ValueError, OverflowError):
                return None

        for p in positions:
            cur = _safe_float(p.current_price)
            sl = _safe_float(p.stop_loss)

            # Stop-loss breach
            if cur is not None and sl is not None and cur <= sl:
                alerts.append(PositionAlert(
                    ticker=p.ticker,
                    severity="critical",
                    alert_type="stop_loss_breach",
                    message=f"{p.ticker} at {cur:.2f} breached stop-loss {sl:.2f}",
                ))

            # Significant drawdown
            pnl = _safe_float(p.pnl_pct)
            if pnl is not None and pnl < -0.15:
                alerts.append(PositionAlert(
                    ticker=p.ticker,
                    severity="high",
                    alert_type="drawdown",
                    message=f"{p.ticker} down {pnl:.1%} from entry — consider thesis review",
                ))
            elif pnl is not None and pnl < -0.10:
                alerts.append(PositionAlert(
                    ticker=p.ticker,
                    severity="medium",
                    alert_type="drawdown",
                    message=f"{p.ticker} down {pnl:.1%} from entry",
                ))

            # Fair value overshoot (>10% above estimate)
            fv = _safe_float(p.fair_value_estimate)
            if cur is not None and fv is not None and cur > fv * 1.1:
                overshoot = (cur - fv) / fv * 100
                alerts.append(PositionAlert(
                    ticker=p.ticker,
                    severity="medium",
                    alert_type="above_fair_value",
                    message=f"{p.ticker} trading {overshoot:.0f}% above fair value estimate — consider taking profit",
                ))

            # Large winner (>30% gain) — profit-taking consideration
            if pnl is not None and pnl > 0.30:
                alerts.append(PositionAlert(
                    ticker=p.ticker,
                    severity="low",
                    alert_type="large_gain",
                    message=f"{p.ticker} up {pnl:.1%} — consider partial profit-taking or trailing stop",
                ))

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda a: severity_order.get(a.severity, 99))
        return alerts

    # ---- Risk Summary ----

    def _build_risk_summary(
        self,
        portfolio: PortfolioSnapshot,
        alerts: list[PositionAlert],
    ) -> RiskSummary:
        concentration_warnings = []
        drawdown_alerts_list = []
        sector_imbalances = []

        # Concentration: any single position >15% of portfolio
        for pos in portfolio.positions:
            if pos.weight_pct > 15:
                concentration_warnings.append(
                    f"{pos.ticker} is {pos.weight_pct:.1f}% of portfolio (target max: 15%)"
                )

        # Sector concentration: any sector >40%
        for sector, pct in portfolio.sector_exposure.items():
            if pct > 40:
                concentration_warnings.append(
                    f"{sector} sector at {pct:.1f}% — consider diversification"
                )

        # Risk category imbalances
        for cat, (min_band, max_band, warn_band) in RISK_BANDS.items():
            actual = portfolio.risk_category_exposure.get(cat, 0)
            if actual > warn_band:
                sector_imbalances.append(
                    f"{cat.title()} exposure at {actual:.1f}% exceeds warning threshold ({warn_band}%)"
                )
            elif actual < min_band and portfolio.position_count >= 5:
                sector_imbalances.append(
                    f"{cat.title()} exposure at {actual:.1f}% — below minimum band ({min_band}%)"
                )

        # Drawdown alerts from position alerts
        for a in alerts:
            if a.alert_type in ("stop_loss_breach", "drawdown"):
                drawdown_alerts_list.append(a.message)

        # Determine overall risk level
        critical_count = sum(1 for a in alerts if a.severity == "critical")
        high_count = sum(1 for a in alerts if a.severity == "high")

        if critical_count > 0:
            overall = "high"
        elif high_count >= 2 or len(concentration_warnings) >= 2:
            overall = "elevated"
        elif high_count > 0 or concentration_warnings or sector_imbalances:
            overall = "moderate"
        else:
            overall = "low"

        return RiskSummary(
            concentration_warnings=concentration_warnings,
            drawdown_alerts=drawdown_alerts_list,
            sector_imbalances=sector_imbalances,
            overall_risk_level=overall,
        )

    # ---- Action Items ----

    def _build_action_items(
        self,
        portfolio: PortfolioSnapshot,
        recommendations: list[Recommendation],
        alerts: list[PositionAlert],
        risk: RiskSummary,
        market: MarketOverview,
    ) -> list[ActionItem]:
        items: list[ActionItem] = []
        priority = 1

        # Critical alerts first
        for a in alerts:
            if a.severity == "critical":
                items.append(ActionItem(
                    priority=priority,
                    category="sell",
                    ticker=a.ticker,
                    action=f"URGENT: {a.message}",
                    reasoning="Stop-loss breached — execute exit plan",
                ))
                priority += 1

        # High severity alerts
        for a in alerts:
            if a.severity == "high":
                items.append(ActionItem(
                    priority=priority,
                    category="review",
                    ticker=a.ticker,
                    action=f"Review thesis for {a.ticker}",
                    reasoning=a.message,
                ))
                priority += 1

        # Fair value overshoot — profit-taking
        for a in alerts:
            if a.alert_type == "above_fair_value":
                items.append(ActionItem(
                    priority=priority,
                    category="sell",
                    ticker=a.ticker,
                    action=f"Consider taking partial profit on {a.ticker}",
                    reasoning=a.message,
                ))
                priority += 1

        # New buy recommendations (top 5)
        # Only recommend if portfolio isn't too concentrated
        for rec in recommendations[:5]:
            # Check if already held
            held_tickers = {p.ticker for p in portfolio.positions}
            if rec.ticker in held_tickers:
                items.append(ActionItem(
                    priority=priority,
                    category="review",
                    ticker=rec.ticker,
                    action=f"Already hold {rec.ticker} — {rec.verdict} reconfirmed",
                    reasoning=f"Confidence {rec.confidence:.0%}, success probability {rec.success_probability:.0%}" if rec.success_probability else f"Confidence {rec.confidence:.0%}",
                ))
            else:
                sizing_note = ""
                mult = market.pendulum.get("sizing_multiplier", 1.0)
                if mult < 1.0:
                    sizing_note = f" (sizing reduced to {mult:.0%} due to {market.pendulum.get('label', 'greed')} regime)"

                items.append(ActionItem(
                    priority=priority,
                    category="buy",
                    ticker=rec.ticker,
                    action=f"Consider buying {rec.ticker} ({rec.verdict})",
                    reasoning=f"{rec.name} — {rec.sector}. Confidence {rec.confidence:.0%}" + (f", success probability {rec.success_probability:.0%}" if rec.success_probability else "") + sizing_note,
                ))
            priority += 1

        # Rebalancing suggestions
        for warning in risk.concentration_warnings:
            items.append(ActionItem(
                priority=priority,
                category="rebalance",
                ticker=None,
                action="Rebalance portfolio concentration",
                reasoning=warning,
            ))
            priority += 1

        # Large winners — trailing stop reminder
        for a in alerts:
            if a.alert_type == "large_gain":
                items.append(ActionItem(
                    priority=priority,
                    category="review",
                    ticker=a.ticker,
                    action=f"Set trailing stop for {a.ticker}",
                    reasoning=a.message,
                ))
                priority += 1

        return items

    # ---- Learning Summary ----

    def _build_learning_summary(self) -> dict:
        from investmentology.learning.predictions import PredictionManager

        pm = PredictionManager(self._registry)
        cal_data = pm.get_calibration_data(window_days=90)

        # Get prediction count
        try:
            rows = self._registry._db.execute(
                "SELECT COUNT(*) as cnt FROM invest.predictions WHERE is_settled = FALSE"
            )
            pending_predictions = rows[0]["cnt"] if rows else 0
        except Exception:
            pending_predictions = 0

        try:
            rows = self._registry._db.execute(
                "SELECT COUNT(*) as cnt FROM invest.predictions WHERE is_settled = TRUE"
            )
            settled_predictions = rows[0]["cnt"] if rows else 0
        except Exception:
            settled_predictions = 0

        return {
            "pending_predictions": pending_predictions,
            "settled_predictions": settled_predictions,
            "calibration": {
                "total_settled": cal_data.get("total_settled", 0),
                "ece": cal_data.get("ece", 0),
                "brier": cal_data.get("brier", 0),
            },
        }


# ---- Serialization ----

def briefing_to_dict(b: DailyBriefing) -> dict:
    """Convert DailyBriefing to JSON-serializable dict."""
    return {
        "date": b.date,
        "marketOverview": {
            "pendulum": b.market_overview.pendulum,
            "macroSignals": b.market_overview.macro_signals,
        },
        "portfolioSnapshot": {
            "positions": [
                {
                    "ticker": p.ticker,
                    "name": p.name,
                    "shares": p.shares,
                    "avgCost": p.avg_cost,
                    "currentPrice": p.current_price,
                    "marketValue": round(p.market_value, 2),
                    "pnlPct": round(p.pnl_pct, 2),
                    "sector": p.sector,
                    "weightPct": p.weight_pct,
                }
                for p in b.portfolio_snapshot.positions
            ],
            "totalValue": round(b.portfolio_snapshot.total_value, 2),
            "positionCount": b.portfolio_snapshot.position_count,
            "sectorExposure": {k: round(v, 1) for k, v in b.portfolio_snapshot.sector_exposure.items()},
            "riskCategoryExposure": {k: round(v, 1) for k, v in b.portfolio_snapshot.risk_category_exposure.items()},
            "totalUnrealizedPnl": round(b.portfolio_snapshot.total_unrealized_pnl, 2),
        },
        "newRecommendations": [
            {
                "ticker": r.ticker,
                "name": r.name,
                "verdict": r.verdict,
                "confidence": r.confidence,
                "successProbability": r.success_probability,
                "sector": r.sector,
                "currentPrice": r.current_price,
                "reasoning": r.reasoning,
            }
            for r in b.new_recommendations
        ],
        "positionAlerts": [
            {
                "ticker": a.ticker,
                "severity": a.severity,
                "type": a.alert_type,
                "message": a.message,
            }
            for a in b.position_alerts
        ],
        "riskSummary": {
            "overallRiskLevel": b.risk_summary.overall_risk_level,
            "concentrationWarnings": b.risk_summary.concentration_warnings,
            "drawdownAlerts": b.risk_summary.drawdown_alerts,
            "sectorImbalances": b.risk_summary.sector_imbalances,
        },
        "actionItems": [
            {
                "priority": a.priority,
                "category": a.category,
                "ticker": a.ticker,
                "action": a.action,
                "reasoning": a.reasoning,
            }
            for a in b.action_items
        ],
        "learningSummary": b.learning_summary,
        "performance": b.performance,
    }
