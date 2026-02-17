from __future__ import annotations

import pytest

from investmentology.models.signal import SignalTag
from investmentology.compatibility.taxonomy import (
    CATEGORY_MAP,
    FUNDAMENTAL_TAGS,
    MACRO_TAGS,
    TECHNICAL_TAGS,
    RISK_TAGS,
    SPECIAL_TAGS,
    ACTION_TAGS,
    get_category,
    get_tags_for_category,
)
from investmentology.compatibility.patterns import (
    PatternDefinition,
    ALL_PATTERNS,
    CONVICTION_BUY,
    WATCHLIST_EARLY,
    WATCHLIST_CATALYST,
    CONTRARIAN_VALUE,
    EARLY_RECOVERY,
    QUALITY_FAIR_PRICE,
    FORCED_SELLING_OVERRIDE,
    MOMENTUM_ONLY,
    VALUE_TRAP,
    HARD_REJECT,
    CONFLICT_REVIEW,
    match_pattern,
    score_pattern,
)


# ── Taxonomy tests ──────────────────────────────────────────────────────


class TestCategoryGroupings:
    def test_all_signal_tags_are_categorized(self):
        """Every SignalTag member must belong to exactly one category."""
        all_categorized = set()
        for tags in CATEGORY_MAP.values():
            all_categorized |= tags
        all_tags = set(SignalTag)
        orphans = all_tags - all_categorized
        assert orphans == set(), f"Uncategorized tags: {orphans}"

    def test_no_tag_in_multiple_categories(self):
        """No SignalTag should appear in more than one category."""
        seen: dict[SignalTag, str] = {}
        duplicates: list[str] = []
        for name, tags in CATEGORY_MAP.items():
            for tag in tags:
                if tag in seen:
                    duplicates.append(f"{tag} in both '{seen[tag]}' and '{name}'")
                seen[tag] = name
        assert duplicates == [], f"Duplicate categorizations: {duplicates}"

    def test_category_sizes(self):
        assert len(FUNDAMENTAL_TAGS) == 19
        assert len(MACRO_TAGS) == 21
        assert len(TECHNICAL_TAGS) == 19
        assert len(RISK_TAGS) == 14
        assert len(SPECIAL_TAGS) == 11
        assert len(ACTION_TAGS) == 18

    def test_total_tag_count(self):
        total = sum(len(tags) for tags in CATEGORY_MAP.values())
        assert total == len(SignalTag)


class TestGetCategory:
    def test_fundamental_tag(self):
        assert get_category(SignalTag.UNDERVALUED) == "fundamental"

    def test_macro_tag(self):
        assert get_category(SignalTag.REGIME_BULL) == "macro"

    def test_technical_tag(self):
        assert get_category(SignalTag.TREND_UPTREND) == "technical"

    def test_risk_tag(self):
        assert get_category(SignalTag.ACCOUNTING_RED_FLAG) == "risk"

    def test_special_tag(self):
        assert get_category(SignalTag.SPINOFF_ANNOUNCED) == "special"

    def test_action_tag(self):
        assert get_category(SignalTag.BUY_NEW) == "action"


class TestGetTagsForCategory:
    def test_known_category(self):
        assert get_tags_for_category("fundamental") is FUNDAMENTAL_TAGS

    def test_unknown_category(self):
        assert get_tags_for_category("nonexistent") == frozenset()


# ── Pattern definition tests ────────────────────────────────────────────


class TestPatternDefinitions:
    def test_all_patterns_count(self):
        assert len(ALL_PATTERNS) == 11

    @pytest.mark.parametrize("pattern", ALL_PATTERNS, ids=lambda p: p.name)
    def test_pattern_signals_are_valid(self, pattern: PatternDefinition):
        """Every signal referenced in a pattern must be a valid SignalTag."""
        all_tags = set(SignalTag)
        for tag in pattern.required_signals:
            assert tag in all_tags, f"{pattern.name}: invalid required tag {tag}"
        for tag in pattern.supportive_signals:
            assert tag in all_tags, f"{pattern.name}: invalid supportive tag {tag}"
        for tag in pattern.absent_signals:
            assert tag in all_tags, f"{pattern.name}: invalid absent tag {tag}"

    @pytest.mark.parametrize("pattern", ALL_PATTERNS, ids=lambda p: p.name)
    def test_pattern_has_name_and_description(self, pattern: PatternDefinition):
        assert pattern.name
        assert pattern.description
        assert pattern.action


# ── match_pattern tests ─────────────────────────────────────────────────


