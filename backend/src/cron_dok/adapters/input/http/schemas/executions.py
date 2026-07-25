"""Execution response schemas (spec 6.3 and 6.4)."""

from datetime import datetime

from pydantic import BaseModel

from cron_dok.domain.entities.execution import Execution, ExecutionStatus, TriggerType


class ExecutionResponse(BaseModel):
    """Metadata of one execution; logs are served separately (spec 6.4).

    ``log_path`` is the file the log is (or will be) written to, when the
    configured LogStore exposes one.
    """

    id: int
    runner_id: int
    status: ExecutionStatus
    trigger_type: TriggerType
    started_at: datetime | None
    finished_at: datetime | None
    exit_code: int | None
    duration_ms: int | None
    log_path: str | None

    @classmethod
    def from_entity(cls, execution: Execution, *, log_path: str | None) -> "ExecutionResponse":
        """Build the response from a persisted domain execution.

        Args:
            execution: the persisted execution.
            log_path: resolved log file path, or None when unavailable.
        """
        assert execution.id is not None  # persisted entities always have an id
        return cls(
            id=execution.id,
            runner_id=execution.runner_id,
            status=execution.status,
            trigger_type=execution.trigger_type,
            started_at=execution.started_at,
            finished_at=execution.finished_at,
            exit_code=execution.exit_code,
            duration_ms=execution.duration_ms,
            log_path=log_path,
        )


class LogChunkResponse(BaseModel):
    """Incremental log read: content since ``offset`` and the next offset."""

    chunk: str
    offset: int
