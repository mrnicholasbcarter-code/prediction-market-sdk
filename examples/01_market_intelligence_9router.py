import asyncio

import httpx

from prediction_market_sdk.kalshi import KalshiClient
from prediction_market_sdk.llm_integration import RouterClient


async def analyze_market_with_9router(market_ticker: str):
    """
    Demonstrates using Async Context Managers coupled with the 9router Multiplexer
    to unify local intelligence retrieval with prediction market endpoints.
    """
    router = RouterClient()

    # 1. SDK provides async context management, cleaning up connections appropriately
    async with KalshiClient(key_id="x", private_key_pem="x", env="paper") as kalshi:
        # Example API retrieval (simulated here since auth is dummy)
        # orderbook = await kalshi.get_orderbook(market_ticker)
        book_summary = "{ 'yes': 55, 'no': 48 }"
        print(f"[{market_ticker}] Market Fetched")

    # 2. Seamlessly bounce analysis request through Omniroute/9router
    print("Initiating 9router analysis (Model Multiplexer)...")
    payload = {
        "model": "auto/best-reasoning",  # 9router takes the wheel on usage availability
        "messages": [
            {"role": "system", "content": "You are a prediction market analyst."},
            {"role": "user", "content": f"Given this book: {book_summary}. Forecast direction?"},
        ],
        "temperature": 0.2,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{router.base_url}/chat/completions",
                json=payload,
                headers=router.get_headers(),
                timeout=10.0,
            )
            print(
                "9Router Decision:",
                response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "Mock response"),
            )
        except Exception as e:
            print(f"Offline - install 9router to view actual pipeline: {e}")


if __name__ == "__main__":
    asyncio.run(analyze_market_with_9router("FED-RATES-UP"))
