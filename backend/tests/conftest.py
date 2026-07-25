"""Shared fixtures: a real SQLite database per test, in pytest's tmp_path."""

from collections.abc import AsyncIterator, Callable

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from cron_dok.adapters.output.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from cron_dok.adapters.output.persistence.models import Base
from cron_dok.adapters.output.persistence.unit_of_work import UnitOfWork
from cron_dok.services.project_service import ProjectService
from cron_dok.services.runner_service import RunnerService


@pytest.fixture
async def engine(tmp_path) -> AsyncIterator[AsyncEngine]:
    engine = create_sqlite_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
def uow(session_factory) -> UnitOfWork:
    return UnitOfWork(session_factory)


@pytest.fixture
def uow_factory(session_factory) -> Callable[[], UnitOfWork]:
    return lambda: UnitOfWork(session_factory)


@pytest.fixture
def project_service(uow_factory) -> ProjectService:
    return ProjectService(uow_factory)


@pytest.fixture
def runner_service(uow_factory) -> RunnerService:
    return RunnerService(uow_factory)
