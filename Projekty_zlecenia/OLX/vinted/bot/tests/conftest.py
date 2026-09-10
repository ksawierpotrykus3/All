import pytest
from curl_cffi import requests as creq
import vintedbot.detection as detection


class MockResponse:
    def __init__(self, body, status_code=200):
        self.content = body if isinstance(body, bytes) else body.encode()
        self.text = self.content.decode("utf-8")
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture
def fake_http(monkeypatch):
    """Mock warstwy HTTP. Zwraca rejestr do ustawiania odpowiedzi per URL."""
    detection._KATALOG_CACHE.clear()
    responses = {}

    def _get(url, **kwargs):
        body = responses.get(url, b"{}")
        return MockResponse(body)

    def _set(url, body):
        responses[url] = body

    monkeypatch.setattr(creq, "get", _get)
    _set.registry = responses
    return _set
