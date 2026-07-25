"""UnitOfWork: commit on clean exit, rollback on exception (spec 6.2)."""

import pytest

from cron_dok.domain.entities.project import Project


async def test_commit_on_clean_exit(uow) -> None:
    async with uow:
        project = await uow.projects.save(Project(name="etl", description="pipelines"))
        assert project.id is not None

    async with uow:
        stored = await uow.projects.get_by_id(project.id)
        assert stored is not None
        assert stored.name == "etl"


async def test_rollback_on_exception(uow) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        async with uow:
            await uow.projects.save(Project(name="doomed"))
            raise RuntimeError("boom")

    async with uow:
        assert await uow.projects.list_all() == []


async def test_multi_step_write_is_atomic(uow) -> None:
    """A failure mid-way rolls back every step of the transaction."""
    from cron_dok.domain.entities.runner import Runner
    from cron_dok.domain.value_objects.cron_expression import CronExpression

    with pytest.raises(RuntimeError):
        async with uow:
            project = await uow.projects.save(Project(name="atomic"))
            await uow.runners.save(
                Runner(
                    project_id=project.id,
                    name="r1",
                    script_content="echo hi",
                    language="bash",
                    cron_expression=CronExpression("* * * * *"),
                )
            )
            raise RuntimeError("fail after two writes")

    async with uow:
        assert await uow.projects.list_all() == []
        # runners of a non-existent project cannot exist either
        assert await uow.runners.list_by_project(1) == []
