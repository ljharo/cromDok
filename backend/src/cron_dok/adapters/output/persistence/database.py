"""Async SQLite engine with the concurrency pragmas from spec section 6.1.

The pragmas are applied on every raw connection via the engine ``connect``
event, so they hold for sessions and for Alembic alike:

- ``journal_mode=WAL``   — readers do not block the writer
- ``busy_timeout=5000``  — retry instead of "database is locked"
- ``synchronous=NORMAL`` — durable enough with WAL, faster
- ``foreign_keys=ON``    — enforce FK constraints (incl. ON DELETE CASCADE)
"""

from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _set_sqlite_pragmas(dbapi_connection: DBAPIConnection, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_sqlite_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an async engine for ``database_url`` with the WAL pragmas attached."""
    engine = create_async_engine(database_url, echo=echo)
    event.listens_for(engine.sync_engine, "connect")(_set_sqlite_pragmas)
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the session factory used by UnitOfWork (spec 6.2)."""
    return async_sessionmaker(engine, expire_on_commit=False)
