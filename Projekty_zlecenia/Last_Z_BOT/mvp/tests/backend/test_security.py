import pytest

from mvp.backend.security import validate_startup_security


def test_validate_rejects_short_secret(monkeypatch):
    from mvp.backend import security
    monkeypatch.setattr(security.settings, "jwt_secret", "short")
    with pytest.raises(RuntimeError):
        validate_startup_security()


def test_validate_rejects_default_secret(monkeypatch):
    from mvp.backend import security
    monkeypatch.setattr(security.settings, "jwt_secret", "dev-secret-change-me")
    with pytest.raises(RuntimeError):
        validate_startup_security()


def test_validate_accepts_strong_secret(monkeypatch):
    from mvp.backend import security
    monkeypatch.setattr(security.settings, "jwt_secret", "strong-" + "s" * 40)
    validate_startup_security()  # should not raise


def test_cors_allows_configured_origin(client):
    resp = client.options(
        "/license/validate",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client):
    resp = client.options(
        "/license/validate",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in resp.headers
