"""Pydantic Settings model for proxy configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Account pool
    max_accounts: int = Field(default=3, ge=1, le=10)
    max_sessions_per_account: int = Field(default=5, ge=1, le=20)
    max_parallel_tool_calls: int = Field(default=20, ge=1, le=50)

    # Rate limiting / throttling
    min_base_delay: float = Field(default=8.0, ge=0.1, le=60.0)
    max_jitter: float = Field(default=5.0, ge=0.0, le=30.0)
    stream_backoff_delays: list[int] = Field(default=[3, 6, 12, 20])
    rate_backoff_delays: list[int] = Field(default=[3, 6, 12, 25])

    # Stream sieve
    max_capture_buf_size: int = Field(default=500_000, ge=10_000, le=10_000_000)
    drain_timeout: float = Field(default=30.0, ge=1.0, le=300.0)

    # Conversation state
    ttl: int = Field(default=86400, ge=300, le=604800)
    dedup_ttl: float = Field(default=60.0, ge=1.0, le=3600.0)

    # Prompt limits
    max_prompt_len: int = Field(default=150_000, ge=1000, le=1_000_000)
    tool_result_max_chars: int = Field(default=10_000, ge=100, le=100_000)

    # Watermark
    watermark_enabled: bool = Field(default=False)

    # Dashboard
    dashboard_db_path: str = Field(default="dashboard.db")

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")


settings = Settings()
