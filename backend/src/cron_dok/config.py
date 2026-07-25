"""Application settings loaded from environment variables (prefix CRONDOK_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """CronDok runtime configuration.

    Values are read from environment variables with the ``CRONDOK_`` prefix
    (e.g. ``CRONDOK_MASTER_KEY``, ``CRONDOK_MAX_CONCURRENT_JOBS``).
    """

    model_config = SettingsConfigDict(env_prefix="CRONDOK_", env_file=".env")

    data_dir: str = "data"
    database_url: str = "sqlite+aiosqlite:///data/crondok.db"
    master_key: str | None = None
    max_concurrent_jobs: int = 4
    log_retention_days: int = 30
    log_dir: str = "data/logs"
    docker_image_python: str = "python:3.12-slim"
    docker_image_node: str = "node:20-slim"
    docker_image_bash: str = "bash:5"
    # When false (or when the Docker daemon is unreachable at startup), the
    # app boots with a fallback executor that fails every execution; useful
    # for running the API without a Docker daemon.
    executor_enabled: bool = True


def get_settings() -> Settings:
    """Build a Settings instance from the current environment."""
    return Settings()
