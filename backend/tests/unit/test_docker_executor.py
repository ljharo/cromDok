"""Unit tests for SecretMasker and DockerExecutor container construction.

The Docker client is mocked throughout: no daemon required. Real-daemon
coverage lives in ``tests/integration/test_docker_executor.py``.
"""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import docker
import pytest

from cron_dok.adapters.output.executor.docker_executor import (
    MASK,
    DockerExecutor,
    SecretMasker,
    build_node_package_manifest,
    parse_node_dependency,
)
from cron_dok.config import Settings
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
        assert masker.mask_all("a s3cr3t b s3cr3t") == f"a {MASK} b {MASK}"

    def test_ignores_values_shorter_than_4_chars(self) -> None:
        masker = SecretMasker(["abc", "", "x"])
        assert masker.mask_all("abc x value") == "abc x value"

    def test_no_secrets_returns_text_unchanged(self) -> None:
        assert SecretMasker([]).mask_all("anything") == "anything"

    def test_longest_value_wins_on_overlap(self) -> None:
        masker = SecretMasker(["abcd", "abcdef"])
        assert masker.mask_all("abcdef") == MASK

    def test_regex_metacharacters_are_escaped(self) -> None:
        masker = SecretMasker(["a.b*c$d+"])
        assert masker.mask_all("key=a.b*c$d+!") == f"key={MASK}!"

    def test_from_env_masks_values_not_keys(self) -> None:
        masker = SecretMasker.from_env({"API_KEY": "s3cr3t-value"})
        assert masker.mask_all("API_KEY=s3cr3t-value") == f"API_KEY={MASK}"

    def test_streaming_masks_secret_split_across_chunks(self) -> None:
        masker = SecretMasker(["s3cr3t-value"])
        chunks = ["first line\nAPI_KEY=s3cr3t", "-value\nsecond line\n"]
        out = "".join(masker.mask(chunk) for chunk in chunks) + masker.flush()
        assert out == f"first line\nAPI_KEY={MASK}\nsecond line\n"

    def test_streaming_output_equals_one_shot_output(self) -> None:
        # Any chunking of the same text must yield the same masked stream.
        text = "head s3cr3t-value middle s3cr3t-value tail"
        expected = SecretMasker(["s3cr3t-value"]).mask_all(text)
        for cut in range(1, len(text)):
            masker = SecretMasker(["s3cr3t-value"])
            assert masker.mask(text[:cut]) + masker.mask(text[cut:]) + masker.flush() == expected

    def test_streaming_withholds_partial_prefix_until_flush(self) -> None:
        masker = SecretMasker(["s3cr3t-value"])
        # A chunk ending in a proper prefix of the secret is withheld.
        assert masker.mask("prefix s3cr") == "prefix "
        assert masker.flush() == "s3cr"

    def test_streaming_does_not_split_occurrence_before_partial_suffix(self) -> None:
        # "fw1234" starts right where "abcdef" ends: a naive cut at the
        # partial suffix would split the complete "abcdef" occurrence.
        masker = SecretMasker(["abcdef", "fw1234"])
        assert masker.mask("zabcdefw") == "z"
        assert masker.flush() == f"{MASK}w"


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


class TestParseNodeDependency:
    def test_bare_name_defaults_to_latest(self) -> None:
        assert parse_node_dependency("pg") == ("pg", "latest")

    def test_name_with_version(self) -> None:
        assert parse_node_dependency("pg@8.11.0") == ("pg", "8.11.0")

    def test_scoped_package_without_version(self) -> None:
        assert parse_node_dependency("@scope/pkg") == ("@scope/pkg", "latest")

    def test_scoped_package_with_version(self) -> None:
        assert parse_node_dependency("@scope/pkg@1.2.3") == ("@scope/pkg", "1.2.3")

    def test_strips_surrounding_whitespace(self) -> None:
        assert parse_node_dependency("  pg@8.11.0  ") == ("pg", "8.11.0")


