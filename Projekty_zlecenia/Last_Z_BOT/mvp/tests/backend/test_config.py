"""Unit tests for mvp.backend.config.Settings."""
import os
from unittest.mock import patch

from mvp.backend.config import Settings


class TestSettingsDefaults:
    def test_database_url_default(self):
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.database_url == "sqlite:///./joaxx.db"

    def test_jwt_secret_default(self):
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.jwt_secret == "dev-secret-change-me"

    def test_jwt_algorithm_default(self):
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.jwt_algorithm == "HS256"

    def test_access_token_expire_minutes_default(self):
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.access_token_expire_minutes == 1440

    def test_stripe_defaults_empty(self):
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.stripe_secret_key == ""
        assert s.stripe_webhook_secret == ""
        assert s.stripe_price_id == ""

    def test_license_grace_period_hours_default(self):
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.license_grace_period_hours == 24


class TestSettingsFromEnv:
    def test_database_url_from_env(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/db"}):
            s = Settings()
            assert s.database_url == "postgresql://localhost/db"

    def test_jwt_secret_from_env(self):
        with patch.dict(os.environ, {"JWT_SECRET": "prod-secret"}):
            s = Settings()
            assert s.jwt_secret == "prod-secret"

    def test_stripe_secret_key_from_env(self):
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_live_123"}):
            s = Settings()
            assert s.stripe_secret_key == "sk_live_123"

    def test_license_grace_period_from_env(self):
        with patch.dict(os.environ, {"LICENSE_GRACE_PERIOD_HOURS": "48"}):
            s = Settings()
            assert s.license_grace_period_hours == 48

    def test_model_config_has_env_file(self):
        assert "env_file" in Settings.model_config
        assert Settings.model_config["env_file"] == ".env"
