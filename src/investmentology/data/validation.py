from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    ticker: str
    is_valid: bool
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """Human-readable summary of validation issues."""
        parts = []
        if self.errors:
            parts.append(f"Errors: {'; '.join(self.errors)}")
        if self.warnings:
            parts.append(f"Warnings: {'; '.join(self.warnings)}")
        return " | ".join(parts) if parts else "OK"


# Reasonable bounds for fundamental data
BOUNDS: dict[str, tuple[float, float]] = {
    "market_cap": (1e6, 5e12),  # $1M to $5T
    "operating_income": (-1e11, 5e11),  # -$100B to $500B
    "price": (0.01, 100_000),  # $0.01 to $100K
    "total_debt": (0, 1e12),  # $0 to $1T
    "shares_outstanding": (1, 1e11),  # 1 to 100B
    "pe_ratio": (-1000, 10_000),  # very wide range
}

# Companies above this market cap MUST have non-zero revenue
# (catches yfinance returning $0 revenue for established companies like PSN)
REVENUE_REQUIRED_ABOVE_MARKET_CAP = 1e8  # $100M


def validate_fundamentals(data: dict) -> ValidationResult:
    """Validate fundamental data is within reasonable bounds.

    Returns ValidationResult with is_valid=False if data is too corrupt
    to produce a meaningful analysis. The pipeline should abort rather
    than feed garbage to LLM agents.
    """
    ticker = data.get("ticker", "UNKNOWN")
    warnings: list[str] = []
    errors: list[str] = []

    # Check required fields exist and are not None
    required = ["market_cap", "price", "shares_outstanding"]
    for field_name in required:
        val = data.get(field_name)
        if val is None:
            errors.append(f"Missing required field: {field_name}")

    # Check bounds
    for field_name, (lo, hi) in BOUNDS.items():
        val = data.get(field_name)
        if val is None:
            continue
        num = float(val) if isinstance(val, Decimal) else val
        if not isinstance(num, (int, float)):
            continue
        if num < lo:
            warnings.append(f"{field_name}={num} below minimum {lo}")
        elif num > hi:
            warnings.append(f"{field_name}={num} above maximum {hi}")

    # Check staleness
    fetched_at_str = data.get("fetched_at")
    if fetched_at_str:
        try:
            fetched_at = datetime.fromisoformat(fetched_at_str)
            if detect_staleness(fetched_at):
                warnings.append(
                    f"Data is stale (fetched_at={fetched_at_str})"
                )
        except (ValueError, TypeError):
            warnings.append(f"Invalid fetched_at format: {fetched_at_str}")

    # Anomaly detection (warnings)
    anomalies = detect_anomalies(data)
    warnings.extend(anomalies)

    # Critical sanity checks — these are ERRORS that abort the pipeline
    critical = detect_critical_anomalies(data)
    errors.extend(critical)

    is_valid = len(errors) == 0
    return ValidationResult(
        ticker=ticker,
        is_valid=is_valid,
        warnings=warnings,
        errors=errors,
    )


def detect_staleness(
    fetched_at: datetime, max_age_days: int = 90
) -> bool:
    """Check if data is too old."""
    now = datetime.now(UTC).replace(tzinfo=None)
    ts = fetched_at.replace(tzinfo=None) if fetched_at.tzinfo else fetched_at
    age = now - ts
    return age > timedelta(days=max_age_days)


