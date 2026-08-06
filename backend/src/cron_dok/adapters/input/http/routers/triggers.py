"""Manual trigger router (spec 6.3, rate limiting per plan 3.2).

Enqueueing is asynchronous: the endpoint answers 202 with the persisted
``queued`` (or ``skipped``, per the runner's overlap policy) execution; the
ExecutionQueue consumer runs it in the background.

``POST /triggers/{runner_id}`` is rate-limited: 100 requests/minute (config
``CRONDOK_RATE_LIMIT_TRIGGERS``) per caller identity (session user or API
key), so a single leaked key or noisy caller cannot flood the queue.
"""

from fastapi import APIRouter, HTTPException, Request, status

from cron_dok.adapters.input.http.dependencies import (
    ExecutionQueueDep,
    RunnerServiceDep,
    WriteUser,
)
from cron_dok.adapters.input.http.rate_limit import SlidingWindowRateLimiter
from cron_dok.adapters.input.http.schemas.executions import ExecutionResponse

router = APIRouter(tags=["triggers"])


@router.post("/triggers/{runner_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_runner(
    runner_id: int,
    request: Request,
    identity: WriteUser,
    runner_service: RunnerServiceDep,
    queue: ExecutionQueueDep,
) -> ExecutionResponse:
    """Enqueue a manual execution of ``runner_id`` (operator+).

    Raises:
        HTTPException: 429 when the caller exceeded the trigger rate limit;
            404 (via ``RunnerNotFoundError``) if the runner does not exist.
    """
    limiter: SlidingWindowRateLimiter = request.app.state.trigger_rate_limiter
    key = identity.rate_limit_key
    if not limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many trigger requests; try again later",
            headers={"Retry-After": str(limiter.retry_after(key))},
        )
    runner = await runner_service.get(runner_id)
    execution = await queue.enqueue(runner, "manual")
    return ExecutionResponse.from_entity(execution)
