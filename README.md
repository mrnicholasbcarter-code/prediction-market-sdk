<div align="center">
  <h1>Prediction Market SDK</h1>
  <p><strong>Ultra-Low Latency Python SDK for Kalshi & Polymarket</strong></p>
  <img src="https://img.shields.io/badge/build-passing-brightgreen" alt="Build Status" />
  <img src="https://img.shields.io/badge/coverage-100%25-brightgreen" alt="Coverage" />
</div>

## Architecture

This SDK strictly relies on `msgspec` to eliminate Python Garbage Collection (GC) pauses during high-frequency L2 order book delta processing. REST clients use `httpx.AsyncClient` for connection pooling and async I/O.

```mermaid
sequenceDiagram
    participant Exchange as Exchange API
    participant Client as Async SDK Client
    participant MsgSpec as msgspec Structs
    participant Engine as Trading Engine

    Exchange->>Client: REST JSON / WebSocket JSON
    Client->>MsgSpec: Raw Bytes Parse (Zero-Alloc)
    MsgSpec->>Engine: Typed Python Struct
```

## Installation

```bash
pip install prediction-market-sdk
```

For local development and test dependencies:

```bash
pip install -e '.[dev]'
```

## Quickstart

```python
import asyncio
from prediction_market_sdk.ws import MarketWebsocket

async def handle_orderbook(delta):
    # Delta is a strongly-typed `msgspec` struct. No dict allocation.
    print(f"L2 Update: {delta.price}c | Vol: {delta.delta}")

ws = MarketWebsocket("wss://trading-api.kalshi.com/trade-api/v2/ws", handle_orderbook)
asyncio.run(ws.connect())
```

## REST Client Examples

### Kalshi

```python
import asyncio
from prediction_market_sdk.kalshi import KalshiClient, RateLimitExceeded

PRIVATE_KEY_PEM = """-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----"""

async def main():
    client = KalshiClient(
        key_id="your-kalshi-key-id",
        private_key_pem=PRIVATE_KEY_PEM,
        env="paper",
    )

    try:
        balance = await client.get_balance()
        print(f"Balance: ${balance:,.2f}")
    except RateLimitExceeded:
        # Retry with backoff.
        raise
    finally:
        await client.session.aclose()

asyncio.run(main())
```

### Polymarket

```python
import asyncio
from prediction_market_sdk.polymarket import PolymarketClient

async def main():
    client = PolymarketClient(
        api_key="your-api-key",
        api_secret="your-api-secret",
        passphrase="your-passphrase",
        env="paper",
    )

    try:
        markets = await client.get_markets()
        print(markets)
    finally:
        await client.session.aclose()

asyncio.run(main())
```

## API Reference

### `prediction_market_sdk.kalshi`

#### `KalshiClient`

High-frequency async Kalshi REST client. It signs private REST requests with RSA-PSS SHA-256 headers and uses an `httpx.AsyncClient` session rooted at the selected Kalshi environment.

```python
KalshiClient(
    key_id: str,
    private_key_pem: str,
    env: Literal["paper", "demo", "live"] = "paper",
)
```

**Parameters**

| Name | Type | Description |
| --- | --- | --- |
| `key_id` | `str` | Kalshi API key identifier sent as `KALSHI-ACCESS-KEY`. |
| `private_key_pem` | `str` | PEM-encoded RSA private key used to sign requests. Invalid PEM raises `AuthConfigurationError`. |
| `env` | `"paper" \| "demo" \| "live"` | `live` uses `https://trading-api.kalshi.com/trade-api/v2`; non-live environments use `https://demo-api.kalshi.co/trade-api/v2`. |

**Attributes**

| Name | Type | Description |
| --- | --- | --- |
| `base_url` | `str` | Resolved exchange base URL. |
| `session` | `httpx.AsyncClient` | Async HTTP session. Call `await client.session.aclose()` when finished. |

#### `await KalshiClient.get_balance() -> float`

Fetches the current portfolio balance from `GET /portfolio/balance`.

**Returns**

- `float`: Account balance converted from cents to dollars.

**Raises**

- `AuthConfigurationError` for HTTP 401.
- `ForbiddenError` for HTTP 403.
- `RateLimitExceeded` for HTTP 429.
- `ExchangeServerError` for HTTP 5xx.
- `PredictionMarketError` for other HTTP 4xx responses or unexpected SDK-level failures.

#### `await KalshiClient.submit_order(ticker, action, side, count, price) -> OrderResponse`

Submits a limit order to `POST /portfolio/orders` and decodes the exchange payload directly into `OrderResponse`.

```python
order = await client.submit_order(
    ticker="KXTEST-26JUL12",
    action="buy",
    side="yes",
    count=1,
    price=50,
)
```

**Parameters**

| Name | Type | Description |
| --- | --- | --- |
| `ticker` | `str` | Kalshi market ticker. |
| `action` | `str` | Order action, for example `buy` or `sell`. |
| `side` | `str` | Contract side, typically `yes` or `no`. Determines whether `yes_price` or `no_price` is sent. |
| `count` | `int` | Number of contracts. |
| `price` | `int` | Limit price in cents. |

**Returns**

- `OrderResponse`: Typed order response struct.

**Raises**

- `AuthConfigurationError` for HTTP 401.
- `ForbiddenError` for HTTP 403.
- `RateLimitExceeded` for HTTP 429.
- `ExchangeServerError` for HTTP 5xx.
- `PredictionMarketError` for other HTTP failures or malformed exchange payloads.

