"""Optional OmniRoute analysis example.

The SDK does not perform model selection itself. This example shows how an
application can call a separately configured OpenAI-compatible gateway such as
llm-gate backed by OmniRoute. It defaults to a dry run and never needs secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import json

import httpx

from prediction_market_sdk.llm_integration import RouterClient


async def analyze_market_with_omniroute(market_ticker: str, *, send: bool = False) -> None:
    router = RouterClient()
    book_summary = {"yes": 55, "no": 48}
    payload = {
        "model": "auto/best-reasoning",
        "messages": [
            {"role": "system", "content": "You are a prediction market analyst."},
            {
                "role": "user",
                "content": f"Given this book: {book_summary}. Forecast direction for {market_ticker}?",
            },
        ],
        "temperature": 0.2,
    }

    if not send:
        print(json.dumps({"endpoint": router.base_url, "payload": payload}, indent=2))
        return

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{router.base_url}/chat/completions",
            json=payload,
            headers=router.get_headers(),
            timeout=10.0,
        )
        response.raise_for_status()
        print(response.json())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("market_ticker", nargs="?", default="FED-RATES-UP")
    parser.add_argument("--send", action="store_true", help="send to the configured gateway")
    args = parser.parse_args()
    asyncio.run(analyze_market_with_omniroute(args.market_ticker, send=args.send))
