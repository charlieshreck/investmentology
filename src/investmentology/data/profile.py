"""Stock profile and news fetcher — pulls business info from yfinance."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import yfinance as yf

from investmentology.registry.db import Database

logger = logging.getLogger(__name__)

# Cache profiles for 24 hours
PROFILE_TTL = timedelta(hours=24)


def fetch_profile_from_yfinance(ticker: str) -> dict | None:
    """Fetch business profile data from yfinance."""
    try:
        t = yf.Ticker(ticker)
        info = t.info
        if not info or not info.get("longBusinessSummary"):
            return None
        return {
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "business_summary": info.get("longBusinessSummary"),
            "website": info.get("website"),
            "employees": info.get("fullTimeEmployees"),
            "city": info.get("city"),
            "country": info.get("country"),
            "beta": info.get("beta"),
            "dividend_yield": info.get("dividendYield"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "average_volume": info.get("averageVolume"),
            "analyst_target": info.get("targetMeanPrice"),
            "analyst_recommendation": info.get("recommendationKey"),
            "analyst_count": info.get("numberOfAnalystOpinions"),
        }
    except Exception:
        logger.exception("Failed to fetch profile for %s", ticker)
        return None


def fetch_news_from_yfinance(ticker: str, limit: int = 10) -> list[dict]:
    """Fetch recent news articles from yfinance."""
    try:
        t = yf.Ticker(ticker)
        raw = t.news or []
        articles = []
        for item in raw[:limit]:
            content = item.get("content", {})
            if not isinstance(content, dict):
                continue
            url_obj = content.get("clickThroughUrl") or content.get("canonicalUrl")
            url = url_obj.get("url") if isinstance(url_obj, dict) else (url_obj or "")
            provider = content.get("provider", {})
            articles.append({
                "title": content.get("title", ""),
                "summary": content.get("summary", ""),
                "publisher": provider.get("displayName", "") if isinstance(provider, dict) else "",
                "url": url,
                "published_at": content.get("pubDate"),
                "type": content.get("contentType", ""),
            })
        return articles
    except Exception:
        logger.exception("Failed to fetch news for %s", ticker)
        return []


def get_or_fetch_profile(db: Database, ticker: str) -> dict | None:
    """Get cached profile or fetch fresh one from yfinance.

    Returns the profile dict or None if unavailable.
    """
    # Check cache
    rows = db.execute(
        "SELECT * FROM invest.stock_profiles WHERE ticker = %s",
        (ticker,),
    )
    if rows:
        profile = rows[0]
        updated = profile.get("updated_at")
        if updated:
            if isinstance(updated, str):
                updated = datetime.fromisoformat(updated)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - updated < PROFILE_TTL:
                return profile

    # Fetch fresh
    data = fetch_profile_from_yfinance(ticker)
    if not data:
        return rows[0] if rows else None

    # Upsert into cache
    db.execute(
        """INSERT INTO invest.stock_profiles (
                ticker, sector, industry, business_summary, website, employees,
                city, country, beta, dividend_yield, trailing_pe, forward_pe,
                price_to_book, price_to_sales, fifty_two_week_high, fifty_two_week_low,
                average_volume, analyst_target, analyst_recommendation, analyst_count,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (ticker) DO UPDATE SET
                sector = EXCLUDED.sector,
                industry = EXCLUDED.industry,
                business_summary = EXCLUDED.business_summary,
                website = EXCLUDED.website,
                employees = EXCLUDED.employees,
                city = EXCLUDED.city,
                country = EXCLUDED.country,
                beta = EXCLUDED.beta,
                dividend_yield = EXCLUDED.dividend_yield,
                trailing_pe = EXCLUDED.trailing_pe,
                forward_pe = EXCLUDED.forward_pe,
                price_to_book = EXCLUDED.price_to_book,
                price_to_sales = EXCLUDED.price_to_sales,
                fifty_two_week_high = EXCLUDED.fifty_two_week_high,
                fifty_two_week_low = EXCLUDED.fifty_two_week_low,
                average_volume = EXCLUDED.average_volume,
                analyst_target = EXCLUDED.analyst_target,
                analyst_recommendation = EXCLUDED.analyst_recommendation,
                analyst_count = EXCLUDED.analyst_count,
                updated_at = NOW()
        """,
        (
            ticker, data["sector"], data["industry"], data["business_summary"],
            data["website"], data["employees"], data["city"], data["country"],
            data["beta"], data["dividend_yield"], data["trailing_pe"], data["forward_pe"],
            data["price_to_book"], data["price_to_sales"],
            data["fifty_two_week_high"], data["fifty_two_week_low"],
            data["average_volume"], data["analyst_target"],
            data["analyst_recommendation"], data["analyst_count"],
        ),
    )

    # Also update stocks table sector/industry if we have new data
    if data.get("sector") or data.get("industry"):
        db.execute(
            "UPDATE invest.stocks SET sector = COALESCE(%s, sector), "
            "industry = COALESCE(%s, industry) WHERE ticker = %s",
            (data["sector"], data["industry"], ticker),
        )

    # Re-read from DB to get consistent types
    rows = db.execute(
        "SELECT * FROM invest.stock_profiles WHERE ticker = %s",
        (ticker,),
    )
    return rows[0] if rows else data
