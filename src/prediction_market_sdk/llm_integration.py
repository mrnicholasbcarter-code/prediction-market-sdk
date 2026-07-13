"""
OmniRoute Integration Boundary
Allows the SDK to unify model providers and transparently query LLM endpoints
(e.g., for sentiment mapping or complex bet logic inference) using the agnostic,
fallback-ready 9Router framework through the configured local OmniRoute filtered proxy.
"""

import os
from collections.abc import Mapping

# Universal endpoint mapping for the decoupled ecosystem
DEFAULT_OMNIROUTE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://127.0.0.1:20132/v1")
DEFAULT_OMNIROUTE_MODELS = "http://127.0.0.1:20132/v1/models"
DEFAULT_OMNIROUTE_USAGE = "http://127.0.0.1:20132/api/usage"


class RouterClient:
    """
    Standardizes interaction with OmniRoute.
    By leveraging multiplexer endpoints, the SDK abstracts away provider-lockin and quota drops.
    """

    def __init__(self, base_url: str = DEFAULT_OMNIROUTE_URL):
        self.base_url = base_url

    def get_headers(self) -> Mapping[str, str]:
        """Fetch unified auth layer. Rely on Router for outbound logic."""
        auth_key = os.getenv("OMNIROUTE_API_KEY")
        headers = {"Content-Type": "application/json"}
        if auth_key:
            headers["Authorization"] = f"Bearer {auth_key}"
        return headers
