"""Env var schemas (spec 9.1).

Responses are built from ``EnvVarSummary`` and **never** include the value —
not even encrypted: the UI renders ``••••••••`` and rotation is write-only.
"""

from pydantic import BaseModel, Field

from cron_dok.domain.entities.env_var import EnvVar
from cron_dok.services.env_var_service import EnvVarSummary


class EnvVarCreate(BaseModel):
    """Payload to create an env var scoped to a project or a single runner."""

    project_id: int
    key: str = Field(min_length=1, max_length=200)
    value: str
    runner_id: int | None = None


class EnvVarRotate(BaseModel):
    """Payload to rotate an env var value (write-only; never read back)."""

    value: str


class EnvVarResponse(BaseModel):
    """An env var without its value (spec 9.1)."""

    id: int
    project_id: int
    key: str
    runner_id: int | None

    @classmethod
    def from_summary(cls, summary: EnvVarSummary) -> "EnvVarResponse":
        """Build the response from a service-layer summary."""
        return cls(
            id=summary.id,
            project_id=summary.project_id,
            key=summary.key,
            runner_id=summary.runner_id,
        )

    @classmethod
    def from_entity(cls, env_var: EnvVar) -> "EnvVarResponse":
        """Build the response from a persisted entity (drops the ciphertext)."""
        assert env_var.id is not None  # persisted entities always have an id
        return cls(
            id=env_var.id,
            project_id=env_var.project_id,
            key=env_var.key,
            runner_id=env_var.runner_id,
        )
