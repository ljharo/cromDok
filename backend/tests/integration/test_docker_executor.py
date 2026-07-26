"""Integration tests for DockerExecutor against a real Docker daemon.

Skipped automatically when no daemon is reachable (CI without Docker). A
session-scoped fixture preloads the per-language images once so individual
tests never pay the pull cost.
"""

import asyncio
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import docker
import pytest

from cron_dok.adapters.output.executor.docker_executor import DockerExecutor
from cron_dok.domain.entities.runner import Runner, RunnerLanguage
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.domain.value_objects.resource_limits import ResourceLimits
from tests.unit.fakes import FakeLogSink

pytestmark = pytest.mark.docker

IMAGES = ("python:3.12-slim", "node:20-slim", "bash:5")
MANAGED_FILTER = {"label": "crondok.managed=true"}


@pytest.fixture(scope="session")
def docker_client() -> docker.DockerClient:
    """Real Docker client; skips the whole module when no daemon answers."""
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker daemon not available")
    for image in IMAGES:
        try:
            client.images.get(image)
        except docker.errors.ImageNotFound:
            client.images.pull(image)
    return client


@pytest.fixture
def executor(docker_client: docker.DockerClient) -> DockerExecutor:
    return DockerExecutor(client=docker_client)


def make_runner(
    script: str,
    language: RunnerLanguage = "python",
    timeout: int = 60,
) -> Runner:
    return Runner(
        project_id=1,
        name="docker-itest",
        script_content=script,
        language=language,
        cron_expression=CronExpression("* * * * *"),
        timeout_seconds=timeout,
    )


def managed_containers(client: docker.DockerClient, *, all: bool = False) -> list[dict[str, Any]]:
    """Managed job containers, via the low-level API.

    ``client.containers.list()`` races with ``auto_remove`` (it inspects each
    container after listing, and the daemon may have already removed it), so
    tests use the raw ``api.containers`` which returns plain dicts.
    """
    return cast(list[dict[str, Any]], client.api.containers(all=all, filters=MANAGED_FILTER))


async def wait_for_containers(
    client: docker.DockerClient, *, expect: bool, all: bool = False
) -> None:
    """Poll until a managed container exists (expect=True) or none remains."""

    def _check() -> bool:
        return bool(managed_containers(client, all=all)) == expect

    for _ in range(100):
        if await asyncio.to_thread(_check):
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"timed out waiting for managed containers (expect={expect})")


async def test_printing_script_streams_logs_and_exits_0(
    executor: DockerExecutor, docker_client: docker.DockerClient
) -> None:
    chunks: list[str] = []
    runner = make_runner("print('hello crondok')")

    result = await executor.execute(runner, {}, FakeLogSink(chunks))

    assert result.exit_code == 0
    assert result.succeeded
    assert not result.timed_out
    assert result.duration_ms >= 0
    assert "hello crondok" in "".join(chunks)
    await wait_for_containers(docker_client, expect=False, all=True)


async def test_failing_script_reports_exit_code_1(executor: DockerExecutor) -> None:
    runner = make_runner("import sys; print('boom'); sys.exit(1)")

    result = await executor.execute(runner, {}, FakeLogSink([]))

    assert result.exit_code == 1
    assert not result.succeeded
    assert not result.timed_out


async def test_bash_and_node_images_run(
    executor: DockerExecutor, docker_client: docker.DockerClient
) -> None:
    # Images are preloaded by the session fixture; this also covers the
    # per-language command mapping.
    bash_chunks: list[str] = []
    node_chunks: list[str] = []

    bash_result = await executor.execute(
        make_runner("echo bash-ok", "bash"), {}, FakeLogSink(bash_chunks)
    )
    node_result = await executor.execute(
        make_runner("console.log('node-ok')", "node"), {}, FakeLogSink(node_chunks)
    )

    assert bash_result.exit_code == 0
    assert "bash-ok" in "".join(bash_chunks)
    assert node_result.exit_code == 0
    assert "node-ok" in "".join(node_chunks)


async def test_timeout_kills_container(
    executor: DockerExecutor, docker_client: docker.DockerClient
) -> None:
    runner = make_runner("import time; time.sleep(120)", timeout=2)

    result = await executor.execute(runner, {}, FakeLogSink([]))

    assert result.timed_out
    assert not result.succeeded
    assert result.exit_code != 0
    assert result.duration_ms < 30_000
    await wait_for_containers(docker_client, expect=False)


async def test_cancellation_kills_container(
    executor: DockerExecutor, docker_client: docker.DockerClient
) -> None:
    runner = make_runner("import time; time.sleep(120)", timeout=300)
    task = asyncio.create_task(executor.execute(runner, {}, FakeLogSink([])))
    await wait_for_containers(docker_client, expect=True)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    await wait_for_containers(docker_client, expect=False)