def detect_anomalies(data: dict) -> list[str]:
    """Flag suspicious data combinations (warnings — don't block pipeline)."""
    anomalies: list[str] = []

    revenue = _to_float(data.get("revenue"))
    operating_income = _to_float(data.get("operating_income"))
    market_cap = _to_float(data.get("market_cap"))
    shares_outstanding = _to_float(data.get("shares_outstanding"))
    total_debt = _to_float(data.get("total_debt"))
    total_assets = _to_float(data.get("total_assets"))
    price = _to_float(data.get("price"))
    pe_ratio = _to_float(data.get("pe_ratio"))
    eps = _to_float(data.get("eps"))
    net_income = _to_float(data.get("net_income"))
    revenue_growth = _to_float(data.get("revenue_growth"))

    # Operating income exceeds revenue
    if (
        operating_income is not None
        and revenue is not None
        and revenue > 0
        and operating_income > revenue
    ):
        anomalies.append(
            f"operating_income ({operating_income}) > revenue ({revenue})"
        )

    # Negative market cap
    if market_cap is not None and market_cap < 0:
        anomalies.append(f"Negative market_cap: {market_cap}")

    # Negative shares outstanding
    if shares_outstanding is not None and shares_outstanding < 0:
        anomalies.append(
            f"Negative shares_outstanding: {shares_outstanding}"
        )

    # Total debt exceeds total assets * 10
    if (
        total_debt is not None
        and total_assets is not None
        and total_assets > 0
        and total_debt > total_assets * 10
    ):
        anomalies.append(
            f"total_debt ({total_debt}) > 10x total_assets ({total_assets})"
        )

    # EPS sign vs net_income sign inconsistency
    # If net_income is positive, EPS should also be positive (and vice versa)
    if eps is not None and net_income is not None and shares_outstanding is not None:
        if shares_outstanding > 0:
            if net_income > 0 and eps < 0:
                anomalies.append(
                    f"EPS ({eps}) is negative but net_income ({net_income}) is positive"
                )
            elif net_income < 0 and eps > 0:
                anomalies.append(
                    f"EPS ({eps}) is positive but net_income ({net_income}) is negative"
                )

    # Market cap vs shares_outstanding * price consistency
    if (
        market_cap is not None
        and shares_outstanding is not None
        and price is not None
        and shares_outstanding > 0
        and price > 0
    ):
        implied_market_cap = shares_outstanding * price
        if implied_market_cap > 0:
            ratio = market_cap / implied_market_cap
            # Allow 20% tolerance for timing differences between fields
            if ratio < 0.5 or ratio > 2.0:
                anomalies.append(
                    f"market_cap ({market_cap:.0f}) inconsistent with "
                    f"shares_outstanding * price ({implied_market_cap:.0f}), "
                    f"ratio={ratio:.2f}"
                )

    # Revenue growth rate sanity for large caps
    # yfinance returns revenueGrowth as a decimal (e.g., 0.15 = 15%)
    if (
        revenue_growth is not None
        and market_cap is not None
        and market_cap > 1e10  # >$10B = large cap
        and revenue_growth > 10.0  # >1000% YoY
    ):
        anomalies.append(
            f"Implausible revenue_growth ({revenue_growth*100:.0f}%) "
            f"for ${market_cap/1e9:.0f}B market cap company — likely data error"
        )

    return anomalies


def detect_critical_anomalies(data: dict) -> list[str]:
    """Detect data corruption that would produce nonsensical analysis.

    These are ERRORS — the pipeline must NOT proceed with this data.
    Catches the classic yfinance bug where established companies return
    $0 revenue, $0 income, leading to "pre-revenue startup" moat analysis
    on a $16B revenue defense contractor.
    """
    errors: list[str] = []

    revenue = _to_float(data.get("revenue"))
    operating_income = _to_float(data.get("operating_income"))
    net_income = _to_float(data.get("net_income"))
    market_cap = _to_float(data.get("market_cap"))
    price = _to_float(data.get("price"))
    pe_ratio = _to_float(data.get("pe_ratio"))

    # P/E ratio sanity: negative P/E for a clearly profitable company = data error
    # A company with positive net_income and positive price should have a positive P/E
    if (
        pe_ratio is not None
        and pe_ratio < 0
        and net_income is not None
        and net_income > 0
        and price is not None
        and price > 0
    ):
        errors.append(
            f"Negative P/E ratio ({pe_ratio}) for profitable company "
            f"(net_income={net_income}) — corrupted data"
        )

    # Established company with zeroed financials = corrupted data
    # Any company with market_cap > $100M should have revenue
    if market_cap is not None and market_cap > REVENUE_REQUIRED_ABOVE_MARKET_CAP:
        if revenue is None or revenue == 0:
            errors.append(
                f"Zeroed revenue for ${market_cap/1e9:.1f}B market cap company — "
                f"likely corrupted data source"
            )
        elif (
            (operating_income is None or operating_income == 0)
            and (net_income is None or net_income == 0)
        ):
            errors.append(
                f"Both operating_income and net_income are zero/missing "
                f"for ${market_cap/1e9:.1f}B company with ${revenue/1e9:.1f}B revenue — "
                f"likely corrupted data source"
            )

    # Price is zero or missing for a company with market cap
    if market_cap is not None and market_cap > 0 and (price is None or price <= 0):
        errors.append(
            f"Zero/missing price for company with ${market_cap/1e9:.1f}B market cap"
        )

    # All key financial fields are zero for a company that should have them
    if (
        market_cap is not None
        and market_cap > REVENUE_REQUIRED_ABOVE_MARKET_CAP
        and (revenue is None or revenue == 0)
        and (operating_income is None or operating_income == 0)
        and (net_income is None or net_income == 0)
    ):
        errors.append("All financial fields zeroed — data source returned empty data")

    # Extreme revenue growth for mega-caps is almost certainly data corruption
    # e.g. yfinance returning revenueGrowth=50.0 (5000%) for Apple
    revenue_growth = _to_float(data.get("revenue_growth"))
    if (
        revenue_growth is not None
        and market_cap is not None
        and market_cap > 1e11  # >$100B mega cap
        and abs(revenue_growth) > 50.0  # >5000% YoY
    ):
        errors.append(
            f"Impossible revenue_growth ({revenue_growth*100:.0f}%) "
            f"for ${market_cap/1e9:.0f}B mega-cap — corrupted data"
        )

    return errors


def _to_float(val: Decimal | float | int | None) -> float | None:
    """Convert a value to float for comparison."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
