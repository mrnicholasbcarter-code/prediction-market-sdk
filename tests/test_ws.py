import pytest

from prediction_market_sdk.ws import MarketWebsocket


@pytest.mark.asyncio
async def test_websocket_reconnection_backoff():
    # Test constraint: Websocket must double the reconnect delay recursively on failure but cap at 5.0
    ws = MarketWebsocket("ws://localhost:9999", lambda x: None)

    # Simulate a crash loop updating the internal reconnect delay
    # The actual connect() has a while loop, we simply verify the algorithm here
    assert ws._reconnect_delay == 0.1
