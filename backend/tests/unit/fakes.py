"""In-memory fakes implementing the repository ports (no database).

State lives in shared dicts so a single :class:`FakeUnitOfWork` instance can
be reused across ``async with`` blocks, mirroring how the real UnitOfWork
persists to the database file between transactions.
"""

import asyncio
from dataclasses import replace
from datetime import datetime
from types import TracebackType

from cron_dok.domain.entities.api_key import ApiKey
from cron_dok.domain.entities.env_var import EnvVar
from cron_dok.domain.entities.execution import Execution
from cron_dok.domain.entities.project import Project
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.entities.session import Session
from cron_dok.domain.entities.user import User
from cron_dok.domain.value_objects.execution_result import ExecutionResult
from cron_dok.ports.executors.job_executor import JobExecutor
from cron_dok.ports.logs.log_store import LogSink, LogStore
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


class InMemoryProjectRepository(ProjectRepository):
    """ProjectRepository backed by a dict."""

    def __init__(self) -> None:
        self._items: dict[int, Project] = {}
        self._next_id = 1

    async def save(self, project: Project) -> Project:
        if project.id is None:
            project = replace(project, id=self._next_id)
            self._next_id += 1
        elif project.id not in self._items:
            raise ValueError(f"Project {project.id} does not exist")
        assert project.id is not None
        self._items[project.id] = project
        return project

    async def get_by_id(self, project_id: int) -> Project | None:
        return self._items.get(project_id)

    async def list_all(self) -> list[Project]:
        return list(self._items.values())

    async def delete(self, project_id: int) -> None:
        self._items.pop(project_id, None)


class InMemoryRunnerRepository(RunnerRepository):
    """RunnerRepository backed by a dict."""

    def __init__(self) -> None:
        self._items: dict[int, Runner] = {}
        self._next_id = 1

    async def save(self, runner: Runner) -> Runner:
        if runner.id is None:
            runner = replace(runner, id=self._next_id)
            self._next_id += 1
        elif runner.id not in self._items:
            raise ValueError(f"Runner {runner.id} does not exist")
        assert runner.id is not None
        self._items[runner.id] = runner
        return runner

    async def get_by_id(self, runner_id: int) -> Runner | None:
        return self._items.get(runner_id)

    async def list_by_project(self, project_id: int) -> list[Runner]:
        return [r for r in self._items.values() if r.project_id == project_id]

    async def list_all(self) -> list[Runner]:
        return list(self._items.values())

    async def delete(self, runner_id: int) -> None:
        self._items.pop(runner_id, None)


class InMemoryExecutionRepository(ExecutionRepository):
    """ExecutionRepository backed by a dict."""

    def __init__(self) -> None:
        self._items: dict[int, Execution] = {}
        self._next_id = 1

    async def save(self, execution: Execution) -> Execution:
        if execution.id is None:
            execution = replace(execution, id=self._next_id)
            self._next_id += 1
        assert execution.id is not None
        self._items[execution.id] = execution
        return execution

    async def get_by_id(self, execution_id: int) -> Execution | None:
        return self._items.get(execution_id)

    async def list_by_runner(self, runner_id: int) -> list[Execution]:
        return [e for e in self._items.values() if e.runner_id == runner_id]

    async def list_finished_before(self, cutoff: datetime) -> list[Execution]:
        return [
            e for e in self._items.values() if e.finished_at is not None and e.finished_at < cutoff
        ]

    async def delete(self, execution_id: int) -> None:
        self._items.pop(execution_id, None)


class InMemoryEnvVarRepository(EnvVarRepository):
    """EnvVarRepository backed by a dict."""

    def __init__(self) -> None:
        self._items: dict[int, EnvVar] = {}
        self._next_id = 1

    async def save(self, env_var: EnvVar) -> EnvVar:
        if env_var.id is None:
            env_var = replace(env_var, id=self._next_id)
            self._next_id += 1
        assert env_var.id is not None
        self._items[env_var.id] = env_var
        return env_var

    async def get_by_id(self, env_var_id: int) -> EnvVar | None:
        return self._items.get(env_var_id)

    async def list_by_project(self, project_id: int) -> list[EnvVar]:
        return [v for v in self._items.values() if v.project_id == project_id]

    async def delete(self, env_var_id: int) -> None:
        self._items.pop(env_var_id, None)


class InMemoryUserRepository(UserRepository):
    """UserRepository backed by a dict."""

    def __init__(self) -> None:
        self._items: dict[int, User] = {}
        self._next_id = 1

    async def save(self, user: User) -> User:
        if user.id is None:
            user = replace(user, id=self._next_id)
            self._next_id += 1
        elif user.id not in self._items:
            raise ValueError(f"User {user.id} does not exist")
        assert user.id is not None
        self._items[user.id] = user
        return user

    async def get_by_id(self, user_id: int) -> User | None:
        return self._items.get(user_id)

    async def get_by_username(self, username: str) -> User | None:
        return next((u for u in self._items.values() if u.username == username), None)

    async def list_all(self) -> list[User]:
        return list(self._items.values())

    async def delete(self, user_id: int) -> None:
        self._items.pop(user_id, None)


