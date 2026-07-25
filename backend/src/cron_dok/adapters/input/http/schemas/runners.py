"""Runner request/response schemas."""

from pydantic import BaseModel, Field

from cron_dok.domain.entities.runner import OverlapPolicy, Runner, RunnerLanguage
from cron_dok.domain.value_objects.resource_limits import ResourceLimits


class ResourceLimitsSchema(BaseModel):
    """Hardware limits for a runner container (spec 9.2 defaults)."""

    memory_mb: int = Field(default=256, gt=0)
    cpu_quota: float = Field(default=1.0, gt=0)
    pids_limit: int = Field(default=100, gt=0)
    network_enabled: bool = False

    def to_domain(self) -> ResourceLimits:
        """Convert to the domain value object."""
        return ResourceLimits(
            memory_mb=self.memory_mb,
            cpu_quota=self.cpu_quota,
            pids_limit=self.pids_limit,
            network_enabled=self.network_enabled,
        )

    @classmethod
    def from_domain(cls, limits: ResourceLimits) -> "ResourceLimitsSchema":
        """Build the schema from the domain value object."""
        return cls(
            memory_mb=limits.memory_mb,
            cpu_quota=limits.cpu_quota,
            pids_limit=limits.pids_limit,
            network_enabled=limits.network_enabled,
        )


class RunnerCreate(BaseModel):
    """Payload to create a runner."""

    project_id: int
    name: str = Field(min_length=1, max_length=100)
    script_content: str
    language: RunnerLanguage
    cron_expression: str = Field(min_length=1, max_length=100)
    resource_limits: ResourceLimitsSchema | None = None
    timeout_seconds: int = Field(default=300, gt=0)
    on_overlap: OverlapPolicy = "skip"


class RunnerUpdate(BaseModel):
    """Payload to update a runner; ``None`` fields are left unchanged."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    script_content: str | None = None
    language: RunnerLanguage | None = None
    cron_expression: str | None = Field(default=None, min_length=1, max_length=100)
    resource_limits: ResourceLimitsSchema | None = None
    timeout_seconds: int | None = Field(default=None, gt=0)
    on_overlap: OverlapPolicy | None = None


class RunnerResponse(BaseModel):
    """A runner as returned by the API."""

    id: int
    project_id: int
    name: str
    script_content: str
    language: RunnerLanguage
    cron_expression: str
    resource_limits: ResourceLimitsSchema
    is_enabled: bool
    timeout_seconds: int
    on_overlap: OverlapPolicy

    @classmethod
    def from_entity(cls, runner: Runner) -> "RunnerResponse":
        """Build the response from a persisted domain runner."""
        assert runner.id is not None  # persisted entities always have an id
        return cls(
            id=runner.id,
            project_id=runner.project_id,
            name=runner.name,
            script_content=runner.script_content,
            language=runner.language,
            cron_expression=runner.cron_expression.value,
            resource_limits=ResourceLimitsSchema.from_domain(runner.resource_limits),
            is_enabled=runner.is_enabled,
            timeout_seconds=runner.timeout_seconds,
            on_overlap=runner.on_overlap,
        )
