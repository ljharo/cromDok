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
    # Failure notification webhook (step 3.4): when None, notifications are
    # a no-op. The timeout applies per HTTP attempt (one retry allowed).
    webhook_url: str | None = None
    webhook_timeout: float = 5.0
    # Manual trigger rate limit (spec 9.4.3, plan 3.2): requests/minute per
    # caller identity (session user or API key).
    rate_limit_triggers: int = 100


def get_settings() -> Settings:
    """Build a Settings instance from the current environment."""
    return Settings()
