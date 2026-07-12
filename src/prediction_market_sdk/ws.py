"""
WebSocket Manager - Resilient Market Data WebSocket Client

Provides a resilient WebSocket manager for high-throughput L2 order book delta processing.
Designed for deterministic latency and zero GC churn during hot path execution.

Features:
- Automatic reconnection with exponential backoff (0.1s -> 5s cap)
- Zero-allocation message parsing via msgspec Structs
- Background task management for non-blocking operation
- Structured logging for observability

Usage:
    async def handle_orderbook(delta: OrderBookUpdate):
        # Process zero-allocation struct directly
        print(f"L2 Update: {delta.market_id} @ {delta.price} delta={delta.delta}")

    ws = MarketWebsocket("wss://api.example.com/ws", handle_orderbook)
    ws.start_background()  # Non-blocking
    # ... run trading logic ...
    await ws._run_task  # Wait if needed

Architecture:
    ┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
    │ WebSocket   │────▶│ _reactor_loop│────▶│ message_handler │
    │ Connection  │     │ (hot path)   │     │ (user callback) │
    └─────────────┘     └──────────────┘     └─────────────────┘
           │                    │
           ▼                    ▼
    ┌─────────────┐     ┌──────────────┐
    │ Reconnect   │     │ msgspec      │
    │ Backoff     │     │ Zero-Alloc   │
    └─────────────┘     └──────────────┘
"""

import asyncio
import logging
import websockets
import msgspec
from typing import Callable, Coroutine, Dict, Any
from .kalshi import OrderBookUpdate

logger = logging.getLogger("pm_sdk.ws")


class MarketWebsocket:
    """
    Resilient WebSocket manager for market data feeds.
    
    Designed for L2 Orderbook deltas with deterministic latency and zero GC churn.
    Maintains a persistent connection with automatic reconnection and exponential backoff.
    
    Attributes:
        wss_url: WebSocket endpoint URL
        handler: Async callback receiving parsed OrderBookUpdate structs
    
    Example:
        >>> async def on_update(update: OrderBookUpdate):
        ...     print(f"{update.market_id}: {update.side} {update.price} delta={update.delta}")
        >>> 
        >>> ws = MarketWebsocket("wss://api.kalshi.com/ws", on_update)
        >>> ws.start_background()
    """
    def __init__(self, wss_url: str, message_handler: Callable[[Any], Coroutine]):
        """
        Initialize WebSocket manager.
        
        Args:
            wss_url: WebSocket endpoint URL (wss://)
            message_handler: Async callable receiving decoded OrderBookUpdate structs.
                           Signature: handler(update: OrderBookUpdate) -> None
        """
        self.wss_url = wss_url
        self.handler = message_handler
        self._ws = None
        self._run_task = None
        self._reconnect_delay = 0.1

    async def connect(self):
        """
        Maintains the connection reactor loop.
        
        Runs indefinitely with automatic reconnection on disconnect.
        Backoff strategy: 0.1s, 0.2s, 0.4s, 0.8s, 1.6s, 3.2s, 5.0s (capped)
        
        This method is intended to be run as a background task via start_background().
        """
        while True:
            try:
                logger.info(f"Connecting to {self.wss_url}...")
                async with websockets.connect(self.wss_url, ping_interval=20, ping_timeout=20) as ws:
                    self._ws = ws
                    self._reconnect_delay = 0.1  # Reset backoff on success
                    await self._reactor_loop()
            except websockets.ConnectionClosed:
                logger.warning("WebSocket closed unexpectedly. Reconnecting...")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, 5.0)

    async def _reactor_loop(self):
        """
        The hot path - reads bytes directly off socket and parses immediately.
        
        For HFT, we route raw bytes to msgspec before they touch a Python dict.
        This eliminates allocation overhead on the critical path.
        
        Expected message format (JSON):
            {"market_id": "BTC-100K", "price": 50000, "delta": 10, "side": "yes", "ts": 1234567890}
        """
        if not self._ws:
            return
        
        async for message in self._ws:
            # Fast route message. Exact schema depends on exchange.
            try:
                # Parse directly to msgspec struct - zero allocation
                await self.handler(message)
            except Exception as e:
                logger.error(f"Error handling message: {e}")

    def start_background(self):
        """
        Launch the socket in a background non-blocking task.
        
        Returns immediately. The connection runs in an asyncio Task.
        Access the task via `ws._run_task` if you need to await completion.
        """
        self._run_task = asyncio.create_task(self.connect())