"""Tests for the license client (mvp.license)."""

import httpx
import pytest

from mvp.license import LicenseError, check_license, is_dev_mode, validate_license


def test_is_dev_mode_false_by_default():
    # Without mvp/build_mode.py (source checkout / PROD build) the gate is closed.
    assert is_dev_mode() is False


def test_is_dev_mode_true_when_build_mode_dev(monkeypatch):
    monkeypatch.setattr("mvp.license.BUILD_MODE", "dev")
    assert is_dev_mode() is True


def test_validate_license_ok(monkeypatch):
    class _Resp:
        status_code = 200

        def json(self):
            return {"valid": True, "expires_at": None}

    monkeypatch.setattr("httpx.post", lambda *a, **k: _Resp())
    monkeypatch.setattr(
        "mvp.license._verify_signature",
        lambda d, k: d.get("valid") is True,
    )
    result = validate_license("http://localhost:8000", "LZ-ABC", "hwid123")
    assert result["valid"] is True


def test_validate_license_rejects(monkeypatch):
    class _Resp:
        status_code = 200

        def json(self):
            return {"valid": False, "message": "License expired"}

    monkeypatch.setattr("httpx.post", lambda *a, **k: _Resp())
    monkeypatch.setattr("mvp.license._verify_signature", lambda d, k: True)
    with pytest.raises(LicenseError, match="License expired"):
        validate_license("http://localhost:8000", "LZ-ABC", "hwid123")


def test_validate_license_rejects_without_message(monkeypatch):
    class _Resp:
        status_code = 200

        def json(self):
            return {"valid": False}

    monkeypatch.setattr("httpx.post", lambda *a, **k: _Resp())
    monkeypatch.setattr("mvp.license._verify_signature", lambda d, k: True)
    with pytest.raises(LicenseError, match="License invalid"):
        validate_license("http://localhost:8000", "LZ-ABC", "hwid123")


