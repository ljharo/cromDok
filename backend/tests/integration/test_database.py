"""The SQLite engine must apply the pragmas of spec 6.1 on every connection."""

from sqlalchemy import text


async def test_wal_mode_enabled(engine) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA journal_mode"))
        assert result.scalar_one() == "wal"


async def test_busy_timeout_enabled(engine) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA busy_timeout"))
        assert result.scalar_one() == 5000


async def test_synchronous_normal(engine) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA synchronous"))
        assert result.scalar_one() == 1  # NORMAL


async def test_foreign_keys_enabled(engine) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA foreign_keys"))
        assert result.scalar_one() == 1
