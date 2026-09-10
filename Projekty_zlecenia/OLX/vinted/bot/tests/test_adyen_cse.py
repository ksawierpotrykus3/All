"""Testy jednostkowe modułu Adyen CSE."""
import base64
import json
import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from vintedbot.adyen_cse import (
    parsuj_access_key,
    szyfruj_pole,
    zaszyfruj_pola_karty,
    zaszyfruj_cala_karte,
)


@pytest.fixture
def rsa_pair():
    priv = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    pub = priv.public_key()
    return priv, pub


def _deszyfruj_jwe(jwe_token: str, priv_key) -> dict:
    parts = jwe_token.split(".")
    assert len(parts) == 5
    
    def b64d(s):
        pad = "=" * (-len(s) % 4)
        return base64.urlsafe_b64decode(s + pad)
    
    header_b64 = parts[0]
    enc_key = b64d(parts[1])
    iv = b64d(parts[2])
    ct = b64d(parts[3])
    tag = b64d(parts[4])
    
    aes_key = priv_key.decrypt(
        enc_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    aesgcm = AESGCM(aes_key)
    plaintext = aesgcm.decrypt(iv, ct + tag, header_b64.encode("ascii"))
    return json.loads(plaintext.decode("utf-8"))


def test_parsuj_access_key(rsa_pair):
    priv, pub = rsa_pair
    nums = pub.public_numbers()
    access_key = f"{format(nums.e, 'X')}|{format(nums.n, 'X')}"
    
    parsed_pub = parsuj_access_key(access_key)
    assert parsed_pub.public_numbers().e == nums.e
    assert parsed_pub.public_numbers().n == nums.n


def test_parsuj_access_key_invalid():
    with pytest.raises(ValueError):
        parsuj_access_key("invalid_key_without_pipe")


def test_szyfruj_pole(rsa_pair):
    priv, pub = rsa_pair
    jwe = szyfruj_pole("number", "4111111111111111", pub)
    
    decrypted = _deszyfruj_jwe(jwe, priv)
    assert decrypted["number"] == "4111111111111111"
    assert "generationtime" in decrypted


def test_zaszyfruj_pola_karty(rsa_pair):
    priv, pub = rsa_pair
    karta = {
        "number": "4111111111111111",
        "expiryMonth": "12",
        "expiryYear": "2026",
        "cvc": "123",
    }
    
    zaszyfrowana = zaszyfruj_pola_karty(karta, pub)
    assert "encryptedCardNumber" in zaszyfrowana
    assert "encryptedExpiryMonth" in zaszyfrowana
    assert "encryptedExpiryYear" in zaszyfrowana
    assert "encryptedSecurityCode" in zaszyfrowana
    
    dec_num = _deszyfruj_jwe(zaszyfrowana["encryptedCardNumber"], priv)
    assert dec_num["number"] == "4111111111111111"
    
    dec_cvc = _deszyfruj_jwe(zaszyfrowana["encryptedSecurityCode"], priv)
    assert dec_cvc["cvc"] == "123"


def test_zaszyfruj_cala_karte(rsa_pair):
    priv, pub = rsa_pair
    karta = {
        "number": "4111111111111111",
        "expiryMonth": "12",
        "expiryYear": "2026",
        "cvc": "123",
    }
    jwe = zaszyfruj_cala_karte(karta, pub)
    decrypted = _deszyfruj_jwe(jwe, priv)
    assert decrypted["number"] == "4111111111111111"
    assert decrypted["expiryMonth"] == "12"
    assert decrypted["cvc"] == "123"
