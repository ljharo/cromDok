"""Execution queue: single-writer dispatch of executions (spec 6.3 and 6.5).

Producers (scheduler, manual triggers) call :meth:`ExecutionQueue.enqueue`,
which creates the ``Execution`` row in state ``queued`` and appends it to an
internal ``asyncio.Queue``. A **single async consumer** (started with
:meth:`ExecutionQueue.start` from the FastAPI lifespan) drains the queue,
persists every state transition via the Unit of Work — it is the only writer
of execution transitions, so this flow cannot hit ``database is locked`` —
and dispatches each execution to the ``JobExecutor``.

Concurrency is bounded by an ``asyncio.Semaphore``
(``settings.max_concurrent_jobs``, default 4): triggers beyond the limit stay
``queued`` until a slot frees (spec 6.5). The per-runner ``on_overlap``
policy is applied at enqueue time:

- ``skip``: the new trigger is persisted as ``skipped`` and never runs.
- ``queue``: it is enqueued normally.
- ``kill_previous``: the previous live execution is cancelled and the new
  one is enqueued.

Cancellation contract for executors (implemented by the DockerExecutor in
step 1.3): the queue tracks each running execution as an ``asyncio.Task``
and cancels that task for ``kill_previous`` (and on shutdown). A
``JobExecutor.execute`` implementation must therefore be cancellation-safe:
on ``asyncio.CancelledError`` it must kill the underlying container/process
and re-raise. The queue catches the cancellation around ``execute`` and
persists the execution as ``killed``.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from cron_dok.domain.entities.execution import Execution, ExecutionStatus, TriggerType
from cron_dok.domain.entities.runner import Runner
from cron_dok.ports.executors.job_executor import JobExecutor
from cron_dok.ports.logs.log_store import LogStore
from cron_dok.ports.unit_of_work import AbstractUnitOfWork

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES: tuple[ExecutionStatus, ...] = ("queued", "running")

EnvResolver = Callable[[Runner], Awaitable[dict[str, str]]]
"""Resolves the env vars to inject into a runner's execution.

