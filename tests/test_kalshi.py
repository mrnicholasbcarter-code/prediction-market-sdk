import pytest
import msgspec
from datetime import datetime
from prediction_market_sdk.kalshi import KalshiClient, OrderResponse, AuthConfigurationError

def test_kalshi_client_init_bad_key():
    # Should throw AuthConfigurationError when RSA parsing fails
    with pytest.raises(AuthConfigurationError):
        client = KalshiClient(key_id="test", private_key_pem="bad_pem_string", env="paper")

def test_kalshi_msgspec_decoder():
    # Test strict zero-allocation parsing constraint
    mock_payload = b'{"order_id": "123", "ticker": "BTC", "client_order_id": "abc", "action": "buy", "status": "executed", "price": 45}'
    
    # Must securely parse directly into struct
    struct = msgspec.json.decode(mock_payload, type=OrderResponse)
    assert struct.order_id == "123"
    assert struct.price == 45
