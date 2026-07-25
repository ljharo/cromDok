"""API test fixtures.

A real FastAPI app per test (lifespan included) over SQLite in ``tmp_path``,
with a fake executor and a fake scheduler backend — the execution queue is
the real one, so trigger → queue → execution runs end to end.
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from cron_dok.config import Settings
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.entities.user import User, UserRole
from cron_dok.main import create_app
from cron_dok.services.scheduler_service import SystemJobCallback, TriggerCallback
from tests.unit.fakes import FakeJobExecutor

DEFAULT_PASSWORD = "test-password-123"
"""Fixture password; meets the 12-char Argon2id policy minimum."""

API = "/api/v1"


class FakeJobScheduler:
    """JobScheduler test double recording registered jobs (never fires)."""

    def __init__(self) -> None:
        self.jobs: dict[int, tuple[Runner, TriggerCallback]] = {}
        self.system_jobs: dict[str, tuple[SystemJobCallback, int, int]] = {}
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def shutdown(self) -> None:
        self.stopped = True

    def add_job(self, runner: Runner, callback: TriggerCallback) -> None:
        assert runner.id is not None
        self.jobs[runner.id] = (runner, callback)

    def remove_job(self, runner_id: int) -> None:
        self.jobs.pop(runner_id, None)

    def add_system_job(
        self, job_id: str, callback: SystemJobCallback, *, hour: int, minute: int
    ) -> None:
        self.system_jobs[job_id] = (callback, hour, minute)


@dataclass
class TestApp:
    """The app under test plus its injected fakes and settings."""

    app: FastAPI
    settings: Settings
    executor: FakeJobExecutor
    scheduler: FakeJobScheduler


@pytest.fixture
async def test_app(tmp_path) -> AsyncIterator[TestApp]:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        log_dir=str(tmp_path / "logs"),
        master_key=Fernet.generate_key().decode("ascii"),
        executor_enabled=False,
    )
    executor = FakeJobExecutor()
    scheduler = FakeJobScheduler()
    app = create_app(settings, executor=executor, scheduler_backend=scheduler)
    async with app.router.lifespan_context(app):
        yield TestApp(app=app, settings=settings, executor=executor, scheduler=scheduler)


@pytest.fixture
def client_factory(test_app: TestApp) -> Callable[[], AsyncClient]:
    """Build clients bound to the test app; each has its own cookie jar."""

    def _factory() -> AsyncClient:
        return AsyncClient(
            transport=ASGITransport(app=test_app.app),
            base_url="http://testserver",
        )

    return _factory


@pytest.fixture
async def client(client_factory) -> AsyncIterator[AsyncClient]:
    async with client_factory() as client:
        yield client


@pytest.fixture
async def admin_client(test_app: TestApp, client_factory) -> AsyncIterator[AsyncClient]:
    """A client logged in as a freshly created admin."""
    await make_user(test_app, "fixture-admin", "admin")
    async with client_factory() as client:
        await login(client, "fixture-admin")
        yield client


async def make_user(
    test_app: TestApp,
    username: str,
    role: UserRole,
    password: str = DEFAULT_PASSWORD,
) -> None:
    """Insert a user directly through the UoW (bypasses the API)."""
    password_service = test_app.app.state.password_service
    async with test_app.app.state.uow_factory() as uow:
        await uow.users.save(
            User(
                username=username,
                password_hash=password_service.hash(password),
                role=role,
            )
        )


async def login(client: AsyncClient, username: str, password: str = DEFAULT_PASSWORD) -> None:
    """Log in through the API; fails the test unless it succeeds."""
    response = await client.post(
        f"{API}/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
