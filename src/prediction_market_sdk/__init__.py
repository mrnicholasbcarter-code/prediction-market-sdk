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
    KalshiClient,
    OrderBookUpdate,
    OrderResponse,
    PredictionMarketError,
    AuthConfigurationError,
    ForbiddenError,
    RateLimitExceeded,
    InsufficientFunds,
    ExchangeServerError,
)
from .polymarket import (
    PolymarketClient,
    PolymarketOrderResponse,
    PredictionMarketError as PolymarketError,
    AuthConfigurationError as PolymarketAuthError,
    ForbiddenError as PolymarketForbiddenError,
    RateLimitExceeded as PolymarketRateLimitError,
    ExchangeServerError as PolymarketServerError,
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
]

__version__ = "0.1.0"