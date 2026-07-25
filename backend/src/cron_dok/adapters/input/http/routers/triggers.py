"""Manual trigger router (spec 6.3).

Enqueueing is asynchronous: the endpoint answers 202 with the persisted
``queued`` (or ``skipped``, per the runner's overlap policy) execution; the
ExecutionQueue consumer runs it in the background.
"""

from fastapi import APIRouter, status

from cron_dok.adapters.input.http.dependencies import (
    ExecutionQueueDep,
    LogStoreDep,
    RunnerServiceDep,
    WriteUser,
)
from cron_dok.adapters.input.http.routers.executions import resolve_log_path
from cron_dok.adapters.input.http.schemas.executions import ExecutionResponse

router = APIRouter(tags=["triggers"])


@router.post("/triggers/{runner_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_runner(
    runner_id: int,
    _user: WriteUser,
    runner_service: RunnerServiceDep,
    queue: ExecutionQueueDep,
    log_store: LogStoreDep,
) -> ExecutionResponse:
    """Enqueue a manual execution of ``runner_id`` (operator+).

    Raises:
        HTTPException: 404 (via ``RunnerNotFoundError``) if the runner does
            not exist.
    """
    runner = await runner_service.get(runner_id)
    execution = await queue.enqueue(runner, "manual")
    return ExecutionResponse.from_entity(execution, log_path=resolve_log_path(execution, log_store))
