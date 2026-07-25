"""Unit of Work (spec 6.2).

Wraps an ``AsyncSession`` so that every multi-step write runs in a single
atomic transaction: commit on clean exit, rollback on exception. The
repositories are exposed as lazy properties built over the active session.

Usage::

    async with UnitOfWork(session_factory) as uow:
        project = await uow.projects.save(Project(name="etl"))
        await uow.runners.save(Runner(project_id=project.id, ...))
"""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cron_dok.adapters.output.persistence.repositories import (
    SqliteEnvVarRepository,
    SqliteExecutionRepository,
    SqliteProjectRepository,
    SqliteRunnerRepository,
)
from cron_dok.ports.repositories import (
    EnvVarRepository,
    ExecutionRepository,
    ProjectRepository,
    RunnerRepository,
)


class UnitOfWork:
    """Atomic transaction scope exposing the repositories lazily."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._projects: ProjectRepository | None = None
        self._runners: RunnerRepository | None = None
        self._executions: ExecutionRepository | None = None
        self._env_vars: EnvVarRepository | None = None

    async def __aenter__(self) -> "UnitOfWork":
        self._session = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self._session is not None, "UnitOfWork used outside its context"
        try:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None
            self._projects = None
            self._runners = None
            self._executions = None
            self._env_vars = None

    @property
    def session(self) -> AsyncSession:
        """The session bound to this transaction."""
        if self._session is None:
            raise RuntimeError("UnitOfWork: no active session; use 'async with uow:'")
        return self._session

    @property
    def projects(self) -> ProjectRepository:
        """Project repository bound to the active session."""
        if self._projects is None:
            self._projects = SqliteProjectRepository(self.session)
        return self._projects

    @property
    def runners(self) -> RunnerRepository:
        """Runner repository bound to the active session."""
        if self._runners is None:
            self._runners = SqliteRunnerRepository(self.session)
        return self._runners

    @property
    def executions(self) -> ExecutionRepository:
        """Execution repository bound to the active session."""
        if self._executions is None:
            self._executions = SqliteExecutionRepository(self.session)
        return self._executions

    @property
    def env_vars(self) -> EnvVarRepository:
        """Env var repository bound to the active session."""
        if self._env_vars is None:
            self._env_vars = SqliteEnvVarRepository(self.session)
        return self._env_vars
