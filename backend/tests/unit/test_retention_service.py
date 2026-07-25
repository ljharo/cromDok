"""Unit tests for RetentionService: purge rules, log deletion, error handling.

Persistence uses the in-memory fakes; the log store is a fake that records
``delete`` calls so the tests assert exactly which executions lost their log.
"""

from datetime import UTC, datetime, timedelta

import pytest

from cron_dok.domain.entities.execution import Execution, ExecutionStatus
from cron_dok.services.retention_service import RetentionService
from tests.unit.fakes import FakeLogStore, FakeUnitOfWork

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
RETENTION_DAYS = 30


class RecordingLogStore(FakeLogStore):
    """FakeLogStore that records every ``delete`` call."""

    def __init__(self) -> None:
        super().__init__()
        self.deleted: list[int] = []

    async def delete(self, execution_id: int) -> None:
        self.deleted.append(execution_id)
        await super().delete(execution_id)


class FailingLogStore(FakeLogStore):
    """FakeLogStore whose ``delete`` always raises."""

    async def delete(self, execution_id: int) -> None:
        raise OSError("disk on fire")


def _execution(
    *,
    status: ExecutionStatus,
    finished_at: datetime | None,
    runner_id: int = 1,
) -> Execution:
    return Execution(runner_id=runner_id, status=status, finished_at=finished_at)


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def log_store() -> RecordingLogStore:
    return RecordingLogStore()


@pytest.fixture
def service(fake_uow: FakeUnitOfWork, log_store: RecordingLogStore) -> RetentionService:
    return RetentionService(
        lambda: fake_uow,
        log_store,
        RETENTION_DAYS,
        clock=lambda: NOW,
    )


async def _seed(fake_uow: FakeUnitOfWork, *executions: Execution) -> list[Execution]:
    async with fake_uow as uow:
        return [await uow.executions.save(e) for e in executions]


async def test_purge_deletes_only_old_terminal_executions(
    fake_uow: FakeUnitOfWork, service: RetentionService
) -> None:
    old = NOW - timedelta(days=RETENTION_DAYS + 10)
    seeded = await _seed(
        fake_uow,
        _execution(status="succeeded", finished_at=old),
        _execution(status="failed", finished_at=old),
        _execution(status="killed", finished_at=old),
        _execution(status="skipped", finished_at=old),
        # Terminal but inside the retention window: kept.
        _execution(status="succeeded", finished_at=NOW - timedelta(days=5)),
        # Old but not terminal: never purged, even with a finished_at set.
        _execution(status="running", finished_at=old),
        _execution(status="queued", finished_at=old),
        # Live executions have no finished_at at all: kept.
        _execution(status="running", finished_at=None),
        _execution(status="queued", finished_at=None),
    )

    purged = await service.purge()

    assert purged == 4
    async with fake_uow as uow:
        remaining = [e.id for e in await uow.executions.list_by_runner(1)]
    assert remaining == [e.id for e in seeded[4:]]


async def test_purge_boundary_is_strict(
    fake_uow: FakeUnitOfWork, service: RetentionService
) -> None:
    exactly_at_cutoff = NOW - timedelta(days=RETENTION_DAYS)
    one_second_past = exactly_at_cutoff - timedelta(seconds=1)
    at_cutoff, past_cutoff = await _seed(
        fake_uow,
        _execution(status="succeeded", finished_at=exactly_at_cutoff),
        _execution(status="succeeded", finished_at=one_second_past),
    )

    purged = await service.purge()

    assert purged == 1
    async with fake_uow as uow:
        assert await uow.executions.get_by_id(at_cutoff.id or -1) is not None
        assert await uow.executions.get_by_id(past_cutoff.id or -1) is None


async def test_purge_calls_log_store_delete_for_each_purged_execution(
    fake_uow: FakeUnitOfWork,
    log_store: RecordingLogStore,
    service: RetentionService,
) -> None:
    old = NOW - timedelta(days=RETENTION_DAYS + 1)
    old_execution, recent_execution = await _seed(
        fake_uow,
        _execution(status="succeeded", finished_at=old),
        _execution(status="succeeded", finished_at=NOW),
    )
    assert old_execution.id is not None and recent_execution.id is not None

    purged = await service.purge()

    assert purged == 1
    assert log_store.deleted == [old_execution.id]


async def test_purge_uses_injected_clock_when_now_is_omitted(
    fake_uow: FakeUnitOfWork, service: RetentionService
) -> None:
    (old_execution,) = await _seed(
        fake_uow,
        _execution(status="succeeded", finished_at=NOW - timedelta(days=RETENTION_DAYS + 1)),
    )

    purged = await service.purge()

    assert purged == 1
    async with fake_uow as uow:
        assert await uow.executions.get_by_id(old_execution.id or -1) is None


async def test_purge_with_nothing_eligible_returns_zero(
    fake_uow: FakeUnitOfWork,
    log_store: RecordingLogStore,
    service: RetentionService,
) -> None:
    await _seed(
        fake_uow,
        _execution(status="succeeded", finished_at=NOW - timedelta(days=1)),
        _execution(status="running", finished_at=None),
    )

    assert await service.purge() == 0
    assert log_store.deleted == []


async def test_purge_safely_swallows_failures(fake_uow: FakeUnitOfWork) -> None:
    (old_execution,) = await _seed(
        fake_uow,
        _execution(status="succeeded", finished_at=NOW - timedelta(days=RETENTION_DAYS + 1)),
    )
    service = RetentionService(lambda: fake_uow, FailingLogStore(), RETENTION_DAYS)

    await service.purge_safely()  # must not raise

    # The log is deleted before the row, so a log failure leaves the row
    # for the next run instead of orphaning the file.
    async with fake_uow as uow:
        assert await uow.executions.get_by_id(old_execution.id or -1) is not None


async def test_explicit_now_overrides_clock(fake_uow: FakeUnitOfWork) -> None:
    def far_future_clock() -> datetime:
        return NOW + timedelta(days=365)

    service = RetentionService(lambda: fake_uow, FakeLogStore(), RETENTION_DAYS, far_future_clock)
    (execution,) = await _seed(
        fake_uow,
        _execution(status="succeeded", finished_at=NOW - timedelta(days=10)),
    )

    # With the clock it would be purged; the explicit ``now`` keeps it.
    assert await service.purge(now=NOW) == 0
    async with fake_uow as uow:
        assert await uow.executions.get_by_id(execution.id or -1) is not None
