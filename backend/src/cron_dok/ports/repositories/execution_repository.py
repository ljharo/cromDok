"""Abstract repository port for Execution."""

from abc import ABC, abstractmethod

from cron_dok.domain.entities.execution import Execution


class ExecutionRepository(ABC):
    """Persistence contract for executions (metadata only; logs live in files)."""

    @abstractmethod
    async def save(self, execution: Execution) -> Execution:
        """Insert (id is None) or update ``execution``; return the stored entity."""

    @abstractmethod
    async def get_by_id(self, execution_id: int) -> Execution | None:
        """Return the execution or None if it does not exist."""

    @abstractmethod
    async def list_by_runner(self, runner_id: int) -> list[Execution]:
        """Return all executions of a runner, oldest first."""
