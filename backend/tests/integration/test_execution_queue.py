"""Integration tests for ExecutionQueue against a real SQLite tmp database."""

import asyncio

import pytest

from cron_dok.adapters.output.logs.file_log_store import FileLogStore
from cron_dok.domain.entities.project import Project
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.services.execution_queue import ExecutionQueue
from tests.unit.fakes import FakeJobExecutor, FakeLogStore


@pytest.fixture
async def runner(uow_factory) -> Runner:
    async with uow_factory() as uow:
        project = await uow.projects.save(Project(name="etl"))
        assert project.id is not None
        saved: Runner = await uow.runners.save(
            Runner(
                project_id=project.id,
                name="stress",
                script_content="echo hi",
                language="bash",
                cron_expression=CronExpression("* * * * *"),
                on_overlap="queue",
            )
        )
        return saved


@pytest.fixture
async def queue(uow_factory):
    instance = ExecutionQueue(
        uow_factory, FakeJobExecutor(delay=0.01), FakeLogStore(), max_concurrent_jobs=4
    )
    yield instance
    await instance.stop()


async def test_stress_50_concurrent_enqueues_all_persisted_in_order(
    uow_factory, queue, runner
) -> None:
    queue.start()

    executions = await asyncio.gather(*[queue.enqueue(runner, "manual") for _ in range(50)])
    await queue.wait_idle()
    await queue.stop()

    ids = [e.id for e in executions]
    assert len(set(ids)) == 50

    async with uow_factory() as uow:
        stored = await uow.executions.list_by_runner(runner.id)

    assert [e.id for e in stored] == sorted(ids)
    assert len(stored) == 50
    for execution in stored:
        assert execution.status == "succeeded"
        assert execution.exit_code == 0
        assert execution.started_at is not None
        assert execution.finished_at is not None
        assert execution.started_at <= execution.finished_at


async def test_queue_with_file_log_store_writes_real_logs(uow_factory, runner, tmp_path) -> None:
    log_store = FileLogStore(tmp_path / "logs")
    queue = ExecutionQueue(uow_factory, FakeJobExecutor(), log_store)
    queue.start()
    try:
        execution = await queue.enqueue(runner, "manual")
        await queue.wait_idle()
    finally:
        await queue.stop()

    assert execution.id is not None
    content, next_offset = await log_store.read(execution.id)
    assert "fake output" in content
    assert next_offset > 0
    assert log_store.path_for(execution.id).exists()
