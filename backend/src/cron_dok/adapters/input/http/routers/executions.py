"""Executions router: listings, detail and incremental logs (spec 6.3, 6.4).

Executions have no application service of their own (they are written only
by the ExecutionQueue), so reads go through the Unit of Work and logs
through the LogStore port.
"""

from fastapi import APIRouter, HTTPException, Query, status

from cron_dok.adapters.input.http.dependencies import (
    CurrentUser,
    LogStoreDep,
    RunnerServiceDep,
    UowFactoryDep,
)
from cron_dok.adapters.input.http.schemas.executions import (
    ExecutionResponse,
    LogChunkResponse,
)
from cron_dok.domain.entities.execution import Execution
from cron_dok.ports.logs.log_store import LogStore
from cron_dok.ports.unit_of_work import AbstractUnitOfWork

router = APIRouter(tags=["executions"])


def resolve_log_path(execution: Execution, log_store: LogStore) -> str | None:
    """Best-effort log path for an execution.

    Prefers the persisted ``execution.log_path``; otherwise, when the
    LogStore exposes a filesystem path (``FileLogStore.path_for``), derives
    it from the execution id. Returns None for LogStores without paths
    (e.g. a future S3 store).
    """
    if execution.log_path is not None:
        return execution.log_path
    path_for = getattr(log_store, "path_for", None)
    if callable(path_for) and execution.id is not None:
        return str(path_for(execution.id))
    return None


async def _get_execution_or_404(uow: AbstractUnitOfWork, execution_id: int) -> Execution:
    execution = await uow.executions.get_by_id(execution_id)
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution not found: id={execution_id}",
        )
    return execution


@router.get("/runners/{runner_id}/executions")
async def list_executions(
    runner_id: int,
    _user: CurrentUser,
    runner_service: RunnerServiceDep,
    uow_factory: UowFactoryDep,
    log_store: LogStoreDep,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ExecutionResponse]:
    """List the executions of a runner, oldest first, paginated.

    Raises:
        HTTPException: 404 (via ``RunnerNotFoundError``) if the runner does
            not exist.
    """
    await runner_service.get(runner_id)
    async with uow_factory() as uow:
        executions = await uow.executions.list_by_runner(runner_id)
    page = executions[offset : offset + limit]
    return [ExecutionResponse.from_entity(e, log_path=resolve_log_path(e, log_store)) for e in page]


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: int,
    _user: CurrentUser,
    uow_factory: UowFactoryDep,
    log_store: LogStoreDep,
) -> ExecutionResponse:
    """Return one execution's metadata.

    Raises:
        HTTPException: 404 if the execution does not exist.
    """
    async with uow_factory() as uow:
        execution = await _get_execution_or_404(uow, execution_id)
    return ExecutionResponse.from_entity(execution, log_path=resolve_log_path(execution, log_store))


@router.get("/executions/{execution_id}/logs")
async def get_execution_logs(
    execution_id: int,
    _user: CurrentUser,
    uow_factory: UowFactoryDep,
    log_store: LogStoreDep,
    offset: int = Query(default=0, ge=0),
) -> LogChunkResponse:
    """Incremental log read (tail-with-polling, spec 6.4).

    Returns the content written since ``offset`` plus the offset for the
    next poll. A missing log file yields an empty chunk with the offset
    unchanged, so polling works before the execution starts.

    Raises:
        HTTPException: 404 if the execution does not exist.
    """
    async with uow_factory() as uow:
        await _get_execution_or_404(uow, execution_id)
    chunk, next_offset = await log_store.read(execution_id, offset)
    return LogChunkResponse(chunk=chunk, offset=next_offset)
