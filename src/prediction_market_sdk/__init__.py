"""
Prediction Market SDK - High-Speed Exchange SDK for Kalshi & Polymarket

This package provides ultra-low latency Python SDKs for prediction market exchanges.
It uses msgspec for zero-allocation parsing and httpx/websockets for async I/O.

Modules:
- kalshi: Kalshi REST client with RSA-PSS signing
- polymarket: Polymarket CLOB REST client with L2 auth
- ws: Resilient WebSocket manager for orderbook deltas
"""

from .kalshi import (
    AuthConfigurationError,
    ExchangeServerError,
    ForbiddenError,
    InsufficientFunds,
    KalshiClient,
    OrderBookUpdate,
    OrderResponse,
    PredictionMarketError,
    RateLimitExceeded,
)
from .orderbook import OrderBook, OrderBookError
from .orderbook import OrderBookUpdate as OrderBookUpdate
from .polymarket import (
    AuthConfigurationError as PolymarketAuthError,
)
from .polymarket import (
    ExchangeServerError as PolymarketServerError,
)
from .polymarket import (
    ForbiddenError as PolymarketForbiddenError,
)
from .polymarket import (
    PolymarketClient,
    PolymarketOrderResponse,
)
from .polymarket import (
    PredictionMarketError as PolymarketError,
)
from .polymarket import (
    RateLimitExceeded as PolymarketRateLimitError,
)
from .ws import MarketWebsocket

__all__ = [
    # Kalshi
    "KalshiClient",
    "OrderBookUpdate",
    "OrderResponse",
    "PredictionMarketError",
    "AuthConfigurationError",
    "ForbiddenError",
    "RateLimitExceeded",
    "InsufficientFunds",
    "ExchangeServerError",
    # Polymarket
    "PolymarketClient",
    "PolymarketOrderResponse",
    "PolymarketError",
    "PolymarketAuthError",
    "PolymarketForbiddenError",
    "PolymarketRateLimitError",
    "PolymarketServerError",
    # WebSocket
    "MarketWebsocket",
    # OrderBook core
    "OrderBook",
    "OrderBookError",
]

__version__ = "0.1.0"
