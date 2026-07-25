"""Integration tests for the scheduler against real APScheduler + SQLite.

The full-cycle test is the only place a real ``AsyncIOScheduler`` is
started; it has a hard timeout and a guaranteed shutdown so the suite can
never hang.
"""

import asyncio
from collections.abc import AsyncIterator, Callable

import pytest

from cron_dok.adapters.input.scheduler.scheduler_adapter import APSchedulerAdapter
from cron_dok.adapters.output.persistence.unit_of_work import UnitOfWork
from cron_dok.domain.entities.project import Project
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.services.execution_queue import ExecutionQueue
from cron_dok.services.scheduler_service import SchedulerService
from tests.unit.fakes import FakeJobExecutor, FakeLogStore

TERMINAL_STATUSES = {"succeeded", "failed", "skipped", "killed"}


async def _seed_runner(
    uow_factory: Callable[[], UnitOfWork],
    name: str,
    cron: str,
    *,
    is_enabled: bool = True,
) -> Runner:
    async with uow_factory() as uow:
        project = await uow.projects.save(Project(name=f"proj-{name}"))
        assert project.id is not None
        return await uow.runners.save(
            Runner(
                project_id=project.id,
                name=name,
                script_content="echo hi",
                language="bash",
                cron_expression=CronExpression(cron),
                is_enabled=is_enabled,
            )
        )


@pytest.fixture
async def service(
    uow_factory,
) -> AsyncIterator[tuple[SchedulerService, APSchedulerAdapter, ExecutionQueue]]:
    adapter = APSchedulerAdapter()
    queue = ExecutionQueue(uow_factory, FakeJobExecutor(delay=0.01), FakeLogStore())
    instance = SchedulerService(uow_factory, queue, adapter)
    yield instance, adapter, queue
    instance.shutdown()
    await queue.stop()


async def test_rehydrate_registers_only_enabled_runners(uow_factory, service) -> None:
    instance, adapter, _queue = service
    enabled_5 = await _seed_runner(uow_factory, "enabled-5", "0 3 * * *")
    enabled_6 = await _seed_runner(uow_factory, "enabled-6", "*/30 * * * * *")
    disabled = await _seed_runner(uow_factory, "disabled", "* * * * *", is_enabled=False)

    count = await instance.rehydrate()

    assert count == 2
    assert enabled_5.id is not None and adapter.get_job(enabled_5.id) is not None
    assert enabled_6.id is not None and adapter.get_job(enabled_6.id) is not None
    assert disabled.id is not None and adapter.get_job(disabled.id) is None

    job = adapter.get_job(enabled_5.id)
    assert job is not None
    assert "hour='3'" in str(job.trigger)
    assert job.max_instances == 1
    assert job.coalesce is True


async def test_full_cycle_cron_fire_produces_persisted_execution(uow_factory, service) -> None:
    instance, _adapter, queue = service
    runner = await _seed_runner(uow_factory, "every-second", "* * * * * *")
    assert runner.id is not None

    count = await instance.rehydrate()
    assert count == 1

    async def wait_for_terminal_execution() -> None:
        while True:
            async with uow_factory() as uow:
                executions = await uow.executions.list_by_runner(runner.id)
            terminal = [
                e
                for e in executions
                if e.status in TERMINAL_STATUSES and e.trigger_type == "scheduled"
            ]
            if terminal:
                return
            await asyncio.sleep(0.2)

    queue.start()
    instance.start()
    # Hard timeout: the suite can never hang on a real scheduler.
    await asyncio.wait_for(wait_for_terminal_execution(), timeout=15)

    async with uow_factory() as uow:
        executions = await uow.executions.list_by_runner(runner.id)
    terminal = [e for e in executions if e.status in TERMINAL_STATUSES]
    assert terminal, "expected at least one persisted execution after ~3s"
    first = terminal[0]
    assert first.trigger_type == "scheduled"
    assert first.status == "succeeded"
    assert first.exit_code == 0
    assert first.started_at is not None
    assert first.finished_at is not None
