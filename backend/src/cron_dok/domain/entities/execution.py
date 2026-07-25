"""Execution entity: metadata of one concrete run of a runner.

Logs live outside the database (spec section 6.4); only ``log_path`` is
stored here.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ExecutionStatus = Literal["queued", "running", "succeeded", "failed", "skipped", "killed"]
TriggerType = Literal["scheduled", "manual"]


@dataclass(kw_only=True)
class Execution:
    """A single run of a runner, scheduled or manual."""

    id: int | None = None
    runner_id: int
    status: ExecutionStatus = "queued"
    trigger_type: TriggerType = "scheduled"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    log_path: str | None = None
