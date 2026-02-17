"""WebSocket endpoint for live price updates."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from investmentology.api.auth import verify_token
from investmentology.api.deps import app_state

logger = logging.getLogger(__name__)

router = APIRouter()

PRICE_INTERVAL = 15  # seconds between price pushes


async def _fetch_prices(tickers: list[str]) -> dict[str, dict]:
    """Fetch current prices for tickers via yfinance. Runs in thread to avoid blocking."""
    if not tickers:
        return {}

    def _sync_fetch() -> dict[str, dict]:
        try:
            import yfinance as yf
            result = {}
            for ticker in tickers:
                try:
                    t = yf.Ticker(ticker)
                    info = t.fast_info
                    price = float(getattr(info, "last_price", 0) or 0)
                    prev = float(getattr(info, "previous_close", 0) or 0)
                    change = price - prev if prev else 0
                    change_pct = (change / prev * 100) if prev else 0
                    result[ticker] = {
                        "price": round(price, 2),
                        "change": round(change, 2),
                        "changePct": round(change_pct, 2),
                    }
                except Exception:
                    pass
            return result
        except ImportError:
            logger.warning("yfinance not installed, cannot fetch prices")
            return {}

    return await asyncio.to_thread(_sync_fetch)


@router.websocket("/ws/prices")
async def ws_prices(websocket: WebSocket):
    """Push live price updates for portfolio tickers every 15 seconds."""
    # Validate JWT from query param or cookie before accepting
    config = app_state.config
    if config and config.auth_secret_key:
        token = websocket.query_params.get("token") or websocket.cookies.get("session")
        if not token or not verify_token(token, config.auth_secret_key):
            await websocket.close(code=4001, reason="Not authenticated")
            return

    await websocket.accept()

    try:
        # Get portfolio tickers
        registry = app_state.registry
        if not registry:
            await websocket.send_json({"type": "error", "message": "Registry not available"})
            await websocket.close()
            return

        positions = registry.get_open_positions()
        tickers = [p.ticker for p in positions]

        if not tickers:
            await websocket.send_json({"type": "init", "prices": {}, "timestamp": datetime.utcnow().isoformat()})
            # Keep alive but no updates
            while True:
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=60)
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "ping"})
                except WebSocketDisconnect:
                    return

        # Initial price push
        prices = await _fetch_prices(tickers)
        await websocket.send_json({
            "type": "init",
            "prices": prices,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Periodic updates
        prev_prices = prices.copy()
        while True:
            try:
                # Wait for interval, but also listen for client messages
                await asyncio.wait_for(websocket.receive_text(), timeout=PRICE_INTERVAL)
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                return

            # Fetch latest prices
            new_prices = await _fetch_prices(tickers)

            # Only send deltas
            deltas: dict[str, dict] = {}
            for t, data in new_prices.items():
                if t not in prev_prices or prev_prices[t]["price"] != data["price"]:
                    deltas[t] = data

            if deltas:
                await websocket.send_json({
                    "type": "update",
                    "prices": deltas,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                prev_prices.update(deltas)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error")
        try:
            await websocket.close()
        except Exception:
            pass
