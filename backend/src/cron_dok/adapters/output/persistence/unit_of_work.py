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
    SqliteApiKeyRepository,
    SqliteEnvVarRepository,
    SqliteExecutionRepository,
    SqliteProjectRepository,
    SqliteRunnerRepository,
    SqliteSessionRepository,
    SqliteUserRepository,
)
from cron_dok.ports.repositories import (
    ApiKeyRepository,
    EnvVarRepository,
    ExecutionRepository,
    ProjectRepository,
    RunnerRepository,
    SessionRepository,
    UserRepository,
)
from cron_dok.ports.unit_of_work import AbstractUnitOfWork


class UnitOfWork(AbstractUnitOfWork):
    """Atomic transaction scope exposing the repositories lazily."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._projects: ProjectRepository | None = None
        self._runners: RunnerRepository | None = None
        self._executions: ExecutionRepository | None = None
        self._env_vars: EnvVarRepository | None = None
        self._users: UserRepository | None = None
        self._sessions: SessionRepository | None = None
        self._api_keys: ApiKeyRepository | None = None

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
            self._users = None
            self._sessions = None
            self._api_keys = None

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

    @property
    def users(self) -> UserRepository:
        """User repository bound to the active session."""
        if self._users is None:
            self._users = SqliteUserRepository(self.session)
        return self._users

    @property
    def sessions(self) -> SessionRepository:
        """Session repository bound to the active session."""
        if self._sessions is None:
            self._sessions = SqliteSessionRepository(self.session)
        return self._sessions

    @property
    def api_keys(self) -> ApiKeyRepository:
        """API key repository bound to the active session."""
        if self._api_keys is None:
            self._api_keys = SqliteApiKeyRepository(self.session)
        return self._api_keys
