"""Runner entity: an executable unit with a script, a cron and its config."""

from dataclasses import dataclass, field
from typing import Literal

from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.domain.value_objects.resource_limits import ResourceLimits

RunnerLanguage = Literal["python", "bash", "node"]
OverlapPolicy = Literal["skip", "queue", "kill_previous"]


@dataclass(kw_only=True)
class Runner:
    """A scheduled (or manually triggerable) script owned by a project.

    ``on_overlap`` decides what happens when cron fires while the previous
    execution is still alive: ``skip`` (default), ``queue`` or
    ``kill_previous`` (spec section 6.5).
    """

    id: int | None = None
    project_id: int
    name: str
    script_content: str
    language: RunnerLanguage
    cron_expression: CronExpression
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    is_enabled: bool = True
    timeout_seconds: int = 300
    on_overlap: OverlapPolicy = "skip"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Runner name must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be positive, got {self.timeout_seconds}")
