"""Abstract repository port for Execution."""

from abc import ABC, abstractmethod
from datetime import datetime

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

    @abstractmethod
    async def list_finished_before(self, cutoff: datetime) -> list[Execution]:
        """Return executions with ``finished_at`` strictly before ``cutoff``.

        Executions without ``finished_at`` (queued/running) are never
        included. Used by the retention purge (spec 6.4); filtering by
        terminal status is left to the caller.
        """

    @abstractmethod
    async def delete(self, execution_id: int) -> None:
        """Delete the execution ``execution_id``; a no-op if it does not exist."""