In production this is backed by ``EnvVarService.resolve_for_runner`` (step
1.7); the queue only depends on the callable so the two stay decoupled.
"""


async def _no_env(_runner: Runner) -> dict[str, str]:
    """Default env resolver: no variables."""
    return {}


@dataclass(frozen=True)
class _QueuedExecution:
    """Internal queue item: the execution row id plus the runner snapshot."""

    execution_id: int
    runner: Runner


class ExecutionQueue:
    """Single-writer queue that dispatches executions to a JobExecutor.

    Args:
        uow_factory: zero-arg callable returning a fresh Unit of Work per
            state transition.
        executor: the executor port used to run each job.
        log_store: log storage; a fresh sink is opened per execution.
        max_concurrent_jobs: maximum jobs running at once (spec 6.5).
        env_resolver: resolves env vars per runner; defaults to no variables.
    """

    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
        executor: JobExecutor,
        log_store: LogStore,
        *,
        max_concurrent_jobs: int = 4,
        env_resolver: EnvResolver | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._executor = executor
        self._log_store = log_store
        self._env_resolver = env_resolver or _no_env
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._queue: asyncio.Queue[_QueuedExecution] = asyncio.Queue()
        self._consumer: asyncio.Task[None] | None = None
        self._workers: set[asyncio.Task[None]] = set()
        self._running: dict[int, asyncio.Task[None]] = {}

    async def enqueue(self, runner: Runner, trigger_type: TriggerType) -> Execution:
        """Create an execution for ``runner`` and enqueue it (or skip it).

        Applies the runner's ``on_overlap`` policy against its live
        (``queued``/``running``) executions, persists the new row and, unless
        skipped, appends it to the internal queue.

        Args:
            runner: the runner to execute; must already be persisted.
            trigger_type: ``"scheduled"`` (cron) or ``"manual"`` (API).

        Returns:
            The persisted execution: ``queued`` when it will run, ``skipped``
            when the overlap policy discarded it.

        Raises:
            ValueError: if ``runner`` has no id (not persisted).
        """
        if runner.id is None:
            raise ValueError("Cannot enqueue a runner without id (not persisted)")
        kill_victims: list[Execution] = []
        async with self._uow_factory() as uow:
            active: list[Execution] = []
            if runner.on_overlap != "queue":
                active = await self._active_executions(uow, runner)
            if active and runner.on_overlap == "skip":
                skipped = Execution(
                    runner_id=runner.id,
                    status="skipped",
                    trigger_type=trigger_type,
                    finished_at=_utcnow(),
                )
                return await uow.executions.save(skipped)
            if active and runner.on_overlap == "kill_previous":
                kill_victims = active
                for victim in kill_victims:
                    # Cancel the victim's worker task if it exists (it may be
                    # running the executor or waiting on the semaphore; the
                    # worker persists "killed" itself once it is past the
                    # semaphore). Victims still queued — including workers not
                    # yet past the semaphore — are marked killed here so the
                    # consumer drops them when they pop.
                    task = self._running.get(_require_id(victim))
                    if task is not None:
                        task.cancel()
                    if task is None or victim.status == "queued":
                        await uow.executions.save(
                            replace(victim, status="killed", finished_at=_utcnow())
                        )
            execution = await uow.executions.save(
                Execution(runner_id=runner.id, status="queued", trigger_type=trigger_type)
            )
        self._queue.put_nowait(_QueuedExecution(execution_id=_require_id(execution), runner=runner))
        return execution

    def start(self) -> None:
        """Start the single consumer task. Call from the FastAPI lifespan.

        Raises:
            RuntimeError: if the queue is already started.
        """
        if self._consumer is not None:
            raise RuntimeError("ExecutionQueue is already started")
        self._consumer = asyncio.create_task(self._consume(), name="execution-queue-consumer")

    async def stop(self) -> None:
        """Stop the consumer and cancel in-flight workers.

        Cancelled workers persist their execution as ``killed`` (see the
        module docstring for the executor cancellation contract).
        """
        if self._consumer is not None:
            self._consumer.cancel()
            await asyncio.gather(self._consumer, return_exceptions=True)
            self._consumer = None
        workers = list(self._workers)
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)

    async def wait_idle(self) -> None:
        """Wait until the queue is drained and no worker is running.

        Intended for tests and graceful shutdown checks; producers may keep
        enqueueing, in which case this waits only for the work present so
        far.
        """
        while True:
            await self._queue.join()
            workers = [task for task in self._workers if not task.done()]
            if not workers and self._queue.empty():
                return
            await asyncio.gather(*workers, return_exceptions=True)

    async def _consume(self) -> None:
        """Drain the queue forever; a bad item never kills the consumer."""
        while True:
            item = await self._queue.get()
            try:
                await self._dispatch(item)
            except Exception:
                logger.exception(
                    "ExecutionQueue: failed to dispatch execution %s", item.execution_id
                )
            finally:
                self._queue.task_done()

    async def _dispatch(self, item: _QueuedExecution) -> None:
        """Spawn a worker task for a queued execution, dropping dead items."""
        async with self._uow_factory() as uow:
            execution = await uow.executions.get_by_id(item.execution_id)
            if execution is None or execution.status != "queued":
                return  # e.g. killed by kill_previous while still queued
        worker = asyncio.create_task(
            self._run(item.runner, item.execution_id),
            name=f"execution-{item.execution_id}",
        )
        self._workers.add(worker)
        self._running[item.execution_id] = worker
        worker.add_done_callback(self._make_done_callback(item.execution_id))

    def _make_done_callback(self, execution_id: int) -> Callable[[asyncio.Task[None]], None]:
        def _on_done(task: asyncio.Task[None]) -> None:
            self._workers.discard(task)
            self._running.pop(execution_id, None)

        return _on_done

    async def _run(self, runner: Runner, execution_id: int) -> None:
        """Execute one job under the semaphore, persisting its transitions."""
        async with self._semaphore:
            await self._transition(execution_id, status="running", started_at=_utcnow())
            sink = await self._log_store.open_writer(execution_id)
            try:
                env_vars = await self._env_resolver(runner)
                result = await self._executor.execute(runner, env_vars, sink)
            except asyncio.CancelledError:
                await self._transition(execution_id, status="killed", finished_at=_utcnow())
                raise
            except Exception:
                logger.exception("Execution %s raised; marking it failed", execution_id)
                await self._transition(execution_id, status="failed", finished_at=_utcnow())
            else:
                status: ExecutionStatus = (
                    "killed" if result.timed_out else "succeeded" if result.succeeded else "failed"
                )
                await self._transition(
                    execution_id,
                    status=status,
                    finished_at=_utcnow(),
                    exit_code=result.exit_code,
                    duration_ms=result.duration_ms,
                )
            finally:
                await sink.close()

    async def _transition(
        self,
        execution_id: int,
        *,
        status: ExecutionStatus,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        exit_code: int | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Persist a state transition of ``execution_id`` via the UoW.

        Fields left as ``None`` keep their current value.
        """
        async with self._uow_factory() as uow:
            execution = await uow.executions.get_by_id(execution_id)
            if execution is None:
                logger.warning(
                    "Execution %s vanished before transition to %s",
                    execution_id,
                    status,
                )
                return
            await uow.executions.save(
                replace(
                    execution,
                    status=status,
                    started_at=(execution.started_at if started_at is None else started_at),
                    finished_at=(execution.finished_at if finished_at is None else finished_at),
                    exit_code=execution.exit_code if exit_code is None else exit_code,
                    duration_ms=(execution.duration_ms if duration_ms is None else duration_ms),
                )
            )

    @staticmethod
    async def _active_executions(uow: AbstractUnitOfWork, runner: Runner) -> list[Execution]:
        """Return the runner's live (queued/running) executions, oldest first."""
        executions = await uow.executions.list_by_runner(_require_id(runner))
        return [e for e in executions if e.status in _ACTIVE_STATUSES]


def _utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def _require_id(entity: Execution | Runner) -> int:
    """Return the id of a persisted entity or raise."""
    assert entity.id is not None, "expected a persisted entity with id"
    return entity.id
