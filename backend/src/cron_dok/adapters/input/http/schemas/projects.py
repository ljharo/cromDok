"""Project request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from cron_dok.domain.entities.project import Project


class ProjectCreate(BaseModel):
    """Payload to create a project."""

    name: str = Field(min_length=1, max_length=100)
    description: str = ""


class ProjectUpdate(BaseModel):
    """Payload to update a project; ``None`` fields are left unchanged."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class ProjectResponse(BaseModel):
    """A project as returned by the API."""

    id: int
    name: str
    description: str
    created_at: datetime

    @classmethod
    def from_entity(cls, project: Project) -> "ProjectResponse":
        """Build the response from a persisted domain project."""
        assert project.id is not None  # persisted entities always have an id
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
        )
