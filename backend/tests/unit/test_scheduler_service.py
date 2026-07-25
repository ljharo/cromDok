"""Unit tests for SchedulerService: registration, firing and rehydration.

The scheduling backend is a fake (no real scheduler is ever started in unit
tests); persistence uses the in-memory fakes. The execution queue is the
real one with fake executor/log store, so ``_fire`` is exercised end to end
up to the enqueue point.
"""

from dataclasses import replace

import pytest

from cron_dok.domain.entities.project import Project
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.services.errors import ProjectNotFoundError
from cron_dok.services.execution_queue import ExecutionQueue
from cron_dok.services.runner_service import RunnerService
from cron_dok.services.scheduler_service import (
    SchedulerService,
    SystemJobCallback,
    TriggerCallback,
)
from tests.unit.fakes import FakeJobExecutor, FakeLogStore, FakeUnitOfWork


class FakeJobScheduler:
    """JobScheduler test double recording registered jobs."""

    def __init__(self) -> None:
        self.jobs: dict[int, tuple[Runner, TriggerCallback]] = {}
        self.system_jobs: dict[str, tuple[SystemJobCallback, int, int]] = {}
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def shutdown(self) -> None:
        self.stopped = True

    def add_job(self, runner: Runner, callback: TriggerCallback) -> None:
        assert runner.id is not None
        self.jobs[runner.id] = (runner, callback)

    def remove_job(self, runner_id: int) -> None:
        self.jobs.pop(runner_id, None)

    def add_system_job(
        self, job_id: str, callback: SystemJobCallback, *, hour: int, minute: int
    ) -> None:
        self.system_jobs[job_id] = (callback, hour, minute)


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def fake_scheduler() -> FakeJobScheduler:
    return FakeJobScheduler()


@pytest.fixture
def queue(fake_uow: FakeUnitOfWork) -> ExecutionQueue:
    return ExecutionQueue(lambda: fake_uow, FakeJobExecutor(), FakeLogStore())


@pytest.fixture
def service(
    fake_uow: FakeUnitOfWork, queue: ExecutionQueue, fake_scheduler: FakeJobScheduler
) -> SchedulerService:
    return SchedulerService(lambda: fake_uow, queue, fake_scheduler)


@pytest.fixture
async def runner(fake_uow: FakeUnitOfWork) -> Runner:
    project = await fake_uow.projects.save(Project(name="etl"))
    assert project.id is not None
    return await fake_uow.runners.save(
        Runner(
            project_id=project.id,
            name="nightly",
            script_content="echo hi",
            language="bash",
            cron_expression=CronExpression("0 3 * * *"),
        )
    )


def test_register_enabled_runner_adds_job(
    service: SchedulerService, fake_scheduler: FakeJobScheduler, runner: Runner
) -> None:
    service.register(runner)

    assert runner.id in fake_scheduler.jobs


def test_register_disabled_runner_registers_nothing(
    service: SchedulerService, fake_scheduler: FakeJobScheduler, runner: Runner
) -> None:
    service.register(replace(runner, is_enabled=False))

    assert fake_scheduler.jobs == {}


def test_register_without_id_raises(service: SchedulerService, runner: Runner) -> None:
    with pytest.raises(ValueError, match="without id"):
        service.register(replace(runner, id=None))


def test_unregister_removes_job(
    service: SchedulerService, fake_scheduler: FakeJobScheduler, runner: Runner
) -> None:
    service.register(runner)
    assert runner.id is not None

    service.unregister(runner.id)

    assert runner.id not in fake_scheduler.jobs


def test_unregister_unknown_runner_is_noop(service: SchedulerService) -> None:
    service.unregister(999)


async def _noop_system_callback() -> None:
    pass


def test_register_system_job_delegates_to_backend(
    service: SchedulerService, fake_scheduler: FakeJobScheduler
) -> None:
    service.register_system_job("retention-purge", _noop_system_callback, hour=4, minute=17)

    assert fake_scheduler.system_jobs["retention-purge"] == (
        _noop_system_callback,
        4,
        17,
    )


def test_update_reregisters_with_new_cron(
    service: SchedulerService, fake_scheduler: FakeJobScheduler, runner: Runner
) -> None:
    service.register(runner)
    updated = replace(runner, cron_expression=CronExpression("*/10 * * * *"))

    service.update(updated)

    assert runner.id is not None
    assert fake_scheduler.jobs[runner.id][0].cron_expression.value == "*/10 * * * *"


def test_update_disabled_runner_removes_job(
    service: SchedulerService, fake_scheduler: FakeJobScheduler, runner: Runner
) -> None:
    service.register(runner)

    service.update(replace(runner, is_enabled=False))

    assert runner.id not in fake_scheduler.jobs


async def test_rehydrate_registers_only_enabled_runners(
    service: SchedulerService,
    fake_scheduler: FakeJobScheduler,
    fake_uow: FakeUnitOfWork,
) -> None:
    project = await fake_uow.projects.save(Project(name="etl"))
    assert project.id is not None
    enabled = await fake_uow.runners.save(
        Runner(
            project_id=project.id,
            name="on",
            script_content="x",
            language="bash",
            cron_expression=CronExpression("* * * * *"),
        )
    )
    disabled = await fake_uow.runners.save(
        Runner(
            project_id=project.id,
            name="off",
            script_content="x",
            language="bash",
            cron_expression=CronExpression("* * * * *"),
            is_enabled=False,
        )
    )

    count = await service.rehydrate()

    assert count == 1
    assert enabled.id in fake_scheduler.jobs
    assert disabled.id not in fake_scheduler.jobs


