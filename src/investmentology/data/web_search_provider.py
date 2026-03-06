"""Web search fallback provider — uses SearXNG when Finnhub/EDGAR return nothing.

For tickers with limited coverage on Finnhub's free tier (small-caps, MLPs,
foreign ADRs, etc.), this provider scrapes structured data from financial
sites via SearXNG search snippets.

Each method returns the same shape as the corresponding Finnhub/EDGAR method
so data flows seamlessly through the enrichment pipeline.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

SEARXNG_URL = os.environ.get(
    "SEARXNG_URL",
    "http://searxng.ai-platform.svc.cluster.local:8080",
)

# Target financial sites for structured data extraction
ANALYST_SITES = "site:marketbeat.com OR site:tipranks.com OR site:zacks.com OR site:wsj.com"
SHORT_INTEREST_SITES = "site:finviz.com OR site:marketbeat.com OR site:nasdaq.com"
INSIDER_SITES = "site:openinsider.com OR site:secform4.com OR site:dataroma.com OR site:finviz.com"
EARNINGS_SITES = "site:earningswhispers.com OR site:zacks.com OR site:nasdaq.com"

_TIMEOUT = httpx.Timeout(15.0)
_MAX_RESULTS = 8


class WebSearchProvider:
    """SearXNG-based fallback for enrichment data when primary providers fail."""

    def __init__(self) -> None:
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=_TIMEOUT)
        return self._client

    def _search(
        self,
        query: str,
        category: str = "general",
        num_results: int = _MAX_RESULTS,
    ) -> list[dict]:
        """Execute a SearXNG search and return results."""
        try:
            client = self._get_client()
            resp = client.get(
                f"{SEARXNG_URL}/search",
                params={
                    "q": query,
                    "format": "json",
                    "categories": category,
                    "language": "en",
                    "pageno": 1,
                },
            )
            resp.raise_for_status()
            return (resp.json().get("results") or [])[:num_results]
        except Exception:
            logger.debug("SearXNG search failed: %s", query[:80], exc_info=True)
            return []

    # ------------------------------------------------------------------
    # News (fallback when Finnhub has no news for ticker)
    # ------------------------------------------------------------------

    def get_news(self, ticker: str) -> list[dict] | None:
        """Search for recent news articles about a ticker."""
        results = self._search(
            f'"{ticker}" stock news analysis',
            category="news",
            num_results=10,
        )
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
    # Analyst Ratings (buy/hold/sell consensus + price targets)
    # ------------------------------------------------------------------

    def get_analyst_ratings(self, ticker: str) -> dict | None:
        """Extract analyst consensus from financial sites.

        Searches MarketBeat, TipRanks, Zacks for buy/hold/sell counts
        and price targets from search snippets.
        """
        results = self._search(
            f"{ticker} analyst ratings consensus price target {ANALYST_SITES}",
        )
        if not results:
            return None

        # Parse structured data from snippets
        trends = []
        target = {}
        recent_changes = []

        for item in results:
            text = f"{item.get('title', '')} {item.get('content', '')}".lower()

            # Extract price target numbers
            target_matches = re.findall(
                r"(?:price\s+target|target\s+price|average\s+target)[:\s]*\$?([\d,.]+)",
                text,
            )
            high_matches = re.findall(
                r"(?:high|highest)[:\s]*\$?([\d,.]+)",
                text,
            )
            low_matches = re.findall(
                r"(?:low|lowest)[:\s]*\$?([\d,.]+)",
                text,
            )

            # Extract buy/hold/sell counts
            buy_match = re.search(r"(\d+)\s*buy", text)
            hold_match = re.search(r"(\d+)\s*hold", text)
            sell_match = re.search(r"(\d+)\s*sell", text)

            if buy_match or hold_match or sell_match:
                trends.append({
                    "period": datetime.now().strftime("%Y-%m"),
                    "strong_buy": 0,
                    "buy": int(buy_match.group(1)) if buy_match else 0,
                    "hold": int(hold_match.group(1)) if hold_match else 0,
                    "sell": int(sell_match.group(1)) if sell_match else 0,
                    "strong_sell": 0,
                    "_source": "web_search",
                })

            if target_matches and not target:
                try:
                    mean_val = float(target_matches[0].replace(",", ""))
                    target = {
                        "mean": mean_val,
                        "median": mean_val,
                        "high": float(high_matches[0].replace(",", "")) if high_matches else None,
                        "low": float(low_matches[0].replace(",", "")) if low_matches else None,
                    }
                except (ValueError, IndexError):
                    pass

            # Extract upgrades/downgrades
            upgrade_match = re.search(
                r"(upgraded?|downgraded?|initiated?|reiterated?)\s+(?:from\s+)?(\w+)\s+(?:to\s+)?(\w+)",
                text,
            )
            if upgrade_match:
                recent_changes.append({
                    "firm": item.get("title", "")[:40],
                    "action": upgrade_match.group(1),
                    "from_grade": upgrade_match.group(2),
                    "to_grade": upgrade_match.group(3),
                    "date": (item.get("publishedDate") or "")[:10],
                    "_source": "web_search",
                })

        if not trends and not target and not recent_changes:
            return None

        return {
            "trends": trends[:4],
            "price_target": target or None,
            "recent_changes": recent_changes[:5],
            "_source": "web_search",
        }

    # ------------------------------------------------------------------
    # Short Interest
    # ------------------------------------------------------------------

    def get_short_interest(self, ticker: str) -> dict | None:
        """Extract short interest data from Finviz, MarketBeat, Nasdaq."""
        results = self._search(
            f"{ticker} short interest float days to cover {SHORT_INTEREST_SITES}",
        )
        if not results:
            return None

        for item in results:
            text = f"{item.get('title', '')} {item.get('content', '')}".lower()

            # Extract short float percentage
            float_match = re.search(
                r"short\s*(?:%\s*of\s*)?float[:\s]*([\d.]+)%",
                text,
            )
            interest_match = re.search(
                r"short\s*interest[:\s]*([\d,.]+[kmb]?)\s*(?:shares)?",
                text,
            )
            dtc_match = re.search(
                r"(?:days?\s*to\s*cover|short\s*ratio)[:\s]*([\d.]+)",
                text,
            )

            if float_match or interest_match:
                short_pct = float(float_match.group(1)) if float_match else None
                short_shares = None
                if interest_match:
                    val_str = interest_match.group(1).replace(",", "")
                    try:
                        multiplier = 1
                        if val_str.endswith("k"):
                            multiplier = 1_000
                            val_str = val_str[:-1]
                        elif val_str.endswith("m"):
                            multiplier = 1_000_000
                            val_str = val_str[:-1]
                        elif val_str.endswith("b"):
                            multiplier = 1_000_000_000
                            val_str = val_str[:-1]
                        short_shares = int(float(val_str) * multiplier)
                    except (ValueError, TypeError):
                        pass

                return {
                    "short_interest": short_shares or 0,
                    "short_float_pct": short_pct,
                    "days_to_cover": float(dtc_match.group(1)) if dtc_match else None,
                    "settlement_date": "",
                    "previous_short_interest": 0,
                    "change_pct": None,
                    "_source": "web_search",
                }

        return None

    # ------------------------------------------------------------------
    # Social Sentiment (Reddit + broader social)
    # ------------------------------------------------------------------

    def get_social_sentiment(self, ticker: str) -> dict | None:
        """Gauge social sentiment from Reddit discussions via SearXNG."""
        results = self._search(
            f'"{ticker}" stock site:reddit.com',
            num_results=10,
        )
        if not results:
            # Broaden search
            results = self._search(
                f'"{ticker}" stock discussion sentiment',
                num_results=6,
            )
        if not results:
            return None

        positive = 0
        negative = 0
        neutral = 0
        total_mentions = len(results)

        bullish_words = {
            "bull", "buy", "long", "moon", "rocket", "undervalued",
            "breakout", "upside", "beat", "growth", "strong", "upgrade",
        }
        bearish_words = {
            "bear", "sell", "short", "crash", "overvalued", "downside",
            "miss", "decline", "weak", "downgrade", "warning", "risk",
        }

        for item in results:
            text = f"{item.get('title', '')} {item.get('content', '')}".lower()
            bull_count = sum(1 for w in bullish_words if w in text)
            bear_count = sum(1 for w in bearish_words if w in text)

            if bull_count > bear_count:
                positive += 1
            elif bear_count > bull_count:
                negative += 1
            else:
                neutral += 1

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
    # Insider Transactions
    # ------------------------------------------------------------------

    def get_insider_transactions(self, ticker: str) -> list[dict] | None:
        """Search for insider trading data from OpenInsider/Finviz."""
        results = self._search(
            f"{ticker} insider trading transactions {INSIDER_SITES}",
        )
        if not results:
            return None

        transactions = []
        for item in results:
            text = f"{item.get('title', '')} {item.get('content', '')}".lower()

            # Look for buy/sell transaction patterns
            tx_match = re.search(
                r"(purchase|sale|buy|sell)[:\s]*([\d,.]+)\s*shares?\s*(?:at|@)?\s*\$?([\d,.]+)?",
                text,
            )
            name_match = re.search(
                r"(ceo|cfo|coo|director|officer|chairman|president|vp|insider|10%)\s*[-:,]?\s*(\w[\w\s]{2,30})",
                text,
            )

            if tx_match:
                tx_type = "buy" if tx_match.group(1) in ("purchase", "buy") else "sell"
                try:
                    share_count = int(float(tx_match.group(2).replace(",", "")))
                except (ValueError, TypeError):
                    share_count = 0

                transactions.append({
                    "name": name_match.group(2).strip()[:30] if name_match else "Insider",
                    "share": share_count,
                    "change": share_count if tx_type == "buy" else -share_count,
                    "transaction_type": tx_type,
                    "filing_date": (item.get("publishedDate") or "")[:10],
                    "transaction_date": "",
                    "_source": "web_search",
                })

        return transactions[:10] if transactions else None

    # ------------------------------------------------------------------
    # Earnings
    # ------------------------------------------------------------------

    def get_earnings(self, ticker: str) -> dict | None:
        """Search for upcoming earnings date and recent results."""
        results = self._search(
            f"{ticker} earnings date estimate EPS {EARNINGS_SITES}",
        )
        if not results:
            return None

        upcoming = None
        surprises = []

        for item in results:
            text = f"{item.get('title', '')} {item.get('content', '')}".lower()

            # Extract earnings date
            date_match = re.search(
                r"(?:earnings|report|results)\s+(?:date|on|expected|scheduled)[:\s]*"
                r"(\w+ \d+,?\s*\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})",
                text,
            )
            if date_match and not upcoming:
                upcoming = {
                    "date": date_match.group(1),
                    "eps_estimate": None,
                    "revenue_estimate": None,
                }
                # Try to extract EPS estimate
                eps_match = re.search(
                    r"eps\s*(?:estimate|forecast|expected|consensus)[:\s]*\$?([\d.]+)",
                    text,
                )
                if eps_match:
                    try:
                        upcoming["eps_estimate"] = float(eps_match.group(1))
                    except ValueError:
                        pass

            # Extract beat/miss info
            beat_match = re.search(
                r"(beat|miss(?:ed)?|met)\s+(?:eps\s+)?(?:estimates?|expectations?|consensus)\s*(?:by\s+\$?([\d.]+))?",
                text,
            )
            if beat_match:
                surprises.append({
                    "period": (item.get("publishedDate") or "")[:7],
                    "actual_eps": None,
                    "estimated_eps": None,
                    "surprise_pct": None,
                    "result": beat_match.group(1),
                    "_source": "web_search",
                })

        if not upcoming and not surprises:
            return None

        return {
            "upcoming": upcoming,
            "recent_surprises": surprises[:4],
            "beat_count": sum(1 for s in surprises if s.get("result") == "beat"),
            "miss_count": sum(1 for s in surprises if "miss" in (s.get("result") or "")),
            "_source": "web_search",
        }

    # ------------------------------------------------------------------
    # Filing context (fallback when edgartools fails)
    # ------------------------------------------------------------------

    def get_filing_context(self, ticker: str) -> dict | None:
        """Search for SEC filing summaries when edgartools can't parse them."""
        results = self._search(
            f'"{ticker}" 10-K OR 10-Q risk factors management discussion SEC filing',
            num_results=5,
        )
        if not results:
            return None

        risk_snippets = []
        mda_snippets = []

        for item in results:
            text = item.get("content", "")
            title = item.get("title", "").lower()

            if "risk" in title or "risk" in text.lower()[:100]:
                risk_snippets.append(text[:500])
            elif "management" in title or "md&a" in title or "discussion" in text.lower()[:100]:
                mda_snippets.append(text[:500])
            else:
                # General filing snippet
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
