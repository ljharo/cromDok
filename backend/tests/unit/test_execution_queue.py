"""Unit tests for ExecutionQueue with fakes (no database, no docker)."""

import asyncio
from collections.abc import Callable

import pytest

from cron_dok.domain.entities.runner import OverlapPolicy, Runner
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.domain.value_objects.execution_result import ExecutionResult
from cron_dok.services.execution_queue import ExecutionQueue
from tests.unit.fakes import FakeJobExecutor, FakeLogStore, FakeUnitOfWork


def make_runner(runner_id: int = 1, on_overlap: OverlapPolicy = "skip") -> Runner:
    return Runner(
        id=runner_id,
        project_id=1,
        name=f"runner-{runner_id}",
        script_content="echo hi",
        language="bash",
        cron_expression=CronExpression("* * * * *"),
        on_overlap=on_overlap,
    )


async def wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    async def _poll() -> None:
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(_poll(), timeout)


@pytest.fixture
async def harness_factory(fake_uow: FakeUnitOfWork):
    queues: list[ExecutionQueue] = []

    def _make(
        executor: FakeJobExecutor | None = None,
        *,
        max_concurrent_jobs: int = 4,
        env_resolver=None,
    ):
        executor = executor or FakeJobExecutor()
        log_store = FakeLogStore()
        queue = ExecutionQueue(
            lambda: fake_uow,
            executor,
            log_store,
            max_concurrent_jobs=max_concurrent_jobs,
            env_resolver=env_resolver,
        )
        queues.append(queue)
        return queue, executor, log_store

    yield _make
    for queue in queues:
        await queue.stop()


async def test_enqueue_persists_queued_execution(fake_uow, harness_factory) -> None:
    queue, _, _ = harness_factory()

    execution = await queue.enqueue(make_runner(), "manual")

    assert execution.id is not None
    assert execution.status == "queued"
    assert execution.trigger_type == "manual"
    stored = await fake_uow.executions.get_by_id(execution.id)
    assert stored is not None and stored.status == "queued"


async def test_enqueue_runner_without_id_raises(harness_factory) -> None:
    queue, _, _ = harness_factory()
    with pytest.raises(ValueError, match="without id"):
        await queue.enqueue(make_runner(runner_id=None), "manual")  # type: ignore[arg-type]


async def test_success_flow_persists_transitions_and_logs(fake_uow, harness_factory) -> None:
    queue, executor, log_store = harness_factory()
    queue.start()

    execution = await queue.enqueue(make_runner(), "scheduled")
    await queue.wait_idle()

    assert execution.id is not None
    stored = await fake_uow.executions.get_by_id(execution.id)
    assert stored is not None
    assert stored.status == "succeeded"
    assert stored.exit_code == 0
    assert stored.duration_ms is not None
    assert stored.started_at is not None
    assert stored.finished_at is not None
    assert "fake output" in log_store.content(execution.id)
    assert log_store.sinks[execution.id].closed is True


async def test_non_zero_exit_code_marks_failed(fake_uow, harness_factory) -> None:
    executor = FakeJobExecutor(result=ExecutionResult(exit_code=3, duration_ms=10))
    queue, _, _ = harness_factory(executor)
    queue.start()

    execution = await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert execution.id is not None
    stored = await fake_uow.executions.get_by_id(execution.id)
    assert stored is not None
    assert stored.status == "failed"
    assert stored.exit_code == 3


async def test_timed_out_marks_killed(fake_uow, harness_factory) -> None:
    executor = FakeJobExecutor(result=ExecutionResult(exit_code=-1, duration_ms=10, timed_out=True))
    queue, _, _ = harness_factory(executor)
    queue.start()

    execution = await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert execution.id is not None
    stored = await fake_uow.executions.get_by_id(execution.id)
    assert stored is not None and stored.status == "killed"


async def test_executor_exception_marks_failed_and_consumer_survives(
    fake_uow, harness_factory
) -> None:
    executor = FakeJobExecutor(error=RuntimeError("boom"))
    queue, _, _ = harness_factory(executor)
    queue.start()

    failed_execution = await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert failed_execution.id is not None
    stored = await fake_uow.executions.get_by_id(failed_execution.id)
    assert stored is not None and stored.status == "failed"

    # The consumer is still alive: a new execution is dispatched normally.
    executor.error = None
    ok_execution = await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert ok_execution.id is not None
    stored = await fake_uow.executions.get_by_id(ok_execution.id)
    assert stored is not None and stored.status == "succeeded"


async def test_semaphore_bounds_concurrency(fake_uow, harness_factory) -> None:
    executor = FakeJobExecutor(delay=0.05)
    queue, _, _ = harness_factory(executor, max_concurrent_jobs=2)
    queue.start()

    runner = make_runner(on_overlap="queue")
    executions = [await queue.enqueue(runner, "manual") for _ in range(5)]
    await queue.wait_idle()

    assert executor.max_concurrent == 2
    for execution in executions:
        assert execution.id is not None
        stored = await fake_uow.executions.get_by_id(execution.id)
        assert stored is not None and stored.status == "succeeded"


