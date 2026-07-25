"""Unit tests for EnvVarService over in-memory fakes (no database)."""

from dataclasses import fields

import pytest

from cron_dok.domain.entities.env_var import InvalidEnvVarKeyError
from cron_dok.domain.entities.project import Project
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.services.env_var_service import EnvVarService, EnvVarSummary
from cron_dok.services.errors import (
    EnvVarNotFoundError,
    ProjectNotFoundError,
    RunnerNotFoundError,
)
from tests.unit.fakes import FakeEncryptor, FakeUnitOfWork


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def encryptor() -> FakeEncryptor:
    return FakeEncryptor()


@pytest.fixture
def env_var_service(fake_uow, encryptor) -> EnvVarService:
    return EnvVarService(lambda: fake_uow, encryptor)


async def _seed_project(fake_uow, name: str = "etl"):
    return await fake_uow.projects.save(Project(name=name))


async def _seed_runner(fake_uow, project_id, name: str = "job"):
    return await fake_uow.runners.save(
        Runner(
            project_id=project_id,
            name=name,
            script_content="echo hi",
            language="bash",
            cron_expression=CronExpression("0 0 * * *"),
        )
    )


async def test_create_persists_value_encrypted(env_var_service, fake_uow) -> None:
    project = await _seed_project(fake_uow)

    env_var = await env_var_service.create(
        project_id=project.id, key="API_KEY", value="plaintext-secret"
    )

    assert env_var.id is not None
    assert env_var.encrypted_value != "plaintext-secret"
    assert "plaintext-secret" not in env_var.encrypted_value
    stored = await fake_uow.env_vars.get_by_id(env_var.id)
    assert stored is not None
    assert "plaintext-secret" not in stored.encrypted_value


@pytest.mark.parametrize("blacklisted", ["PATH", "LD_PRELOAD", "HOME"])
async def test_create_blacklisted_key_raises(env_var_service, fake_uow, blacklisted) -> None:
    project = await _seed_project(fake_uow)

    with pytest.raises(InvalidEnvVarKeyError, match="blacklisted"):
        await env_var_service.create(project_id=project.id, key=blacklisted, value="x")

    assert await fake_uow.env_vars.list_by_project(project.id) == []


async def test_create_invalid_key_format_raises(env_var_service, fake_uow) -> None:
    project = await _seed_project(fake_uow)

    with pytest.raises(InvalidEnvVarKeyError):
        await env_var_service.create(project_id=project.id, key="1BAD-KEY", value="x")


async def test_create_missing_project_raises(env_var_service) -> None:
    with pytest.raises(ProjectNotFoundError):
        await env_var_service.create(project_id=999, key="API_KEY", value="x")


async def test_create_missing_runner_raises(env_var_service, fake_uow) -> None:
    project = await _seed_project(fake_uow)

    with pytest.raises(RunnerNotFoundError):
        await env_var_service.create(project_id=project.id, key="API_KEY", value="x", runner_id=999)


async def test_create_runner_of_another_project_raises(env_var_service, fake_uow) -> None:
    project_a = await _seed_project(fake_uow, "a")
    project_b = await _seed_project(fake_uow, "b")
    runner = await _seed_runner(fake_uow, project_b.id)

    with pytest.raises(RunnerNotFoundError):
        await env_var_service.create(
            project_id=project_a.id, key="API_KEY", value="x", runner_id=runner.id
        )


async def test_list_returns_summaries_without_values(env_var_service, fake_uow) -> None:
    project = await _seed_project(fake_uow)
    runner = await _seed_runner(fake_uow, project.id)
    await env_var_service.create(project_id=project.id, key="PROJECT_VAR", value="p")
    await env_var_service.create(
        project_id=project.id, key="RUNNER_VAR", value="r", runner_id=runner.id
    )

    summaries = await env_var_service.list(project.id)

    assert [s.key for s in summaries] == ["PROJECT_VAR", "RUNNER_VAR"]
    assert all(isinstance(s, EnvVarSummary) for s in summaries)
    assert {f.name for f in fields(EnvVarSummary)} == {
        "id",
        "project_id",
        "key",
        "runner_id",
    }
    assert summaries[0].runner_id is None
    assert summaries[1].runner_id == runner.id


