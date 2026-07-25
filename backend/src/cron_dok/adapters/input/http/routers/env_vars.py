"""Env vars router (spec 9.1).

Values are write-only: create and rotate accept a plaintext value, but no
endpoint ever returns one — responses carry only the summary (id, project,
key, runner scope).
"""

from fastapi import APIRouter, Query, status

from cron_dok.adapters.input.http.dependencies import (
    CurrentUser,
    EnvVarServiceDep,
    WriteUser,
)
from cron_dok.adapters.input.http.schemas.env_vars import (
    EnvVarCreate,
    EnvVarResponse,
    EnvVarRotate,
)

router = APIRouter(prefix="/env-vars", tags=["env-vars"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_env_var(
    body: EnvVarCreate, _user: WriteUser, service: EnvVarServiceDep
) -> EnvVarResponse:
    """Create an env var (operator+); the value is encrypted before persisting."""
    env_var = await service.create(
        project_id=body.project_id,
        key=body.key,
        value=body.value,
        runner_id=body.runner_id,
    )
    return EnvVarResponse.from_entity(env_var)


@router.get("")
async def list_env_vars(
    _user: CurrentUser,
    service: EnvVarServiceDep,
    project_id: int = Query(),
    runner_id: int | None = Query(default=None),
) -> list[EnvVarResponse]:
    """List the env vars of a project, without values (any role)."""
    summaries = await service.list(project_id, runner_id=runner_id)
    return [EnvVarResponse.from_summary(summary) for summary in summaries]


@router.delete("/{env_var_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_env_var(env_var_id: int, _user: WriteUser, service: EnvVarServiceDep) -> None:
    """Delete an env var (operator+)."""
    await service.delete(env_var_id)


@router.post("/{env_var_id}/rotate")
async def rotate_env_var(
    env_var_id: int,
    body: EnvVarRotate,
    _user: WriteUser,
    service: EnvVarServiceDep,
) -> EnvVarResponse:
    """Rotate an env var value (operator+); re-encrypts, never reads."""
    env_var = await service.rotate(env_var_id, body.value)
    return EnvVarResponse.from_entity(env_var)
