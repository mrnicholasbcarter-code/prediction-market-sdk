import pytest

from prediction_market_sdk.llm_integration import RouterClient


def test_router_client_defaults_to_filtered_omniroute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OMNIROUTE_BASE_URL", raising=False)
    client = RouterClient()
    assert client.base_url == "http://127.0.0.1:20132/v1"


def test_router_client_does_not_emit_dummy_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OMNIROUTE_API_KEY", raising=False)
    assert RouterClient().get_headers() == {"Content-Type": "application/json"}


def test_router_client_uses_explicit_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMNIROUTE_API_KEY", "test-key")
    assert RouterClient().get_headers()["Authorization"] == "Bearer test-key"
