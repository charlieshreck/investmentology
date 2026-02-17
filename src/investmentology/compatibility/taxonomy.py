from __future__ import annotations

from investmentology.models.signal import SignalTag

# Category sets — group SignalTag members by category
FUNDAMENTAL_TAGS: frozenset[SignalTag] = frozenset({
    SignalTag.UNDERVALUED, SignalTag.OVERVALUED, SignalTag.FAIRLY_VALUED, SignalTag.DEEP_VALUE,
    SignalTag.MOAT_WIDENING, SignalTag.MOAT_STABLE, SignalTag.MOAT_NARROWING, SignalTag.NO_MOAT,
    SignalTag.EARNINGS_QUALITY_HIGH, SignalTag.EARNINGS_QUALITY_LOW,
    SignalTag.REVENUE_ACCELERATING, SignalTag.REVENUE_DECELERATING,
    SignalTag.MARGIN_EXPANDING, SignalTag.MARGIN_COMPRESSING,
    SignalTag.BALANCE_SHEET_STRONG, SignalTag.BALANCE_SHEET_WEAK,
    SignalTag.DIVIDEND_GROWING, SignalTag.BUYBACK_ACTIVE, SignalTag.MANAGEMENT_ALIGNED,
})

MACRO_TAGS: frozenset[SignalTag] = frozenset({
    SignalTag.REGIME_BULL, SignalTag.REGIME_BEAR, SignalTag.REGIME_NEUTRAL, SignalTag.REGIME_TRANSITION,
    SignalTag.SECTOR_ROTATION_INTO, SignalTag.SECTOR_ROTATION_OUT,
    SignalTag.CREDIT_TIGHTENING, SignalTag.CREDIT_EASING,
    SignalTag.RATE_RISING, SignalTag.RATE_FALLING,
    SignalTag.INFLATION_HIGH, SignalTag.INFLATION_LOW,
    SignalTag.DOLLAR_STRONG, SignalTag.DOLLAR_WEAK,
    SignalTag.GEOPOLITICAL_RISK, SignalTag.SUPPLY_CHAIN_DISRUPTION,
    SignalTag.FISCAL_STIMULUS, SignalTag.FISCAL_CONTRACTION,
    SignalTag.LIQUIDITY_ABUNDANT, SignalTag.LIQUIDITY_TIGHT,
    SignalTag.REFLEXIVITY_DETECTED,
})

TECHNICAL_TAGS: frozenset[SignalTag] = frozenset({
    SignalTag.TREND_UPTREND, SignalTag.TREND_DOWNTREND, SignalTag.TREND_SIDEWAYS,
    SignalTag.MOMENTUM_STRONG, SignalTag.MOMENTUM_WEAK, SignalTag.MOMENTUM_DIVERGENCE,
    SignalTag.BREAKOUT_CONFIRMED, SignalTag.BREAKDOWN_CONFIRMED,
    SignalTag.SUPPORT_NEAR, SignalTag.RESISTANCE_NEAR,
    SignalTag.VOLUME_SURGE, SignalTag.VOLUME_DRY, SignalTag.VOLUME_CLIMAX,
    SignalTag.RSI_OVERSOLD, SignalTag.RSI_OVERBOUGHT,
    SignalTag.GOLDEN_CROSS, SignalTag.DEATH_CROSS,
    SignalTag.RELATIVE_STRENGTH_HIGH, SignalTag.RELATIVE_STRENGTH_LOW,
})

RISK_TAGS: frozenset[SignalTag] = frozenset({
    SignalTag.CONCENTRATION, SignalTag.CORRELATION_HIGH, SignalTag.CORRELATION_LOW,
    SignalTag.LIQUIDITY_LOW, SignalTag.LIQUIDITY_OK,
    SignalTag.DRAWDOWN_RISK, SignalTag.ACCOUNTING_RED_FLAG, SignalTag.GOVERNANCE_CONCERN,
    SignalTag.LEVERAGE_HIGH, SignalTag.LEVERAGE_OK,
    SignalTag.VOLATILITY_HIGH, SignalTag.VOLATILITY_LOW,
    SignalTag.SECTOR_OVERWEIGHT, SignalTag.SECTOR_UNDERWEIGHT,
})

SPECIAL_TAGS: frozenset[SignalTag] = frozenset({
    SignalTag.SPINOFF_ANNOUNCED, SignalTag.MERGER_TARGET,
    SignalTag.INSIDER_CLUSTER_BUY, SignalTag.INSIDER_CLUSTER_SELL,
    SignalTag.ACTIVIST_INVOLVED, SignalTag.MANAGEMENT_CHANGE, SignalTag.REGULATORY_CHANGE,
    SignalTag.PATENT_CATALYST, SignalTag.EARNINGS_SURPRISE,
    SignalTag.GUIDANCE_RAISED, SignalTag.GUIDANCE_LOWERED,
})

ACTION_TAGS: frozenset[SignalTag] = frozenset({
    SignalTag.BUY_NEW, SignalTag.BUY_ADD, SignalTag.TRIM, SignalTag.SELL_FULL, SignalTag.SELL_PARTIAL,
    SignalTag.HOLD, SignalTag.HOLD_STRONG,
    SignalTag.WATCHLIST_ADD, SignalTag.WATCHLIST_REMOVE, SignalTag.WATCHLIST_PROMOTE,
    SignalTag.REJECT, SignalTag.REJECT_HARD,
    SignalTag.CONFLICT_FLAG, SignalTag.REVIEW_REQUIRED,
    SignalTag.MUNGER_PROCEED, SignalTag.MUNGER_CAUTION, SignalTag.MUNGER_VETO,
    SignalTag.NO_ACTION,
})

CATEGORY_MAP: dict[str, frozenset[SignalTag]] = {
    "fundamental": FUNDAMENTAL_TAGS,
    "macro": MACRO_TAGS,
    "technical": TECHNICAL_TAGS,
    "risk": RISK_TAGS,
    "special": SPECIAL_TAGS,
    "action": ACTION_TAGS,
}


def get_category(tag: SignalTag) -> str:
    """Return the category name for a signal tag."""
    for name, tags in CATEGORY_MAP.items():
        if tag in tags:
            return name
    return "unknown"


def get_tags_for_category(category: str) -> frozenset[SignalTag]:
    """Return all tags in a category."""
    return CATEGORY_MAP.get(category, frozenset())
