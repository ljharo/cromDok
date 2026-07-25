"""Unit tests for RunnerService over in-memory fakes (no database)."""

import pytest

from cron_dok.domain.value_objects.cron_expression import InvalidCronExpressionError
from cron_dok.domain.value_objects.resource_limits import ResourceLimits
from cron_dok.services.errors import (
    DuplicateNameError,
    ProjectNotFoundError,
    RunnerNotFoundError,
)


async def _project(project_service, name: str = "etl"):
    return await project_service.create(name=name)


async def test_create_with_defaults(project_service, runner_service) -> None:
    project = await _project(project_service)

    runner = await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="*/5 * * * *",
    )

    assert runner.id is not None
    assert runner.project_id == project.id
    assert runner.resource_limits == ResourceLimits()
    assert runner.on_overlap == "skip"
    assert runner.is_enabled is True
    assert runner.timeout_seconds == 300


async def test_create_normalizes_resource_limits_and_overlap(
    project_service, runner_service
) -> None:
    project = await _project(project_service)

    runner = await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="python",
        cron_expression="0 * * * *",
        resource_limits=ResourceLimits(memory_mb=512, network_enabled=True),
        timeout_seconds=60,
        on_overlap="kill_previous",
    )

    assert runner.resource_limits.memory_mb == 512
    assert runner.resource_limits.network_enabled is True
    assert runner.on_overlap == "kill_previous"
    assert runner.timeout_seconds == 60


async def test_create_unknown_project_raises(project_service, runner_service) -> None:
    with pytest.raises(ProjectNotFoundError):
        await runner_service.create(
            project_id=999,
            name="sync",
            script_content="echo hi",
            language="bash",
            cron_expression="* * * * *",
        )


async def test_create_invalid_cron_raises(project_service, runner_service) -> None:
    project = await _project(project_service)

    with pytest.raises(InvalidCronExpressionError):
        await runner_service.create(
            project_id=project.id,
            name="sync",
            script_content="echo hi",
            language="bash",
            cron_expression="not a cron",
        )


async def test_create_duplicate_name_in_project_raises(project_service, runner_service) -> None:
    project = await _project(project_service)
    await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )

    with pytest.raises(DuplicateNameError, match="runner"):
        await runner_service.create(
            project_id=project.id,
            name="sync",
            script_content="echo again",
            language="bash",
            cron_expression="* * * * *",
        )


async def test_same_name_allowed_in_different_projects(project_service, runner_service) -> None:
    project_a = await _project(project_service, "a")
    project_b = await _project(project_service, "b")

    await runner_service.create(
        project_id=project_a.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )
    runner = await runner_service.create(
        project_id=project_b.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )

    assert runner.project_id == project_b.id


async def test_get_missing_raises(runner_service) -> None:
    with pytest.raises(RunnerNotFoundError):
        await runner_service.get(999)


async def test_list_by_project(project_service, runner_service) -> None:
    project = await _project(project_service)
    other = await _project(project_service, "other")
    for name in ("r1", "r2"):
        await runner_service.create(
            project_id=project.id,
            name=name,
            script_content="echo hi",
            language="bash",
            cron_expression="* * * * *",
        )
    await runner_service.create(
        project_id=other.id,
        name="r3",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )

    runners = await runner_service.list_by_project(project.id)

    assert [r.name for r in runners] == ["r1", "r2"]


async def test_list_by_project_missing_project_raises(runner_service) -> None:
    with pytest.raises(ProjectNotFoundError):
        await runner_service.list_by_project(999)


async def test_update_changes_fields(project_service, runner_service) -> None:
    project = await _project(project_service)
    runner = await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )

    updated = await runner_service.update(
        runner.id,
        name="renamed",
        script_content="echo bye",
        cron_expression="0 3 * * *",
        timeout_seconds=120,
        on_overlap="queue",
    )

    assert updated.id == runner.id
    assert updated.name == "renamed"
    assert updated.script_content == "echo bye"
    assert str(updated.cron_expression) == "0 3 * * *"
    assert updated.timeout_seconds == 120
    assert updated.on_overlap == "queue"


async def test_update_missing_raises(runner_service) -> None:
    with pytest.raises(RunnerNotFoundError):
        await runner_service.update(999, name="x")


async def test_update_invalid_cron_raises(project_service, runner_service) -> None:
    project = await _project(project_service)
    runner = await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )

    with pytest.raises(InvalidCronExpressionError):
        await runner_service.update(runner.id, cron_expression="99 * * * *")


async def test_update_to_taken_name_raises(project_service, runner_service) -> None:
    project = await _project(project_service)
    for name in ("r1", "r2"):
        await runner_service.create(
            project_id=project.id,
            name=name,
            script_content="echo hi",
            language="bash",
            cron_expression="* * * * *",
        )
    runner2 = await runner_service.list_by_project(project.id)

    with pytest.raises(DuplicateNameError):
        await runner_service.update(runner2[1].id, name="r1")


async def test_delete_removes_runner(project_service, runner_service) -> None:
    project = await _project(project_service)
    runner = await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )

    await runner_service.delete(runner.id)

    assert await runner_service.list_by_project(project.id) == []


async def test_delete_missing_raises(runner_service) -> None:
    with pytest.raises(RunnerNotFoundError):
        await runner_service.delete(999)


async def test_enable_and_disable(project_service, runner_service) -> None:
    project = await _project(project_service)
    runner = await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )
    assert runner.is_enabled is True

    disabled = await runner_service.disable(runner.id)
    assert disabled.is_enabled is False
    assert (await runner_service.get(runner.id)).is_enabled is False

    enabled = await runner_service.enable(runner.id)
    assert enabled.is_enabled is True


async def test_enable_missing_raises(runner_service) -> None:
    with pytest.raises(RunnerNotFoundError):
        await runner_service.enable(999)


async def test_disable_missing_raises(runner_service) -> None:
    with pytest.raises(RunnerNotFoundError):
        await runner_service.disable(999)