#### `OrderResponse`

`msgspec.Struct` returned by `submit_order`.

| Field | Type | Description |
| --- | --- | --- |
| `order_id` | `str` | Exchange order identifier. |
| `ticker` | `str` | Market ticker. |
| `client_order_id` | `str` | Client-supplied order identifier returned by the exchange. |
| `action` | `str` | Order action. |
| `status` | `str` | Exchange order status. |
| `price` | `int` | Limit price in cents. |

#### `OrderBookUpdate`

Zero-allocation `msgspec.Struct` for order book deltas.

| Field | Type | Description |
| --- | --- | --- |
| `market_id` | `str` | Market identifier. |
| `price` | `int` | Price level in cents. |
| `delta` | `int` | Signed quantity change at the price level. |
| `side` | `Literal["yes", "no"]` | Contract side. Invalid values fail msgspec validation. |
| `ts` | `int` | Exchange timestamp. |

#### Kalshi Exceptions

All Kalshi exceptions inherit from `PredictionMarketError`.

| Exception | When it is raised |
| --- | --- |
| `AuthConfigurationError` | Invalid RSA key configuration or HTTP 401 authentication failure. |
| `ForbiddenError` | HTTP 403 permission or entitlement failure. |
| `RateLimitExceeded` | HTTP 429 exchange rate limit response. |
| `InsufficientFunds` | Reserved for insufficient buying power workflows. |
| `ExchangeServerError` | HTTP 5xx exchange-side failure. |
| `PredictionMarketError` | Base class and fallback for other SDK or HTTP errors. |

### `prediction_market_sdk.polymarket`

#### `PolymarketClient`

Async Polymarket CLOB REST client. It prepares L2 authentication headers and uses an `httpx.AsyncClient` session rooted at the selected environment.

```python
PolymarketClient(
    api_key: str,
    api_secret: str,
    passphrase: str,
    env: Literal["paper", "demo", "live"] = "paper",
)
```

**Parameters**

| Name | Type | Description |
| --- | --- | --- |
| `api_key` | `str` | Polymarket API key sent as `POLY-API-KEY`. |
| `api_secret` | `str` | API secret retained for L2 signing workflows. |
| `passphrase` | `str` | API passphrase sent as `POLY-PASSPHRASE`. |
| `env` | `"paper" \| "demo" \| "live"` | `live` uses `https://clob.polymarket.com`; non-live environments use `https://clob.sandbox.polymarket.com`. |

**Attributes**

| Name | Type | Description |
| --- | --- | --- |
| `base_url` | `str` | Resolved CLOB base URL. |
| `session` | `httpx.AsyncClient` | Async HTTP session. Call `await client.session.aclose()` when finished. |

#### `await PolymarketClient.get_markets() -> dict`

Fetches active Polymarket CLOB markets from `GET /markets`.

**Returns**

- `dict`: Decoded JSON response from the exchange.

**Raises**

- `AuthConfigurationError` for HTTP 401.
- `ForbiddenError` for HTTP 403.
- `RateLimitExceeded` for HTTP 429.
- `ExchangeServerError` for HTTP 5xx.
- `PredictionMarketError` for other HTTP failures.

#### `PolymarketOrderResponse`

`msgspec.Struct` for Polymarket order acknowledgements.

| Field | Type | Description |
| --- | --- | --- |
| `orderID` | `str` | Polymarket order identifier. |
| `status` | `str` | Order status. |
| `message` | `str \| None` | Optional exchange message. Defaults to `None`. |

#### Polymarket Exceptions

All Polymarket exceptions inherit from `PredictionMarketError`.

| Exception | When it is raised |
| --- | --- |
| `AuthConfigurationError` | HTTP 401 authentication failure. |
| `ForbiddenError` | HTTP 403 permission or entitlement failure. |
| `RateLimitExceeded` | HTTP 429 exchange rate limit response. |
| `ExchangeServerError` | HTTP 5xx exchange-side failure. |
| `PredictionMarketError` | Base class and fallback for other SDK or HTTP errors. |

### `prediction_market_sdk.ws`

#### `MarketWebsocket`

Async market data websocket client for receiving and decoding order book deltas.

```python
MarketWebsocket(url: str, on_update: Callable[[OrderBookUpdate], Any])
```

**Parameters**

| Name | Type | Description |
| --- | --- | --- |
| `url` | `str` | WebSocket endpoint URL. |
| `on_update` | `Callable` | Callback invoked with each decoded `OrderBookUpdate`. |

**Behavior**

- Maintains a reconnect delay starting at `0.1` seconds.
- Intended for high-throughput JSON delta processing via `msgspec` structs.

## HTTP Error Handling Contract

The REST clients normalize important exchange status codes into SDK exceptions so callers do not need to parse raw response objects.

| HTTP status | Kalshi exception | Polymarket exception |
| --- | --- | --- |
| `401` | `AuthConfigurationError` | `AuthConfigurationError` |
| `403` | `ForbiddenError` | `ForbiddenError` |
| `429` | `RateLimitExceeded` | `RateLimitExceeded` |
| `500` and other `5xx` | `ExchangeServerError` | `ExchangeServerError` |
| Other `4xx` | `PredictionMarketError` | `PredictionMarketError` |

## Testing

```bash
pytest -q
```

The test suite uses `pytest-httpx` to mock exchange responses and verifies that Kalshi and Polymarket clients map 401, 403, 429, and 500 responses to stable SDK exceptions.
