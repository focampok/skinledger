"""Application settings read from environment variables (and `.env` in development)."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secret values are never shown by `repr` or `str`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    youcam_api_key: SecretStr | None = None
    youcam_base_url: str = "https://yce-api-01.makeupar.com"
    youcam_skin_version: str = "v2.0"
    youcam_mock: bool = True
    youcam_poll_interval_s: int = 5
    youcam_poll_timeout_s: int = 180
    data_dir: Path = Path("./data")
    public_url: str = "http://localhost:8000"
    invite_code: SecretStr = SecretStr("")
    admin_token: SecretStr = SecretStr("")
    max_real_analyses_per_person: int = 2
    daily_unit_cap: int = 96
    total_unit_cap: int = 480
    units_per_analysis: int = 16
    allow_upload: bool = True
    store_masks: bool = True
    camera_kit_language: str = "enu"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings object (cached)."""
    return Settings()


settings = get_settings()
