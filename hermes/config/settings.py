from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="HERMES_",
        extra="ignore",
    )

    app_name: str = "HERMES"
    environment: str = "development"
    version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://hermes:change-me@localhost:5432/hermes"
    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=20, ge=0)

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    log_level: str = "INFO"
    log_format: str = "json"

    enable_scheduler: bool = True
    scheduler_timezone: str = "America/Sao_Paulo"
    collector_interval_seconds: int = Field(default=900, ge=60)
    collector_initial_lookback_days: int = Field(default=30, ge=1)

    classifier_provider: str = "keyword"
    deepseek_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

