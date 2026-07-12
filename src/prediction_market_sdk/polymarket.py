import time
import asyncio
import httpx
import msgspec
from typing import Literal

# ---------------------------------------------------------
# Zero-allocation msgspec Models
# ---------------------------------------------------------

class PolymarketOrderResponse(msgspec.Struct, gc=False):
    orderID: str
    status: str
    message: str | None = None

class PredictionMarketError(Exception): pass
class AuthConfigurationError(PredictionMarketError): pass
class ForbiddenError(PredictionMarketError): pass
class RateLimitExceeded(PredictionMarketError): pass
class ExchangeServerError(PredictionMarketError): pass

# ---------------------------------------------------------
# Client Architecture
# ---------------------------------------------------------

class PolymarketClient:
    """
    High-frequency async Polymarket (CLOB) REST Client.
    Implements Polygon L2 API interactions with zero-allocation parsing.
    """
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str,
        env: Literal["paper", "demo", "live"] = "paper"
    ):
        self.api_key = api_key
        self._secret = api_secret
        self._passphrase = passphrase
        
        # Sandbox (Mumbai) vs Live (Polygon Mainnet)
        if env == "live":
            self.base_url = "https://clob.polymarket.com"
        else:
            self.base_url = "https://clob.sandbox.polymarket.com"
            
        self.session = httpx.AsyncClient(base_url=self.base_url)

    def _generate_l2_headers(self, method: str, path: str) -> dict:
        """
        Cryptographic L2 signature generation (EIP-712).
        Sanitized implementation mapping to standard CLOB spec.
        """
        timestamp = str(int(time.time()))
        # In a full extraction, the L2 HMAC/ECDSA signing payload goes here.
        # Stripped of proprietary logic/keys for open-source safety.
        mock_signature = "0x..." 
        
        return {
            "POLY-API-KEY": self.api_key,
            "POLY-TIMESTAMP": timestamp,
            "POLY-SIGNATURE": mock_signature,
            "POLY-PASSPHRASE": self._passphrase
        }

    @staticmethod
    def _raise_for_status(res: httpx.Response, action: str) -> None:
        """Map Polymarket HTTP failures to stable SDK exceptions."""
        if res.status_code < 400:
            return

        detail = f"Polymarket {action} failed with HTTP {res.status_code}: {res.text}"
        if res.status_code == 401:
            raise AuthConfigurationError(detail)
        if res.status_code == 403:
            raise ForbiddenError(detail)
        if res.status_code == 429:
            raise RateLimitExceeded(detail)
        if res.status_code >= 500:
            raise ExchangeServerError(detail)
        raise PredictionMarketError(detail)

    async def _request_with_retry(self, method: str, path: str, action: str, **kwargs) -> httpx.Response:
        max_retries = 3
        for attempt in range(max_retries):
            headers = self._generate_l2_headers(method.upper(), path)
            req_kwargs = kwargs.copy()
            req_headers = req_kwargs.pop("headers", {})
            headers.update(req_headers)
            
            try:
                res = await self.session.request(method, path, headers=headers, **req_kwargs)
                if res.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    await asyncio.sleep(0.1 * (2 ** attempt))
                    continue
                self._raise_for_status(res, action)
                return res
            except httpx.TimeoutException as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1 * (2 ** attempt))
                    continue
                raise ExchangeServerError(f"Polymarket {action} failed with timeout: {str(e)}") from e
        raise ExchangeServerError(f"Polymarket {action} failed after max retries")

    async def get_markets(self) -> dict:
        """Fetch active markets."""
        res = await self._request_with_retry("GET", "/markets", action="markets request")
        return res.json()