async def test_list_filtered_by_runner(env_var_service, fake_uow) -> None:
    project = await _seed_project(fake_uow)
    runner = await _seed_runner(fake_uow, project.id)
    await env_var_service.create(project_id=project.id, key="PROJECT_VAR", value="p")
    await env_var_service.create(
        project_id=project.id, key="RUNNER_VAR", value="r", runner_id=runner.id
    )

    summaries = await env_var_service.list(project.id, runner_id=runner.id)

    assert [s.key for s in summaries] == ["RUNNER_VAR"]


async def test_list_missing_project_raises(env_var_service) -> None:
    with pytest.raises(ProjectNotFoundError):
        await env_var_service.list(999)


async def test_delete_removes_env_var(env_var_service, fake_uow) -> None:
    project = await _seed_project(fake_uow)
    env_var = await env_var_service.create(project_id=project.id, key="API_KEY", value="x")

    await env_var_service.delete(env_var.id)

    assert await fake_uow.env_vars.get_by_id(env_var.id) is None


async def test_delete_missing_raises(env_var_service) -> None:
    with pytest.raises(EnvVarNotFoundError):
        await env_var_service.delete(999)


async def test_resolve_for_runner_decrypts_and_merges(env_var_service, fake_uow) -> None:
    project = await _seed_project(fake_uow)
    runner = await _seed_runner(fake_uow, project.id)
    await env_var_service.create(project_id=project.id, key="SHARED", value="project-value")
    await env_var_service.create(project_id=project.id, key="ONLY_PROJECT", value="p")
    await env_var_service.create(
        project_id=project.id, key="SHARED", value="runner-value", runner_id=runner.id
    )
    await env_var_service.create(
        project_id=project.id, key="ONLY_RUNNER", value="r", runner_id=runner.id
    )

    resolved = await env_var_service.resolve_for_runner(runner.id)

    assert resolved == {
        "SHARED": "runner-value",  # runner overrides the project value
        "ONLY_PROJECT": "p",
        "ONLY_RUNNER": "r",
    }


async def test_resolve_for_runner_ignores_other_runners(env_var_service, fake_uow) -> None:
    project = await _seed_project(fake_uow)
    runner_a = await _seed_runner(fake_uow, project.id, "a")
    runner_b = await _seed_runner(fake_uow, project.id, "b")
    await env_var_service.create(
        project_id=project.id, key="FOR_B", value="secret-b", runner_id=runner_b.id
    )

    resolved = await env_var_service.resolve_for_runner(runner_a.id)

    assert resolved == {}


async def test_resolve_missing_runner_raises(env_var_service) -> None:
    with pytest.raises(RunnerNotFoundError):
        await env_var_service.resolve_for_runner(999)


async def test_rotate_reencrypts_without_reading(env_var_service, fake_uow, encryptor) -> None:
    project = await _seed_project(fake_uow)
    runner = await _seed_runner(fake_uow, project.id)
    env_var = await env_var_service.create(
        project_id=project.id, key="API_KEY", value="old-value", runner_id=runner.id
    )
    old_ciphertext = env_var.encrypted_value

    rotated = await env_var_service.rotate(env_var.id, "new-value")

    assert rotated.id == env_var.id
    assert rotated.encrypted_value != old_ciphertext
    assert "new-value" not in rotated.encrypted_value
    assert encryptor.decrypt(rotated.encrypted_value) == "new-value"
    resolved = await env_var_service.resolve_for_runner(runner.id)
    assert resolved == {"API_KEY": "new-value"}


async def test_rotate_missing_raises(env_var_service) -> None:
    with pytest.raises(EnvVarNotFoundError):
        await env_var_service.rotate(999, "x")
