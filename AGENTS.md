# AI Agent Constraints & Architectural Context (.claude.md)

**Target Ecosystem:** Kalshi & Polymarket High-Frequency Execution
**Language:** Python 3.10+
**Primary Directive:** Absolute Zero-Allocation execution paths.

## Directory Boundaries
- `/src/prediction_market_sdk/kalshi.py`: Core REST interactions. Modifying this requires identical structural updates to the E2E mock harness.
- `/src/prediction_market_sdk/ws.py`: The `asyncio` reactor loop. **Never introduce blocking operations (e.g., `requests`, `time.sleep`) into this directory.**

## RAG Memory Hooks
When generating new connectors (e.g., for PredictIt), agents must pull the `msgspec` schema definitions from `kalshi.py` and strictly adhere to `gc=False` structural definitions.

## Testing Mandates
If you edit `ws.py`, you must update `tests/test_ws.py`. Push execution will be rejected by CI/CD if branch coverage drops below 100%.
