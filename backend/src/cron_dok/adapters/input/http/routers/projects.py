"""Projects router: CRUD (spec 6). Reads need any role; writes operator+."""

from fastapi import APIRouter, status

from cron_dok.adapters.input.http.dependencies import (
    CurrentUser,
    ProjectServiceDep,
    WriteUser,
)
from cron_dok.adapters.input.http.schemas.projects import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects(_user: CurrentUser, service: ProjectServiceDep) -> list[ProjectResponse]:
    """List every project (any authenticated role)."""
    projects = await service.list()
    return [ProjectResponse.from_entity(project) for project in projects]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate, _user: WriteUser, service: ProjectServiceDep
) -> ProjectResponse:
    """Create a project (operator+)."""
    project = await service.create(name=body.name, description=body.description)
    return ProjectResponse.from_entity(project)


@router.get("/{project_id}")
async def get_project(
    project_id: int, _user: CurrentUser, service: ProjectServiceDep
) -> ProjectResponse:
    """Return one project (any authenticated role)."""
    project = await service.get(project_id)
    return ProjectResponse.from_entity(project)


@router.patch("/{project_id}")
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    _user: WriteUser,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """Update a project (operator+); omitted fields stay unchanged."""
    project = await service.update(project_id, name=body.name, description=body.description)
    return ProjectResponse.from_entity(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: int, _user: WriteUser, service: ProjectServiceDep) -> None:
    """Delete a project (operator+); runners/executions/env vars cascade."""
    await service.delete(project_id)