class TestBuildNodePackageManifest:
    def test_builds_package_json_with_parsed_dependencies(self) -> None:
        package = json.loads(build_node_package_manifest("pg@8.11.0\nlodash\n\n"))
        assert package["dependencies"] == {"pg": "8.11.0", "lodash": "latest"}


class TestContainerKwargsWithDependencies:
    def test_no_deps_dir_means_no_deps_mount_or_path_env(self) -> None:
        executor = DockerExecutor(client=MagicMock())
        kwargs = executor._build_container_kwargs(make_runner(), {}, Path("/tmp/x/script.py"))
        assert all(v["bind"] != "/deps" for v in kwargs["volumes"].values())
        assert "PYTHONPATH" not in kwargs["environment"]

    def test_python_mounts_deps_readonly_and_sets_pythonpath(self) -> None:
        executor = DockerExecutor(client=MagicMock())
        kwargs = executor._build_container_kwargs(
            make_runner(), {}, Path("/tmp/x/script.py"), Path("/tmp/deps/pkgs")
        )
        assert kwargs["volumes"]["/tmp/deps/pkgs"] == {"bind": "/deps", "mode": "ro"}
        assert kwargs["environment"]["PYTHONPATH"] == "/deps"

    def test_node_sets_node_path(self) -> None:
        executor = DockerExecutor(client=MagicMock())
        kwargs = executor._build_container_kwargs(
            make_runner(language="node"), {}, Path("/tmp/x/script.js"), Path("/tmp/deps/pkgs")
        )
        assert kwargs["environment"]["NODE_PATH"] == "/deps/node_modules"


