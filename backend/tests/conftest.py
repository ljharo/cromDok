"""Shared fixtures: a real SQLite database per test, in pytest's tmp_path."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from cron_dok.adapters.output.persistence.database import (
    create_session_factory,
    create_sqlite_engine,
)
from cron_dok.adapters.output.persistence.models import Base
from cron_dok.adapters.output.persistence.unit_of_work import UnitOfWork


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
