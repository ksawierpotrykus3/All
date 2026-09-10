"""Unit tests for Pydantic schemas in mvp.backend.schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from mvp.backend.schemas import (
    AdminCreateLicenseRequest,
    AdminResetHwidRequest,
    LicenseInfo,
    LicenseValidateRequest,
    LicenseValidateResponse,
    TokenResponse,
    UserInfo,
    UserLogin,
    UserRegister,
)


class TestUserRegister:
    def test_valid_email_and_password(self):
        u = UserRegister(email="test@example.com", password="secret123")
        assert u.email == "test@example.com"
        assert u.password == "secret123"

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            UserRegister(email="not-an-email", password="secret123")

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError):
            UserRegister(password="secret123")

    def test_missing_password_raises(self):
        with pytest.raises(ValidationError):
            UserRegister(email="test@example.com")

    def test_short_password_rejected(self):
        """Pydantic Field(min_length=8) rejects short passwords."""
        with pytest.raises(ValidationError):
            UserRegister(email="test@example.com", password="short")

    def test_overlong_password_rejected(self):
        """Field(max_length=72) rejects passwords longer than 72 chars (bcrypt limit)."""
        with pytest.raises(ValidationError):
            UserRegister(email="test@example.com", password="a" * 73)


class TestUserLogin:
    def test_valid(self):
        u = UserLogin(email="test@example.com", password="secret123")
        assert u.email == "test@example.com"

    def test_short_password_rejected(self):
        """Pydantic Field(min_length=8) rejects short passwords."""
        with pytest.raises(ValidationError):
            UserLogin(email="test@example.com", password="short")

    def test_overlong_password_rejected(self):
        """Field(max_length=72) rejects passwords longer than 72 chars (bcrypt limit)."""
        with pytest.raises(ValidationError):
            UserLogin(email="test@example.com", password="a" * 73)


class TestTokenResponse:
    def test_default_token_type(self):
        t = TokenResponse(access_token="abc123")
        assert t.access_token == "abc123"
        assert t.token_type == "bearer"

    def test_custom_token_type(self):
        t = TokenResponse(access_token="abc123", token_type="jwt")
        assert t.token_type == "jwt"


class TestLicenseValidateRequest:
    def test_valid(self):
        r = LicenseValidateRequest(license_key="LZ-ABCD-1234")
        assert r.license_key == "LZ-ABCD-1234"

    def test_missing_key_raises(self):
        with pytest.raises(ValidationError):
            LicenseValidateRequest()


class TestLicenseValidateResponse:
    def test_valid_with_all_fields(self):
        payload = {"valid": True, "expires_at": "2026-12-31T23:59:59Z", "message": "ok"}
        r = LicenseValidateResponse(signature="sig123", signed_payload=payload)
        assert r.signature == "sig123"
        assert r.signed_payload == payload

    def test_defaults(self):
        r = LicenseValidateResponse()
        assert r.signature is None
        assert r.signed_payload is None


class TestUserInfo:
    def test_from_attributes(self):
        dt = datetime(2026, 1, 1)
        u = UserInfo(id="uuid-1", email="a@b.com", is_active=True, created_at=dt)
        assert u.id == "uuid-1"
        assert u.email == "a@b.com"
        assert u.is_active is True
        # Naive datetime from SQLite is coerced to UTC.
        assert u.created_at == dt.replace(tzinfo=UTC)
        assert u.created_at.tzinfo is not None

    def test_model_config_from_attributes(self):
        assert UserInfo.model_config["from_attributes"] is True


class TestLicenseInfo:
    def test_with_all_fields(self):
        dt = datetime(2026, 6, 1)
        li = LicenseInfo(
            id="lic-1",
            key="LZ-KEY",
            is_active=True,
            expires_at=dt,
            last_validated_at=dt,
        )
        assert li.id == "lic-1"
        assert li.key == "LZ-KEY"
        assert li.is_active is True
        # Naive datetimes from SQLite are coerced to UTC.
        assert li.expires_at == dt.replace(tzinfo=UTC)
        assert li.expires_at.tzinfo is not None
        assert li.last_validated_at == dt.replace(tzinfo=UTC)

    def test_model_config_from_attributes(self):
        assert LicenseInfo.model_config["from_attributes"] is True


class TestAdminCreateLicenseRequest:
    def test_valid(self):
        r = AdminCreateLicenseRequest(user_email="a@b.com")
        assert r.user_email == "a@b.com"
        assert r.expires_in_days == 30

    def test_zero_days_rejected(self):
        with pytest.raises(ValidationError):
            AdminCreateLicenseRequest(user_email="a@b.com", expires_in_days=0)

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            AdminCreateLicenseRequest(user_email="not-an-email")


class TestAdminResetHwidRequest:
    def test_valid(self):
        r = AdminResetHwidRequest(license_key="LZ-ABC")
        assert r.license_key == "LZ-ABC"

    def test_missing_key_raises(self):
        with pytest.raises(ValidationError):
            AdminResetHwidRequest()
