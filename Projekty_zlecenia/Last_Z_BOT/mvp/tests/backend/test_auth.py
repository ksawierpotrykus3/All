"""Unit tests for mvp.backend.auth (password hashing + JWT)."""
from unittest.mock import patch

from mvp.backend.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_returns_string(self):
        h = hash_password("mysecret")
        assert isinstance(h, str)
        assert h != "mysecret"

    def test_verify_correct_password(self):
        h = hash_password("correct")
        assert verify_password("correct", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("correct")
        assert verify_password("wrong", h) is False

    def test_hash_is_deterministic_for_verify(self):
        """Same password hashed twice produces different salts but both verify."""
        h1 = hash_password("secret")
        h2 = hash_password("secret")
        assert h1 != h2  # different salts
        assert verify_password("secret", h1) is True
        assert verify_password("secret", h2) is True


class TestJWT:
    def test_create_and_decode_roundtrip(self):
        token = create_access_token("user-123", expires_minutes=60)
        assert isinstance(token, str)

        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user-123"

    def test_decode_invalid_token_returns_none(self):
        assert decode_access_token("not.a.valid.token") is None

    def test_decode_empty_string_returns_none(self):
        assert decode_access_token("") is None

    def test_token_contains_exp_and_iat(self):
        token = create_access_token("user-456", expires_minutes=30)
        decoded = decode_access_token(token)
        assert "exp" in decoded
        assert "iat" in decoded
        assert decoded["sub"] == "user-456"

    def test_expired_token_returns_none(self):
        with patch("mvp.backend.auth.settings") as mock_settings:
            mock_settings.jwt_secret = "test-secret"
            mock_settings.jwt_algorithm = "HS256"
            mock_settings.access_token_expire_minutes = 1440

            # Create token with negative expiry
            token = create_access_token("user-789", expires_minutes=-1)
            # Token expired immediately
            decoded = decode_access_token(token)
            assert decoded is None
