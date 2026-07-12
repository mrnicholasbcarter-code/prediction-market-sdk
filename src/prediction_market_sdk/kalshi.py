"""
Kalshi REST Client - High-Frequency Async SDK

Provides an ultra-low latency async client for Kalshi's trading API.
Features:
- RSA-PSS SHA-256 request signing (Kalshi auth spec)
- Connection pooling via httpx.AsyncClient
- Automatic retry with exponential backoff for 429/5xx
- Zero-allocation response parsing via msgspec Structs
- Comprehensive exception taxonomy mapping HTTP codes to SDK exceptions

Usage:
    client = KalshiClient(key_id="...", private_key_pem="...", env="paper")
    balance = await client.get_balance()
    order = await client.submit_order("BTC-100K", "buy", "yes", 1, 50)
    await client.session.aclose()

Authentication:
    Kalshi uses RSA-PSS signatures with headers:
    - KALSHI-ACCESS-KEY: key_id
    - KALSHI-ACCESS-SIGNATURE: base64(RSA-PSS-SHA256(timestamp + method + path))
    - KALSHI-ACCESS-TIMESTAMP: milliseconds since epoch

    The private key is loaded once at initialization and cached in memory.
    Invalid PEM raises AuthConfigurationError immediately.
"""

import asyncio
import base64
import random
from datetime import datetime, timezone
from typing import Literal

import httpx
import msgspec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

# ---------------------------------------------------------
# Zero-allocation msgspec Models (HFT Limit Order Book / Ticks)
# ---------------------------------------------------------


class OrderBookUpdate(msgspec.Struct, gc=False):
    """
    Zero-allocation order book delta struct.

    Used for HFT L2 orderbook delta processing. gc=False disables
    Python GC tracking for maximum throughput on hot paths.

    Fields:
        market_id: Exchange market identifier (e.g., "KXBTC-100K")
        price: Price level in cents (e.g., 4500 = $45.00)
        delta: Signed quantity change at this price level
        side: Contract side - "yes" or "no"
        ts: Exchange timestamp in milliseconds since epoch
    """

    market_id: str
    price: int
    delta: int
    side: Literal["yes", "no"]
    ts: int


class OrderResponse(msgspec.Struct, gc=False):
    """
    Zero-allocation order acknowledgement struct.

    Maps directly to Kalshi's POST /portfolio/orders response.
    gc=False for zero-GC overhead on order submission hot path.

    Fields:
        order_id: Exchange-assigned order identifier
        ticker: Market ticker symbol
        client_order_id: Client-supplied order ID echoed back
        action: Order action ("buy" or "sell")
        status: Order status ("resting", "filled", "cancelled", etc.)
        price: Limit price in cents
    """

    order_id: str
    ticker: str
    client_order_id: str
    action: str
    status: str
    price: int


# ---------------------------------------------------------
# Exception Taxonomy
# ---------------------------------------------------------


class PredictionMarketError(Exception):
    """Base exception for all SDK errors."""

    pass


class AuthConfigurationError(PredictionMarketError):
    """
    Raised when authentication configuration is invalid.

    Triggers:
    - Invalid PEM format on client initialization
    - HTTP 401 response from exchange
    """

    pass


class ForbiddenError(PredictionMarketError):
    """
    Raised on HTTP 403 - permission/entitlement failure.

    Indicates valid auth but insufficient permissions for the operation.
    """

    pass


class RateLimitExceeded(PredictionMarketError):
    """
    Raised on HTTP 429 - exchange rate limit exceeded.

    Clients should implement exponential backoff when catching this.
    """

    pass


class InsufficientFunds(PredictionMarketError):
    """
    Raised when order submission fails due to insufficient buying power.

    Reserved for future use when exchange returns specific insufficient funds code.
    """

    pass


class ExchangeServerError(PredictionMarketError):
    """
    Raised on HTTP 5xx - exchange-side server error.

    Indicates temporary exchange unavailability. Safe to retry with backoff.
    """

    pass


# ---------------------------------------------------------
# Client Architecture
# ---------------------------------------------------------


