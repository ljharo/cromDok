"""APScheduler adapter: thin wrapper over ``AsyncIOScheduler`` (spec 6.5, 7).

The scheduler uses an **in-memory jobstore** — nothing is persisted, which
keeps the process stateless: on startup the application re-registers every
enabled runner from the database (rehydration, spec 7).

Each job:

- has a deterministic id (``runner-{id}``), so updates simply replace it;
- fires an async callback with the runner id — the callback enqueues the
  execution, it never runs anything itself;
- is configured with ``max_instances=1`` and ``coalesce=True`` as a second
  line of defense behind the runner's ``on_overlap`` policy (spec 6.5).

Cron mapping: the domain accepts standard 5-field cron and 6-field cron
(with a leading seconds field, as validated by croniter). Both map onto
APScheduler's ``CronTrigger``. Day-of-week numbers are translated to names
because the conventions differ: cron uses ``0``/``7`` for Sunday while
APScheduler numbers weekdays starting at Monday (``0`` = Monday).
"""

import re

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.services.scheduler_service import SystemJobCallback, TriggerCallback

_CRON_DOW_NAMES = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")


def job_id_for(runner_id: int) -> str:
    """Deterministic job id for a runner: ``runner-{id}``."""
    return f"runner-{runner_id}"


def system_job_id_for(job_id: str) -> str:
    """Deterministic id for a system job: ``system-{job_id}``."""
    return f"system-{job_id}"


def build_trigger(cron: CronExpression) -> CronTrigger:
    """Build an APScheduler ``CronTrigger`` from a domain cron expression.

    Supports 5 fields (``minute hour day month dow``) and 6 fields
    (``second minute hour day month dow``), matching the formats accepted
    by the domain validator.

    Raises:
        ValueError: if the expression does not have 5 or 6 fields. This is
            unreachable for domain-validated expressions.
    """
    fields = cron.value.split()
    if len(fields) == 5:
        second = "0"
        minute, hour, day, month, day_of_week = fields
    elif len(fields) == 6:
        second, minute, hour, day, month, day_of_week = fields
    else:
        raise ValueError(f"Cron expression must have 5 or 6 fields: {cron.value!r}")
    return CronTrigger(
        second=second,
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=_convert_day_of_week(day_of_week),
    )


def _convert_day_of_week(field: str) -> str:
    """Translate cron day-of-week numbers to APScheduler weekday names.

    Cron numbers Sunday as ``0`` (or ``7``); APScheduler numbers Monday as
    ``0``. Names, ``*``, ranges, lists and steps pass through untouched.
    """

    def _replace(match: re.Match[str]) -> str:
        return _CRON_DOW_NAMES[int(match.group(0)) % 7]

    return re.sub(r"\d+", _replace, field)


class APSchedulerAdapter:
    """Wraps ``AsyncIOScheduler`` with runner-centric job management.

    The scheduler is not started by the constructor; call :meth:`start`
    from the FastAPI lifespan and :meth:`shutdown` on teardown.
    """

    def __init__(self, scheduler: AsyncIOScheduler | None = None) -> None:
        """Initialize the adapter.

        Args:
            scheduler: an ``AsyncIOScheduler`` instance to wrap; a new one is
                created when omitted (injectable for tests).
        """
        self._scheduler = scheduler or AsyncIOScheduler()

    def start(self) -> None:
        """Start the underlying scheduler (jobs begin firing)."""
        self._scheduler.start()

    def shutdown(self) -> None:
        """Stop the scheduler; pending job executions are not awaited.

        A no-op when the scheduler was never started, so teardown is safe
        even after a partial startup.
        """
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def add_job(self, runner: Runner, callback: TriggerCallback) -> None:
        """Register (or replace) the cron job of ``runner``.

        Args:
            runner: the runner to schedule; must already be persisted.
            callback: async callable invoked with the runner id on each fire.

        Raises:
            ValueError: if ``runner`` has no id (not persisted).
        """
        if runner.id is None:
            raise ValueError("Cannot schedule a runner without id (not persisted)")
        # ``replace_existing`` only deduplicates once the scheduler runs;
        # while stopped, jobs pile up in a pending list, so remove first to
        # guarantee replace semantics in both states.
        job_id = job_id_for(runner.id)
        while self._scheduler.get_job(job_id) is not None:
            self._scheduler.remove_job(job_id)
        self._scheduler.add_job(
            callback,
            trigger=build_trigger(runner.cron_expression),
            id=job_id,
            args=[runner.id],
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

    def remove_job(self, runner_id: int) -> None:
        """Remove the job of ``runner_id``; a no-op if it is not registered."""
        job_id = job_id_for(runner_id)
        if self._scheduler.get_job(job_id) is not None:
            self._scheduler.remove_job(job_id)

    def add_system_job(
        self, job_id: str, callback: SystemJobCallback, *, hour: int, minute: int
    ) -> None:
        """Register (or replace) a system job firing daily at ``hour:minute``.

        System jobs live in the ``system-`` id namespace, disjoint from the
        runner jobs, and keep the same defenses (``max_instances=1``,
        ``coalesce=True``).
        """
        full_id = system_job_id_for(job_id)
        while self._scheduler.get_job(full_id) is not None:
            self._scheduler.remove_job(full_id)
        self._scheduler.add_job(
            callback,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=full_id,
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )

    def get_job(self, runner_id: int) -> Job | None:
        """Return the registered job of ``runner_id``, or None (for tests)."""
        return self._scheduler.get_job(job_id_for(runner_id))

    def get_system_job(self, job_id: str) -> Job | None:
        """Return the registered system job ``job_id``, or None (for tests)."""
        return self._scheduler.get_job(system_job_id_for(job_id))
