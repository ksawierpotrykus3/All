
import builtins
import logging
import os
import sys
from base64 import b64decode

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from mvp.backend.license_signing import canonical_bytes

logger = logging.getLogger(__name__)

try:
    if globals().get("__compiled__") or getattr(builtins, "__compiled__", False):
        from mvp.license_verify import verify_response as _compiled_verify_response
    else:
        _compiled_verify_response = None
except ImportError:
    _compiled_verify_response = None

try:
    from mvp.build_mode import BUILD_MODE
except ImportError:
    BUILD_MODE = os.environ.get("LASTZ_BUILD_MODE", "prod")

_VALIDATE_PATH = "/license/validate"

LICENSE_PUBLIC_KEY_PEM = """\
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAk7M3GIr+YzDB8c4ZHmJCnHMrLDr/JApUGr/H/9iJOLc=
-----END PUBLIC KEY-----"""


class LicenseError(Exception):
    pass


def is_dev_mode() -> bool:
    if BUILD_MODE == "prod":
        return False
    if BUILD_MODE == "dev":
        return True
    return "--dev" in sys.argv or os.environ.get("LASTZ_DEV_MODE", "").lower() in (
        "1",
        "true",
        "yes",
        "dev",
    )


def _verify_signature(data: dict, expected_license_key: str) -> bool:
    if _compiled_verify_response is not None:
        return _compiled_verify_response(data, expected_license_key)
    sig = data.get("signature")
    payload = data.get("signed_payload")
    if not isinstance(sig, str) or not isinstance(payload, dict):
        return False
    if payload.get("license_key") != expected_license_key:
        return False
    raw = canonical_bytes(payload)
    try:
        key = serialization.load_pem_public_key(LICENSE_PUBLIC_KEY_PEM.encode("utf-8"))
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("Expected Ed25519 public key")
        key.verify(b64decode(sig.encode("ascii")), raw)
        return payload.get("valid") is True
    except (InvalidSignature, ValueError):
        return False


def validate_license(
    backend_url: str,
    license_key: str,
    hwid: str,
    timeout_s: float = 10.0,
) -> dict:
    if not backend_url or not license_key:
        raise LicenseError("Missing backend_url or license_key in config.json")
    url = backend_url.rstrip("/") + _VALIDATE_PATH
    logger.debug("Validating license against %s", url)
    try:
        resp = httpx.post(
            url,
            json={"license_key": license_key, "hwid": hwid},
            timeout=timeout_s,
        )
    except httpx.HTTPError as exc:
        raise LicenseError(f"Cannot connect to backend: {exc}") from exc
    if resp.status_code == 403:
        raise LicenseError("Access blocked by backend (403)")
    if resp.status_code != 200:
        raise LicenseError(f"Backend returned status {resp.status_code}")
    try:
        data = resp.json()
    except (ValueError, AttributeError):
        raise LicenseError("Backend returned invalid JSON") from None
    if not isinstance(data, dict):
        raise LicenseError("Backend returned unexpected payload")
    if not _verify_signature(data, license_key):
        raise LicenseError("License response signature invalid")
    signed = data.get("signed_payload") or data
    if not signed.get("valid"):
        raise LicenseError(signed.get("message") or "License invalid")
    return data


def check_license(backend_url: str, license_key: str, hwid: str) -> None:
    if is_dev_mode():
        logger.info("DEV mode: skipping license validation (build mode)")
        return
    validate_license(backend_url, license_key, hwid)
    logger.info("License verified successfully")