class TestMatchPattern:
    def test_conviction_buy_matches(self):
        signals = {SignalTag.UNDERVALUED, SignalTag.TREND_UPTREND}
        result = match_pattern(signals, avg_confidence=0.75)
        assert result is CONVICTION_BUY

    def test_conviction_buy_blocked_by_absent_signal(self):
        signals = {
            SignalTag.UNDERVALUED, SignalTag.TREND_UPTREND,
            SignalTag.ACCOUNTING_RED_FLAG,
        }
        result = match_pattern(signals, avg_confidence=0.75)
        # HARD_REJECT takes priority since ACCOUNTING_RED_FLAG is present
        assert result is HARD_REJECT

    def test_conviction_buy_requires_confidence(self):
        signals = {SignalTag.UNDERVALUED, SignalTag.TREND_UPTREND}
        result = match_pattern(signals, avg_confidence=0.50)
        # Should not match CONVICTION_BUY (needs 0.70), falls through to other patterns
        assert result is not CONVICTION_BUY

    def test_hard_reject_takes_priority(self):
        """HARD_REJECT should override any other pattern match."""
        signals = {
            SignalTag.UNDERVALUED, SignalTag.TREND_UPTREND,
            SignalTag.GOVERNANCE_CONCERN,
        }
        result = match_pattern(signals, avg_confidence=0.80)
        assert result is HARD_REJECT

    def test_hard_reject_on_munger_veto(self):
        signals = {SignalTag.MUNGER_VETO}
        result = match_pattern(signals)
        assert result is HARD_REJECT

    def test_conflict_review_matches(self):
        signals = {SignalTag.CONFLICT_FLAG}
        result = match_pattern(signals)
        assert result is CONFLICT_REVIEW

    def test_conflict_review_priority_over_normal(self):
        """CONFLICT_REVIEW should match even with other signals present."""
        signals = {SignalTag.CONFLICT_FLAG, SignalTag.UNDERVALUED, SignalTag.TREND_UPTREND}
        result = match_pattern(signals, avg_confidence=0.80)
        assert result is CONFLICT_REVIEW

    def test_value_trap_matches(self):
        signals = {SignalTag.UNDERVALUED, SignalTag.REVENUE_DECELERATING}
        result = match_pattern(signals)
        assert result is VALUE_TRAP

    def test_no_match_returns_none(self):
        signals = {SignalTag.HOLD}
        result = match_pattern(signals)
        assert result is None

    def test_empty_signals_no_match(self):
        result = match_pattern(set())
        assert result is None

    def test_momentum_only_matches(self):
        signals = {SignalTag.MOMENTUM_STRONG, SignalTag.TREND_UPTREND}
        result = match_pattern(signals)
        assert result is MOMENTUM_ONLY

    def test_momentum_only_blocked_by_value(self):
        """MOMENTUM_ONLY requires value signals to be absent."""
        signals = {
            SignalTag.MOMENTUM_STRONG, SignalTag.TREND_UPTREND,
            SignalTag.UNDERVALUED,
        }
        result = match_pattern(signals)
        assert result is not MOMENTUM_ONLY

    def test_watchlist_early_matches(self):
        """WATCHLIST_EARLY requires UNDERVALUED but not TREND_UPTREND or MOMENTUM_STRONG."""
        signals = {SignalTag.UNDERVALUED}
        result = match_pattern(signals)
        assert result is WATCHLIST_EARLY

    def test_contrarian_value_matches(self):
        signals = {SignalTag.DEEP_VALUE}
        result = match_pattern(signals)
        assert result is CONTRARIAN_VALUE

    def test_early_recovery_matches(self):
        signals = {SignalTag.DEEP_VALUE, SignalTag.REVENUE_ACCELERATING}
        result = match_pattern(signals)
        assert result is EARLY_RECOVERY

    def test_quality_fair_price_matches(self):
        signals = {SignalTag.FAIRLY_VALUED, SignalTag.MOAT_WIDENING}
        result = match_pattern(signals)
        assert result is QUALITY_FAIR_PRICE

    def test_forced_selling_override_matches(self):
        signals = {SignalTag.DEEP_VALUE, SignalTag.VOLUME_CLIMAX}
        result = match_pattern(signals)
        assert result is FORCED_SELLING_OVERRIDE


# ── score_pattern tests ─────────────────────────────────────────────────


class TestScorePattern:
    def test_zero_when_required_missing(self):
        signals: set[SignalTag] = {SignalTag.TREND_UPTREND}
        assert score_pattern(CONVICTION_BUY, signals) == 0.0

    def test_zero_when_absent_present(self):
        signals = {
            SignalTag.UNDERVALUED, SignalTag.TREND_UPTREND,
            SignalTag.ACCOUNTING_RED_FLAG,
        }
        assert score_pattern(CONVICTION_BUY, signals) == 0.0

    def test_base_score_with_required_only(self):
        signals = {SignalTag.UNDERVALUED, SignalTag.TREND_UPTREND}
        score = score_pattern(CONVICTION_BUY, signals)
        assert score == 0.5

    def test_higher_with_supportive_signals(self):
        base_signals = {SignalTag.UNDERVALUED, SignalTag.TREND_UPTREND}
        score_base = score_pattern(CONVICTION_BUY, base_signals)

        with_support = base_signals | {SignalTag.MOAT_WIDENING, SignalTag.MOMENTUM_STRONG}
        score_supported = score_pattern(CONVICTION_BUY, with_support)

        assert score_supported > score_base

    def test_max_score_with_all_supportive(self):
        signals = {
            SignalTag.UNDERVALUED, SignalTag.TREND_UPTREND,
            SignalTag.MOAT_WIDENING, SignalTag.MOMENTUM_STRONG,
            SignalTag.EARNINGS_QUALITY_HIGH, SignalTag.BALANCE_SHEET_STRONG,
        }
        score = score_pattern(CONVICTION_BUY, signals)
        assert score == pytest.approx(1.0)

    def test_partial_supportive(self):
        signals = {SignalTag.UNDERVALUED, SignalTag.TREND_UPTREND, SignalTag.MOAT_WIDENING}
        score = score_pattern(CONVICTION_BUY, signals)
        # 0.5 base + 0.5 * (1/4) = 0.625
        assert score == pytest.approx(0.625)

    def test_no_required_no_supportive(self):
        """HARD_REJECT has no required or supportive signals; base score is 0.5."""
        signals: set[SignalTag] = set()
        score = score_pattern(HARD_REJECT, signals)
        assert score == 0.5
