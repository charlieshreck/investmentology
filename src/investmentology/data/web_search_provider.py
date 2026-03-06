"""Fallback data provider — fills gaps when Finnhub/EDGAR return nothing.

Uses a tiered strategy:
1. **yfinance** (primary fallback) — already installed, has analyst ratings,
   short interest, insider transactions, and earnings for most US equities
2. **SearXNG** (secondary fallback) — web search for news and social sentiment

For tickers with limited Finnhub free-tier coverage (small-caps, MLPs,
foreign ADRs), this fills the data gaps that would otherwise leave agents
making decisions on incomplete information.

Each method returns the same shape as the corresponding Finnhub/EDGAR method
so data flows seamlessly through the enrichment pipeline.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

SEARXNG_URL = os.environ.get(
    "SEARXNG_URL",
    "http://searxng.ai-platform.svc.cluster.local:8080",
)

_TIMEOUT = httpx.Timeout(15.0)


class FallbackProvider:
    """yfinance + SearXNG fallback for enrichment data gaps."""

    def __init__(self) -> None:
        self._http: httpx.Client | None = None

    def _get_http(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=_TIMEOUT)
        return self._http

    def _yf_ticker(self, ticker: str):
        import yfinance as yf
        return yf.Ticker(ticker)

    # ------------------------------------------------------------------
    # Analyst Ratings — yfinance stock.info + stock.recommendations
    # ------------------------------------------------------------------

    def get_analyst_ratings(self, ticker: str) -> dict | None:
        """Extract analyst consensus from yfinance."""
        try:
            stock = self._yf_ticker(ticker)
            info = stock.info or {}

            # Recommendation trends from stock.recommendations
            trends = []
            try:
                recs = stock.recommendations
                if recs is not None and not recs.empty:
                    for _, row in recs.iterrows():
                        trends.append({
                            "period": row.get("period", ""),
                            "strong_buy": int(row.get("strongBuy", 0) or 0),
                            "buy": int(row.get("buy", 0) or 0),
                            "hold": int(row.get("hold", 0) or 0),
                            "sell": int(row.get("sell", 0) or 0),
                            "strong_sell": int(row.get("strongSell", 0) or 0),
                        })
            except Exception:
                pass

            # Price target from stock.info
            target = None
            target_mean = info.get("targetMeanPrice")
            if target_mean is not None:
                target = {
                    "high": info.get("targetHighPrice"),
                    "low": info.get("targetLowPrice"),
                    "mean": target_mean,
                    "median": info.get("targetMedianPrice"),
                }

            # Recent upgrades/downgrades
            recent_changes = []
            try:
                upgrades = stock.upgrades_downgrades
                if upgrades is not None and not upgrades.empty:
                    for idx, row in upgrades.head(5).iterrows():
                        recent_changes.append({
                            "firm": str(row.get("Firm", ""))[:40],
                            "action": str(row.get("Action", "")),
                            "from_grade": str(row.get("FromGrade", "")),
                            "to_grade": str(row.get("ToGrade", "")),
                            "date": str(idx)[:10] if idx else "",
                        })
            except Exception:
                pass

            if not trends and not target and not recent_changes:
                return None

            return {
                "trends": trends[:4],
                "price_target": target,
                "recent_changes": recent_changes[:5],
                "consensus": info.get("recommendationKey"),
                "num_analysts": info.get("numberOfAnalystOpinions"),
                "_source": "yfinance_fallback",
            }
        except Exception:
            logger.debug("yfinance analyst ratings fallback failed for %s", ticker)
            return None

    # ------------------------------------------------------------------
    # Short Interest — yfinance stock.info
    # ------------------------------------------------------------------

    def get_short_interest(self, ticker: str) -> dict | None:
        """Extract short interest from yfinance stock.info."""
        try:
            stock = self._yf_ticker(ticker)
            info = stock.info or {}

            short_pct = info.get("shortPercentOfFloat")
            short_ratio = info.get("shortRatio")
            shares_short = info.get("sharesShort")
            prior_short = info.get("sharesShortPriorMonth")

            if short_pct is None and short_ratio is None and shares_short is None:
                return None

            change_pct = None
            if shares_short and prior_short and prior_short > 0:
                change_pct = round(
                    (shares_short - prior_short) / prior_short * 100, 1,
                )

            return {
                "short_interest": shares_short or 0,
                "short_float_pct": (
                    round(short_pct * 100, 2) if short_pct else None
                ),
                "days_to_cover": short_ratio,
                "settlement_date": info.get("dateShortInterest", ""),
                "previous_short_interest": prior_short or 0,
                "change_pct": change_pct,
                "_source": "yfinance_fallback",
            }
        except Exception:
            logger.debug("yfinance short interest fallback failed for %s", ticker)
            return None

    # ------------------------------------------------------------------
    # Insider Transactions — yfinance stock.insider_transactions
    # ------------------------------------------------------------------

    def get_insider_transactions(self, ticker: str) -> list[dict] | None:
        """Extract insider transactions from yfinance."""
        try:
            stock = self._yf_ticker(ticker)
            df = stock.insider_transactions

            if df is None or df.empty:
                return None

            transactions = []
            for _, row in df.head(10).iterrows():
                text = str(row.get("Text", "")).lower()
                shares = int(row.get("Shares", 0) or 0)
                value = int(row.get("Value", 0) or 0)

                # Determine transaction type from Text field
                if "purchase" in text or "buy" in text:
                    tx_type = "buy"
                    change = shares
                elif "sale" in text or "sell" in text:
                    tx_type = "sell"
                    change = -shares
                else:
                    tx_type = "other"
                    change = shares

                start_date = row.get("Start Date")
                date_str = str(start_date)[:10] if start_date is not None else ""

                transactions.append({
                    "name": str(row.get("Insider", "Unknown"))[:40],
                    "share": shares,
                    "change": change,
                    "transaction_type": tx_type,
                    "filing_date": date_str,
                    "transaction_date": date_str,
                    "position": str(row.get("Position", ""))[:40],
                    "value": value,
                    "_source": "yfinance_fallback",
                })

            return transactions if transactions else None
        except Exception:
            logger.debug("yfinance insider fallback failed for %s", ticker)
            return None

    # ------------------------------------------------------------------
    # Earnings — yfinance stock.earnings_dates + stock.earnings
    # ------------------------------------------------------------------

    def get_earnings(self, ticker: str) -> dict | None:
        """Extract earnings data from yfinance."""
        try:
            stock = self._yf_ticker(ticker)

            # Upcoming earnings from calendar
            upcoming = None
            try:
                cal = stock.calendar
                if cal and isinstance(cal, dict):
                    earnings_dates = cal.get("Earnings Date")
                    if earnings_dates:
                        if not isinstance(earnings_dates, list):
                            earnings_dates = [earnings_dates]
                        upcoming = {
                            "date": str(earnings_dates[0])[:10],
                            "eps_estimate": cal.get("Earnings Average"),
                            "revenue_estimate": cal.get("Revenue Average"),
                        }
            except Exception:
                pass

            # Recent earnings surprises
            surprises = []
            try:
                earnings = stock.earnings_history
                if earnings is not None and not earnings.empty:
                    for _, row in earnings.tail(4).iterrows():
                        actual = row.get("epsActual")
                        estimate = row.get("epsEstimate")
                        surprise_pct = row.get("surprisePercent")

                        surprises.append({
                            "period": str(row.get("quarter", ""))[:7],
                            "actual_eps": float(actual) if actual is not None else None,
                            "estimated_eps": float(estimate) if estimate is not None else None,
                            "surprise_pct": (
                                float(surprise_pct) if surprise_pct is not None else None
                            ),
                        })
            except Exception:
                pass

            if not upcoming and not surprises:
                return None

            return {
                "upcoming": upcoming,
                "recent_surprises": surprises,
                "beat_count": sum(
                    1 for s in surprises if (s.get("surprise_pct") or 0) > 0
                ),
                "miss_count": sum(
                    1 for s in surprises if (s.get("surprise_pct") or 0) < 0
                ),
                "_source": "yfinance_fallback",
            }
        except Exception:
            logger.debug("yfinance earnings fallback failed for %s", ticker)
            return None

    # ------------------------------------------------------------------
    # News — SearXNG web search (yfinance news is often empty)
    # ------------------------------------------------------------------

    def get_news(self, ticker: str) -> list[dict] | None:
        """Search for recent news articles via SearXNG."""
        try:
            client = self._get_http()
            resp = client.get(
                f"{SEARXNG_URL}/search",
                params={
                    "q": f"{ticker} stock news",
                    "format": "json",
                    "categories": "news",
                    "engines": "google,bing,duckduckgo",
                    "language": "en",
                    "pageno": 1,
                },
            )
            resp.raise_for_status()
            results = (resp.json().get("results") or [])[:10]
        except Exception:
            logger.debug("SearXNG news fallback failed for %s", ticker)
            return None

        if not results:
            return None

        articles = []
        for item in results:
            articles.append({
                "headline": item.get("title", ""),
                "summary": (item.get("content") or "")[:200],
                "source": item.get("engine", "web"),
                "datetime": (item.get("publishedDate") or "")[:19],
                "url": item.get("url", ""),
                "_source": "web_search",
            })
        return articles if articles else None

    # ------------------------------------------------------------------
    # Social Sentiment — SearXNG Reddit search + keyword scoring
    # ------------------------------------------------------------------

    def get_social_sentiment(self, ticker: str) -> dict | None:
        """Gauge social sentiment from Reddit discussions via SearXNG."""
        try:
            client = self._get_http()
            resp = client.get(
                f"{SEARXNG_URL}/search",
                params={
                    "q": f'"{ticker}" stock site:reddit.com',
                    "format": "json",
                    "categories": "general",
                    "engines": "google,bing,duckduckgo",
                    "language": "en",
                    "pageno": 1,
                },
            )
            resp.raise_for_status()
            results = (resp.json().get("results") or [])[:10]
        except Exception:
            logger.debug("SearXNG social sentiment fallback failed for %s", ticker)
            return None

        if not results:
            return None

        bullish_words = {
            "bull", "buy", "long", "moon", "undervalued",
            "breakout", "upside", "beat", "growth", "strong", "upgrade",
        }
        bearish_words = {
            "bear", "sell", "short", "crash", "overvalued", "downside",
            "miss", "decline", "weak", "downgrade", "warning", "risk",
        }

        positive = 0
        negative = 0
        total_mentions = len(results)

        for item in results:
            text = f"{item.get('title', '')} {item.get('content', '')}".lower()
            bull_count = sum(1 for w in bullish_words if w in text)
            bear_count = sum(1 for w in bearish_words if w in text)

            if bull_count > bear_count:
                positive += 1
            elif bear_count > bull_count:
                negative += 1

        total = positive + negative
        if total == 0:
            return None

        return {
            "reddit": {
                "mention": total_mentions,
                "positive_mention": positive,
                "negative_mention": negative,
                "score": round(positive / total, 3) if total > 0 else 0.5,
            },
            "aggregate": {
                "positive_ratio": round(positive / total, 3) if total > 0 else 0.5,
                "total_mentions": total_mentions,
                "bias": (
                    "bullish" if positive > negative * 1.5
                    else "bearish" if negative > positive * 1.5
                    else "neutral"
                ),
            },
            "_source": "web_search",
        }

    # ------------------------------------------------------------------
    # Filing context (fallback when edgartools fails)
    # ------------------------------------------------------------------

    def get_filing_context(self, ticker: str) -> dict | None:
        """Search for SEC filing summaries when edgartools can't parse them."""
        try:
            client = self._get_http()
            resp = client.get(
                f"{SEARXNG_URL}/search",
                params={
                    "q": f'"{ticker}" 10-K risk factors management discussion SEC',
                    "format": "json",
                    "categories": "general",
                    "engines": "google,bing,duckduckgo",
                    "language": "en",
                    "pageno": 1,
                },
            )
            resp.raise_for_status()
            results = (resp.json().get("results") or [])[:5]
        except Exception:
            logger.debug("SearXNG filing fallback failed for %s", ticker)
            return None

        if not results:
            return None

        risk_snippets = []
        mda_snippets = []

        for item in results:
            text = item.get("content", "")
            title = item.get("title", "").lower()

            if "risk" in title or "risk" in text.lower()[:100]:
                risk_snippets.append(text[:500])
            elif "management" in title or "md&a" in title:
                mda_snippets.append(text[:500])
            else:
                risk_snippets.append(text[:300])

        if not risk_snippets and not mda_snippets:
            return None

        return {
            "risk_factors": "\n".join(risk_snippets[:3])[:3000] or None,
            "mda": "\n".join(mda_snippets[:3])[:3000] or None,
            "filing_date": "",
            "filing_type": "web_search",
            "_source": "web_search",
        }


# Backward compatibility alias
WebSearchProvider = FallbackProvider
