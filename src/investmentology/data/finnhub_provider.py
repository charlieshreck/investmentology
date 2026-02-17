"""Finnhub data provider for news, sentiment, earnings, and insider data.

Single API integration that provides:
- Company news + sentiment scores
- Earnings calendar + surprises
- Insider transactions
- Social sentiment (Reddit/Twitter)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FinnhubProvider:
    """Fetches news, sentiment, earnings, and insider data from Finnhub."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = None
        self._cache: dict[str, tuple[datetime, object]] = {}
        self._cache_ttl = timedelta(hours=1)

    def _get_client(self):
        if self._client is None:
            import finnhub
            self._client = finnhub.Client(api_key=self._api_key)
        return self._client

    def _cached(self, key: str):
        if key in self._cache:
            cached_at, data = self._cache[key]
            if datetime.now() - cached_at < self._cache_ttl:
                return data
        return None

    def _set_cache(self, key: str, data: object):
        self._cache[key] = (datetime.now(), data)

    def get_news(self, ticker: str, days: int = 7) -> list[dict]:
        """Get recent company news with headlines and sentiment."""
        cache_key = f"news:{ticker}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        client = self._get_client()
        end = datetime.now()
        start = end - timedelta(days=days)

        try:
            raw = client.company_news(
                ticker,
                _from=start.strftime("%Y-%m-%d"),
                to=end.strftime("%Y-%m-%d"),
            )
            news = [
                {
                    "headline": item.get("headline", ""),
                    "summary": item.get("summary", "")[:200],
                    "source": item.get("source", ""),
                    "datetime": datetime.fromtimestamp(item["datetime"]).isoformat()
                    if item.get("datetime")
                    else "",
                    "url": item.get("url", ""),
                }
                for item in (raw or [])[:10]  # Limit to 10 most recent
            ]
            self._set_cache(cache_key, news)
            return news
        except Exception:
            logger.debug("Failed to fetch Finnhub news for %s", ticker)
            return []

    def get_earnings(self, ticker: str) -> dict | None:
        """Get upcoming earnings date and recent earnings surprises."""
        cache_key = f"earnings:{ticker}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        client = self._get_client()

        try:
            # Earnings calendar
            calendar = client.earnings_calendar(
                _from=datetime.now().strftime("%Y-%m-%d"),
                to=(datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                symbol=ticker,
            )
            upcoming = None
            for event in (calendar or {}).get("earningsCalendar", []):
                if event.get("symbol") == ticker:
                    upcoming = {
                        "date": event.get("date"),
                        "eps_estimate": event.get("epsEstimate"),
                        "revenue_estimate": event.get("revenueEstimate"),
                    }
                    break

            # Recent surprises
            surprises_raw = client.company_earnings(ticker, limit=4)
            surprises = []
            for s in (surprises_raw or []):
                surprises.append({
                    "period": s.get("period", ""),
                    "actual_eps": s.get("actual"),
                    "estimated_eps": s.get("estimate"),
                    "surprise_pct": s.get("surprisePercent"),
                })

            result = {
                "upcoming": upcoming,
                "recent_surprises": surprises,
                "beat_count": sum(1 for s in surprises if (s.get("surprise_pct") or 0) > 0),
                "miss_count": sum(1 for s in surprises if (s.get("surprise_pct") or 0) < 0),
            }
            self._set_cache(cache_key, result)
            return result
        except Exception:
            logger.debug("Failed to fetch Finnhub earnings for %s", ticker)
            return None

    def get_insider_transactions(self, ticker: str) -> list[dict]:
        """Get recent insider transactions (Form 4 filings)."""
        cache_key = f"insider:{ticker}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        client = self._get_client()

        try:
            raw = client.stock_insider_transactions(ticker)
            transactions = []
            for t in (raw or {}).get("data", [])[:10]:
                transactions.append({
                    "name": t.get("name", ""),
                    "share": t.get("share", 0),
                    "change": t.get("change", 0),
                    "transaction_type": (
                        "buy" if (t.get("change") or 0) > 0
                        else "sell" if (t.get("change") or 0) < 0
                        else "other"
                    ),
                    "filing_date": t.get("filingDate", ""),
                    "transaction_date": t.get("transactionDate", ""),
                })

            self._set_cache(cache_key, transactions)
            return transactions
        except Exception:
            logger.debug("Failed to fetch Finnhub insider data for %s", ticker)
            return []

    def get_social_sentiment(self, ticker: str) -> dict | None:
        """Get aggregated social media sentiment (Reddit + Twitter)."""
        cache_key = f"social:{ticker}"
        cached = self._cached(cache_key)
        if cached is not None:
            return cached

        client = self._get_client()

        try:
            raw = client.stock_social_sentiment(ticker)
            result = {}
            for source in ["reddit", "twitter"]:
                data = (raw or {}).get(source, [])
                if data:
                    latest = data[-1] if data else {}
                    result[source] = {
                        "mention": latest.get("mention", 0),
                        "positive_mention": latest.get("positiveMention", 0),
                        "negative_mention": latest.get("negativeMention", 0),
                        "score": latest.get("score", 0),
                    }

            if result:
                # Compute aggregate sentiment
                total_pos = sum(s.get("positive_mention", 0) for s in result.values())
                total_neg = sum(s.get("negative_mention", 0) for s in result.values())
                total = total_pos + total_neg
                result["aggregate"] = {
                    "positive_ratio": round(total_pos / total, 3) if total > 0 else 0.5,
                    "total_mentions": total,
                    "bias": "bullish" if total_pos > total_neg * 1.5 else
                            "bearish" if total_neg > total_pos * 1.5 else "neutral",
                }

            self._set_cache(cache_key, result)
            return result if result else None
        except Exception:
            logger.debug("Failed to fetch Finnhub social sentiment for %s", ticker)
            return None