async def test_skip_policy_discards_overlapping_trigger(fake_uow, harness_factory) -> None:
    executor = FakeJobExecutor(block=True)
    queue, _, _ = harness_factory(executor)
    queue.start()
    runner = make_runner(on_overlap="skip")

    first = await queue.enqueue(runner, "scheduled")
    await wait_until(lambda: len(executor.started_runners) == 1)

    second = await queue.enqueue(runner, "scheduled")

    assert second.status == "skipped"
    assert second.finished_at is not None
    assert len(executor.started_runners) == 1

    executor.release.set()
    await queue.wait_idle()
    assert first.id is not None
    stored = await fake_uow.executions.get_by_id(first.id)
    assert stored is not None and stored.status == "succeeded"


async def test_queue_policy_enqueues_despite_overlap(fake_uow, harness_factory) -> None:
    executor = FakeJobExecutor(block=True)
    queue, _, _ = harness_factory(executor)
    queue.start()
    runner = make_runner(on_overlap="queue")

    first = await queue.enqueue(runner, "scheduled")
    await wait_until(lambda: len(executor.started_runners) == 1)
    second = await queue.enqueue(runner, "scheduled")
    assert second.status == "queued"

    executor.release.set()
    await queue.wait_idle()

    assert len(executor.started_runners) == 2
    for execution in (first, second):
        assert execution.id is not None
        stored = await fake_uow.executions.get_by_id(execution.id)
        assert stored is not None and stored.status == "succeeded"


async def test_kill_previous_cancels_running_execution(fake_uow, harness_factory) -> None:
    executor = FakeJobExecutor(block=True)
    queue, _, _ = harness_factory(executor)
    queue.start()
    runner = make_runner(on_overlap="kill_previous")

    first = await queue.enqueue(runner, "scheduled")
    await wait_until(lambda: len(executor.started_runners) == 1)

    second = await queue.enqueue(runner, "scheduled")
    assert second.status == "queued"
    await wait_until(lambda: len(executor.started_runners) == 2)

    assert executor.cancelled_runners == [runner.id]
    assert first.id is not None
    stored_first = await fake_uow.executions.get_by_id(first.id)
    assert stored_first is not None and stored_first.status == "killed"

    executor.release.set()
    await queue.wait_idle()
    assert second.id is not None
    stored_second = await fake_uow.executions.get_by_id(second.id)
    assert stored_second is not None and stored_second.status == "succeeded"


async def test_kill_previous_kills_queued_victim_without_running_it(
    fake_uow, harness_factory
) -> None:
    executor = FakeJobExecutor(block=True)
    queue, _, _ = harness_factory(executor, max_concurrent_jobs=1)
    queue.start()
    runner = make_runner(on_overlap="kill_previous")

    first = await queue.enqueue(runner, "scheduled")
    await wait_until(lambda: len(executor.started_runners) == 1)
    queued_victim = await queue.enqueue(runner, "scheduled")
    assert queued_victim.status == "queued"

    third = await queue.enqueue(runner, "scheduled")
    await wait_until(lambda: len(executor.started_runners) == 2)

    # The queued victim was killed and never dispatched to the executor.
    assert queued_victim.id is not None
    stored_victim = await fake_uow.executions.get_by_id(queued_victim.id)
    assert stored_victim is not None and stored_victim.status == "killed"
    assert stored_victim.started_at is None

    executor.release.set()
    await queue.wait_idle()
    assert first.id is not None and third.id is not None
    assert (await fake_uow.executions.get_by_id(first.id)).status == "killed"
    assert (await fake_uow.executions.get_by_id(third.id)).status == "succeeded"


async def test_env_resolver_feeds_the_executor(harness_factory) -> None:
    async def resolver(runner: Runner) -> dict[str, str]:
        return {"RUNNER_NAME": runner.name}

    queue, executor, _ = harness_factory(env_resolver=resolver)
    queue.start()

    await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert executor.env_vars_received == [{"RUNNER_NAME": "runner-1"}]


async def test_stop_cancels_running_execution_and_marks_killed(fake_uow, harness_factory) -> None:
    executor = FakeJobExecutor(block=True)
    queue, _, _ = harness_factory(executor)
    queue.start()

    execution = await queue.enqueue(make_runner(), "manual")
    await wait_until(lambda: len(executor.started_runners) == 1)

    await queue.stop()

    assert execution.id is not None
    stored = await fake_uow.executions.get_by_id(execution.id)
    assert stored is not None and stored.status == "killed"
    assert stored.finished_at is not None


async def test_double_start_raises(harness_factory) -> None:
    queue, _, _ = harness_factory()
    queue.start()
    with pytest.raises(RuntimeError, match="already started"):
        queue.start()