class KalshiClient:
    """
    High-frequency async Kalshi REST Client.

    Employs connection pooling, RSA-PSS signatures, and rigorous rate-limiting.
    All methods are async and thread-safe for concurrent use.

    Attributes:
        base_url: Resolved exchange base URL for the environment
        session: httpx.AsyncClient session (call aclose() when done)
        key_id: Kalshi API key identifier

    Example:
        >>> client = KalshiClient("key_id", "private_key_pem", "paper")
        >>> balance = await client.get_balance()
        >>> order = await client.submit_order("BTC-100K", "buy", "yes", 1, 5000)
        >>> await client.session.aclose()
    """

    def __init__(
        self, key_id: str, private_key_pem: str, env: Literal["paper", "demo", "live"] = "paper"
    ):
        """
        Initialize Kalshi client.

        Args:
            key_id: Kalshi API key identifier (sent as KALSHI-ACCESS-KEY header)
            private_key_pem: PEM-encoded RSA private key for request signing.
                Loaded once at init; invalid PEM raises AuthConfigurationError.
            env: Trading environment:
                - "live": https://trading-api.kalshi.com/trade-api/v2
                - "paper"/"demo": https://demo-api.kalshi.co/trade-api/v2

        Raises:
            AuthConfigurationError: If private_key_pem is invalid PEM format
        """
        self.key_id = key_id

        # Security Boundary: RSA Key initialized into memory once
        try:
            self.rsa_key = load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
        except Exception as e:
            raise AuthConfigurationError("Failed to parse RSA Private Key PEM") from e

        # DNS mapping based on 3-environment state
        if env == "live":
            self.base_url = "https://trading-api.kalshi.com/trade-api/v2"
        else:
            self.base_url = "https://demo-api.kalshi.co/trade-api/v2"

        self.session = httpx.AsyncClient(base_url=self.base_url)

    def _generate_rsa_headers(self, method: str, path: str) -> dict:
        """
        Calculate instantaneous RSA-PSS SHA-256 signature required by exchange.

        Performance budget: <10µs per signature generation.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (e.g., "/portfolio/balance")

        Returns:
            Dict with KALSHI-ACCESS-KEY, KALSHI-ACCESS-SIGNATURE, KALSHI-ACCESS-TIMESTAMP
        """
        timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        msg_string = timestamp + method.upper() + path

        signature = self.rsa_key.sign(
            msg_string.encode("utf-8"),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )

        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("utf-8"),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }

    @staticmethod
    def _raise_for_status(res: httpx.Response, action: str) -> None:
        """
        Map Kalshi HTTP failures to stable SDK exceptions.

        Args:
            res: httpx.Response object
            action: Human-readable action description for error messages

        Raises:
            AuthConfigurationError: HTTP 401
            ForbiddenError: HTTP 403
            RateLimitExceeded: HTTP 429
            ExchangeServerError: HTTP 5xx
            PredictionMarketError: Other HTTP 4xx or unexpected errors
        """
        if res.status_code < 400:
            return

        detail = f"Kalshi {action} failed with HTTP {res.status_code}: {res.text}"
        if res.status_code == 401:
            raise AuthConfigurationError(detail)
        if res.status_code == 403:
            raise ForbiddenError(detail)
        if res.status_code == 429:
            raise RateLimitExceeded(detail)
        if res.status_code >= 500:
            raise ExchangeServerError(detail)
        raise PredictionMarketError(detail)

    async def _request_with_retry(
        self, method: str, path: str, action: str, **kwargs
    ) -> httpx.Response:
        """
        Execute HTTP request with automatic retry on transient failures with jitter.

        Retries on: 429 (rate limit), 500, 502, 503, 504 (server errors)
        Max retries: 3 with exponential backoff + jitter

        Args:
            method: HTTP method
            path: Request path
            action: Action description for error messages
            **kwargs: Additional arguments passed to httpx request

        Returns:
            httpx.Response on success

        Raises:
            ExchangeServerError: After max retries exhausted
            Various SDK exceptions: For non-retryable HTTP errors
        """
        max_retries = 3
        for attempt in range(max_retries):
            base_delay = 0.1 * (2**attempt)
            # Add jitter: 0-100ms to each retry
            delay = base_delay + (random.random() * 0.1)

            headers = self._generate_rsa_headers(method.upper(), path)
            req_kwargs = kwargs.copy()
            req_headers = req_kwargs.pop("headers", {})
            headers.update(req_headers)

            try:
                res = await self.session.request(method, path, headers=headers, **req_kwargs)
                if res.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    continue
                self._raise_for_status(res, action)
                return res
            except httpx.TimeoutException as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    continue
                raise ExchangeServerError(f"Kalshi {action} failed with timeout: {e!s}") from e
        raise ExchangeServerError(f"Kalshi {action} failed after max retries")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.aclose()

    async def get_balance(self) -> float:
        """
        Fetch real-time portfolio balance.

        Calls GET /portfolio/balance and converts cents to dollars.

        Returns:
            float: Account balance in dollars (e.g., 1234.56)

        Raises:
            AuthConfigurationError: HTTP 401 - invalid credentials
            ForbiddenError: HTTP 403 - insufficient permissions
            RateLimitExceeded: HTTP 429 - rate limited
            ExchangeServerError: HTTP 5xx - exchange unavailable
            PredictionMarketError: Other HTTP errors
        """
        res = await self._request_with_retry("GET", "/portfolio/balance", action="balance request")

        data = res.json()
        return data.get("balance", 0) / 100.0  # Convert cents to dollars

    async def submit_order(
        self, ticker: str, action: str, side: str, count: int, price: int
    ) -> OrderResponse:
        """
        Submit a limit order mapped against the msgspec response struct.

        Calls POST /portfolio/orders with limit order payload.

        Args:
            ticker: Kalshi market ticker (e.g., "KXBTC-100K")
            action: "buy" or "sell"
            side: "yes" or "no" - determines which price field is sent
            count: Number of contracts
            price: Limit price in cents (e.g., 5000 = $50.00)

        Returns:
            OrderResponse: Typed order acknowledgement struct

        Raises:
            AuthConfigurationError: HTTP 401
            ForbiddenError: HTTP 403
            RateLimitExceeded: HTTP 429
            ExchangeServerError: HTTP 5xx
            InsufficientFunds: Reserved for insufficient buying power
            PredictionMarketError: Other errors or malformed exchange response
        """
        payload = {
            "action": action,
            "side": side,
            "count": count,
            "type": "limit",
            "yes_price": price if side == "yes" else None,
            "no_price": price if side == "no" else None,
            "ticker": ticker,
        }

        # Clean nulls
        payload = {k: v for k, v in payload.items() if v is not None}

        path = "/portfolio/orders"
        res = await self._request_with_retry("POST", path, action="order submission", json=payload)

        # Zero-allocation deserialization
        try:
            return msgspec.json.decode(res.content, type=OrderResponse)
        except Exception as e:
            raise PredictionMarketError(f"Unexpected exchange payload: {res.text}") from e
