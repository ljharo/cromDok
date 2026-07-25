"""Project application service: CRUD use cases over the Unit of Work."""

from collections.abc import Callable
from dataclasses import replace

from cron_dok.domain.entities.project import Project
from cron_dok.ports.unit_of_work import AbstractUnitOfWork
from cron_dok.services.errors import DuplicateNameError, ProjectNotFoundError


class ProjectService:
    """CRUD use cases for projects.

    Every write runs inside ``async with uow:`` so operations are atomic
    (commit on success, rollback on error, spec 6.2). Delete cascades to
    runners, executions and env vars via the FK ``ON DELETE CASCADE``.
    """

    def __init__(self, uow_factory: Callable[[], AbstractUnitOfWork]) -> None:
        """Initialize the service.

        Args:
            uow_factory: zero-arg callable returning a fresh Unit of Work per
                operation.
        """
        self._uow_factory = uow_factory

    async def create(self, *, name: str, description: str = "") -> Project:
        """Create a project.

        Raises:
            DuplicateNameError: if a project named ``name`` already exists.
            ValueError: if ``name`` is empty (domain validation).
        """
        async with self._uow_factory() as uow:
            await self._ensure_name_available(uow, name)
            return await uow.projects.save(Project(name=name, description=description))

    async def get(self, project_id: int) -> Project:
        """Return a project by id.

        Raises:
            ProjectNotFoundError: if the project does not exist.
        """
        async with self._uow_factory() as uow:
            return await self._get_or_raise(uow, project_id)

    async def list(self) -> list[Project]:
        """Return all projects, oldest first."""
        async with self._uow_factory() as uow:
            return await uow.projects.list_all()

    async def update(
        self,
        project_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Project:
        """Update a project; ``None`` fields are left unchanged.

        Raises:
            ProjectNotFoundError: if the project does not exist.
            DuplicateNameError: if ``name`` is taken by another project.
            ValueError: if ``name`` is empty (domain validation).
        """
        async with self._uow_factory() as uow:
            project = await self._get_or_raise(uow, project_id)
            if name is not None and name != project.name:
                await self._ensure_name_available(uow, name)
            updated = replace(
                project,
                name=project.name if name is None else name,
                description=project.description if description is None else description,
            )
            return await uow.projects.save(updated)

    async def delete(self, project_id: int) -> None:
        """Delete a project; its runners, executions and env vars cascade.

        Raises:
            ProjectNotFoundError: if the project does not exist.
        """
        async with self._uow_factory() as uow:
            await self._get_or_raise(uow, project_id)
            await uow.projects.delete(project_id)

    @staticmethod
    async def _get_or_raise(uow: AbstractUnitOfWork, project_id: int) -> Project:
        project = await uow.projects.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    @staticmethod
    async def _ensure_name_available(uow: AbstractUnitOfWork, name: str) -> None:
        if any(p.name == name for p in await uow.projects.list_all()):
            raise DuplicateNameError("project", name)
