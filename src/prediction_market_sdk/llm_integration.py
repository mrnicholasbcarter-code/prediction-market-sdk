"""
Omniroute & 9Router Ecosystem Integration
Allows the SDK to unify model providers and transparently query LLM endpoints
(e.g., for sentiment mapping or complex bet logic inference) using the agnostic,
fallback-ready 9Router framework at localhost:20128.
"""

import os
from collections.abc import Mapping

# Universal endpoint mapping for the decoupled ecosystem
DEFAULT_9ROUTER_URL = os.getenv("ROUTER_URL", "http://localhost:20128/v1")
DEFAULT_9ROUTER_MODELS = "http://localhost:20128/v1/models"
DEFAULT_9ROUTER_USAGE = "http://localhost:20128/api/usage"


class RouterClient:
    """
    Standardizes interaction with Omniroute/9router.
    By leveraging multiplexer endpoints, the SDK abstracts away provider-lockin and quota drops.
    """

    def __init__(self, base_url: str = DEFAULT_9ROUTER_URL):
        self.base_url = base_url

    def get_headers(self) -> Mapping[str, str]:
        """Fetch unified auth layer. Rely on Router for outbound logic."""
        auth_key = os.getenv("ROUTER_API_KEY", "dummy")
        return {"Authorization": f"Bearer {auth_key}", "Content-Type": "application/json"}
