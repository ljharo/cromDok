"""Abstract repository port for Runner."""

from abc import ABC, abstractmethod

from cron_dok.domain.entities.runner import Runner


class RunnerRepository(ABC):
    """Persistence contract for runners."""

    @abstractmethod
    async def save(self, runner: Runner) -> Runner:
        """Insert (id is None) or update ``runner``; return the stored entity."""

    @abstractmethod
    async def get_by_id(self, runner_id: int) -> Runner | None:
        """Return the runner or None if it does not exist."""

    @abstractmethod
    async def list_by_project(self, project_id: int) -> list[Runner]:
        """Return all runners of a project."""

    @abstractmethod
    async def list_all(self) -> list[Runner]:
        """Return every runner, across all projects (used by rehydration)."""

    @abstractmethod
    async def delete(self, runner_id: int) -> None:
        """Delete a runner; its executions and runner-scoped env vars cascade."""
