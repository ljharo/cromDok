"""Log storage port (spec 4.2.2 and 6.4).

Logs are kept outside the database; MVP implementation is local files
(``data/logs/<execution_id>.log``), future implementations could target S3.
"""

from abc import ABC, abstractmethod


class LogSink(ABC):
    """Writable stream for the output of one execution."""

    @abstractmethod
    async def write(self, chunk: str) -> None:
        """Append a chunk of output."""

    @abstractmethod
    async def close(self) -> None:
        """Flush and close the sink."""


class LogStore(ABC):
    """Storage contract for execution logs."""

    @abstractmethod
    async def open_writer(self, execution_id: int) -> LogSink:
        """Open a sink for ``execution_id`` (truncating any previous content)."""

    @abstractmethod
    async def read(self, execution_id: int, offset: int = 0) -> tuple[str, int]:
        """Read content from byte ``offset``; return (content, next_offset)."""

    @abstractmethod
    async def delete(self, execution_id: int) -> None:
        """Delete the log of ``execution_id`` (no error if missing)."""
