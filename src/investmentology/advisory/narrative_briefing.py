"""Monday Morning Briefing — narrative-first format.

Transforms the data-heavy DailyBriefing into a prioritized narrative:
  1. Immediate attention: thesis health challenges, critical alerts
  2. This week's events: earnings proximity, macro data
  3. Watchlist gap: BUY-rated stocks not yet in portfolio
  4. Monitoring: F-Score changes, quant rank movements, sell discipline
  5. Portfolio posture: cash level, sector concentration, performance vs SPY

The narrative is designed to be read top-to-bottom in < 5 minutes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class NarrativeSection:
    heading: str
    items: list[str]
    severity: str = "info"  # info, warn, critical


@dataclass
class MondayBriefing:
    date: str
    sections: list[NarrativeSection]

    def to_text(self) -> str:
        """Render as plain-text narrative."""
        lines = [f"# Monday Morning Briefing — {self.date}", ""]
        for section in self.sections:
            if not section.items:
                continue
            prefix = ""
            if section.severity == "critical":
                prefix = "[!] "
            elif section.severity == "warn":
                prefix = "[*] "
            lines.append(f"## {prefix}{section.heading}")
            lines.append("")
            for item in section.items:
                lines.append(f"- {item}")
            lines.append("")
        if not any(s.items for s in self.sections):
            lines.append("All clear — no immediate actions required.")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict."""
        return {
            "date": self.date,
            "sections": [
                {
                    "heading": s.heading,
                    "severity": s.severity,
                    "items": s.items,
                }
                for s in self.sections
            ],
        }


@dataclass
class BriefingInputs:
    """All data needed to build a Monday briefing.

    Decoupled from DailyBriefing so the narrative can be built from
    any data source (API, pipeline, tests).
    """

    as_of: date | None = None

    # Section 1: Immediate attention
    critical_alerts: list[str] = field(default_factory=list)
    thesis_challenges: list[str] = field(default_factory=list)

    # Section 2: This week's events
    earnings_alerts: list[str] = field(default_factory=list)
    macro_signals: list[str] = field(default_factory=list)

    # Section 3: Watchlist gap
    buy_rated_not_held: list[str] = field(default_factory=list)

    # Section 4: Monitoring
    sell_discipline_alerts: list[str] = field(default_factory=list)
    monitoring_notes: list[str] = field(default_factory=list)

    # Section 5: Portfolio posture
    position_count: int = 0
    total_value: float = 0.0
    cash_pct: float = 0.0
    sector_warnings: list[str] = field(default_factory=list)
    allocation_guidance: str = ""
    performance_vs_spy: str = ""
    overall_risk_level: str = "low"


def build_monday_briefing(inputs: BriefingInputs) -> MondayBriefing:
    """Build the narrative Monday Morning Briefing from structured inputs."""
    today = (inputs.as_of or date.today()).isoformat()

    sections: list[NarrativeSection] = []

    # --- Section 1: Immediate Attention ---
    immediate = inputs.critical_alerts + inputs.thesis_challenges
    if immediate:
        sections.append(NarrativeSection(
            heading="Immediate Attention",
            items=immediate,
            severity="critical",
        ))

    # --- Section 2: This Week's Events ---
    events = inputs.earnings_alerts + inputs.macro_signals
    if events:
        severity = "warn" if inputs.earnings_alerts else "info"
        sections.append(NarrativeSection(
            heading="This Week's Events",
            items=events,
            severity=severity,
        ))

    # --- Section 3: Watchlist Gap ---
    if inputs.buy_rated_not_held:
        sections.append(NarrativeSection(
            heading="Watchlist Gap — BUY-Rated, Not Yet Held",
            items=inputs.buy_rated_not_held,
            severity="info",
        ))

    # --- Section 4: Monitoring ---
    monitoring = inputs.sell_discipline_alerts + inputs.monitoring_notes
    if monitoring:
        sections.append(NarrativeSection(
            heading="Monitoring",
            items=monitoring,
            severity="warn" if inputs.sell_discipline_alerts else "info",
        ))

    # --- Section 5: Portfolio Posture ---
    posture_items: list[str] = []

    if inputs.position_count > 0:
        posture_items.append(
            f"{inputs.position_count} positions, "
            f"${inputs.total_value:,.0f} total value"
        )
    if inputs.cash_pct > 0:
        posture_items.append(f"Cash allocation: {inputs.cash_pct:.1f}%")
    if inputs.allocation_guidance:
        posture_items.append(inputs.allocation_guidance)
    posture_items.extend(inputs.sector_warnings)
    if inputs.performance_vs_spy:
        posture_items.append(inputs.performance_vs_spy)
    if inputs.overall_risk_level != "low":
        posture_items.append(f"Overall risk level: {inputs.overall_risk_level}")

    if posture_items:
        severity = "warn" if inputs.overall_risk_level in ("elevated", "high") else "info"
        sections.append(NarrativeSection(
            heading="Portfolio Posture",
            items=posture_items,
            severity=severity,
        ))

    return MondayBriefing(date=today, sections=sections)
