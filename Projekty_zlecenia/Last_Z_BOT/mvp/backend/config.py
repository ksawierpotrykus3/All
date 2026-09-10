from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./joaxx.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""
    checkout_allowed_domains: str = "localhost"
    license_grace_period_hours: int = 24
    redis_url: str = "redis://localhost:6379/0"
    allowed_origins: str = "http://localhost:5173"
    license_private_key_pem: str = ""
    # In production the license response MUST be signed; the client verifies the signature.
    allow_unsigned_license_response: bool = False
    # Fail-closed: a Redis (rate limit) outage blocks validation instead of letting it pass.
    rate_limit_fail_closed: bool = True
    auto_create_tables: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
