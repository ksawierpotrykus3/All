# cython: language_level=3
"""Compiled license-response verification (Ed25519). Obfuscation layer.

This module is compiled to a native .pyd by mvp/build/build_cython.ps1 with
the license backend public key embedded at build time. Inside frozen Nuitka
builds mvp.license prefers this module over the pure-Python fallback.
"""

from base64 import b64decode

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from mvp.backend.license_signing import canonical_bytes

_PUBLIC_KEY_PEM = "INJECT_PUBLIC_KEY_PEM_HERE"


def verify_response(data: dict, expected_license_key: str) -> bool:
    sig = data.get("signature")
    payload = data.get("signed_payload")
    if not isinstance(sig, str) or not isinstance(payload, dict):
        return False
    if payload.get("license_key") != expected_license_key:
        return False
    try:
        key = serialization.load_pem_public_key(_PUBLIC_KEY_PEM.encode("utf-8"))
        if not isinstance(key, Ed25519PublicKey):
            return False
        key.verify(b64decode(sig.encode("ascii")), canonical_bytes(payload))
        return payload.get("valid") is True
    except (InvalidSignature, ValueError):
        return False
