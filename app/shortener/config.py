from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (12-factor style)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://shortener:shortener@localhost:5432/shortener"
    base_url: str = "http://localhost:8000"
    code_length: int = 7
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
