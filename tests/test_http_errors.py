"""HTTP error handling tests for Kalshi and Polymarket clients."""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from prediction_market_sdk.kalshi import (
    AuthConfigurationError as KalshiAuthConfigurationError,
)
from prediction_market_sdk.kalshi import (
    ExchangeServerError as KalshiExchangeServerError,
)
from prediction_market_sdk.kalshi import (
    ForbiddenError as KalshiForbiddenError,
)
from prediction_market_sdk.kalshi import (
    KalshiClient,
)
from prediction_market_sdk.kalshi import (
    PredictionMarketError as KalshiPredictionMarketError,
)
from prediction_market_sdk.kalshi import (
    RateLimitExceeded as KalshiRateLimitExceeded,
)
from prediction_market_sdk.polymarket import (
    AuthConfigurationError as PolymarketAuthConfigurationError,
)
from prediction_market_sdk.polymarket import (
    ExchangeServerError as PolymarketExchangeServerError,
)
from prediction_market_sdk.polymarket import (
    ForbiddenError as PolymarketForbiddenError,
)
from prediction_market_sdk.polymarket import (
    PolymarketClient,
)
from prediction_market_sdk.polymarket import (
    PredictionMarketError as PolymarketPredictionMarketError,
)
from prediction_market_sdk.polymarket import (
    RateLimitExceeded as PolymarketRateLimitExceeded,
)


def generate_private_key_pem() -> str:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


KALSHI_ERROR_CASES = [
    (401, KalshiAuthConfigurationError),
    (403, KalshiForbiddenError),
    (429, KalshiRateLimitExceeded),
    (500, KalshiExchangeServerError),
]

POLYMARKET_ERROR_CASES = [
    (401, PolymarketAuthConfigurationError),
    (403, PolymarketForbiddenError),
    (429, PolymarketRateLimitExceeded),
    (500, PolymarketExchangeServerError),
]


@pytest_asyncio.fixture
async def kalshi_client():
    client = KalshiClient(
        key_id="test-key", private_key_pem=generate_private_key_pem(), env="paper"
    )
    try:
        yield client
    finally:
        await client.session.aclose()


@pytest_asyncio.fixture
async def polymarket_client():
    client = PolymarketClient(api_key="key", api_secret="secret", passphrase="pass", env="paper")
    try:
        yield client
    finally:
        await client.session.aclose()


class TestKalshiHttpErrors:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(("status_code", "expected_error"), KALSHI_ERROR_CASES)
    async def test_get_balance_maps_http_errors(
        self, httpx_mock, kalshi_client, status_code, expected_error
    ):
        num_requests = 3 if status_code in (429, 500) else 1
        for _ in range(num_requests):
            httpx_mock.add_response(
                method="GET",
                url="https://demo-api.kalshi.co/trade-api/v2/portfolio/balance",
                status_code=status_code,
                json={"error": f"status {status_code}"},
            )

        with pytest.raises(expected_error, match=str(status_code)) as exc_info:
            await kalshi_client.get_balance()

        assert isinstance(exc_info.value, KalshiPredictionMarketError)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("status_code", "expected_error"), KALSHI_ERROR_CASES)
    async def test_submit_order_maps_http_errors(
        self, httpx_mock, kalshi_client, status_code, expected_error
    ):
        num_requests = 3 if status_code in (429, 500) else 1
        for _ in range(num_requests):
            httpx_mock.add_response(
                method="POST",
                url="https://demo-api.kalshi.co/trade-api/v2/portfolio/orders",
                status_code=status_code,
                json={"error": f"status {status_code}"},
            )

        with pytest.raises(expected_error, match=str(status_code)) as exc_info:
            await kalshi_client.submit_order(
                ticker="KXTEST-26JUL12",
                action="buy",
                side="yes",
                count=1,
                price=50,
            )

        assert isinstance(exc_info.value, KalshiPredictionMarketError)

    @pytest.mark.asyncio
    async def test_kalshi_timeout_retry(self, httpx_mock, kalshi_client):
        def raise_timeout(*args, **kwargs):
            raise httpx.TimeoutException("Read timeout")

        for _ in range(3):
            httpx_mock.add_callback(
                raise_timeout, url="https://demo-api.kalshi.co/trade-api/v2/portfolio/balance"
            )

        with pytest.raises(KalshiExchangeServerError, match="timeout"):
            await kalshi_client.get_balance()


class TestPolymarketHttpErrors:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(("status_code", "expected_error"), POLYMARKET_ERROR_CASES)
    async def test_get_markets_maps_http_errors(
        self, httpx_mock, polymarket_client, status_code, expected_error
    ):
        num_requests = 3 if status_code in (429, 500) else 1
        for _ in range(num_requests):
            httpx_mock.add_response(
                method="GET",
                url="https://clob.sandbox.polymarket.com/markets",
                status_code=status_code,
                json={"error": f"status {status_code}"},
            )

        with pytest.raises(expected_error, match=str(status_code)) as exc_info:
            await polymarket_client.get_markets()

        assert isinstance(exc_info.value, PolymarketPredictionMarketError)

    @pytest.mark.asyncio
    async def test_polymarket_timeout_retry(self, httpx_mock, polymarket_client):
        def raise_timeout(*args, **kwargs):
            raise httpx.TimeoutException("Read timeout")

        for _ in range(3):
            httpx_mock.add_callback(
                raise_timeout, url="https://clob.sandbox.polymarket.com/markets"
            )

        with pytest.raises(PolymarketExchangeServerError, match="timeout"):
            await polymarket_client.get_markets()
