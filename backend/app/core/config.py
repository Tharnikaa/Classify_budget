"""Application configuration loaded via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
CONTRACTS_DIR = REPO_ROOT / "contracts"


class Settings(BaseSettings):
    """Runtime settings for ExpenseIt backend."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    DATABASE_URL: str = f"sqlite:///{(BACKEND_ROOT / 'expenseit_dev.db').as_posix()}"
    JWT_SECRET: str = "dev-only-expenseit-jwt-secret-change-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 720
    CORS_ORIGINS: str = "*"
    STORAGE_LOCAL_DIR: str = str(BACKEND_ROOT / "uploads")
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    BASE_CURRENCY: str = "INR"
    COMPANY_TIMEZONE: str = "Asia/Kolkata"

    @property
    def is_dev_role_switcher_enabled(self) -> bool:
        """Role switcher endpoint is strictly restricted to development mode."""
        return self.APP_ENV == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.CORS_ORIGINS.strip()
        if raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

