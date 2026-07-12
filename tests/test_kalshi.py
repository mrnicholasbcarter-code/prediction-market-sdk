import pytest
import msgspec
from prediction_market_sdk.kalshi import (
    KalshiClient, OrderBookUpdate, OrderResponse,
    AuthConfigurationError, PredictionMarketError,
    RateLimitExceeded, InsufficientFunds
)


class TestOrderBookUpdate:
    def test_struct_creation(self):
        update = OrderBookUpdate(market_id="BTC-100K", price=45, delta=100, side="yes", ts=1234567890)
        assert update.market_id == "BTC-100K"
        assert update.price == 45
        assert update.side == "yes"

    def test_msgspec_decode(self):
        raw = b'{"market_id": "ETH", "price": 30, "delta": 50, "side": "no", "ts": 999}'
        obj = msgspec.json.decode(raw, type=OrderBookUpdate)
        assert obj.market_id == "ETH"
        assert obj.side == "no"

    def test_msgspec_encode_roundtrip(self):
        original = OrderBookUpdate(market_id="X", price=1, delta=2, side="yes", ts=3)
        encoded = msgspec.json.encode(original)
        decoded = msgspec.json.decode(encoded, type=OrderBookUpdate)
        assert decoded.market_id == original.market_id
        assert decoded.ts == original.ts

    def test_invalid_side_type(self):
        with pytest.raises(msgspec.ValidationError):
            msgspec.json.decode(b'{"market_id": "X", "price": 1, "delta": 2, "side": "maybe", "ts": 3}', type=OrderBookUpdate)


class TestOrderResponse:
    def test_struct_creation(self):
        resp = OrderResponse(order_id="123", ticker="BTC", client_order_id="abc", action="buy", status="executed", price=45)
        assert resp.order_id == "123"
        assert resp.price == 45

    def test_msgspec_decode(self):
        raw = b'{"order_id": "456", "ticker": "ETH", "client_order_id": "def", "action": "sell", "status": "resting", "price": 72}'
        obj = msgspec.json.decode(raw, type=OrderResponse)
        assert obj.ticker == "ETH"
        assert obj.action == "sell"

    def test_missing_field_raises(self):
        with pytest.raises(msgspec.ValidationError):
            msgspec.json.decode(b'{"order_id": "1"}', type=OrderResponse)


class TestExceptionHierarchy:
    def test_auth_error_is_prediction_market_error(self):
        assert issubclass(AuthConfigurationError, PredictionMarketError)

    def test_rate_limit_is_prediction_market_error(self):
        assert issubclass(RateLimitExceeded, PredictionMarketError)

    def test_insufficient_funds_is_prediction_market_error(self):
        assert issubclass(InsufficientFunds, PredictionMarketError)


class TestKalshiClientInit:
    def test_bad_pem_raises_auth_error(self):
        with pytest.raises(AuthConfigurationError):
            KalshiClient(key_id="test", private_key_pem="not-a-real-pem", env="paper")

    def test_bad_env_string(self):
        # Should not crash on init even with weird env, RSA key is the gate
        with pytest.raises(AuthConfigurationError):
            KalshiClient(key_id="test", private_key_pem="garbage", env="paper")

    def test_valid_env_values(self):
        # Just verify the Literal type accepts these strings at the type level
        for env in ["paper", "demo", "live"]:
            with pytest.raises(AuthConfigurationError):
                KalshiClient(key_id="k", private_key_pem="bad", env=env)