def test_validate_license_http_error(monkeypatch):
    def _raise(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr("httpx.post", _raise)
    with pytest.raises(LicenseError, match="Cannot connect to backend"):
        validate_license("http://localhost:8000", "LZ-ABC", "hwid123")


def test_validate_license_server_error(monkeypatch):
    class _Resp:
        status_code = 500

    monkeypatch.setattr("httpx.post", lambda *a, **k: _Resp())
    with pytest.raises(LicenseError, match="500"):
        validate_license("http://localhost:8000", "LZ-ABC", "hwid123")


def test_validate_license_invalid_json(monkeypatch):
    class _Resp:
        status_code = 200

        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr("httpx.post", lambda *a, **k: _Resp())
    with pytest.raises(LicenseError, match="invalid JSON"):
        validate_license("http://localhost:8000", "LZ-ABC", "hwid123")


def test_validate_license_forbidden(monkeypatch):
    class _Resp:
        status_code = 403

    monkeypatch.setattr("httpx.post", lambda *a, **k: _Resp())
    with pytest.raises(LicenseError, match="403"):
        validate_license("http://localhost:8000", "LZ-ABC", "hwid123")


def test_validate_license_missing_config():
    with pytest.raises(LicenseError):
        validate_license("", "", "hwid")


def _boom(*args, **kwargs):
    raise LicenseError("should not be called")


def test_check_license_dev_skips(monkeypatch):
    monkeypatch.setattr("mvp.license.BUILD_MODE", "dev")
    monkeypatch.setattr("mvp.license.validate_license", _boom)
    check_license("http://x", "k", "hwid")  # no raise


def test_check_license_prod_ok(monkeypatch):
    calls = {}
    monkeypatch.setattr(
        "mvp.license.validate_license",
        lambda u, k, h: calls.update(u=u, k=k, h=h) or {"valid": True},
    )
    check_license("http://x", "LZ-ABC", "hwid123")
    assert calls == {"u": "http://x", "k": "LZ-ABC", "h": "hwid123"}


def test_check_license_prod_with_dev_flags_still_validates(monkeypatch):
    # PROD build must ignore --dev / LASTZ_DEV_MODE: the license gate stays closed.
    calls = {}
    monkeypatch.setattr("mvp.license.BUILD_MODE", "prod")
    monkeypatch.setattr("sys.argv", ["LastZBot.exe", "--dev"])
    monkeypatch.setenv("LASTZ_DEV_MODE", "1")
    monkeypatch.setattr(
        "mvp.license.validate_license",
        lambda u, k, h: calls.update(u=u, k=k, h=h) or {"valid": True},
    )
    check_license("http://x", "LZ-ABC", "hwid123")
    assert calls  # validate_license MUST have been called


def test_check_license_prod_invalid_raises(monkeypatch):
    monkeypatch.setattr("mvp.license.validate_license", _boom)
    with pytest.raises(LicenseError, match="should not be called"):
        check_license("http://x", "k", "hwid")


def test_is_dev_mode_prod_ignores_dev_flag(monkeypatch):
    # PROD build must NOT honor --dev / env; BUILD_MODE wins.
    monkeypatch.setattr("mvp.license.BUILD_MODE", "prod")
    monkeypatch.setattr("sys.argv", ["LastZBot.exe", "--dev"])
    monkeypatch.setenv("LASTZ_DEV_MODE", "1")
    assert is_dev_mode() is False


def test_is_dev_mode_dev_build_still_dev(monkeypatch):
    monkeypatch.setattr("mvp.license.BUILD_MODE", "dev")
    monkeypatch.setattr("sys.argv", ["LastZBot.exe"])
    monkeypatch.delenv("LASTZ_DEV_MODE", raising=False)
    assert is_dev_mode() is True


def test_is_dev_mode_unknown_build_mode_honors_dev_flag(monkeypatch):
    monkeypatch.setattr("mvp.license.BUILD_MODE", "unknown")
    monkeypatch.setattr("sys.argv", ["LastZBot.exe", "--dev"])
    monkeypatch.delenv("LASTZ_DEV_MODE", raising=False)
    assert is_dev_mode() is True


def test_is_dev_mode_unknown_build_mode_false_without_flags(monkeypatch):
    monkeypatch.setattr("mvp.license.BUILD_MODE", "unknown")
    monkeypatch.setattr("sys.argv", ["LastZBot.exe"])
    monkeypatch.delenv("LASTZ_DEV_MODE", raising=False)
    assert is_dev_mode() is False


def test_validate_license_rejects_bad_signature(monkeypatch):
    class _Resp:
        status_code = 200

        def json(self):
            return {"valid": True, "signature": "ZmFsc2U=", "signed_payload": {"valid": True}}

    monkeypatch.setattr("httpx.post", lambda *a, **k: _Resp())
    monkeypatch.setattr("mvp.license._verify_signature", lambda d, k: False)
    with pytest.raises(LicenseError, match="signature"):
        validate_license("http://localhost:8000", "LZ-ABC", "hwid123")


def test_verify_signature_rejects_mismatched_key(monkeypatch):
    # signature is valid for a different license key -> rejected
    from mvp.backend.license_signing import generate_keypair, sign_payload

    priv, pub = generate_keypair()
    payload = {"valid": True, "license_key": "LZ-OTHER", "hwid": None}
    sig = sign_payload(payload, priv)
    # patch the public key constant so verification uses the generated key
    import mvp.license as license_mod

    monkeypatch.setattr(license_mod, "LICENSE_PUBLIC_KEY_PEM", pub)
    assert license_mod._verify_signature(
        {"signature": sig, "signed_payload": payload}, "LZ-ABC"
    ) is False


def test_verify_signature_accepts_valid_signed_payload(monkeypatch):
    from mvp.backend.license_signing import generate_keypair, sign_payload

    priv, pub = generate_keypair()
    payload = {"license_key": "LZ-ABC", "hwid": "hwid123", "valid": True,
               "message": "OK", "expires_at": None}
    sig = sign_payload(payload, priv)
    import mvp.license as license_mod

    monkeypatch.setattr(license_mod, "LICENSE_PUBLIC_KEY_PEM", pub)
    assert license_mod._verify_signature(
        {"signature": sig, "signed_payload": payload}, "LZ-ABC"
    ) is True


def test_verify_signature_rejects_missing_signature():
    import mvp.license as license_mod

    assert license_mod._verify_signature(
        {"valid": True, "signed_payload": {"valid": True}}, "LZ-ABC"
    ) is False


def test_verify_signature_rejects_non_string_signature():
    import mvp.license as license_mod

    assert license_mod._verify_signature(
        {"signature": 123, "signed_payload": {"valid": True}}, "LZ-ABC"
    ) is False
