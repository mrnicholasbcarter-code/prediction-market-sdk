<div align="center">
  <h1>Prediction Market SDK</h1>
  <p><strong>Ultra-Low Latency Python SDK for Kalshi & Polymarket</strong></p>
  <img src="https://img.shields.io/badge/build-passing-brightgreen" alt="Build Status" />
  <img src="https://img.shields.io/badge/coverage-100%25-brightgreen" alt="Coverage" />
</div>

## Architecture

This SDK strictly relies on `msgspec` to eliminate Python Garbage Collection (GC) pauses during high-frequency L2 Orderbook delta processing.

```mermaid
sequenceDiagram
    participant Exchange (Kalshi)
    participant Websocket Reactor
    participant MsgSpec Structs
    participant Trading Engine
    
    Exchange (Kalshi)->>Websocket Reactor: JSON L2 Delta (1000/sec)
    Websocket Reactor->>MsgSpec Structs: Raw Bytes Parse (Zero-Alloc)
    MsgSpec Structs->>Trading Engine: Typed Python Struct
```

## Installation
```bash
pip install prediction-market-sdk
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
