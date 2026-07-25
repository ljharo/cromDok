"""Scheduler application service: stateless cron registration (spec 7).

The scheduler backend (APScheduler via an adapter, or a fake in tests) is
injected, keeping this service free of APScheduler imports. Jobs carry only
the runner id: when a job fires, the runner is **re-read from the database**
and enqueued — never executed directly and never from a stale snapshot.
Re-reading on every fire is one cheap indexed SELECT per trigger and
guarantees executions always use the current script, limits and overlap
policy, even if an update notification was ever lost.

Rehydration (spec 7): on startup, :meth:`SchedulerService.rehydrate`
registers every runner with ``is_enabled=true``. Because the jobstore lives
in memory, restarting the process loses nothing — the database is the only
source of truth.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

from cron_dok.domain.entities.runner import Runner
from cron_dok.ports.unit_of_work import AbstractUnitOfWork
from cron_dok.services.execution_queue import ExecutionQueue

TriggerCallback = Callable[[int], Awaitable[None]]
"""Async callable invoked with the runner id each time a cron job fires."""

logger = logging.getLogger(__name__)


class JobScheduler(Protocol):
    """Scheduling backend contract (APScheduler adapter or test fake)."""

    def start(self) -> None:
        """Start the backend (jobs begin firing)."""
        ...

    def shutdown(self) -> None:
        """Stop the backend."""
        ...

    def add_job(self, runner: Runner, callback: TriggerCallback) -> None:
        """Register (or replace) the cron job of ``runner``."""
        ...

    def remove_job(self, runner_id: int) -> None:
        """Remove the job of ``runner_id``; a no-op if not registered."""
        ...


class RunnerScheduler(Protocol):
    """Hook notified by RunnerService after runner writes (spec 7).

    Notifications happen **after** the database write succeeds (DB first,
    scheduler second). Implemented by :class:`SchedulerService`; runner CRUD
    works without it when no scheduler is wired (e.g. unit tests).
    """

    def register(self, runner: Runner) -> None:
        """Schedule ``runner`` (no-op effect if it is disabled)."""
        ...

    def unregister(self, runner_id: int) -> None:
        """Remove ``runner_id`` from the schedule."""
        ...

    def update(self, runner: Runner) -> None:
        """Re-register ``runner`` with its current configuration."""
        ...


class SchedulerService:
    """Registers runner cron jobs and routes their fires to the queue.

    Args:
        uow_factory: zero-arg callable returning a fresh Unit of Work per
            operation.
        queue: the execution queue every cron fire is enqueued into.
        scheduler: the scheduling backend (adapter or fake).
    """

    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
        queue: ExecutionQueue,
        scheduler: JobScheduler,
    ) -> None:
        self._uow_factory = uow_factory
        self._queue = queue
        self._scheduler = scheduler

    def start(self) -> None:
        """Start the scheduling backend. Call from the FastAPI lifespan."""
        self._scheduler.start()

    def shutdown(self) -> None:
        """Stop the scheduling backend. Call on lifespan teardown."""
        self._scheduler.shutdown()

    def register(self, runner: Runner) -> None:
        """Register the job of an enabled runner (or ensure removal if disabled).

        Raises:
            ValueError: if ``runner`` has no id (not persisted).
        """
        if runner.id is None:
            raise ValueError("Cannot register a runner without id (not persisted)")
        if not runner.is_enabled:
            self._scheduler.remove_job(runner.id)
            return
        self._scheduler.add_job(runner, self._fire)

    def unregister(self, runner_id: int) -> None:
        """Remove the job of ``runner_id``; a no-op if not registered."""
        self._scheduler.remove_job(runner_id)

    def update(self, runner: Runner) -> None:
        """Re-register ``runner`` so the job matches its current state.

        Idempotent: job ids are deterministic and the backend replaces
        existing jobs, so calling this on every runner update is safe even
        when the cron expression did not change.
        """
        self.register(runner)

    async def rehydrate(self) -> int:
        """Register every enabled runner found in the database (spec 7).

        Returns:
            The number of jobs registered.
        """
        async with self._uow_factory() as uow:
            runners = await uow.runners.list_all()
        registered = 0
        for runner in runners:
            if runner.is_enabled:
                self.register(runner)
                registered += 1
        logger.info("Scheduler rehydrated: %d job(s) registered", registered)
        return registered

    async def _fire(self, runner_id: int) -> None:
        """Job callback: re-read the runner and enqueue it (never executes).

        If the runner was deleted or disabled after the job was registered,
        the stale job is removed and nothing is enqueued.
        """
        async with self._uow_factory() as uow:
            runner = await uow.runners.get_by_id(runner_id)
        if runner is None:
            logger.warning("Cron fired for deleted runner %s; removing stale job", runner_id)
            self._scheduler.remove_job(runner_id)
            return
        if not runner.is_enabled:
            logger.info("Cron fired for disabled runner %s; removing stale job", runner_id)
            self._scheduler.remove_job(runner_id)
            return
        await self._queue.enqueue(runner, "scheduled")
