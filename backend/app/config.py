from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Ins"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://ins:ins@localhost:5432/ins"
    redis_url: str = "redis://localhost:6379/0"

    admin_password: str = "admin"
    auth_secret: str = "change-me-in-production-please-use-32-chars"
    auth_ttl_seconds: int = 60 * 60 * 24 * 7

    storage_dir: Path = Path("storage")
    job_ttl_hours: int = 24

    download_min_interval: float = 3.0
    download_timeout: float = 30.0
    download_attempts: int = 3

    instagram_login: str | None = None
    instagram_session_file: Path | None = None

    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    max_batch_size: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="INS_",
        extra="ignore",
    )

    @field_validator("instagram_login", "instagram_session_file", mode="before")
    @classmethod
    def empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def highlights_available(self) -> bool:
        return bool(
            self.instagram_login
            and self.instagram_session_file
            and self.instagram_session_file.is_file()
        )

    @property
    def highlights_reason(self) -> str | None:
        if self.highlights_available:
            return None
        return (
            "Highlights требуют сессию Instagram: задайте INS_INSTAGRAM_LOGIN "
            "и INS_INSTAGRAM_SESSION_FILE."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
