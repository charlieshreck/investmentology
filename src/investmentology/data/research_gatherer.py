"""Research data gatherer — collects raw material for Gemini research synthesis.

Gathers from:
- SearXNG: web search for news, Reddit discussions, event context
- yfinance: 90-day price history with significant move detection
- Finnhub: analyst ratings, short interest (via enricher)

The raw material is sent to Gemini (via HB proxy) for synthesis into
a structured research briefing that agents can use.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# SearXNG in the same K8s cluster (ai-platform namespace)
SEARXNG_URL = os.environ.get(
    "SEARXNG_URL",
    "http://searxng.ai-platform.svc.cluster.local:8080",
)

# Limits
MAX_SEARCH_RESULTS = 8
MAX_ARTICLE_CHARS = 3000
MAX_ARTICLES_TO_FETCH = 5
SIGNIFICANT_MOVE_PCT = 5.0  # Flag moves > 5%


class ResearchGatherer:
    """Gathers raw research material for a ticker."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._client

    async def gather(self, ticker: str, company_name: str) -> dict:
        """Gather all raw research material. Returns a dict of sections."""
        result: dict = {
            "ticker": ticker,
            "company_name": company_name,
            "articles": [],
            "reddit_posts": [],
            "price_events": [],
            "catalysts": [],
            "gathered_at": datetime.now().isoformat(),
        }

        # Run all gathering tasks, each failing independently
        await self._gather_news(ticker, company_name, result)
        await self._gather_reddit(ticker, company_name, result)
        await self._gather_price_events(ticker, result)
        await self._gather_catalysts(ticker, company_name, result)

        total_sources = (
            len(result["articles"])
            + len(result["reddit_posts"])
            + len(result["price_events"])
            + len(result["catalysts"])
        )
        logger.info(
            "Research gathered for %s: %d articles, %d reddit, %d price events, %d catalysts",
            ticker,
            len(result["articles"]),
            len(result["reddit_posts"]),
            len(result["price_events"]),
            len(result["catalysts"]),
        )
        return result if total_sources > 0 else {}

    async def _gather_news(
        self, ticker: str, company_name: str, result: dict,
    ) -> None:
        """Search for recent news articles and fetch their content."""
        try:
            client = await self._get_client()

            # Search for recent news
            search_results = await self._searxng_search(
                client,
                f'"{ticker}" OR "{company_name}" stock news',
                category="news",
                num_results=MAX_SEARCH_RESULTS,
            )

            articles = []
            fetched = 0
            for item in search_results:
                article = {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": item.get("engine", ""),
                    "published": item.get("publishedDate", ""),
                    "snippet": item.get("content", "")[:500],
                    "body": "",
                }

                # Fetch article body for top results
                if fetched < MAX_ARTICLES_TO_FETCH and item.get("url"):
                    body = await self._fetch_article_body(client, item["url"])
                    if body:
                        article["body"] = body[:MAX_ARTICLE_CHARS]
                        fetched += 1

                articles.append(article)

            result["articles"] = articles
        except Exception:
            logger.warning("News gathering failed for %s", ticker, exc_info=True)

    async def _gather_reddit(
        self, ticker: str, company_name: str, result: dict,
    ) -> None:
        """Search Reddit for discussions about this ticker."""
        try:
            client = await self._get_client()

            search_results = await self._searxng_search(
                client,
                f'"{ticker}" stock site:reddit.com',
                category="general",
                num_results=6,
            )

            posts = []
            for item in search_results:
                posts.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")[:500],
                })

            result["reddit_posts"] = posts
        except Exception:
            logger.warning("Reddit gathering failed for %s", ticker, exc_info=True)

    async def _gather_price_events(self, ticker: str, result: dict) -> None:
        """Detect significant price moves in the last 90 days."""
        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")

            if hist.empty:
                return

            events = []
            for i in range(1, len(hist)):
                prev_close = hist["Close"].iloc[i - 1]
                curr_close = hist["Close"].iloc[i]
                if prev_close == 0:
                    continue

                pct_change = ((curr_close - prev_close) / prev_close) * 100

                if abs(pct_change) >= SIGNIFICANT_MOVE_PCT:
                    date = hist.index[i].strftime("%Y-%m-%d")
                    events.append({
                        "date": date,
                        "pct_change": round(pct_change, 1),
                        "from_price": round(float(prev_close), 2),
                        "to_price": round(float(curr_close), 2),
                        "direction": "up" if pct_change > 0 else "down",
                        "volume": int(hist["Volume"].iloc[i]),
                    })

            # Sort by magnitude (largest moves first)
            events.sort(key=lambda e: abs(e["pct_change"]), reverse=True)
            result["price_events"] = events[:10]  # Top 10 moves

        except Exception:
            logger.warning("Price event detection failed for %s", ticker, exc_info=True)

    async def _gather_catalysts(
        self, ticker: str, company_name: str, result: dict,
    ) -> None:
        """Gather upcoming catalysts: earnings, dividends, scheduled events."""
        catalysts: list[dict] = []
        today = datetime.now().date()

        # 1. yfinance calendar (earnings date, ex-dividend, dividend date)
        try:
            import yfinance as yf

            stock = yf.Ticker(ticker)
            cal = stock.calendar
            if cal is not None:
                # yfinance returns a dict with keys like 'Earnings Date', 'Ex-Dividend Date', etc.
                cal_dict = cal if isinstance(cal, dict) else {}

                # Earnings date(s)
                earnings_dates = cal_dict.get("Earnings Date")
                if earnings_dates:
                    if not isinstance(earnings_dates, list):
                        earnings_dates = [earnings_dates]
                    for ed in earnings_dates:
                        date_str = str(ed)[:10]
                        try:
                            ed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                            days_away = (ed_date - today).days
                            if -7 <= days_away <= 90:
                                catalysts.append({
                                    "type": "earnings",
                                    "date": date_str,
                                    "days_away": days_away,
                                    "urgency": "high" if days_away <= 7 else "medium" if days_away <= 30 else "low",
                                    "description": f"Earnings report {'(PAST — just reported)' if days_away < 0 else ''}",
                                    "eps_estimate": cal_dict.get("Earnings Average"),
                                    "revenue_estimate": cal_dict.get("Revenue Average"),
                                })
                        except (ValueError, TypeError):
                            pass

                # Ex-dividend date
                ex_div = cal_dict.get("Ex-Dividend Date")
                if ex_div:
                    date_str = str(ex_div)[:10]
                    try:
                        ex_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        days_away = (ex_date - today).days
                        if -3 <= days_away <= 90:
                            div_amount = cal_dict.get("Dividend Rate")
                            catalysts.append({
                                "type": "dividend",
                                "date": date_str,
                                "days_away": days_away,
                                "urgency": "medium" if days_away <= 7 else "low",
                                "description": f"Ex-dividend date (${div_amount}/share)" if div_amount else "Ex-dividend date",
                            })
                    except (ValueError, TypeError):
                        pass

        except Exception:
            logger.warning("yfinance calendar failed for %s", ticker, exc_info=True)

        # 2. SearXNG search for upcoming events/catalysts
        try:
            client = await self._get_client()
            search_results = await self._searxng_search(
                client,
                f'"{ticker}" OR "{company_name}" upcoming catalyst OR FDA OR approval OR conference OR guidance 2026',
                category="news",
                num_results=5,
            )

            for item in search_results:
                title = item.get("title", "")
                snippet = item.get("content", "")[:300]
                published = item.get("publishedDate", "")

                # Only include if it mentions future/upcoming events
                text_lower = (title + " " + snippet).lower()
                future_keywords = {
                    "upcoming", "scheduled", "expected", "announce", "guidance",
                    "fda", "approval", "conference", "launch", "release",
                    "ipo", "spin-off", "merger", "acquisition", "trial",
                }
                if any(kw in text_lower for kw in future_keywords):
                    catalysts.append({
                        "type": "event",
                        "date": published[:10] if published else "",
                        "days_away": None,
                        "urgency": "medium",
                        "description": title[:120],
                        "source_snippet": snippet[:200],
                    })
        except Exception:
            logger.warning("Catalyst search failed for %s", ticker, exc_info=True)

        # Sort: urgent first, then by date
        urgency_order = {"high": 0, "medium": 1, "low": 2}
        catalysts.sort(key=lambda c: (urgency_order.get(c.get("urgency", "low"), 2), c.get("date", "z")))
        result["catalysts"] = catalysts[:15]

    async def _searxng_search(
        self,
        client: httpx.AsyncClient,
        query: str,
        category: str = "general",
        num_results: int = 8,
    ) -> list[dict]:
        """Execute a SearXNG search."""
        params = {
            "q": query,
            "format": "json",
            "categories": category,
            "language": "en",
            "pageno": 1,
        }

        response = await client.get(f"{SEARXNG_URL}/search", params=params)
        response.raise_for_status()
        data = response.json()
        return (data.get("results") or [])[:num_results]

    async def _fetch_article_body(
        self, client: httpx.AsyncClient, url: str,
    ) -> str:
        """Fetch and extract text from a news article URL."""
        try:
            response = await client.get(
                url,
                follow_redirects=True,
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"},
            )
            if response.status_code != 200:
                return ""

            # Basic HTML to text extraction
            text = response.text
            # Remove script and style tags
            import re
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            # Remove HTML tags
            text = re.sub(r"<[^>]+>", " ", text)
            # Clean whitespace
            text = re.sub(r"\s+", " ", text).strip()

            return text[:MAX_ARTICLE_CHARS] if text else ""
        except Exception:
            return ""

    def build_research_prompt(
        self, ticker: str, company_name: str, raw: dict,
    ) -> str:
        """Build the research prompt to send to Gemini."""
        parts = [
            f"Prepare a comprehensive research briefing for {ticker} ({company_name}).",
            f"Today's date: {datetime.now().strftime('%Y-%m-%d')}.",
            "",
        ]

        # News articles
        if raw.get("articles"):
            parts.append("## Recent News Articles")
            for i, article in enumerate(raw["articles"], 1):
                parts.append(f"\n### Article {i}: {article['title']}")
                if article.get("published"):
                    parts.append(f"Published: {article['published']}")
                if article.get("source"):
                    parts.append(f"Source: {article['source']}")
                if article.get("body"):
                    parts.append(f"Content:\n{article['body']}")
                elif article.get("snippet"):
                    parts.append(f"Snippet: {article['snippet']}")
            parts.append("")

        # Reddit discussions
        if raw.get("reddit_posts"):
            parts.append("## Reddit Discussions")
            for post in raw["reddit_posts"]:
                parts.append(f"- **{post['title']}**")
                if post.get("snippet"):
                    parts.append(f"  {post['snippet']}")
            parts.append("")

        # Price events
        if raw.get("price_events"):
            parts.append("## Significant Price Moves (last 90 days)")
            for event in raw["price_events"]:
                direction = "UP" if event["direction"] == "up" else "DOWN"
                parts.append(
                    f"- {event['date']}: {direction} {abs(event['pct_change'])}% "
                    f"(${event['from_price']} → ${event['to_price']}, "
                    f"volume: {event['volume']:,})"
                )
            parts.append("")

        # Upcoming catalysts
        if raw.get("catalysts"):
            parts.append("## Upcoming Catalysts & Scheduled Events")
            for cat in raw["catalysts"]:
                urgency_tag = f"[{cat.get('urgency', 'low').upper()}]" if cat.get("urgency") else ""
                date_str = cat.get("date", "TBD")
                days = cat.get("days_away")
                days_str = f" ({days}d away)" if days is not None else ""
                parts.append(
                    f"- {urgency_tag} {cat['type'].upper()}: {date_str}{days_str} — {cat.get('description', '')}"
                )
                if cat.get("eps_estimate"):
                    parts.append(f"  EPS estimate: {cat['eps_estimate']}")
                if cat.get("revenue_estimate"):
                    parts.append(f"  Revenue estimate: ${cat['revenue_estimate']:,.0f}" if isinstance(cat["revenue_estimate"], (int, float)) else f"  Revenue estimate: {cat['revenue_estimate']}")
                if cat.get("source_snippet"):
                    parts.append(f"  Context: {cat['source_snippet']}")
            parts.append("")

        parts.extend([
            "## Instructions",
            "Produce a research briefing with these sections:",
            "1. **KEY EVENTS**: What happened recently and why? Explain any major price moves with specific causes.",
            "2. **MANAGEMENT & BUSINESS**: Any management changes, strategic shifts, or business model developments?",
            "3. **ANALYST & MARKET VIEW**: What do analysts and the market think? Any notable upgrades/downgrades?",
            "4. **SENTIMENT**: What are retail investors and social media saying? Any unusual patterns?",
            "5. **RISKS & RED FLAGS**: What could go wrong that isn't obvious from the financial statements?",
            "6. **UPCOMING CATALYSTS**: What events in the next 1-3 months could move the stock?",
            "",
            "Be specific with dates, numbers, and attributions. Every sentence must contain a fact.",
            "If the data is thin for a section, say so — don't pad with generalities.",
        ])

        return "\n".join(parts)

    def build_fallback_briefing(self, ticker: str, raw: dict) -> str:
        """Build a minimal briefing from raw data when Gemini is unavailable."""
        parts = [f"Research briefing for {ticker} (auto-generated, Gemini unavailable):"]

        if raw.get("articles"):
            parts.append("\nRecent headlines:")
            for article in raw["articles"][:5]:
                parts.append(f"- {article['title']}")

        if raw.get("price_events"):
            parts.append("\nSignificant price moves:")
            for event in raw["price_events"][:5]:
                direction = "UP" if event["direction"] == "up" else "DOWN"
                parts.append(
                    f"- {event['date']}: {direction} {abs(event['pct_change'])}% "
                    f"(${event['from_price']} → ${event['to_price']})"
                )

        if raw.get("reddit_posts"):
            parts.append("\nReddit discussions:")
            for post in raw["reddit_posts"][:3]:
                parts.append(f"- {post['title']}")

        if raw.get("catalysts"):
            parts.append("\nUpcoming catalysts:")
            for cat in raw["catalysts"][:5]:
                date_str = cat.get("date", "TBD")
                parts.append(f"- {cat['type'].upper()} {date_str}: {cat.get('description', '')}")

        return "\n".join(parts)
