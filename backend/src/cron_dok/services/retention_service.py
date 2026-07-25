"""Retention maintenance service: purges old executions and their logs (spec 6.4).

Executions in a terminal status whose ``finished_at`` is older than
``log_retention_days`` are deleted from the database together with their log
file. Executions still ``queued`` or ``running`` are never touched, no matter
how old they are. The purge runs as a **system job** registered directly in
the scheduler (daily at a fixed hour) — it does not go through the
``ExecutionQueue`` and does not create an ``Execution`` of its own.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from cron_dok.domain.entities.execution import ExecutionStatus
from cron_dok.ports.logs.log_store import LogStore
from cron_dok.ports.unit_of_work import AbstractUnitOfWork

TERMINAL_STATUSES: frozenset[ExecutionStatus] = frozenset(
    {"succeeded", "failed", "killed", "skipped"}
)
"""Statuses eligible for purging; queued/running executions are never deleted."""

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class RetentionService:
    """Purges terminal executions older than the configured retention window.

    Args:
        uow_factory: zero-arg callable returning a fresh Unit of Work per
            purge.
        log_store: log storage whose files are deleted alongside each
            execution row.
        retention_days: executions finished more than this many days ago are
            purged (``settings.log_retention_days``).
        clock: time source (injectable for tests); must return UTC-aware
            datetimes, the domain convention.
    """

    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
        log_store: LogStore,
        retention_days: int,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._uow_factory = uow_factory
        self._log_store = log_store
        self._retention_days = retention_days
        self._clock = clock

    async def purge(self, now: datetime | None = None) -> int:
        """Delete terminal executions finished before the retention cutoff.

        For each purged execution the log file is deleted first (tolerating
        a missing file) and the database row second, so a failure leaves the
        row for the next run instead of orphaning the log.

        Args:
            now: reference time; defaults to the injected clock. Must be
                UTC-aware.

        Returns:
            The number of executions purged.
        """
        effective_now = now if now is not None else self._clock()
        cutoff = effective_now - timedelta(days=self._retention_days)
        purged = 0
        async with self._uow_factory() as uow:
            candidates = await uow.executions.list_finished_before(cutoff)
            for execution in candidates:
                if execution.status not in TERMINAL_STATUSES:
                    continue
                assert execution.id is not None  # listed executions are persisted
                await self._log_store.delete(execution.id)
                await uow.executions.delete(execution.id)
                purged += 1
        logger.info(
            "Retention purge: deleted %d execution(s) finished before %s (retention: %d days)",
            purged,
            cutoff.isoformat(),
            self._retention_days,
        )
        return purged

    async def purge_safely(self) -> None:
        """System-job entry point: purge, logging failures instead of raising.

        A purge failure must never take down the scheduler; the next daily
        run retries.
        """
        try:
            await self.purge()
        except Exception:
            logger.exception("Retention purge failed; will retry on the next scheduled run")