class InMemorySessionRepository(SessionRepository):
    """SessionRepository backed by a dict."""

    def __init__(self) -> None:
        self._items: dict[int, Session] = {}
        self._next_id = 1

    async def save(self, session: Session) -> Session:
        if session.id is None:
            session = replace(session, id=self._next_id)
            self._next_id += 1
        assert session.id is not None
        self._items[session.id] = session
        return session

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        return next((s for s in self._items.values() if s.token_hash == token_hash), None)

    async def delete_by_token_hash(self, token_hash: str) -> None:
        for session_id, session in list(self._items.items()):
            if session.token_hash == token_hash:
                del self._items[session_id]

    async def delete_by_user(self, user_id: int) -> None:
        for session_id, session in list(self._items.items()):
            if session.user_id == user_id:
                del self._items[session_id]


class InMemoryApiKeyRepository(ApiKeyRepository):
    """ApiKeyRepository backed by a dict."""

    def __init__(self) -> None:
        self._items: dict[int, ApiKey] = {}
        self._next_id = 1

    async def save(self, api_key: ApiKey) -> ApiKey:
        if api_key.id is None:
            api_key = replace(api_key, id=self._next_id)
            self._next_id += 1
        elif api_key.id not in self._items:
            raise ValueError(f"ApiKey {api_key.id} does not exist")
        assert api_key.id is not None
        self._items[api_key.id] = api_key
        return api_key

    async def get_by_id(self, api_key_id: int) -> ApiKey | None:
        return self._items.get(api_key_id)

    async def get_by_key_hash(self, key_hash: str) -> ApiKey | None:
        return next((k for k in self._items.values() if k.key_hash == key_hash), None)

    async def list_all(self) -> list[ApiKey]:
        return list(self._items.values())


class FakeEncryptor:
    """Reversible test double for the Encryptor protocol (no real crypto).

    Reverses the plaintext so ciphertext never contains it verbatim,
    mirroring what tests assert about the real Fernet adapter.
    """

    def encrypt(self, plaintext: str) -> str:
        return f"enc::{plaintext[::-1]}"

    def decrypt(self, token: str) -> str:
        return token.removeprefix("enc::")[::-1]


class FakeUnitOfWork(AbstractUnitOfWork):
    """Unit of Work over the in-memory repositories (no transaction)."""

    def __init__(self) -> None:
        self._projects = InMemoryProjectRepository()
        self._runners = InMemoryRunnerRepository()
        self._executions = InMemoryExecutionRepository()
        self._env_vars = InMemoryEnvVarRepository()
        self._users = InMemoryUserRepository()
        self._sessions = InMemorySessionRepository()
        self._api_keys = InMemoryApiKeyRepository()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    @property
    def projects(self) -> ProjectRepository:
        return self._projects

    @property
    def runners(self) -> RunnerRepository:
        return self._runners

    @property
    def executions(self) -> ExecutionRepository:
        return self._executions

    @property
    def env_vars(self) -> EnvVarRepository:
        return self._env_vars

    @property
    def users(self) -> UserRepository:
        return self._users

    @property
    def sessions(self) -> SessionRepository:
        return self._sessions

    @property
    def api_keys(self) -> ApiKeyRepository:
        return self._api_keys


class FakeLogSink(LogSink):
    """LogSink appending chunks to a shared list."""

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks
        self.closed = False

    async def write(self, chunk: str) -> None:
        self.chunks.append(chunk)

    async def close(self) -> None:
        self.closed = True


class FakeLogStore(LogStore):
    """LogStore keeping logs in memory, keyed by execution id."""

    def __init__(self) -> None:
        self._logs: dict[int, list[str]] = {}
        self.sinks: dict[int, FakeLogSink] = {}

    async def open_writer(self, execution_id: int) -> FakeLogSink:
        sink = FakeLogSink(self._logs.setdefault(execution_id, []))
        self.sinks[execution_id] = sink
        return sink

    async def read(self, execution_id: int, offset: int = 0) -> tuple[str, int]:
        content = "".join(self._logs.get(execution_id, []))
        return content[offset:], len(content)

    async def delete(self, execution_id: int) -> None:
        self._logs.pop(execution_id, None)

    def content(self, execution_id: int) -> str:
        """Return the whole log of an execution ("" if none)."""
        return "".join(self._logs.get(execution_id, []))


class FakeJobExecutor(JobExecutor):
    """JobExecutor with controllable timing and outcome.

    Tracks concurrency (``max_concurrent``) for semaphore tests. With
    ``block=True`` every call waits until cancelled or until ``release`` is
    set; cancellations are recorded in ``cancelled_runners`` and re-raised,
    honoring the cancellation contract expected by ExecutionQueue.
    """

    def __init__(
        self,
        result: ExecutionResult | None = None,
        *,
        delay: float = 0.0,
        block: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.result = result or ExecutionResult(exit_code=0, duration_ms=1)
        self.delay = delay
        self.block = block
        self.error = error
        self.release = asyncio.Event()
        self.started_runners: list[int] = []
        self.cancelled_runners: list[int] = []
        self.env_vars_received: list[dict[str, str]] = []
        self.current = 0
        self.max_concurrent = 0

    async def execute(
        self, runner: Runner, env_vars: dict[str, str], log_sink: LogSink
    ) -> ExecutionResult:
        assert runner.id is not None
        self.started_runners.append(runner.id)
        self.env_vars_received.append(dict(env_vars))
        self.current += 1
        self.max_concurrent = max(self.max_concurrent, self.current)
        try:
            if self.block:
                await self.release.wait()
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.error is not None:
                raise self.error
            await log_sink.write(f"fake output for runner {runner.id}\n")
            return self.result
        except asyncio.CancelledError:
            self.cancelled_runners.append(runner.id)
            raise
        finally:
            self.current -= 1
