"""Abstract Unit of Work port (spec 6.2).

Application services depend on this abstraction through a factory
(``Callable[[], AbstractUnitOfWork]``) so they can be unit tested with
in-memory fakes; the production implementation is
``cron_dok.adapters.output.persistence.unit_of_work.UnitOfWork``.
"""

from abc import ABC, abstractmethod
from types import TracebackType

from cron_dok.ports.repositories import (
    EnvVarRepository,
    ExecutionRepository,
    ProjectRepository,
    RunnerRepository,
    SessionRepository,
    UserRepository,
)


class AbstractUnitOfWork(ABC):
    """Atomic transaction scope exposing the repositories.

    Entering the context opens a transaction; leaving it commits on clean
    exit and rolls back on exception.
    """

    @abstractmethod
    async def __aenter__(self) -> "AbstractUnitOfWork":
        """Open the transaction scope."""

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Commit on clean exit, roll back on exception."""

    @property
    @abstractmethod
    def projects(self) -> ProjectRepository:
        """Project repository bound to the active transaction."""

    @property
    @abstractmethod
    def runners(self) -> RunnerRepository:
        """Runner repository bound to the active transaction."""

    @property
    @abstractmethod
    def executions(self) -> ExecutionRepository:
        """Execution repository bound to the active transaction."""

    @property
    @abstractmethod
    def env_vars(self) -> EnvVarRepository:
        """Env var repository bound to the active transaction."""

    @property
    @abstractmethod
    def users(self) -> UserRepository:
        """User repository bound to the active transaction."""

    @property
    @abstractmethod
    def sessions(self) -> SessionRepository:
        """Session repository bound to the active transaction."""
