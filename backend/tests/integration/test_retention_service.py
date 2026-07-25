"""Integration tests for the retention purge over a real SQLite database.

Executions are seeded with mixed statuses and ages, with real log files on
disk (FileLogStore over tmp_path); after the purge the surviving rows and
files are asserted.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cron_dok.adapters.output.logs.file_log_store import FileLogStore
from cron_dok.adapters.output.persistence.unit_of_work import UnitOfWork
from cron_dok.domain.entities.execution import Execution, ExecutionStatus
from cron_dok.domain.entities.project import Project
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.services.retention_service import RetentionService

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
RETENTION_DAYS = 30


async def _seed_runner(uow_factory: Callable[[], UnitOfWork]) -> Runner:
    async with uow_factory() as uow:
        project = await uow.projects.save(Project(name="etl"))
        assert project.id is not None
        return await uow.runners.save(
            Runner(
                project_id=project.id,
                name="nightly",
                script_content="echo hi",
                language="bash",
                cron_expression=CronExpression("0 3 * * *"),
            )
        )


async def _seed_execution(
    uow_factory: Callable[[], UnitOfWork],
    log_dir: Path,
    runner_id: int,
    *,
    status: ExecutionStatus,
    finished_at: datetime | None,
    with_log: bool = True,
) -> Execution:
    async with uow_factory() as uow:
        execution = await uow.executions.save(
            Execution(runner_id=runner_id, status=status, finished_at=finished_at)
        )
    assert execution.id is not None
    if with_log:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{execution.id}.log").write_text(f"log of {execution.id}\n", encoding="utf-8")
    return execution


async def test_purge_deletes_old_terminal_rows_and_their_log_files(
    uow_factory: Callable[[], UnitOfWork], tmp_path: Path
) -> None:
    runner = await _seed_runner(uow_factory)
    assert runner.id is not None
    log_dir = tmp_path / "logs"
    old = NOW - timedelta(days=RETENTION_DAYS + 10)

    old_succeeded = await _seed_execution(
        uow_factory, log_dir, runner.id, status="succeeded", finished_at=old
    )
    old_failed = await _seed_execution(
        uow_factory, log_dir, runner.id, status="failed", finished_at=old
    )
    old_running = await _seed_execution(
        uow_factory, log_dir, runner.id, status="running", finished_at=old
    )
    recent = await _seed_execution(
        uow_factory,
        log_dir,
        runner.id,
        status="succeeded",
        finished_at=NOW - timedelta(days=5),
    )
    at_cutoff = await _seed_execution(
        uow_factory,
        log_dir,
        runner.id,
        status="succeeded",
        finished_at=NOW - timedelta(days=RETENTION_DAYS),
    )
    live = await _seed_execution(
        uow_factory,
        log_dir,
        runner.id,
        status="queued",
        finished_at=None,
        with_log=False,
    )

    log_store = FileLogStore(log_dir)
    service = RetentionService(uow_factory, log_store, RETENTION_DAYS)

    purged = await service.purge(now=NOW)

    assert purged == 2
    assert old_succeeded.id is not None and old_failed.id is not None
    assert not (log_dir / f"{old_succeeded.id}.log").exists()
    assert not (log_dir / f"{old_failed.id}.log").exists()

    kept = [old_running, recent, at_cutoff, live]
    for execution in kept:
        assert execution.id is not None
    for execution in (old_running, recent, at_cutoff):
        assert execution.id is not None
        assert (log_dir / f"{execution.id}.log").exists()
    kept_ids = {e.id for e in kept}
    async with uow_factory() as uow:
        remaining = await uow.executions.list_by_runner(runner.id)
    assert {e.id for e in remaining} == kept_ids


async def test_purge_tolerates_missing_log_files(
    uow_factory: Callable[[], UnitOfWork], tmp_path: Path
) -> None:
    runner = await _seed_runner(uow_factory)
    assert runner.id is not None
    log_dir = tmp_path / "logs"
    execution = await _seed_execution(
        uow_factory,
        log_dir,
        runner.id,
        status="failed",
        finished_at=NOW - timedelta(days=RETENTION_DAYS + 1),
        with_log=False,
    )

    service = RetentionService(uow_factory, FileLogStore(log_dir), RETENTION_DAYS)

    assert await service.purge(now=NOW) == 1
    assert execution.id is not None
    async with uow_factory() as uow:
        assert await uow.executions.get_by_id(execution.id) is None


async def test_purge_leaves_other_runners_executions_untouched(
    uow_factory: Callable[[], UnitOfWork], tmp_path: Path
) -> None:
    runner = await _seed_runner(uow_factory)
    assert runner.id is not None
    log_dir = tmp_path / "logs"
    await _seed_execution(
        uow_factory,
        log_dir,
        runner.id,
        status="succeeded",
        finished_at=NOW - timedelta(days=1),
    )

    service = RetentionService(uow_factory, FileLogStore(log_dir), RETENTION_DAYS)

    assert await service.purge(now=NOW) == 0
    async with uow_factory() as uow:
        assert len(await uow.executions.list_by_runner(runner.id)) == 1
