import pytest

from cron_dok.domain.entities.env_var import (
    BLACKLISTED_KEYS,
    EnvVar,
    InvalidEnvVarKeyError,
)
from cron_dok.domain.entities.execution import Execution
from cron_dok.domain.entities.project import Project
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.cron_expression import CronExpression


def test_project_requires_non_empty_name() -> None:
    with pytest.raises(ValueError, match="name"):
        Project(name="   ")


def test_project_defaults() -> None:
    project = Project(name="etl")
    assert project.id is None
    assert project.description == ""
    assert project.created_at is not None


def _make_runner(**overrides: object) -> Runner:
    kwargs: dict[str, object] = {
        "project_id": 1,
        "name": "sync",
        "script_content": "echo hi",
        "language": "bash",
        "cron_expression": CronExpression("*/5 * * * *"),
    }
    kwargs.update(overrides)
    return Runner(**kwargs)  # type: ignore[arg-type]


def test_runner_defaults_match_spec() -> None:
    runner = _make_runner()
    assert runner.timeout_seconds == 300
    assert runner.on_overlap == "skip"
    assert runner.is_enabled is True
    assert runner.resource_limits.network_enabled is False


def test_runner_requires_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        _make_runner(timeout_seconds=0)


def test_runner_requires_non_empty_name() -> None:
    with pytest.raises(ValueError, match="name"):
        _make_runner(name="")


def test_execution_defaults() -> None:
    execution = Execution(runner_id=7)
    assert execution.status == "queued"
    assert execution.trigger_type == "scheduled"
    assert execution.log_path is None
    assert execution.exit_code is None


def test_env_var_valid() -> None:
    var = EnvVar(project_id=1, key="API_TOKEN", encrypted_value="gAAAA...")
    assert var.runner_id is None


@pytest.mark.parametrize("key", ["1BAD", "HAS SPACE", "HAS-DASH", ""])
def test_env_var_invalid_key_format(key: str) -> None:
    with pytest.raises(InvalidEnvVarKeyError):
        EnvVar(project_id=1, key=key, encrypted_value="x")


@pytest.mark.parametrize("key", sorted(BLACKLISTED_KEYS))
def test_env_var_blacklisted_keys(key: str) -> None:
    with pytest.raises(InvalidEnvVarKeyError, match="blacklisted"):
        EnvVar(project_id=1, key=key, encrypted_value="x")
