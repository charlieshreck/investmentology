"""Tests for Monday Morning Briefing narrative format."""

from datetime import date

from investmentology.advisory.narrative_briefing import (
    BriefingInputs,
    MondayBriefing,
    NarrativeSection,
    build_monday_briefing,
)


class TestBuildMondayBriefing:
    def test_empty_inputs_produces_all_clear(self):
        inputs = BriefingInputs(as_of=date(2026, 3, 9))
        result = build_monday_briefing(inputs)
        assert result.date == "2026-03-09"
        assert all(not s.items for s in result.sections)
        text = result.to_text()
        assert "All clear" in text

    def test_critical_alerts_come_first(self):
        inputs = BriefingInputs(
            as_of=date(2026, 3, 9),
            critical_alerts=["AAPL breached stop-loss at $180"],
            monitoring_notes=["MSFT F-Score stable at 7"],
        )
        result = build_monday_briefing(inputs)
        assert result.sections[0].heading == "Immediate Attention"
        assert result.sections[0].severity == "critical"
        assert "AAPL" in result.sections[0].items[0]

    def test_thesis_challenges_in_immediate(self):
        inputs = BriefingInputs(
            thesis_challenges=["GOOG thesis CHALLENGED: search market share declining"],
        )
        result = build_monday_briefing(inputs)
        section = result.sections[0]
        assert section.heading == "Immediate Attention"
        assert "GOOG" in section.items[0]

    def test_earnings_alerts_in_events(self):
        inputs = BriefingInputs(
            earnings_alerts=["AAPL: Earnings in 5d — DEFER new entry"],
        )
        result = build_monday_briefing(inputs)
        events = next(s for s in result.sections if "Events" in s.heading)
        assert events.severity == "warn"
        assert "AAPL" in events.items[0]

    def test_macro_signals_in_events(self):
        inputs = BriefingInputs(
            macro_signals=["Fear regime — increased sizing justified"],
        )
        result = build_monday_briefing(inputs)
        events = next(s for s in result.sections if "Events" in s.heading)
        assert "Fear regime" in events.items[0]

    def test_watchlist_gap(self):
        inputs = BriefingInputs(
            buy_rated_not_held=["NVDA — STRONG_BUY, 82% confidence, not in portfolio"],
        )
        result = build_monday_briefing(inputs)
        gap = next(s for s in result.sections if "Watchlist" in s.heading)
        assert "NVDA" in gap.items[0]

    def test_sell_discipline_in_monitoring(self):
        inputs = BriefingInputs(
            sell_discipline_alerts=[
                "TSLA: Piotroski dropped 3 points (7 → 4)",
                "META: P/FV = 1.15x — may be fully valued",
            ],
        )
        result = build_monday_briefing(inputs)
        monitoring = next(s for s in result.sections if "Monitoring" in s.heading)
        assert monitoring.severity == "warn"
        assert len(monitoring.items) == 2

    def test_portfolio_posture_section(self):
        inputs = BriefingInputs(
            position_count=12,
            total_value=150000.0,
            cash_pct=18.5,
            allocation_guidance="Macro: expansion — standard allocation (70-85% equity)",
            sector_warnings=["Technology at 35% — exceeds 30% threshold"],
            performance_vs_spy="Portfolio +12.3% vs SPY +8.1% (alpha +4.2%)",
            overall_risk_level="moderate",
        )
        result = build_monday_briefing(inputs)
        posture = next(s for s in result.sections if "Posture" in s.heading)
        items_text = " ".join(posture.items)
        assert "12 positions" in items_text
        assert "$150,000" in items_text
        assert "18.5%" in items_text
        assert "expansion" in items_text
        assert "Technology" in items_text
        assert "alpha" in items_text

    def test_elevated_risk_warns_in_posture(self):
        inputs = BriefingInputs(
            position_count=5,
            total_value=50000.0,
            overall_risk_level="elevated",
        )
        result = build_monday_briefing(inputs)
        posture = next(s for s in result.sections if "Posture" in s.heading)
        assert posture.severity == "warn"
        assert any("elevated" in item for item in posture.items)

    def test_full_briefing_section_order(self):
        """All 5 sections present and in correct order."""
        inputs = BriefingInputs(
            critical_alerts=["Alert"],
            earnings_alerts=["Earnings"],
            buy_rated_not_held=["Gap"],
            sell_discipline_alerts=["Discipline"],
            position_count=5,
            total_value=100000.0,
        )
        result = build_monday_briefing(inputs)
        headings = [s.heading for s in result.sections]
        assert headings[0] == "Immediate Attention"
        assert "Events" in headings[1]
        assert "Watchlist" in headings[2]
        assert "Monitoring" in headings[3]
        assert "Posture" in headings[4]

    def test_to_text_format(self):
        inputs = BriefingInputs(
            as_of=date(2026, 3, 9),
            critical_alerts=["AAPL stop-loss breached"],
        )
        result = build_monday_briefing(inputs)
        text = result.to_text()
        assert text.startswith("# Monday Morning Briefing")
        assert "2026-03-09" in text
        assert "## [!] Immediate Attention" in text
        assert "- AAPL stop-loss breached" in text

    def test_to_dict_serialization(self):
        inputs = BriefingInputs(
            as_of=date(2026, 3, 9),
            macro_signals=["Neutral sentiment"],
            position_count=3,
            total_value=50000.0,
        )
        result = build_monday_briefing(inputs)
        d = result.to_dict()
        assert d["date"] == "2026-03-09"
        assert isinstance(d["sections"], list)
        assert all("heading" in s and "items" in s for s in d["sections"])

    def test_empty_sections_omitted_from_text(self):
        """Sections with no items don't appear in text output."""
        inputs = BriefingInputs(
            earnings_alerts=["Earnings in 3d"],
        )
        result = build_monday_briefing(inputs)
        text = result.to_text()
        assert "Immediate Attention" not in text
        assert "Watchlist" not in text
        assert "Events" in text
