import time
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
class RateLimitExceeded(PredictionMarketError): pass

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

    async def get_markets(self) -> dict:
        """Fetch active markets."""
        res = await self.session.get("/markets")
        if res.status_code == 429:
            raise RateLimitExceeded("Polymarket rate limit violated")
        return res.json()
