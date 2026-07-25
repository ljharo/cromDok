"""SQLite implementation of ProjectRepository (SQLAlchemy 2.0 async)."""

from datetime import UTC

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cron_dok.adapters.output.persistence.models.project import ProjectModel
from cron_dok.domain.entities.project import Project
from cron_dok.ports.repositories.project_repository import ProjectRepository


class SqliteProjectRepository(ProjectRepository):
    """Translates between ProjectModel rows and Project domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, project: Project) -> Project:
        if project.id is None:
            model = ProjectModel(name=project.name, description=project.description)
            self._session.add(model)
            await self._session.flush()
            return self._to_entity(model)
        existing = await self._session.get(ProjectModel, project.id)
        if existing is None:
            raise ValueError(f"Project {project.id} does not exist")
        existing.name = project.name
        existing.description = project.description
        await self._session.flush()
        return self._to_entity(existing)

    async def get_by_id(self, project_id: int) -> Project | None:
        model = await self._session.get(ProjectModel, project_id)
        return self._to_entity(model) if model is not None else None

    async def list_all(self) -> list[Project]:
        result = await self._session.scalars(select(ProjectModel).order_by(ProjectModel.id))
        return [self._to_entity(model) for model in result]

    async def delete(self, project_id: int) -> None:
        await self._session.execute(delete(ProjectModel).where(ProjectModel.id == project_id))
        await self._session.flush()

    @staticmethod
    def _to_entity(model: ProjectModel) -> Project:
        created_at = model.created_at
        # SQLite may return naive datetimes; the domain convention is UTC.
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return Project(
            id=model.id,
            name=model.name,
            description=model.description,
            created_at=created_at,
        )
