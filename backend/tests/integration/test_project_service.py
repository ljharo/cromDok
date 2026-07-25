"""Integration tests for ProjectService against a real SQLite tmp database."""

import pytest

from cron_dok.domain.entities.env_var import EnvVar
from cron_dok.domain.entities.execution import Execution
from cron_dok.services.errors import DuplicateNameError, ProjectNotFoundError


async def test_create_get_list_roundtrip(project_service) -> None:
    project = await project_service.create(name="etl", description="pipelines")
    assert project.id is not None

    stored = await project_service.get(project.id)
    assert stored.name == "etl"

    await project_service.create(name="backups")
    assert [p.name for p in await project_service.list()] == ["etl", "backups"]


async def test_create_duplicate_name_rolls_back(project_service) -> None:
    await project_service.create(name="etl")

    with pytest.raises(DuplicateNameError):
        await project_service.create(name="etl")

    assert [p.name for p in await project_service.list()] == ["etl"]


async def test_update_persists(project_service) -> None:
    project = await project_service.create(name="old")

    await project_service.update(project.id, name="new", description="renamed")

    stored = await project_service.get(project.id)
    assert stored.name == "new"
    assert stored.description == "renamed"


async def test_update_missing_raises(project_service) -> None:
    with pytest.raises(ProjectNotFoundError):
        await project_service.update(999, name="x")


async def test_delete_missing_raises(project_service) -> None:
    with pytest.raises(ProjectNotFoundError):
        await project_service.delete(999)


async def test_delete_cascades_runners_executions_and_env_vars(
    project_service, runner_service, uow_factory
) -> None:
    """Deleting a project through the service leaves no orphaned rows."""
    project = await project_service.create(name="etl")
    runner = await runner_service.create(
        project_id=project.id,
        name="sync",
        script_content="echo hi",
        language="bash",
        cron_expression="* * * * *",
    )
    async with uow_factory() as uow:
        await uow.executions.save(Execution(runner_id=runner.id))
        await uow.env_vars.save(
            EnvVar(
                project_id=project.id,
                runner_id=runner.id,
                key="TOKEN",
                encrypted_value="enc",
            )
        )

    await project_service.delete(project.id)

    async with uow_factory() as uow:
        assert await uow.projects.get_by_id(project.id) is None
        assert await uow.runners.list_by_project(project.id) == []
        assert await uow.executions.list_by_runner(runner.id) == []
        assert await uow.env_vars.list_by_project(project.id) == []
