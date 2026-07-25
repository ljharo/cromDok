"""Integration tests for RunnerService against a real SQLite tmp database."""

import pytest

from cron_dok.domain.value_objects.cron_expression import InvalidCronExpressionError
from cron_dok.domain.value_objects.resource_limits import ResourceLimits
from cron_dok.services.errors import (
    DuplicateNameError,
    ProjectNotFoundError,
    RunnerNotFoundError,
)


async def test_create_persists_defaults(project_service, runner_service) -> None:
    project = await project_service.create(name="etl")

    runner = await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="*/5 * * * *",
    )

    stored = await runner_service.get(runner.id)
    assert stored.resource_limits == ResourceLimits()
    assert stored.on_overlap == "skip"
    assert stored.is_enabled is True
    assert str(stored.cron_expression) == "*/5 * * * *"


async def test_create_persists_custom_limits(project_service, runner_service) -> None:
    project = await project_service.create(name="etl")

    runner = await runner_service.create(
        project_id=project.id,
        name="heavy",
        script_content="train()",
        language="python",
        cron_expression="0 3 * * *",
        resource_limits=ResourceLimits(memory_mb=1024, cpu_quota=2.0, network_enabled=True),
        timeout_seconds=3600,
        on_overlap="kill_previous",
    )

    stored = await runner_service.get(runner.id)
    assert stored.resource_limits.memory_mb == 1024
    assert stored.resource_limits.network_enabled is True
    assert stored.timeout_seconds == 3600
    assert stored.on_overlap == "kill_previous"


async def test_create_unknown_project_raises_and_persists_nothing(
    project_service, runner_service, uow_factory
) -> None:
    with pytest.raises(ProjectNotFoundError):
        await runner_service.create(
            project_id=999,
            name="sync",
            script_content="echo hi",
            language="bash",
            cron_expression="* * * * *",
        )

    async with uow_factory() as uow:
        assert await uow.runners.list_by_project(999) == []


async def test_create_invalid_cron_raises_and_persists_nothing(
    project_service, runner_service
) -> None:
    project = await project_service.create(name="etl")

    with pytest.raises(InvalidCronExpressionError):
        await runner_service.create(
            project_id=project.id,
            name="sync",
            script_content="echo hi",
            language="bash",
            cron_expression="definitely not cron",
        )

    assert await runner_service.list_by_project(project.id) == []


async def test_create_duplicate_name_rolls_back(project_service, runner_service) -> None:
    project = await project_service.create(name="etl")
    await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )

    with pytest.raises(DuplicateNameError):
        await runner_service.create(
            project_id=project.id,
            name="sync",
            script_content="echo again",
            language="bash",
            cron_expression="* * * * *",
        )

    runners = await runner_service.list_by_project(project.id)
    assert [r.script_content for r in runners] == ["echo hi"]


async def test_update_persists(project_service, runner_service) -> None:
    project = await project_service.create(name="etl")
    runner = await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )

    await runner_service.update(
        runner.id,
        script_content="echo bye",
        cron_expression="0 3 * * *",
        resource_limits=ResourceLimits(memory_mb=512),
    )

    stored = await runner_service.get(runner.id)
    assert stored.script_content == "echo bye"
    assert str(stored.cron_expression) == "0 3 * * *"
    assert stored.resource_limits.memory_mb == 512


async def test_update_missing_raises(runner_service) -> None:
    with pytest.raises(RunnerNotFoundError):
        await runner_service.update(999, name="x")


async def test_enable_disable_persist(project_service, runner_service) -> None:
    project = await project_service.create(name="etl")
    runner = await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )

    await runner_service.disable(runner.id)
    assert (await runner_service.get(runner.id)).is_enabled is False

    await runner_service.enable(runner.id)
    assert (await runner_service.get(runner.id)).is_enabled is True


async def test_delete_removes_runner_but_keeps_project(project_service, runner_service) -> None:
    project = await project_service.create(name="etl")
    runner = await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )

    await runner_service.delete(runner.id)

    assert await runner_service.list_by_project(project.id) == []
    assert (await project_service.get(project.id)).name == "etl"
