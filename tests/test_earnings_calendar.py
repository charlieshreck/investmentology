"""Tests for earnings calendar with sizing guidance."""

from datetime import date

from investmentology.advisory.earnings_calendar import (
    EarningsSizingGuidance,
    classify_earnings_proximity,
    format_earnings_alert,
)


class TestEarningsProximity:
    def test_no_data_returns_standard(self):
        result = classify_earnings_proximity("AAPL", None)
        assert result.guidance == EarningsSizingGuidance.STANDARD
        assert result.days_to_earnings is None

    def test_empty_dict_returns_standard(self):
        result = classify_earnings_proximity("AAPL", {})
        assert result.guidance == EarningsSizingGuidance.STANDARD

    def test_block_within_7_days(self):
        result = classify_earnings_proximity(
            "AAPL",
            {"date": "2026-03-14"},
            as_of=date(2026, 3, 9),
        )
        assert result.days_to_earnings == 5
        assert result.guidance == EarningsSizingGuidance.BLOCK

    def test_defer_within_15_days(self):
        result = classify_earnings_proximity(
            "AAPL",
            {"date": "2026-03-20"},
            as_of=date(2026, 3, 9),
        )
        assert result.days_to_earnings == 11
        assert result.guidance == EarningsSizingGuidance.DEFER

    def test_caution_within_30_days(self):
        result = classify_earnings_proximity(
            "AAPL",
            {"date": "2026-04-01"},
            as_of=date(2026, 3, 9),
        )
        assert result.days_to_earnings == 23
        assert result.guidance == EarningsSizingGuidance.CAUTION

    def test_standard_beyond_30_days(self):
        result = classify_earnings_proximity(
            "AAPL",
            {"date": "2026-05-01"},
            as_of=date(2026, 3, 9),
        )
        assert result.days_to_earnings == 53
        assert result.guidance == EarningsSizingGuidance.STANDARD

    def test_past_earnings_date_is_standard(self):
        result = classify_earnings_proximity(
            "AAPL",
            {"date": "2026-02-01"},
            as_of=date(2026, 3, 9),
        )
        assert result.days_to_earnings < 0
        assert result.guidance == EarningsSizingGuidance.STANDARD

    def test_accepts_upcoming_earnings_date_key(self):
        result = classify_earnings_proximity(
            "AAPL",
            {"upcoming_earnings_date": "2026-03-12"},
            as_of=date(2026, 3, 9),
        )
        assert result.days_to_earnings == 3
        assert result.guidance == EarningsSizingGuidance.BLOCK

    def test_accepts_date_object(self):
        result = classify_earnings_proximity(
            "AAPL",
            {"date": date(2026, 3, 25)},
            as_of=date(2026, 3, 9),
        )
        assert result.days_to_earnings == 16
        assert result.guidance == EarningsSizingGuidance.CAUTION

    def test_estimates_passed_through(self):
        result = classify_earnings_proximity(
            "AAPL",
            {"date": "2026-04-15", "eps_estimate": 1.52, "revenue_estimate": 94.5e9},
            as_of=date(2026, 3, 9),
        )
        assert result.eps_estimate == 1.52
        assert result.revenue_estimate == 94.5e9


class TestFormatEarningsAlert:
    def test_no_alert_for_standard(self):
        result = classify_earnings_proximity(
            "AAPL",
            {"date": "2026-05-01"},
            as_of=date(2026, 3, 9),
        )
        assert format_earnings_alert(result) is None

    def test_block_alert_contains_defer(self):
        result = classify_earnings_proximity(
            "AAPL",
            {"date": "2026-03-13"},
            as_of=date(2026, 3, 9),
        )
        alert = format_earnings_alert(result)
        assert alert is not None
        assert "DEFER" in alert
        assert "4d" in alert

    def test_caution_alert_contains_starter(self):
        result = classify_earnings_proximity(
            "AAPL",
            {"date": "2026-04-01"},
            as_of=date(2026, 3, 9),
        )
        alert = format_earnings_alert(result)
        assert alert is not None
        assert "starter" in alert.lower()

    def test_no_alert_for_none_date(self):
        result = classify_earnings_proximity("AAPL", None)
        assert format_earnings_alert(result) is None