async def test_secret_env_value_is_masked_in_logs(executor: DockerExecutor) -> None:
    secret = "s3cr3t-value-123"
    chunks: list[str] = []
    runner = make_runner("import os; print('token=' + os.environ['API_TOKEN'])")

    result = await executor.execute(runner, {"API_TOKEN": secret}, FakeLogSink(chunks))

    log = "".join(chunks)
    assert result.exit_code == 0
    assert "token=********" in log
    assert secret not in log


def _clean_dependency_cache(
    executor: DockerExecutor, docker_client: docker.DockerClient, runner_id: int
) -> None:
    """Remove a runner's dependency cache dir.

    Installed packages are owned by the sandboxed ``nobody`` UID (65534), so
    the host test process can't ``shutil.rmtree`` them directly — root inside
    a throwaway container can, same as CronDok itself never needs to.
    """
    cache_root = Path(executor._settings.data_dir).resolve() / "dep_cache" / str(runner_id)
    if not cache_root.exists():
        return
    docker_client.containers.run(
        "python:3.12-slim",
        ["sh", "-c", "rm -rf /target/* /target/.[!.]* 2>/dev/null; exit 0"],
        volumes={str(cache_root): {"bind": "/target", "mode": "rw"}},
        remove=True,
    )
    shutil.rmtree(cache_root, ignore_errors=True)


async def test_python_dependency_is_installed_and_cached_across_runs(
    executor: DockerExecutor, docker_client: docker.DockerClient
) -> None:
    """First run installs a real pip package (network required); the second
    run reuses the cache even with network fully disabled — proving the
    manifest-hash cache actually skips the install step, not just retries it."""
    runner_id = 900_001
    _clean_dependency_cache(executor, docker_client, runner_id)
    try:
        runner = replace(
            make_runner("import six; print('six version:', six.__version__)", timeout=120),
            id=runner_id,
            dependencies="six==1.17.0",
            resource_limits=ResourceLimits(network_enabled=True),
        )
        chunks: list[str] = []
        result = await executor.execute(runner, {}, FakeLogSink(chunks))
        assert result.succeeded, "".join(chunks)
        assert "six version: 1.17.0" in "".join(chunks)

        cached_runner = replace(runner, resource_limits=ResourceLimits(network_enabled=False))
        chunks_cached: list[str] = []
        result_cached = await executor.execute(cached_runner, {}, FakeLogSink(chunks_cached))
        assert result_cached.succeeded, "".join(chunks_cached)
        assert "six version: 1.17.0" in "".join(chunks_cached)
    finally:
        _clean_dependency_cache(executor, docker_client, runner_id)


async def test_node_dependency_is_installed_and_usable(
    executor: DockerExecutor, docker_client: docker.DockerClient
) -> None:
    runner_id = 900_002
    _clean_dependency_cache(executor, docker_client, runner_id)
    try:
        runner = replace(
            make_runner(
                "const ms = require('ms'); console.log('one minute is', ms('1m'), 'ms');",
                language="node",
                timeout=120,
            ),
            id=runner_id,
            dependencies="ms@2.1.3",
            resource_limits=ResourceLimits(network_enabled=True),
        )
        chunks: list[str] = []
        result = await executor.execute(runner, {}, FakeLogSink(chunks))
        assert result.succeeded, "".join(chunks)
        assert "one minute is 60000 ms" in "".join(chunks)
    finally:
        _clean_dependency_cache(executor, docker_client, runner_id)


async def test_nonexistent_dependency_fails_the_execution(
    executor: DockerExecutor, docker_client: docker.DockerClient
) -> None:
    runner_id = 900_003
    _clean_dependency_cache(executor, docker_client, runner_id)
    try:
        runner = replace(
            make_runner("print('should not run')", timeout=60),
            id=runner_id,
            dependencies="this-package-definitely-does-not-exist-crondok-test",
            resource_limits=ResourceLimits(network_enabled=True),
        )
        with pytest.raises(RuntimeError, match="dependencias"):
            await executor.execute(runner, {}, FakeLogSink([]))
    finally:
        _clean_dependency_cache(executor, docker_client, runner_id)


async def test_dependencies_with_network_disabled_fails_clearly(
    executor: DockerExecutor, docker_client: docker.DockerClient
) -> None:
    runner_id = 900_004
    _clean_dependency_cache(executor, docker_client, runner_id)
    try:
        runner = replace(
            make_runner("print('should not run')", timeout=60),
            id=runner_id,
            dependencies="six",
            resource_limits=ResourceLimits(network_enabled=False),
        )
        with pytest.raises(RuntimeError, match="red desactivada"):
            await executor.execute(runner, {}, FakeLogSink([]))
    finally:
        _clean_dependency_cache(executor, docker_client, runner_id)
