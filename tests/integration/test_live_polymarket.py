import pytest

from prediction_market_sdk.polymarket import PolymarketClient


@pytest.mark.asyncio
async def test_live_polymarket_fetch() -> None:
    """
    REAL INTEGRATION TEST.
    No mocks. Connects to the actual Polymarket API and validates
    the SDK successfully parses live exchange data.
    """
    # Using dummy credentials since /markets is public
    client = PolymarketClient(
        api_key="public", api_secret="public", passphrase="public", env="live"
    )

    # Actually hit the live REST endpoint
    markets = await client.get_markets()

    # Assert the network connection succeeded and we received actual data
    assert isinstance(markets, dict)
    assert "data" in markets or "next_cursor" in markets

    # Validate the data contains expected exchange structuring
    if "data" in markets and len(markets["data"]) > 0:
        market = markets["data"][0]
        assert "condition_id" in market or "question" in market

    await client.session.aclose()
