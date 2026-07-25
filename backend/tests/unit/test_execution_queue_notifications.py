"""Queue-level tests for failure notifications (step 3.4).

Covers when the ExecutionQueue invokes the notifier (failed and killed by
timeout; never succeeded, skipped or killed by kill_previous), the masked
log excerpt, and the fire-and-forget guarantee: a broken notifier never
breaks the execution nor the consumer.
"""

import asyncio

import pytest

from cron_dok.domain.entities.execution import Execution
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.execution_result import ExecutionResult
from cron_dok.ports.executors.job_executor import JobExecutor
from cron_dok.ports.logs.log_store import LogSink
from cron_dok.services.execution_queue import ExecutionQueue
from tests.unit.fakes import FakeJobExecutor, FakeLogStore, FakeUnitOfWork
from tests.unit.test_execution_queue import make_runner, wait_until


class FakeNotifier:
    """FailureNotifier test double recording calls; can be made to raise."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[Execution, Runner, str]] = []
        self.error = error

    async def notify_failure(self, execution: Execution, runner: Runner, log_excerpt: str) -> None:
        self.calls.append((execution, runner, log_excerpt))
        if self.error is not None:
            raise self.error


class LoggingExecutor(JobExecutor):
    """Executor writing a fixed text to the log sink before returning."""

    def __init__(self, result: ExecutionResult, log_text: str) -> None:
        self.result = result
        self.log_text = log_text

    async def execute(
        self, runner: Runner, env_vars: dict[str, str], log_sink: LogSink
    ) -> ExecutionResult:
        await log_sink.write(self.log_text)
        return self.result


@pytest.fixture
async def harness_factory(fake_uow: FakeUnitOfWork):
    queues: list[ExecutionQueue] = []

    def _make(
        executor: JobExecutor | None = None,
        notifier: FakeNotifier | None = None,
        *,
        env_resolver=None,
    ):
        executor = executor or FakeJobExecutor()
        log_store = FakeLogStore()
        queue = ExecutionQueue(
            lambda: fake_uow,
            executor,
            log_store,
            env_resolver=env_resolver,
            notifier=notifier,
        )
        queues.append(queue)
        return queue, log_store

    yield _make
    for queue in queues:
        await queue.stop()


async def test_failed_execution_notifies_with_masked_excerpt(fake_uow, harness_factory) -> None:
    secret = "s3cr3t-value"  # pragma: allowlist secret
    log_text = f"starting\nconnecting with token {secret}\nfailed badly\n"

    async def resolver(runner: Runner) -> dict[str, str]:
        return {"API_TOKEN": secret}

    notifier = FakeNotifier()
    executor = LoggingExecutor(ExecutionResult(exit_code=3, duration_ms=10), log_text)
    queue, _ = harness_factory(executor, notifier, env_resolver=resolver)
    queue.start()

    execution = await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert len(notifier.calls) == 1
    notified_execution, notified_runner, excerpt = notifier.calls[0]
    assert notified_execution.id == execution.id
    assert notified_execution.status == "failed"
    assert notified_execution.exit_code == 3
    assert notified_execution.finished_at is not None
    assert notified_runner.id == execution.runner_id
    assert secret not in excerpt
    assert "********" in excerpt
    assert "failed badly" in excerpt


async def test_excerpt_is_limited_to_the_log_tail(harness_factory) -> None:
    log_text = "A" * 200 + "B" * 400
    notifier = FakeNotifier()
    executor = LoggingExecutor(ExecutionResult(exit_code=1, duration_ms=1), log_text)
    queue, _ = harness_factory(executor, notifier)
    queue.start()

    await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    _, _, excerpt = notifier.calls[0]
    assert len(excerpt) == 500
    assert excerpt == "A" * 100 + "B" * 400


async def test_succeeded_execution_does_not_notify(harness_factory) -> None:
    notifier = FakeNotifier()
    queue, _ = harness_factory(notifier=notifier)
    queue.start()

    await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert notifier.calls == []


async def test_skipped_execution_does_not_notify(harness_factory) -> None:
    executor = FakeJobExecutor(block=True)
    notifier = FakeNotifier()
    queue, _ = harness_factory(executor, notifier)
    queue.start()
    runner = make_runner(on_overlap="skip")

    await queue.enqueue(runner, "scheduled")
    await wait_until(lambda: len(executor.started_runners) == 1)
    second = await queue.enqueue(runner, "scheduled")
    assert second.status == "skipped"

    executor.release.set()
    await queue.wait_idle()
    assert notifier.calls == []


async def test_killed_by_timeout_notifies(harness_factory) -> None:
    notifier = FakeNotifier()
    executor = FakeJobExecutor(result=ExecutionResult(exit_code=-1, duration_ms=10, timed_out=True))
    queue, _ = harness_factory(executor, notifier)
    queue.start()

    execution = await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert len(notifier.calls) == 1
    notified_execution, _, _ = notifier.calls[0]
    assert notified_execution.id == execution.id
    assert notified_execution.status == "killed"


async def test_killed_by_kill_previous_does_not_notify(fake_uow, harness_factory) -> None:
    executor = FakeJobExecutor(block=True)
    notifier = FakeNotifier()
    queue, _ = harness_factory(executor, notifier)
    queue.start()
    runner = make_runner(on_overlap="kill_previous")

    first = await queue.enqueue(runner, "scheduled")
    await wait_until(lambda: len(executor.started_runners) == 1)
    await queue.enqueue(runner, "scheduled")
    await wait_until(lambda: len(executor.started_runners) == 2)

    executor.release.set()
    await queue.wait_idle()

    assert first.id is not None
    stored = await fake_uow.executions.get_by_id(first.id)
    assert stored is not None and stored.status == "killed"
    assert notifier.calls == []


async def test_notifier_exception_does_not_break_execution_or_consumer(
    fake_uow, harness_factory
) -> None:
    notifier = FakeNotifier(error=RuntimeError("webhook exploded"))
    executor = FakeJobExecutor(result=ExecutionResult(exit_code=3, duration_ms=10))
    queue, _ = harness_factory(executor, notifier)
    queue.start()

    failed_execution = await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert len(notifier.calls) == 1
    assert failed_execution.id is not None
    stored = await fake_uow.executions.get_by_id(failed_execution.id)
    assert stored is not None and stored.status == "failed"

    # The consumer is still alive: a new execution runs and succeeds.
    executor.result = ExecutionResult(exit_code=0, duration_ms=1)
    ok_execution = await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert ok_execution.id is not None
    stored_ok = await fake_uow.executions.get_by_id(ok_execution.id)
    assert stored_ok is not None and stored_ok.status == "succeeded"
    assert len(notifier.calls) == 1


async def test_no_notifier_configured_is_a_no_op(fake_uow, harness_factory) -> None:
    executor = FakeJobExecutor(result=ExecutionResult(exit_code=3, duration_ms=10))
    queue, _ = harness_factory(executor, notifier=None)
    queue.start()

    execution = await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert execution.id is not None
    stored = await fake_uow.executions.get_by_id(execution.id)
    assert stored is not None and stored.status == "failed"


async def test_failed_execution_without_log_sends_empty_excerpt(
    harness_factory,
) -> None:
    notifier = FakeNotifier()
    executor = FakeJobExecutor(error=RuntimeError("boom"))  # writes no log
    queue, _ = harness_factory(executor, notifier)
    queue.start()

    await queue.enqueue(make_runner(), "manual")
    await queue.wait_idle()

    assert len(notifier.calls) == 1
    _, _, excerpt = notifier.calls[0]
    assert excerpt == ""


async def test_notification_does_not_block_the_terminal_transition(
    fake_uow, harness_factory
) -> None:
    """Fire-and-forget: the execution is already terminal while the webhook
    is still in flight, and wait_idle drains the pending notification."""
    entered = asyncio.Event()
    release = asyncio.Event()

    class SlowNotifier:
        def __init__(self) -> None:
            self.finished = 0

        async def notify_failure(
            self, execution: Execution, runner: Runner, log_excerpt: str
        ) -> None:
            entered.set()
            await release.wait()
            self.finished += 1

    notifier = SlowNotifier()
    executor = FakeJobExecutor(result=ExecutionResult(exit_code=1, duration_ms=1))
    queue, _ = harness_factory(executor, notifier)
    queue.start()

    execution = await queue.enqueue(make_runner(), "manual")
    await wait_until(lambda: entered.is_set())

    # The webhook is still blocked, but the execution already finished.
    assert execution.id is not None
    stored = await fake_uow.executions.get_by_id(execution.id)
    assert stored is not None and stored.status == "failed"

    release.set()
    await queue.wait_idle()
    assert notifier.finished == 1
