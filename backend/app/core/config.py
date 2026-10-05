from functools import cached_property
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "AttendEase API"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/attendease"

    SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 15

    # JSON list, e.g. ["http://localhost:5173"]
    CORS_ORIGINS: list[str] = []

    # Used to decide what "today" is when marking attendance
    TIMEZONE: str = "UTC"
    # Term name used when no term in the database covers the attendance date
    CURRENT_TERM: str = "2026-Term1"

    FIRST_ADMIN_EMAIL: str | None = None
    FIRST_ADMIN_PASSWORD: str | None = None
    FIRST_ADMIN_NAME: str = "System Administrator"

    @field_validator("DATABASE_URL")
    @classmethod
    def use_asyncpg_driver(cls, v: str) -> str:
        # Hosts such as Render and Railway hand out postgres:// URLs
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v.removeprefix(prefix)
        return v

    @field_validator("TIMEZONE")
    @classmethod
    def valid_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(
                f"'{v}' is not a timezone name. Use a region name such as "
                "Africa/Lagos, Europe/London or America/New_York (not UTC+1)."
            ) from None
        return v

    @cached_property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.TIMEZONE)


settings = Settings()
