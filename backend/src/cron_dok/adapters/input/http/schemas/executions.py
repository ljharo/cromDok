"""Execution response schemas (spec 6.3 and 6.4)."""

from datetime import datetime

from pydantic import BaseModel

from cron_dok.domain.entities.execution import Execution, ExecutionStatus, TriggerType


class ExecutionResponse(BaseModel):
    """Metadata of one execution; logs are served separately (spec 6.4).

    The log file path is deliberately NOT part of the API: it is a
    server-side filesystem detail (information disclosure) and clients read
    logs through ``GET /executions/{id}/logs``.
    """

    id: int
    runner_id: int
    status: ExecutionStatus
    trigger_type: TriggerType
    started_at: datetime | None
    finished_at: datetime | None
    exit_code: int | None
    duration_ms: int | None

    @classmethod
    def from_entity(cls, execution: Execution) -> "ExecutionResponse":
        """Build the response from a persisted domain execution."""
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
        )


class LogChunkResponse(BaseModel):
    """Incremental log read: content since ``offset`` and the next offset."""

    chunk: str
    offset: int
