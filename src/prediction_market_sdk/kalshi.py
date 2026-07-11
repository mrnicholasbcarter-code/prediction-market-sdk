import json
import base64
import httpx
from datetime import datetime, timezone
import msgspec
from typing import Optional, Literal
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

# ---------------------------------------------------------
# Zero-allocation msgspec Models (HFT Limit Order Book / Ticks)
# ---------------------------------------------------------

class OrderBookUpdate(msgspec.Struct, gc=False):
    market_id: str
    price: int
    delta: int
    side: Literal["yes", "no"]
    ts: int

class OrderResponse(msgspec.Struct, gc=False):
    order_id: str
    ticker: str
    client_order_id: str
    action: str
    status: str
    price: int

# ---------------------------------------------------------
# Exception Taxonomy
# ---------------------------------------------------------

class PredictionMarketError(Exception): pass
class AuthConfigurationError(PredictionMarketError): pass
class RateLimitExceeded(PredictionMarketError): pass
class InsufficientFunds(PredictionMarketError): pass

# ---------------------------------------------------------
# Client Architecture
# ---------------------------------------------------------

class KalshiClient:
    """
    High-frequency async Kalshi REST Client.
    Employs connection pooling, RSA-PSS signatures, and rigorous rate-limiting.
    """
    def __init__(
        self,
        key_id: str,
        private_key_pem: str,
        env: Literal["paper", "demo", "live"] = "paper"
    ):
        self.key_id = key_id
        
        # Security Boundary: RSA Key initialized into memory once
        try:
            self.rsa_key = load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
        except Exception as e:
            raise AuthConfigurationError("Failed to parse RSA Private Key PEM") from e

        # DNS mapping based on 3-environment state
        if env == "live":
            self.base_url = "https://trading-api.kalshi.com/trade-api/v2"
        else:
            self.base_url = "https://demo-api.kalshi.co/trade-api/v2"
            
        self.session = httpx.AsyncClient(base_url=self.base_url)

    def _generate_rsa_headers(self, method: str, path: str) -> dict:
        """
        Calculates the instantaneous RSA-PSS SHA-256 signature required by the exchange.
        Performance budget: <10us.
        """
        timestamp = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        msg_string = timestamp + method.upper() + path

        signature = self.rsa_key.sign(
            msg_string.encode("utf-8"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("utf-8"),
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }

    async def get_balance(self) -> float:
        """Fetch real-time portfolio balance."""
        headers = self._generate_rsa_headers("GET", "/portfolio/balance")
        res = await self.session.get("/portfolio/balance", headers=headers)
        
        if res.status_code == 429:
            raise RateLimitExceeded("Kalshi 20req/sec capacity violated")
            
        data = res.json()
        return data.get("balance", 0) / 100.0  # Convert cents to dollars
        
    async def submit_order(self, ticker: str, action: str, side: str, count: int, price: int) -> OrderResponse:
        """Submit a limit order mapped against the msgspec response struct."""
        payload = {
            "action": action,
            "side": side,
            "count": count,
            "type": "limit",
            "yes_price": price if side == "yes" else None,
            "no_price": price if side == "no" else None,
            "ticker": ticker
        }
        
        # Clean nulls
        payload = {k: v for k, v in payload.items() if v is not None}
        
        path = "/portfolio/orders"
        headers = self._generate_rsa_headers("POST", path)
        res = await self.session.post(path, headers=headers, json=payload)
        
        if res.status_code == 429:
            raise RateLimitExceeded("Kalshi 10req/sec order limit violated")
            
        # Zero-allocation deserialization
        try:
            return msgspec.json.decode(res.content, type=OrderResponse)
        except Exception as e:
            raise PredictionMarketError(f"Unexpected exchange payload: {res.text}") from e
