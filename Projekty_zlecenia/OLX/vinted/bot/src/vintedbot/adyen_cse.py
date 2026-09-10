"""Adyen Client-Side Encryption (CSE) w czystym Pythonie.

Algorytm odtworzony z dekompilacji APK Vinted 26.33.1 (jadx):
- JWE Header: {"alg":"RSA-OAEP-256","enc":"A256GCM","version":"1"}
- Klucz publiczny Adyen: format "EXPONENT|MODULUS" (hex) z pola access_key w odpowiedzi POST card_registrations.
- Szyfrowanie klucza AES (32B) przez RSA-OAEP-256 (SHA-256 / MGF1-SHA256).
- Szyfrowanie danych JSON przez AES-256-GCM (12B IV, 16B auth tag, AAD=base64url(header)).
- Zwracany format: compact JWE (header.encrypted_key.iv.ciphertext.auth_tag).
"""
import base64
import json
import os
from datetime import datetime, timezone

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

JWE_HEADER = {"alg": "RSA-OAEP-256", "enc": "A256GCM", "version": "1"}


def b64url(data: bytes) -> str:
    """Kodowanie Base64 URL-safe bez dopełnienia '='."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def parsuj_access_key(access_key: str) -> rsa.RSAPublicKey:
    """Parsuje ciąg 'EXPONENT|MODULUS' lub 'MODULUS|EXPONENT' do obiektu RSAPublicKey."""
    parts = access_key.strip().split("|")
    if len(parts) != 2:
        raise ValueError(f"Nieprawidłowy format access_key: {access_key[:30]}...")

    p0, p1 = parts[0].strip(), parts[1].strip()
    if len(p0) < len(p1):
        exponent_hex, modulus_hex = p0, p1
    else:
        modulus_hex, exponent_hex = p0, p1

    e = int(exponent_hex, 16)
    n = int(modulus_hex, 16)
    pub_numbers = rsa.RSAPublicNumbers(e, n)
    return pub_numbers.public_key(backend=default_backend())


def szyfruj_pole(field_name: str, field_value: str, pub_key: rsa.RSAPublicKey) -> str:
    """Szyfruje pojedyncze pole karty do tokenu JWE (format APK encryptFields)."""
    now = datetime.now(timezone.utc)
    generationtime = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    plaintext_obj = {field_name: str(field_value), "generationtime": generationtime}
    plaintext = json.dumps(plaintext_obj, separators=(",", ":")).encode("utf-8")

    header_b64 = b64url(json.dumps(JWE_HEADER, separators=(",", ":")).encode("utf-8"))
    aes_key = os.urandom(32)

    encrypted_key = pub_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    iv = os.urandom(12)
    aad = header_b64.encode("ascii")
    aesgcm = AESGCM(aes_key)
    ct_with_tag = aesgcm.encrypt(iv, plaintext, aad)
    ciphertext = ct_with_tag[:-16]
    auth_tag = ct_with_tag[-16:]

    return ".".join([
        header_b64,
        b64url(encrypted_key),
        b64url(iv),
        b64url(ciphertext),
        b64url(auth_tag),
    ])


def zaszyfruj_pola_karty(karta: dict[str, str], access_key: str | rsa.RSAPublicKey) -> dict[str, str]:
    """Zwraca zaszyfrowane pola (encryptedCardNumber, encryptedExpiryMonth, etc.) dla PUT card_registrations."""
    pub_key = access_key if isinstance(access_key, rsa.RSAPublicKey) else parsuj_access_key(access_key)
    
    mapping = {
        "number": "encryptedCardNumber",
        "expiryMonth": "encryptedExpiryMonth",
        "expiryYear": "encryptedExpiryYear",
        "cvc": "encryptedSecurityCode",
    }
    
    wynik = {}
    for src_key, dst_key in mapping.items():
        if src_key in karta:
            wynik[dst_key] = szyfruj_pole(src_key, karta[src_key], pub_key)
    return wynik


def zaszyfruj_cala_karte(karta: dict[str, str], access_key: str | rsa.RSAPublicKey) -> str:
    """Zwraca pojedynczy JWE ze wszystkimi polami (dla tokenu updateCardRegistration)."""
    pub_key = access_key if isinstance(access_key, rsa.RSAPublicKey) else parsuj_access_key(access_key)
    now = datetime.now(timezone.utc)
    generationtime = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    
    payload = dict(karta)
    payload["generationtime"] = generationtime
    plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    header_b64 = b64url(json.dumps(JWE_HEADER, separators=(",", ":")).encode("utf-8"))
    aes_key = os.urandom(32)

    encrypted_key = pub_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    iv = os.urandom(12)
    aad = header_b64.encode("ascii")
    aesgcm = AESGCM(aes_key)
    ct_with_tag = aesgcm.encrypt(iv, plaintext, aad)
    ciphertext = ct_with_tag[:-16]
    auth_tag = ct_with_tag[-16:]

    return ".".join([
        header_b64,
        b64url(encrypted_key),
        b64url(iv),
        b64url(ciphertext),
        b64url(auth_tag),
    ])