class TestEnsureDependencies:
    @staticmethod
    def make_executor(tmp_path: Path, client: MagicMock) -> DockerExecutor:
        return DockerExecutor(settings=Settings(data_dir=str(tmp_path)), client=client)

    async def test_no_dependencies_returns_none_and_touches_nothing(self, tmp_path: Path) -> None:
        client = MagicMock()
        executor = self.make_executor(tmp_path, client)
        runner = replace(make_runner(), id=1)
        result = await executor._ensure_dependencies(client, runner, FakeLogSink([]))
        assert result is None
        client.containers.create.assert_not_called()

    async def test_blank_dependencies_are_treated_as_none(self, tmp_path: Path) -> None:
        client = MagicMock()
        executor = self.make_executor(tmp_path, client)
        runner = replace(make_runner(), id=1, dependencies="   \n  ")
        result = await executor._ensure_dependencies(client, runner, FakeLogSink([]))
        assert result is None
        client.containers.create.assert_not_called()

    async def test_bash_language_ignores_dependencies(self, tmp_path: Path) -> None:
        client = MagicMock()
        executor = self.make_executor(tmp_path, client)
        runner = replace(make_runner(language="bash"), id=1, dependencies="whatever")
        result = await executor._ensure_dependencies(client, runner, FakeLogSink([]))
        assert result is None
        client.containers.create.assert_not_called()

    async def test_network_disabled_raises_before_creating_a_container(
        self, tmp_path: Path
    ) -> None:
        client = MagicMock()
        executor = self.make_executor(tmp_path, client)
        runner = replace(
            make_runner(limits=ResourceLimits(network_enabled=False)),
            id=1,
            dependencies="requests",
        )
        with pytest.raises(RuntimeError, match="red desactivada"):
            await executor._ensure_dependencies(client, runner, FakeLogSink([]))
        client.containers.create.assert_not_called()

    async def test_installs_and_writes_hash_marker_on_cache_miss(self, tmp_path: Path) -> None:
        client = MagicMock()
        container = client.containers.create.return_value
        container.wait.return_value = {"StatusCode": 0}
        executor = self.make_executor(tmp_path, client)
        runner = replace(
            make_runner(limits=ResourceLimits(network_enabled=True)),
            id=42,
            dependencies="requests==2.31.0",
        )
        result = await executor._ensure_dependencies(client, runner, FakeLogSink([]))
        assert result == tmp_path / "dep_cache" / "42" / "pkgs"
        marker = tmp_path / "dep_cache" / "42" / "pkgs.hash"
        assert marker.read_text() == hashlib.sha256(b"requests==2.31.0").hexdigest()
        client.containers.create.assert_called_once()
        create_kwargs = client.containers.create.call_args.kwargs
        assert create_kwargs["command"] == [
            "sh",
            "-c",
            (
                "rm -rf /deps/* /deps/.[!.]* 2>/dev/null; "
                'printf "%s" "$CRONDOK_DEPS_MANIFEST" > /deps/requirements.txt && '
                "pip install --no-cache-dir --target /deps -r /deps/requirements.txt"
            ),
        ]
        assert create_kwargs["environment"]["CRONDOK_DEPS_MANIFEST"] == "requests==2.31.0"
        assert create_kwargs["environment"]["HOME"] == "/deps"
        container.remove.assert_called_once_with(force=True)

    async def test_cache_hit_skips_install_even_with_network_disabled(self, tmp_path: Path) -> None:
        client = MagicMock()
        executor = self.make_executor(tmp_path, client)
        cache_root = tmp_path / "dep_cache" / "7"
        (cache_root / "pkgs").mkdir(parents=True)
        (cache_root / "pkgs.hash").write_text(hashlib.sha256(b"requests").hexdigest())
        runner = replace(
            make_runner(limits=ResourceLimits(network_enabled=False)),
            id=7,
            dependencies="requests",
        )
        result = await executor._ensure_dependencies(client, runner, FakeLogSink([]))
        assert result == cache_root / "pkgs"
        client.containers.create.assert_not_called()

    async def test_changed_dependencies_trigger_reinstall(self, tmp_path: Path) -> None:
        client = MagicMock()
        container = client.containers.create.return_value
        container.wait.return_value = {"StatusCode": 0}
        executor = self.make_executor(tmp_path, client)
        cache_root = tmp_path / "dep_cache" / "9"
        (cache_root / "pkgs").mkdir(parents=True)
        (cache_root / "pkgs.hash").write_text(hashlib.sha256(b"old-dep").hexdigest())
        runner = replace(
            make_runner(limits=ResourceLimits(network_enabled=True)),
            id=9,
            dependencies="new-dep",
        )
        await executor._ensure_dependencies(client, runner, FakeLogSink([]))
        client.containers.create.assert_called_once()
        assert (cache_root / "pkgs.hash").read_text() == hashlib.sha256(b"new-dep").hexdigest()

    async def test_node_manifest_is_built_into_package_json_env_var(self, tmp_path: Path) -> None:
        client = MagicMock()
        container = client.containers.create.return_value
        container.wait.return_value = {"StatusCode": 0}
        executor = self.make_executor(tmp_path, client)
        runner = replace(
            make_runner(language="node", limits=ResourceLimits(network_enabled=True)),
            id=13,
            dependencies="pg@8.11.0",
        )
        await executor._ensure_dependencies(client, runner, FakeLogSink([]))
        create_kwargs = client.containers.create.call_args.kwargs
        manifest = json.loads(create_kwargs["environment"]["CRONDOK_DEPS_MANIFEST"])
        assert manifest["dependencies"] == {"pg": "8.11.0"}
        assert create_kwargs["command"][2].endswith(
            "npm install --prefix /deps --no-audit --no-fund"
        )

    async def test_install_failure_raises_and_logs_output(self, tmp_path: Path) -> None:
        client = MagicMock()
        container = client.containers.create.return_value
        container.wait.return_value = {"StatusCode": 1}
        container.logs.return_value = b"ERROR: could not find package\n"
        executor = self.make_executor(tmp_path, client)
        runner = replace(
            make_runner(limits=ResourceLimits(network_enabled=True)),
            id=11,
            dependencies="totally-not-a-real-package",
        )
        chunks: list[str] = []
        with pytest.raises(RuntimeError, match="Falló la instalación"):
            await executor._ensure_dependencies(client, runner, FakeLogSink(chunks))
        assert "could not find package" in "".join(chunks)
        container.remove.assert_called_once_with(force=True)
