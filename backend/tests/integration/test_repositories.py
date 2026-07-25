"""Integration tests for the four SQLite repositories over a real tmp database."""

from cron_dok.domain.entities.env_var import EnvVar
from cron_dok.domain.entities.execution import Execution
from cron_dok.domain.entities.project import Project
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.domain.value_objects.resource_limits import ResourceLimits


def _runner(project_id: int, name: str = "sync", **overrides) -> Runner:
    return Runner(
        project_id=project_id,
        name=name,
        script_content="echo hi",
        language="bash",
        cron_expression=CronExpression("*/5 * * * *"),
        **overrides,
    )


async def test_project_save_get_list_delete(uow) -> None:
    async with uow:
        project = await uow.projects.save(Project(name="etl", description="pipelines"))
        assert project.id is not None
        assert project.created_at is not None

        stored = await uow.projects.get_by_id(project.id)
        assert stored == project

        await uow.projects.save(Project(name="backups"))
        assert [p.name for p in await uow.projects.list_all()] == ["etl", "backups"]

        await uow.projects.delete(project.id)
        assert await uow.projects.get_by_id(project.id) is None


async def test_project_update(uow) -> None:
    async with uow:
        project = await uow.projects.save(Project(name="old"))
        updated = await uow.projects.save(Project(id=project.id, name="new", description="renamed"))
        assert updated.id == project.id
        assert (await uow.projects.get_by_id(project.id)).name == "new"


async def test_runner_roundtrip_with_value_objects(uow) -> None:
    async with uow:
        project = await uow.projects.save(Project(name="p"))
        runner = await uow.runners.save(
            _runner(
                project.id,
                resource_limits=ResourceLimits(memory_mb=512, cpu_quota=2.0, pids_limit=50),
                on_overlap="kill_previous",
                timeout_seconds=60,
                is_enabled=False,
            )
        )
        assert runner.id is not None

        stored = await uow.runners.get_by_id(runner.id)
        assert stored == runner
        assert stored.cron_expression == CronExpression("*/5 * * * *")
        assert stored.resource_limits.memory_mb == 512
        assert stored.on_overlap == "kill_previous"

        assert [r.name for r in await uow.runners.list_by_project(project.id)] == ["sync"]


async def test_execution_save_and_list_by_runner(uow) -> None:
    async with uow:
        project = await uow.projects.save(Project(name="p"))
        runner = await uow.runners.save(_runner(project.id))

        execution = await uow.executions.save(Execution(runner_id=runner.id))
        assert execution.id is not None
        assert execution.status == "queued"

        finished = await uow.executions.save(
            Execution(
                id=execution.id,
                runner_id=runner.id,
                status="succeeded",
                trigger_type="manual",
                exit_code=0,
                duration_ms=150,
                log_path="data/logs/1.log",
            )
        )
        assert finished.exit_code == 0
        assert finished.log_path == "data/logs/1.log"

        executions = await uow.executions.list_by_runner(runner.id)
        assert len(executions) == 1
        assert executions[0].status == "succeeded"


async def test_env_var_scopes(uow) -> None:
    async with uow:
        project = await uow.projects.save(Project(name="p"))
        runner = await uow.runners.save(_runner(project.id))

        project_var = await uow.env_vars.save(
            EnvVar(project_id=project.id, key="REGION", encrypted_value="enc1")
        )
        await uow.env_vars.save(
            EnvVar(
                project_id=project.id,
                runner_id=runner.id,
                key="TOKEN",
                encrypted_value="enc2",
            )
        )

        vars_ = await uow.env_vars.list_by_project(project.id)
        assert [v.key for v in vars_] == ["REGION", "TOKEN"]
        assert vars_[0].runner_id is None
        assert vars_[1].runner_id == runner.id

        stored = await uow.env_vars.get_by_id(project_var.id)
        assert stored.encrypted_value == "enc1"

        await uow.env_vars.delete(project_var.id)
        assert [v.key for v in await uow.env_vars.list_by_project(project.id)] == ["TOKEN"]


async def test_delete_project_cascades_runners_executions_and_env_vars(uow) -> None:
    async with uow:
        project = await uow.projects.save(Project(name="p"))
        runner = await uow.runners.save(_runner(project.id))
        await uow.executions.save(Execution(runner_id=runner.id))
        await uow.env_vars.save(
            EnvVar(
                project_id=project.id,
                runner_id=runner.id,
                key="TOKEN",
                encrypted_value="enc",
            )
        )

        await uow.projects.delete(project.id)

        assert await uow.runners.list_by_project(project.id) == []
        assert await uow.executions.list_by_runner(runner.id) == []
        assert await uow.env_vars.list_by_project(project.id) == []


async def test_delete_runner_cascades_executions(uow) -> None:
    async with uow:
        project = await uow.projects.save(Project(name="p"))
        runner = await uow.runners.save(_runner(project.id))
        await uow.executions.save(Execution(runner_id=runner.id))

        await uow.runners.delete(runner.id)

        assert await uow.runners.get_by_id(runner.id) is None
        assert await uow.executions.list_by_runner(runner.id) == []
        # the project itself survives
        assert await uow.projects.get_by_id(project.id) is not None
