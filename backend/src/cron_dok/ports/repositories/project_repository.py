"""Abstract repository port for Project (spec 4.2.2)."""

from abc import ABC, abstractmethod

from cron_dok.domain.entities.project import Project


class ProjectRepository(ABC):
    """Persistence contract for projects."""

    @abstractmethod
    async def save(self, project: Project) -> Project:
        """Insert (id is None) or update ``project``; return the stored entity."""

    @abstractmethod
    async def get_by_id(self, project_id: int) -> Project | None:
        """Return the project or None if it does not exist."""

    @abstractmethod
    async def list_all(self) -> list[Project]:
        """Return all projects."""

    @abstractmethod
    async def delete(self, project_id: int) -> None:
        """Delete a project; its runners (and their executions) cascade."""
