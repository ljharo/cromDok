"""Abstract repository port for EnvVar."""

from abc import ABC, abstractmethod

from cron_dok.domain.entities.env_var import EnvVar


class EnvVarRepository(ABC):
    """Persistence contract for environment variables (encrypted at rest)."""

    @abstractmethod
    async def save(self, env_var: EnvVar) -> EnvVar:
        """Insert (id is None) or update ``env_var``; return the stored entity."""

    @abstractmethod
    async def get_by_id(self, env_var_id: int) -> EnvVar | None:
        """Return the env var or None if it does not exist."""

    @abstractmethod
    async def list_by_project(self, project_id: int) -> list[EnvVar]:
        """Return all env vars of a project (project- and runner-scoped)."""

    @abstractmethod
    async def delete(self, env_var_id: int) -> None:
        """Delete an env var."""
