"""Testy jednostkowe modułu rejestracji kart (card_manager)."""
import json
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

from vintedbot.card_manager import (
    zarejestruj_karte,
    pobierz_zapisane_karty,
    usun_karte,
)
from vintedbot.models import KonfiguracjaKonta


class MockResponse:
    def __init__(self, data, status_code=200):
        self.status_code = status_code
        self.content = json.dumps(data).encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self.content.decode("utf-8"))


@pytest.fixture
def test_rsa_key():
    priv = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    pub = priv.public_key()
    nums = pub.public_numbers()
    access_key = f"{format(nums.e, 'X')}|{format(nums.n, 'X')}"
    return access_key


def test_zarejestruj_karte_sukces(monkeypatch, test_rsa_key):
    posted_payloads = []
    
    def mock_post(url, **kw):
        return MockResponse({
            "card_registration": {
                "id": "REG_12345",
                "access_key": test_rsa_key,
                "provider": "adyen",
            }
        })
    
    def mock_put(url, **kw):
        posted_payloads.append(kw.get("json"))
        return MockResponse({
            "card": {
                "id": 998877,
                "last4": "1111",
                "brand": "visa",
                "is_default": True,
            }
        })
    
    import vintedbot.card_manager as cm
    monkeypatch.setattr(cm.creq, "post", mock_post)
    monkeypatch.setattr(cm.creq, "put", mock_put)
    
    konto = KonfiguracjaKonta(cookies={"access_token_web": "fake_token"})
    karta = {
        "number": "4111111111111111",
        "expiryMonth": "12",
        "expiryYear": "2026",
        "cvc": "123",
    }
    
    res = zarejestruj_karte(karta, konto)
    assert res["card"]["id"] == 998877
    assert res["card"]["last4"] == "1111"
    assert len(posted_payloads) == 1
    
    # Weryfikacja że wysłano zaszyfrowane pola JWE
    card_reg = posted_payloads[0]["card_registration"]
    enc_details = card_reg["encrypted_card_details"]
    assert len(enc_details["number"].split(".")) == 5
    assert len(enc_details["security_code"].split(".")) == 5


def test_pobierz_zapisane_karty(monkeypatch):
    def mock_get(url, **kw):
        return MockResponse({
            "cards": [
                {"id": 1, "last4": "1111", "brand": "visa"},
                {"id": 2, "last4": "2222", "brand": "mastercard"},
            ]
        })
    
    import vintedbot.card_manager as cm
    monkeypatch.setattr(cm.creq, "get", mock_get)
    
    konto = KonfiguracjaKonta(cookies={"access_token_web": "fake_token"})
    karty = pobierz_zapisane_karty(konto)
    assert len(karty) == 2
    assert karty[0]["last4"] == "1111"


def test_usun_karte(monkeypatch):
    def mock_delete(url, **kw):
        assert "cards/998877" in url
        return MockResponse({}, status_code=204)
    
    import vintedbot.card_manager as cm
    monkeypatch.setattr(cm.creq, "delete", mock_delete)
    
    konto = KonfiguracjaKonta(cookies={"access_token_web": "fake_token"})
    assert usun_karte(998877, konto) is True


def test_pobierz_lub_pobierz_access_key_i_pre_szyfrowanie(monkeypatch, test_rsa_key):
    import vintedbot.card_manager as cm
    cm._ACCESS_KEY_CACHE.clear()
    
    call_count = 0
    def mock_post(url, **kw):
        nonlocal call_count
        call_count += 1
        return MockResponse({
            "card_registration": {
                "id": "REG_999",
                "access_key": test_rsa_key,
                "provider": "adyen",
            }
        })
    
    monkeypatch.setattr(cm.creq, "post", mock_post)
    konto = KonfiguracjaKonta(anon_id="test_anon_123")
    
    key1 = cm.pobierz_lub_pobierz_access_key(konto)
    assert key1 == test_rsa_key
    assert call_count == 1
    
    # Drugie wywołanie z cache
    key2 = cm.pobierz_lub_pobierz_access_key(konto)
    assert key2 == test_rsa_key
    assert call_count == 1
    
    # Pre-szyfrowanie
    karta = {
        "number": "4111111111111111",
        "expiryMonth": "12",
        "expiryYear": "2028",
        "cvc": "123",
    }
    zasz = cm.przygotuj_zaszyfrowana_karte(karta, key1)
    assert len(zasz["encryptedCardNumber"].split(".")) == 5
    assert len(zasz["encryptedSecurityCode"].split(".")) == 5
