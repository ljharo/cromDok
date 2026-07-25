"""Alembic environment (async).

URL resolution order:
1. ``CRONDOK_DATABASE_URL`` environment variable (used by tests/CI to point
   at a temporary database).
2. ``sqlalchemy.url`` from alembic.ini, if set.
3. ``Settings().database_url`` (default: ``sqlite+aiosqlite:///data/crondok.db``).

The engine is built with ``cron_dok.adapters.output.persistence.database``
so migrations run with the same WAL pragmas as the application (spec 6.1);
``journal_mode=WAL`` persists in the database file.
"""

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.engine import Connection

from alembic import context
from cron_dok.adapters.output.persistence.database import create_sqlite_engine
from cron_dok.adapters.output.persistence.models import Base
from cron_dok.config import Settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

database_url = (
    os.environ.get("CRONDOK_DATABASE_URL")
    or config.get_main_option("sqlalchemy.url")
    or Settings().database_url
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a connection)."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an engine (with WAL pragmas) and run the migrations."""
    connectable = create_sqlite_engine(database_url)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
