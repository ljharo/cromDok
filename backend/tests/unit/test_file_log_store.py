"""Unit tests for FileLogStore against a real filesystem (tmp_path)."""

import pytest

from cron_dok.adapters.output.logs.file_log_store import FileLogStore


@pytest.fixture
def log_store(tmp_path) -> FileLogStore:
    return FileLogStore(tmp_path / "logs")


async def test_write_then_read_full(log_store) -> None:
    sink = await log_store.open_writer(1)
    await sink.write("hello ")
    await sink.write("world\n")
    await sink.close()

    content, next_offset = await log_store.read(1)
    assert content == "hello world\n"
    assert next_offset == len(b"hello world\n")


async def test_read_is_incremental(log_store) -> None:
    sink = await log_store.open_writer(2)
    await sink.write("first\n")

    chunk, offset = await log_store.read(2)
    assert chunk == "first\n"

    await sink.write("second\n")
    chunk, offset2 = await log_store.read(2, offset)
    assert chunk == "second\n"
    assert offset2 > offset

    # Nothing new: empty chunk, offset unchanged.
    chunk, offset3 = await log_store.read(2, offset2)
    assert chunk == ""
    assert offset3 == offset2
    await sink.close()


async def test_open_writer_truncates_previous_content(log_store) -> None:
    sink = await log_store.open_writer(3)
    await sink.write("old content\n")
    await sink.close()

    sink = await log_store.open_writer(3)
    await sink.write("new\n")
    await sink.close()

    content, _ = await log_store.read(3)
    assert content == "new\n"


async def test_read_missing_file_returns_empty(log_store) -> None:
    content, next_offset = await log_store.read(999, offset=10)
    assert content == ""
    assert next_offset == 10


async def test_delete_removes_file_and_is_idempotent(log_store) -> None:
    sink = await log_store.open_writer(4)
    await sink.write("bye\n")
    await sink.close()
    assert log_store.path_for(4).exists()

    await log_store.delete(4)
    assert not log_store.path_for(4).exists()

    await log_store.delete(4)  # no error when missing


async def test_handles_non_ascii_content(log_store) -> None:
    sink = await log_store.open_writer(5)
    await sink.write("café ☕\n")
    await sink.close()

    content, _ = await log_store.read(5)
    assert content == "café ☕\n"
