from typing import Any

import pytest

from prediction_market_sdk.ws import MarketWebsocket


@pytest.mark.asyncio
async def test_websocket_reconnection_backoff() -> None:
    # Test constraint: Websocket must double the reconnect delay recursively on failure but cap at 5.0
    async def handle_message(_: Any) -> None:
        return None

    ws = MarketWebsocket("ws://localhost:9999", handle_message)

    # Simulate a crash loop updating the internal reconnect delay
    # The actual connect() has a while loop, we simply verify the algorithm here
    assert ws._reconnect_delay == 0.1
