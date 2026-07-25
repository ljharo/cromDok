"""Unit tests for SecretMasker and DockerExecutor container construction.

The Docker client is mocked throughout: no daemon required. Real-daemon
coverage lives in ``tests/integration/test_docker_executor.py``.
"""

from pathlib import Path
from unittest.mock import MagicMock

import docker

from cron_dok.adapters.output.executor.docker_executor import (
    MASK,
    DockerExecutor,
    SecretMasker,
)
from cron_dok.domain.entities.runner import Runner, RunnerLanguage
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.domain.value_objects.resource_limits import ResourceLimits
from tests.unit.fakes import FakeLogSink


def make_runner(
    language: RunnerLanguage = "python",
    limits: ResourceLimits | None = None,
) -> Runner:
    return Runner(
        project_id=1,
        name="unit",
        script_content="print('hi')",
        language=language,
        cron_expression=CronExpression("* * * * *"),
        resource_limits=limits or ResourceLimits(),
    )


class TestSecretMasker:
    def test_masks_every_occurrence(self) -> None:
        masker = SecretMasker(["s3cr3t"])
        assert masker.mask("a s3cr3t b s3cr3t") == f"a {MASK} b {MASK}"

    def test_ignores_values_shorter_than_4_chars(self) -> None:
        masker = SecretMasker(["abc", "", "x"])
        assert masker.mask("abc x value") == "abc x value"

    def test_no_secrets_returns_text_unchanged(self) -> None:
        assert SecretMasker([]).mask("anything") == "anything"

    def test_longest_value_wins_on_overlap(self) -> None:
        masker = SecretMasker(["abcd", "abcdef"])
        assert masker.mask("abcdef") == MASK

    def test_regex_metacharacters_are_escaped(self) -> None:
        masker = SecretMasker(["a.b*c$d+"])
        assert masker.mask("key=a.b*c$d+!") == f"key={MASK}!"

    def test_from_env_masks_values_not_keys(self) -> None:
        masker = SecretMasker.from_env({"API_KEY": "s3cr3t-value"})
        assert masker.mask("API_KEY=s3cr3t-value") == f"API_KEY={MASK}"


class TestContainerKwargs:
    def test_sandboxing_defaults(self) -> None:
        executor = DockerExecutor(client=MagicMock())
        kwargs = executor._build_container_kwargs(
            make_runner(), {"A": "1"}, Path("/tmp/x/script.py")
        )
        assert kwargs["auto_remove"] is True
        assert kwargs["detach"] is True
        assert kwargs["mem_limit"] == "256m"
        assert kwargs["nano_cpus"] == 1_000_000_000
        assert kwargs["pids_limit"] == 100
        assert kwargs["network_disabled"] is True
        assert kwargs["user"] == "65534:65534"
        assert kwargs["working_dir"] == "/workspace"
        assert kwargs["environment"] == {"A": "1"}
        assert kwargs["volumes"] == {"/tmp/x": {"bind": "/workspace", "mode": "rw"}}
        assert kwargs["image"] == "python:3.12-slim"
        assert kwargs["command"] == ["python", "/workspace/script.py"]

    def test_network_enabled_when_runner_allows_it(self) -> None:
        executor = DockerExecutor(client=MagicMock())
        runner = make_runner(limits=ResourceLimits(network_enabled=True))
        kwargs = executor._build_container_kwargs(runner, {}, Path("/tmp/x/script.py"))
        assert kwargs["network_disabled"] is False

    def test_custom_limits_are_applied(self) -> None:
        executor = DockerExecutor(client=MagicMock())
        runner = make_runner(limits=ResourceLimits(memory_mb=512, cpu_quota=0.5, pids_limit=50))
        kwargs = executor._build_container_kwargs(runner, {}, Path("/tmp/x/script.py"))
        assert kwargs["mem_limit"] == "512m"
        assert kwargs["nano_cpus"] == 500_000_000
        assert kwargs["pids_limit"] == 50

    def test_command_and_image_per_language(self) -> None:
        executor = DockerExecutor(client=MagicMock())
        expected: dict[RunnerLanguage, tuple[str, list[str]]] = {
            "python": ("python:3.12-slim", ["python", "/workspace/script.py"]),
            "node": ("node:20-slim", ["node", "/workspace/script.js"]),
            "bash": ("bash:5", ["bash", "/workspace/script.sh"]),
        }
        for language, (image, command) in expected.items():
            kwargs = executor._build_container_kwargs(
                make_runner(language=language), {}, Path("/tmp/x/script.py")
            )
            assert kwargs["image"] == image
            assert kwargs["command"] == command


class TestImagePull:
    async def test_pulls_image_when_missing(self) -> None:
        client = MagicMock()
        client.images.get.side_effect = docker.errors.ImageNotFound("missing")
        executor = DockerExecutor(client=client)
        await executor._ensure_image(client, "python:3.12-slim")
        client.images.pull.assert_called_once_with("python:3.12-slim")

    async def test_skips_pull_when_image_present(self) -> None:
        client = MagicMock()
        executor = DockerExecutor(client=client)
        await executor._ensure_image(client, "python:3.12-slim")
        client.images.pull.assert_not_called()


class TestExecuteWithMockedClient:
    def mock_client(self, chunks: list[bytes], status_code: int = 0) -> MagicMock:
        client = MagicMock()
        container = client.containers.create.return_value
        container.logs.return_value = iter(chunks)
        container.wait.return_value = {"StatusCode": status_code}
        return client

    async def test_streams_masked_output_and_returns_exit_code(self) -> None:
        client = self.mock_client([b"token=s3cr3t\n", b"done\n"])
        executor = DockerExecutor(client=client)
        chunks: list[str] = []
        result = await executor.execute(make_runner(), {"API_KEY": "s3cr3t"}, FakeLogSink(chunks))
        assert result.exit_code == 0
        assert result.succeeded
        assert not result.timed_out
        log = "".join(chunks)
        assert "s3cr3t" not in log
        assert f"token={MASK}" in log
        assert "done" in log

    async def test_failing_container_reports_exit_code(self) -> None:
        client = self.mock_client([b"boom\n"], status_code=1)
        executor = DockerExecutor(client=client)
        result = await executor.execute(make_runner(), {}, FakeLogSink([]))
        assert result.exit_code == 1
        assert not result.succeeded

    async def test_script_is_written_world_readable(self, tmp_path: Path) -> None:
        script_path = DockerExecutor._write_script(make_runner(), tmp_path)
        assert script_path.read_text() == "print('hi')"
        assert script_path.stat().st_mode & 0o777 == 0o644
        assert tmp_path.stat().st_mode & 0o777 == 0o777
