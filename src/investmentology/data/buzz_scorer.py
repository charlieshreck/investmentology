"""Buzz scorer — measures news volume and headline sentiment per ticker.

Uses SearXNG (via external MCP) for broad web/news search, with Finnhub as fallback.
Computes:
- News volume (7d article counts from SearXNG + Finnhub)
- Simple headline sentiment (positive/negative keyword ratio)
- Normalized buzz score (0-100)
- Contrarian flag: low buzz + high fundamental score = potential mispricing
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

EXTERNAL_MCP_URL = os.environ.get(
    "EXTERNAL_MCP_URL", "https://external-mcp.agentic.kernow.io/mcp"
)

# Simple keyword-based headline sentiment
_POSITIVE_WORDS = frozenset({
    "beat", "beats", "exceeds", "surge", "surges", "rally", "rallies",
    "upgrade", "upgraded", "bullish", "outperform", "growth", "profit",
    "record", "strong", "positive", "gain", "gains", "boom", "soar",
    "soars", "raises", "raised", "optimistic", "buy", "breakout",
    "accelerate", "expand", "expansion", "dividend", "buyback",
})
_NEGATIVE_WORDS = frozenset({
    "miss", "misses", "decline", "declines", "downgrade", "downgraded",
    "bearish", "underperform", "loss", "losses", "weak", "negative",
    "crash", "plunge", "plunges", "cut", "cuts", "warning", "risk",
    "sell", "selloff", "slowdown", "recession", "layoff", "layoffs",
    "default", "bankruptcy", "fraud", "investigation", "probe", "fine",
})


def _headline_sentiment(headline: str) -> float:
    """Score a headline from -1.0 (bearish) to +1.0 (bullish)."""
    words = set(re.findall(r"[a-z]+", headline.lower()))
    pos = len(words & _POSITIVE_WORDS)
    neg = len(words & _NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def _buzz_label(score: float) -> str:
    if score >= 75:
        return "HIGH"
    if score >= 50:
        return "ELEVATED"
    if score >= 25:
        return "NORMAL"
    return "QUIET"


def _call_mcp_tool(tool_name: str, arguments: dict, timeout: float = 15.0) -> list[dict]:
    """Call an external MCP tool via JSON-RPC over SSE."""
    try:
        response = httpx.post(
            EXTERNAL_MCP_URL,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 1,
                "params": {"name": tool_name, "arguments": arguments},
            },
            headers={"Accept": "application/json, text/event-stream"},
            timeout=timeout,
        )
        if response.status_code != 200:
            return []

        # Parse SSE response — find the data line with result
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                result = data.get("result", {})
                content = result.get("content", [])
                for item in content:
                    if item.get("type") == "text":
                        return json.loads(item["text"])
        return []
    except Exception:
        logger.debug("MCP tool call failed: %s", tool_name)
        return []


def _searxng_news_search(ticker: str, num_results: int = 10) -> list[dict]:
    """Search for recent news via SearXNG through external MCP."""
    results = _call_mcp_tool(
        "websearch_search_news",
        {"query": f"{ticker} stock", "num_results": num_results, "time_range": "week"},
    )
    return [
        {
            "headline": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "source": r.get("source", ""),
            "url": r.get("url", ""),
            "published_date": r.get("published_date"),
        }
        for r in results
    ]


def _searxng_general_search(ticker: str, num_results: int = 10) -> list[dict]:
    """Search for general web mentions via SearXNG."""
    results = _call_mcp_tool(
        "websearch_search",
        {"query": f'"{ticker}" stock analysis OR investment', "num_results": num_results},
    )
    return [
        {
            "headline": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "url": r.get("url", ""),
        }
        for r in results
    ]


class BuzzScorer:
    """Compute buzz scores using SearXNG (via MCP) + Finnhub."""

    def __init__(self, finnhub_provider=None) -> None:
        self._finnhub = finnhub_provider

    def score_ticker(self, ticker: str) -> dict:
        """Compute buzz score for a single ticker.

        Returns dict with: news_count_7d, searxng_mentions, headline_sentiment,
        buzz_score, buzz_label, headlines, sources.
        """
        # Primary: SearXNG news search (broad coverage)
        searxng_news = _searxng_news_search(ticker, num_results=10)
        searxng_general = _searxng_general_search(ticker, num_results=10)

        # Secondary: Finnhub news (complementary)
        finnhub_news = []
        if self._finnhub:
            try:
                finnhub_news = self._finnhub.get_news(ticker, days=7)
            except Exception:
                pass

        # Combine unique headlines
        seen_headlines = set()
        all_headlines = []
        for source_name, items in [
            ("searxng_news", searxng_news),
            ("searxng_web", searxng_general),
            ("finnhub", finnhub_news),
        ]:
            for item in items:
                headline = item.get("headline", item.get("title", "")).strip()
                if headline and headline.lower() not in seen_headlines:
                    seen_headlines.add(headline.lower())
                    all_headlines.append({"headline": headline, "source": source_name})

        total_mentions = len(all_headlines)
        searxng_count = len(searxng_news) + len(searxng_general)

        # Headline sentiment
        sentiments = [_headline_sentiment(h["headline"]) for h in all_headlines]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

        # Buzz score: weighted combination
        # SearXNG news (broader reach) weighted more heavily
        volume_score = min(80, searxng_count * 4 + len(finnhub_news) * 5)

        # Recency bonus from SearXNG dates
        recency_bonus = 0
        now = datetime.now()
        for item in searxng_news:
            pub = item.get("published_date")
            if pub:
                try:
                    dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                    if (now - dt.replace(tzinfo=None)) < timedelta(hours=24):
                        recency_bonus += 5
                except (ValueError, TypeError):
                    pass
        recency_bonus = min(20, recency_bonus)

        buzz_score = min(100, volume_score + recency_bonus)

        return {
            "news_count_7d": total_mentions,
            "searxng_mentions": searxng_count,
            "finnhub_mentions": len(finnhub_news),
            "headline_sentiment": round(avg_sentiment, 3),
            "buzz_score": round(buzz_score, 1),
            "buzz_label": _buzz_label(buzz_score),
            "contrarian_flag": False,
            "headlines": [h["headline"] for h in all_headlines[:5]],
            "sources": list({h["source"] for h in all_headlines}),
        }

    def score_watchlist(self, tickers: list[str], registry=None) -> dict[str, dict]:
        """Score all watchlist tickers in parallel and optionally persist to DB."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        _empty = {
            "news_count_7d": 0, "searxng_mentions": 0, "finnhub_mentions": 0,
            "headline_sentiment": 0.0, "buzz_score": 0.0, "buzz_label": "QUIET",
            "contrarian_flag": False,
        }
        results: dict[str, dict] = {}

        def _score_one(ticker: str) -> tuple[str, dict]:
            try:
                return ticker, self.score_ticker(ticker)
            except Exception:
                logger.debug("Failed to score buzz for %s", ticker)
                return ticker, dict(_empty)

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(_score_one, t): t for t in tickers}
            for future in as_completed(futures):
                try:
                    ticker, score = future.result(timeout=15)
                except Exception:
                    ticker = futures[future]
                    score = dict(_empty)
                results[ticker] = score

        # Post-process: contrarian flags and persistence (fast, serial is fine)
        for ticker, score in results.items():
            if registry and score["buzz_score"] < 25:
                try:
                    rows = registry._db.execute(
                        """SELECT verdict FROM invest.verdicts
                           WHERE ticker = %s ORDER BY created_at DESC LIMIT 1""",
                        (ticker,),
                    )
                    if rows and rows[0]["verdict"] in ("STRONG_BUY", "BUY", "ACCUMULATE"):
                        score["contrarian_flag"] = True
                except Exception:
                    pass

            if registry:
                try:
                    registry._db.execute(
                        """INSERT INTO invest.buzz_scores
                           (ticker, news_count_7d, news_count_30d, headline_sentiment,
                            buzz_score, buzz_label, contrarian_flag, details)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
                        (
                            ticker,
                            score["news_count_7d"],
                            0,
                            score["headline_sentiment"],
                            score["buzz_score"],
                            score["buzz_label"],
                            score.get("contrarian_flag", False),
                            json.dumps({
                                "headlines": score.get("headlines", []),
                                "sources": score.get("sources", []),
                            }),
                        ),
                    )
                except Exception:
                    logger.debug("Failed to persist buzz score for %s", ticker)

        return results
