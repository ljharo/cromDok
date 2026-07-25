"""Application settings loaded from environment variables (prefix CRONDOK_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """CronDok runtime configuration.

    Values are read from environment variables with the ``CRONDOK_`` prefix
    (e.g. ``CRONDOK_MASTER_KEY``, ``CRONDOK_MAX_CONCURRENT_JOBS``).
    """

    model_config = SettingsConfigDict(env_prefix="CRONDOK_", env_file=".env")

    database_url: str = "sqlite+aiosqlite:///data/crondok.db"
    master_key: str | None = None
    max_concurrent_jobs: int = 4
    log_retention_days: int = 30
    log_dir: str = "data/logs"


def get_settings() -> Settings:
    """Build a Settings instance from the current environment."""
    return Settings()
