"""ReAct Tool Catalog — read-only data tools for agent tool-use loops.

Each tool wraps an existing data function, exposes an OpenAI function-calling
schema, and returns JSON-serializable results.  All underlying calls are
synchronous and run via ``asyncio.to_thread`` in the executor.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _to_serializable(obj: Any) -> Any:
    """Recursively convert Decimals and other non-JSON types to primitives."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(v) for v in obj]
    return obj


@dataclass
class ToolDef:
    """A single tool definition."""

    name: str
    description: str
    parameters: dict  # JSON Schema for function parameters
    handler: Callable[..., Any]  # sync callable(*args) -> JSON-serializable


class ToolCatalog:
    """Registry of tools available to ReAct agents.

    Accepts pre-existing data source instances from the controller so we
    don't duplicate connections or API keys.
    """

    def __init__(
        self,
        yf_client=None,
        finnhub=None,
        fred=None,
    ) -> None:
        self._yf = yf_client
        self._finnhub = finnhub
        self._fred = fred
        self._tools: dict[str, ToolDef] = {}
        self._register_all()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def openai_schema(self) -> list[dict]:
        """Return the list of tools in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def handlers(self) -> dict[str, Callable]:
        """Return a name→handler mapping for the executor."""
        return {t.name: t.handler for t in self._tools.values()}

    async def execute(self, name: str, arguments: dict) -> str:
        """Execute a tool by name, returning JSON string result."""
        handler = self._tools.get(name)
        if handler is None:
            return json.dumps({"error": f"Unknown tool: {name}"})
        try:
            result = await asyncio.to_thread(handler.handler, **arguments)
            return json.dumps(_to_serializable(result))
        except Exception as e:
            logger.warning("Tool %s failed: %s", name, e)
            return json.dumps({"error": str(e)})

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def _register_all(self) -> None:
        self._register(ToolDef(
            name="get_technical_indicators",
            description=(
                "Get RSI, MACD, Bollinger Bands, ATR, OBV, SMA, volume metrics, "
                "and 52-week range for a stock ticker."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                },
                "required": ["ticker"],
            },
            handler=self._call_technical_indicators,
        ))

        self._register(ToolDef(
            name="get_price_history",
            description=(
                "Get recent OHLCV price history for a ticker. "
                "Returns last 20 rows of daily data."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "period": {
                        "type": "string",
                        "description": "History period (e.g. '3mo', '6mo', '1y')",
                        "default": "3mo",
                    },
                },
                "required": ["ticker"],
            },
            handler=self._call_price_history,
        ))

        self._register(ToolDef(
            name="get_fundamentals",
            description=(
                "Get key fundamentals: P/E, revenue, margins, market cap, debt, "
                "cash, growth rates, and valuation metrics."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                },
                "required": ["ticker"],
            },
            handler=self._call_fundamentals,
        ))

        self._register(ToolDef(
            name="get_market_snapshot",
            description=(
                "Get current market indices (SPY, QQQ, IWM), VIX, treasury yields, "
                "and sector ETF prices."
            ),
            parameters={"type": "object", "properties": {}},
            handler=self._call_market_snapshot,
        ))

        if self._fred:
            self._register(ToolDef(
                name="get_macro_context",
                description=(
                    "Get FRED macro data: GDP, CPI, unemployment, fed funds rate, "
                    "treasury yields, credit spreads, oil price."
                ),
                parameters={"type": "object", "properties": {}},
                handler=self._call_macro_context,
            ))

        self._register(ToolDef(
            name="get_pendulum_reading",
            description=(
                "Get current market pendulum (fear/greed composite) based on "
                "VIX, high-yield spreads, put/call ratio, and SPY trend."
            ),
            parameters={"type": "object", "properties": {}},
            handler=self._call_pendulum,
        ))

        if self._finnhub:
            self._register(ToolDef(
                name="get_news",
                description="Get recent news headlines and summaries for a ticker.",
                parameters={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    },
                    "required": ["ticker"],
                },
                handler=self._call_news,
            ))

            self._register(ToolDef(
                name="get_earnings",
                description=(
                    "Get earnings history (beat/miss record) and upcoming earnings date."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    },
                    "required": ["ticker"],
                },
                handler=self._call_earnings,
            ))

            self._register(ToolDef(
                name="get_analyst_ratings",
                description=(
                    "Get consensus analyst ratings, price targets, and recent upgrades/downgrades."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    },
                    "required": ["ticker"],
                },
                handler=self._call_analyst_ratings,
            ))

            self._register(ToolDef(
                name="get_insider_transactions",
                description="Get recent insider buys and sells for a ticker.",
                parameters={
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    },
                    "required": ["ticker"],
                },
                handler=self._call_insider_transactions,
            ))

    def _register(self, tool: ToolDef) -> None:
        self._tools[tool.name] = tool

    # ------------------------------------------------------------------
    # Tool handler implementations (all sync)
    # ------------------------------------------------------------------

    @staticmethod
    def _call_technical_indicators(ticker: str) -> dict:
        from investmentology.data.technical_indicators import (
            compute_technical_indicators,
        )
        result = compute_technical_indicators(ticker)
        if result is None:
            return {"error": f"No technical data available for {ticker}"}
        return result

    @staticmethod
    def _call_price_history(ticker: str, period: str = "3mo") -> dict:
        import yfinance as yf

        df = yf.download(ticker, period=period, progress=False)
        if df.empty:
            return {"error": f"No price data for {ticker}"}

        # Flatten MultiIndex columns if present
        if hasattr(df.columns, "levels"):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        # Return last 20 rows as list of dicts
        recent = df.tail(20)
        rows = []
        for date, row in recent.iterrows():
            rows.append({
                "date": str(date.date()),
                "open": round(float(row.get("Open", 0)), 2),
                "high": round(float(row.get("High", 0)), 2),
                "low": round(float(row.get("Low", 0)), 2),
                "close": round(float(row.get("Close", 0)), 2),
                "volume": int(row.get("Volume", 0)),
            })
        return {"ticker": ticker, "period": period, "data": rows}

    def _call_fundamentals(self, ticker: str) -> dict:
        if self._yf is None:
            return {"error": "YFinance client not available"}
        result = self._yf.get_fundamentals(ticker)
        if result is None:
            return {"error": f"No fundamentals for {ticker}"}
        # Strip internal keys
        return {
            k: v for k, v in result.items()
            if not k.startswith("_")
        }

    @staticmethod
    def _call_market_snapshot() -> dict:
        from investmentology.data.snapshots import fetch_market_snapshot
        return fetch_market_snapshot()

    def _call_macro_context(self) -> dict:
        if self._fred is None:
            return {"error": "FRED provider not available"}
        return self._fred.get_macro_context()

    @staticmethod
    def _call_pendulum() -> dict:
        from investmentology.data.pendulum_feeds import auto_pendulum_reading
        reading = auto_pendulum_reading()
        if reading is None:
            return {"error": "Pendulum reading unavailable (VIX data missing)"}
        return {
            "score": float(getattr(reading, "score", 0)),
            "label": getattr(reading, "label", "unknown"),
            "components": {
                k: float(v) if isinstance(v, (Decimal, float, int)) else str(v)
                for k, v in (getattr(reading, "components", None) or {}).items()
            },
        }

    def _call_news(self, ticker: str) -> dict:
        if self._finnhub is None:
            return {"error": "Finnhub provider not available"}
        return {"ticker": ticker, "articles": self._finnhub.get_news(ticker)}

    def _call_earnings(self, ticker: str) -> dict:
        if self._finnhub is None:
            return {"error": "Finnhub provider not available"}
        result = self._finnhub.get_earnings(ticker)
        if result is None:
            return {"error": f"No earnings data for {ticker}"}
        return result

    def _call_analyst_ratings(self, ticker: str) -> dict:
        if self._finnhub is None:
            return {"error": "Finnhub provider not available"}
        result = self._finnhub.get_analyst_ratings(ticker)
        if result is None:
            return {"error": f"No analyst ratings for {ticker}"}
        return result

    def _call_insider_transactions(self, ticker: str) -> dict:
        if self._finnhub is None:
            return {"error": "Finnhub provider not available"}
        txns = self._finnhub.get_insider_transactions(ticker)
        return {"ticker": ticker, "transactions": txns}
