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
    # Default runner images are tags so jobs pick up upstream patch releases;
    # pin them by digest (e.g. "python:3.12-slim@sha256:...") via the env vars
    # if you prefer reproducible pulls over automatic updates.
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
    # Frontend build to serve alongside the API (phase 4, spec 1.3: one
    # container, no separate nginx just for static files). None in dev/tests,
    # where the frontend runs on its own Vite dev server.
    static_dir: str | None = None
    # Docker-out-of-Docker path translation (phase 4, spec 9.3): when CronDok
    # itself runs in a container with the host's socket mounted, paths it
    # gives the daemon for bind mounts (job workspaces) are resolved by the
    # daemon against the HOST filesystem, not this container's. Set to the
    # absolute host path backing ``data_dir`` (e.g. the left side of the
    # ``./data:/app/data`` compose volume) so the executor can translate;
    # None when CronDok runs directly on the host (dev), where no
    # translation is needed.
    host_data_dir: str | None = None
    # Set the Secure flag on the session cookie. Enable ONLY behind a TLS
    # reverse proxy — over plain HTTP the browser would refuse to send the
    # cookie back and login would break.
    cookie_secure: bool = False
    # Comma-separated IPs of trusted reverse proxies. When the socket peer is
    # one of them, the login rate limiter keys on the first X-Forwarded-For
    # entry instead of the proxy's IP. Only list proxies that overwrite the
    # X-Forwarded-For header; an empty list (default) never trusts it.
    trusted_proxies: str = ""


def get_settings() -> Settings:
    """Build a Settings instance from the current environment."""
    return Settings()
