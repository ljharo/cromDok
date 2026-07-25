"""Runners router: CRUD plus enable/disable (spec 6 and 7)."""

from fastapi import APIRouter, Query, status

from cron_dok.adapters.input.http.dependencies import (
    CurrentUser,
    RunnerServiceDep,
    WriteUser,
)
from cron_dok.adapters.input.http.schemas.runners import (
    RunnerCreate,
    RunnerResponse,
    RunnerUpdate,
)

router = APIRouter(prefix="/runners", tags=["runners"])


@router.get("")
async def list_runners(
    _user: CurrentUser,
    service: RunnerServiceDep,
    project_id: int = Query(),
) -> list[RunnerResponse]:
    """List the runners of a project (any authenticated role)."""
    runners = await service.list_by_project(project_id)
    return [RunnerResponse.from_entity(runner) for runner in runners]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_runner(
    body: RunnerCreate, _user: WriteUser, service: RunnerServiceDep
) -> RunnerResponse:
    """Create a runner (operator+); an enabled runner is scheduled at once."""
    runner = await service.create(
        project_id=body.project_id,
        name=body.name,
        script_content=body.script_content,
        language=body.language,
        cron_expression=body.cron_expression,
        resource_limits=(body.resource_limits.to_domain() if body.resource_limits else None),
        timeout_seconds=body.timeout_seconds,
        on_overlap=body.on_overlap,
    )
    return RunnerResponse.from_entity(runner)


@router.get("/{runner_id}")
async def get_runner(
    runner_id: int, _user: CurrentUser, service: RunnerServiceDep
) -> RunnerResponse:
    """Return one runner (any authenticated role)."""
    runner = await service.get(runner_id)
    return RunnerResponse.from_entity(runner)


@router.patch("/{runner_id}")
async def update_runner(
    runner_id: int,
    body: RunnerUpdate,
    _user: WriteUser,
    service: RunnerServiceDep,
) -> RunnerResponse:
    """Update a runner (operator+); omitted fields stay unchanged."""
    runner = await service.update(
        runner_id,
        name=body.name,
        script_content=body.script_content,
        language=body.language,
        cron_expression=body.cron_expression,
        resource_limits=(body.resource_limits.to_domain() if body.resource_limits else None),
        timeout_seconds=body.timeout_seconds,
        on_overlap=body.on_overlap,
    )
    return RunnerResponse.from_entity(runner)


@router.delete("/{runner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_runner(runner_id: int, _user: WriteUser, service: RunnerServiceDep) -> None:
    """Delete a runner (operator+); its cron job is unregistered."""
    await service.delete(runner_id)


@router.post("/{runner_id}/enable")
async def enable_runner(
    runner_id: int, _user: WriteUser, service: RunnerServiceDep
) -> RunnerResponse:
    """Enable a runner (operator+); the scheduler will fire it."""
    runner = await service.enable(runner_id)
    return RunnerResponse.from_entity(runner)


@router.post("/{runner_id}/disable")
async def disable_runner(
    runner_id: int, _user: WriteUser, service: RunnerServiceDep
) -> RunnerResponse:
    """Disable a runner (operator+); its cron job is removed."""
    runner = await service.disable(runner_id)
    return RunnerResponse.from_entity(runner)