async def test_fire_enqueues_with_scheduled_trigger_and_fresh_runner(
    service: SchedulerService,
    fake_scheduler: FakeJobScheduler,
    fake_uow: FakeUnitOfWork,
    runner: Runner,
) -> None:
    service.register(runner)
    assert runner.id is not None
    # Mutate the runner after registration: the fire must use the fresh
    # database state, not the snapshot captured at registration time.
    fresh = await fake_uow.runners.save(replace(runner, script_content="echo changed"))

    await fake_scheduler.jobs[runner.id][1](runner.id)

    executions = await fake_uow.executions.list_by_runner(runner.id)
    assert len(executions) == 1
    assert executions[0].trigger_type == "scheduled"
    assert executions[0].status == "queued"
    assert fresh.script_content == "echo changed"


async def test_fire_for_deleted_runner_removes_stale_job(
    service: SchedulerService,
    fake_scheduler: FakeJobScheduler,
    fake_uow: FakeUnitOfWork,
    runner: Runner,
) -> None:
    service.register(runner)
    assert runner.id is not None
    await fake_uow.runners.delete(runner.id)

    await fake_scheduler.jobs[runner.id][1](runner.id)

    assert runner.id not in fake_scheduler.jobs
    assert await fake_uow.executions.list_by_runner(runner.id) == []


async def test_fire_for_disabled_runner_removes_stale_job(
    service: SchedulerService,
    fake_scheduler: FakeJobScheduler,
    fake_uow: FakeUnitOfWork,
    runner: Runner,
) -> None:
    service.register(runner)
    assert runner.id is not None
    await fake_uow.runners.save(replace(runner, is_enabled=False))

    await fake_scheduler.jobs[runner.id][1](runner.id)

    assert runner.id not in fake_scheduler.jobs
    assert await fake_uow.executions.list_by_runner(runner.id) == []


def test_start_and_shutdown_delegate(service: SchedulerService, fake_scheduler) -> None:
    service.start()
    service.shutdown()

    assert fake_scheduler.started
    assert fake_scheduler.stopped


# --- Wiring: RunnerService notifies the scheduler after DB writes (spec 7) ---


@pytest.fixture
def wired_runner_service(
    fake_uow: FakeUnitOfWork, queue: ExecutionQueue, fake_scheduler: FakeJobScheduler
) -> RunnerService:
    scheduler_service = SchedulerService(lambda: fake_uow, queue, fake_scheduler)
    return RunnerService(lambda: fake_uow, scheduler=scheduler_service)


async def test_create_registers_job(
    wired_runner_service: RunnerService,
    fake_scheduler: FakeJobScheduler,
    fake_uow: FakeUnitOfWork,
) -> None:
    project = await fake_uow.projects.save(Project(name="etl"))
    assert project.id is not None

    runner = await wired_runner_service.create(
        project_id=project.id,
        name="nightly",
        script_content="echo hi",
        language="bash",
        cron_expression="0 3 * * *",
    )

    assert runner.id in fake_scheduler.jobs


async def test_disable_removes_job_and_enable_restores_it(
    wired_runner_service: RunnerService,
    fake_scheduler: FakeJobScheduler,
    fake_uow: FakeUnitOfWork,
) -> None:
    project = await fake_uow.projects.save(Project(name="etl"))
    assert project.id is not None
    runner = await wired_runner_service.create(
        project_id=project.id,
        name="nightly",
        script_content="echo hi",
        language="bash",
        cron_expression="0 3 * * *",
    )
    assert runner.id is not None

    await wired_runner_service.disable(runner.id)
    assert runner.id not in fake_scheduler.jobs

    await wired_runner_service.enable(runner.id)
    assert runner.id in fake_scheduler.jobs


async def test_update_reregisters_job(
    wired_runner_service: RunnerService,
    fake_scheduler: FakeJobScheduler,
    fake_uow: FakeUnitOfWork,
) -> None:
    project = await fake_uow.projects.save(Project(name="etl"))
    assert project.id is not None
    runner = await wired_runner_service.create(
        project_id=project.id,
        name="nightly",
        script_content="echo hi",
        language="bash",
        cron_expression="0 3 * * *",
    )
    assert runner.id is not None

    await wired_runner_service.update(runner.id, cron_expression="15 4 * * 1")

    assert fake_scheduler.jobs[runner.id][0].cron_expression.value == "15 4 * * 1"


async def test_delete_unregisters_job(
    wired_runner_service: RunnerService,
    fake_scheduler: FakeJobScheduler,
    fake_uow: FakeUnitOfWork,
) -> None:
    project = await fake_uow.projects.save(Project(name="etl"))
    assert project.id is not None
    runner = await wired_runner_service.create(
        project_id=project.id,
        name="nightly",
        script_content="echo hi",
        language="bash",
        cron_expression="0 3 * * *",
    )
    assert runner.id is not None

    await wired_runner_service.delete(runner.id)

    assert runner.id not in fake_scheduler.jobs


async def test_failed_create_does_not_notify(
    wired_runner_service: RunnerService,
    fake_scheduler: FakeJobScheduler,
    fake_uow: FakeUnitOfWork,
) -> None:
    with pytest.raises(ProjectNotFoundError):
        await wired_runner_service.create(
            project_id=999,
            name="nightly",
            script_content="echo hi",
            language="bash",
            cron_expression="0 3 * * *",
        )

    assert fake_scheduler.jobs == {}
