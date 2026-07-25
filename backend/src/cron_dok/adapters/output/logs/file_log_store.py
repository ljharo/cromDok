"""File-based LogStore adapter (spec 6.4).

One file per execution: ``<log_dir>/<execution_id>.log``. Writes go through
``asyncio.to_thread`` so appending never blocks the event loop, and every
write is flushed so incremental readers (polling with an offset) see fresh
content while the execution is still running.
"""

import asyncio
from pathlib import Path
from typing import TextIO

from cron_dok.ports.logs.log_store import LogSink, LogStore


class _FileLogSink(LogSink):
    """LogSink appending to an open text file, flushed on every write."""

    def __init__(self, handle: TextIO) -> None:
        self._handle = handle

    async def write(self, chunk: str) -> None:
        await asyncio.to_thread(self._write_and_flush, chunk)

    def _write_and_flush(self, chunk: str) -> None:
        self._handle.write(chunk)
        self._handle.flush()

    async def close(self) -> None:
        await asyncio.to_thread(self._handle.close)


class FileLogStore(LogStore):
    """LogStore persisting logs as local files under ``log_dir``."""

    def __init__(self, log_dir: str | Path) -> None:
        """Initialize the store; the directory is created lazily on first write.

        Args:
            log_dir: directory holding one ``<execution_id>.log`` file per
                execution (``settings.log_dir`` in production).
        """
        self._log_dir = Path(log_dir)

    def path_for(self, execution_id: int) -> Path:
        """Return the log file path of ``execution_id`` (it may not exist yet)."""
        return self._log_dir / f"{execution_id}.log"

    async def open_writer(self, execution_id: int) -> LogSink:
        """Open a sink for ``execution_id``, truncating any previous content."""
        await asyncio.to_thread(self._log_dir.mkdir, parents=True, exist_ok=True)
        handle = await asyncio.to_thread(self.path_for(execution_id).open, "w", encoding="utf-8")
        return _FileLogSink(handle)

    async def read(self, execution_id: int, offset: int = 0) -> tuple[str, int]:
        """Read from byte ``offset``; return (content, next_offset).

        A missing log file is not an error: it returns an empty chunk with
        the offset unchanged, so polling works before the execution starts.
        """

        def _read() -> tuple[str, int]:
            path = self.path_for(execution_id)
            if not path.exists():
                return "", offset
            with path.open("rb") as handle:
                handle.seek(offset)
                data = handle.read()
            return data.decode("utf-8", errors="replace"), offset + len(data)

        return await asyncio.to_thread(_read)

    async def delete(self, execution_id: int) -> None:
        """Delete the log of ``execution_id`` (no error if missing)."""
        await asyncio.to_thread(self.path_for(execution_id).unlink, missing_ok=True)
