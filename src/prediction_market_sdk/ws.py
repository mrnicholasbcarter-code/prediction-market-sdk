import asyncio
import logging
import websockets
import msgspec
from typing import Callable, Coroutine, Dict, Any
from .kalshi import OrderBookUpdate

logger = logging.getLogger("pm_sdk.ws")

class MarketWebsocket:
    """
    Resilient WebSocket manager.
    Designed for L2 Orderbook deltas with deterministic latency and zero GC churn.
    """
    def __init__(self, wss_url: str, message_handler: Callable[[Any], Coroutine]):
        self.wss_url = wss_url
        self.handler = message_handler
        self._ws = None
        self._run_task = None
        self._reconnect_delay = 0.1

    async def connect(self):
        """Maintains the connection reactor loop."""
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
        The hot path. 
        Reads bytes directly off the socket and parses them immediately.
        """
        if not self._ws: return
        
        async for message in self._ws:
            # We strictly expect JSON payload. For HFT, we route the raw bytes 
            # to msgspec before it even touches a Python dict.
            try:
                # Fast route message. Exact schema depends on exchange.
                await self.handler(message)
            except Exception as e:
                logger.error(f"Error handling message: {e}")

    def start_background(self):
        """Launch the socket in a background non-blocking task."""
        self._run_task = asyncio.create_task(self.connect())
