"""Docker-backed JobExecutor: one ephemeral container per execution (spec 9.2).

Each execution writes the runner's script to a temporary directory, mounts it
at ``/workspace`` and runs it in an ephemeral (``auto_remove``) container with
the resource limits of the runner: memory, CPU and PID caps, no network unless
explicitly enabled, and the unprivileged ``nobody`` user (UID 65534).

docker-py is synchronous, so every daemon access goes through
``asyncio.to_thread`` and log streaming runs in a pump thread that feeds an
``asyncio.Queue`` — the event loop never blocks (spec 8.4).

Cancellation contract (see ``services/execution_queue.py``): on
``asyncio.CancelledError`` the container is killed and the error re-raised, so
``kill_previous`` and shutdown never leave containers behind.
"""

import asyncio
import logging
import re
import tempfile
import threading
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import docker
from docker.models.containers import Container

from cron_dok.config import Settings, get_settings
from cron_dok.domain.entities.runner import Runner, RunnerLanguage
from cron_dok.domain.value_objects.execution_result import ExecutionResult
from cron_dok.ports.executors.job_executor import JobExecutor
from cron_dok.ports.logs.log_store import LogSink

logger = logging.getLogger(__name__)

MASK = "********"
"""Replacement text for secret values found in log output (spec 9.1)."""

_MIN_SECRET_LENGTH = 4
"""Secrets shorter than this are not masked: masking tiny values (e.g. ``1``)
would destroy the log content."""

_WORKSPACE = "/workspace"
_NOBODY = "65534:65534"
_NO_EXIT_CODE = -1
"""exit_code used when the container never reported one (timeout/kill)."""

_STREAM_END: Any = object()
"""Sentinel pushed by the pump thread when the log stream ends."""

_SCRIPT_COMMANDS: dict[RunnerLanguage, tuple[str, list[str]]] = {
    "python": ("script.py", ["python", "/workspace/script.py"]),
    "node": ("script.js", ["node", "/workspace/script.js"]),
    "bash": ("script.sh", ["bash", "/workspace/script.sh"]),
}


class SecretMasker:
    """Masks secret values in log chunks before they hit the LogSink (spec 9.1).

    Only values of at least ``_MIN_SECRET_LENGTH`` characters are masked.
    Masking is per chunk: a secret split across two stream chunks may leak
    partially — an accepted trade-off of streaming (chunks are line-oriented
    in practice, since Docker's log stream flushes per write).
    """

    def __init__(self, secrets: Iterable[str]) -> None:
        """Build a masker for the given raw secret values.

        Args:
            secrets: plaintext values to mask; values shorter than
                ``_MIN_SECRET_LENGTH`` are ignored. Longer values are matched
                first so overlapping secrets mask maximally.
        """
        values = sorted({s for s in secrets if len(s) >= _MIN_SECRET_LENGTH}, key=len, reverse=True)
        self._pattern = re.compile("|".join(re.escape(v) for v in values)) if values else None

    @classmethod
    def from_env(cls, env_vars: dict[str, str]) -> "SecretMasker":
        """Build a masker covering every value of an env var mapping."""
        return cls(env_vars.values())

    def mask(self, text: str) -> str:
        """Return ``text`` with every known secret replaced by ``MASK``."""
        if self._pattern is None:
            return text
        return self._pattern.sub(MASK, text)


class DockerExecutor(JobExecutor):
    """JobExecutor running scripts in ephemeral local Docker containers.

    Args:
        settings: application settings; per-language images come from
            ``docker_image_{python,node,bash}``. Defaults to ``get_settings()``.
        client: optional prebuilt ``docker.DockerClient`` (used by tests); when
            omitted, one is created lazily from the environment.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        client: docker.DockerClient | None = None,
    ) -> None:
        settings = settings or get_settings()
        self._images: dict[RunnerLanguage, str] = {
            "python": settings.docker_image_python,
            "node": settings.docker_image_node,
            "bash": settings.docker_image_bash,
        }
        self._client = client

    async def execute(
        self, runner: Runner, env_vars: dict[str, str], log_sink: LogSink
    ) -> ExecutionResult:
        """Run ``runner``'s script in a sandboxed container.

        Streams stdout+stderr to ``log_sink`` (masking env var values), kills
        the container when ``runner.timeout_seconds`` elapses and, on
        ``asyncio.CancelledError``, kills the container and re-raises.

        Returns:
            The execution outcome; ``timed_out=True`` with ``exit_code=-1``
            when the timeout fired.
        """
        client = await asyncio.to_thread(self._get_client)
        masker = SecretMasker.from_env(env_vars)
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="crondok-") as script_dir:
            script_path = await asyncio.to_thread(self._write_script, runner, Path(script_dir))
            await self._ensure_image(client, self._images[runner.language])
            kwargs = self._build_container_kwargs(runner, env_vars, script_path)
            container = await asyncio.to_thread(client.containers.create, **kwargs)
            try:
                await asyncio.to_thread(container.start)
                timed_out = await self._stream_output(
                    container, runner.timeout_seconds, masker, log_sink
                )
                if timed_out:
                    await self._kill(container)
                    exit_code = _NO_EXIT_CODE
                else:
                    exit_code = await self._wait_exit_code(container)
            except BaseException:
                # Covers CancelledError (kill_previous/shutdown contract) and
                # unexpected daemon errors: never leave the container running.
                await self._kill(container)
                raise
        return ExecutionResult(
            exit_code=exit_code,
            duration_ms=int((time.monotonic() - started) * 1000),
            timed_out=timed_out,
        )

    def _get_client(self) -> docker.DockerClient:
        """Return the Docker client, creating it from the environment lazily."""
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    async def _ensure_image(self, client: docker.DockerClient, image: str) -> None:
        """Pull ``image`` unless it is already present locally."""

        def _ensure() -> None:
            try:
                client.images.get(image)
            except docker.errors.ImageNotFound:
                logger.info("Pulling Docker image %s", image)
                client.images.pull(image)

        await asyncio.to_thread(_ensure)

    @staticmethod
    def _write_script(runner: Runner, script_dir: Path) -> Path:
        """Write the runner's script into ``script_dir``; return its path.

        The directory is made world-accessible so the container's ``nobody``
        user can traverse it and read the script.
        """
        script_dir.chmod(0o777)
        filename, _ = _SCRIPT_COMMANDS[runner.language]
        script_path = script_dir / filename
        script_path.write_text(runner.script_content, encoding="utf-8")
        script_path.chmod(0o644)
        return script_path

    def _build_container_kwargs(
        self, runner: Runner, env_vars: dict[str, str], script_path: Path
    ) -> dict[str, Any]:
        """Build the ``containers.create`` kwargs applying the spec 9.2 sandbox."""
        limits = runner.resource_limits
        _, command = _SCRIPT_COMMANDS[runner.language]
        return {
            "image": self._images[runner.language],
            "command": command,
            "auto_remove": True,
            "detach": True,
            "environment": dict(env_vars),
            "mem_limit": f"{limits.memory_mb}m",
            "nano_cpus": int(limits.cpu_quota * 1_000_000_000),
            "pids_limit": limits.pids_limit,
            "network_disabled": not limits.network_enabled,
            "user": _NOBODY,
            "working_dir": _WORKSPACE,
            "volumes": {str(script_path.parent): {"bind": _WORKSPACE, "mode": "rw"}},
            # Marks every job container so cleanup and tests can find them.
            "labels": {"crondok.managed": "true"},
        }

    async def _stream_output(
        self,
        container: Container,
        timeout_seconds: int,
        masker: SecretMasker,
        log_sink: LogSink,
    ) -> bool:
        """Stream container output to ``log_sink`` until EOF or timeout.

        A daemon thread iterates the blocking docker-py log stream and feeds
        decoded chunks into an ``asyncio.Queue`` consumed here, so the event
        loop stays responsive and cancellation works.

        Returns:
            ``True`` when ``timeout_seconds`` elapsed (caller must kill the
            container), ``False`` when the stream ended normally.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Any] = asyncio.Queue()

        def _pump() -> None:
            try:
                stream = container.logs(stream=True, follow=True, stdout=True, stderr=True)
                for chunk in stream:
                    text = chunk.decode("utf-8", errors="replace")
                    loop.call_soon_threadsafe(queue.put_nowait, text)
            except Exception:
                # wait() still decides the outcome; log for diagnostics.
                logger.exception("Log stream of container %s failed", container.id)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, _STREAM_END)

        pump = threading.Thread(target=_pump, name=f"crondok-logs-{container.id}", daemon=True)
        pump.start()
        deadline = loop.time() + timeout_seconds
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return True
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=remaining)
                except TimeoutError:
                    return True
                if item is _STREAM_END:
                    return False
                await log_sink.write(masker.mask(cast(str, item)))
        finally:
            # Non-blocking: on timeout/cancellation the thread is still blocked
            # on the stream and exits once execute() kills the container.
            pump.join(timeout=0)

    async def _wait_exit_code(self, container: Container) -> int:
        """Wait for the container to exit and return its exit code.

        With ``auto_remove`` the daemon may drop the container before
        ``wait()`` observes it; the stream already ended by then, so the code
        is reported as unknown (-1).
        """
        try:
            result = await asyncio.to_thread(container.wait)
        except docker.errors.NotFound:
            return _NO_EXIT_CODE
        return int(result.get("StatusCode", _NO_EXIT_CODE))

    async def _kill(self, container: Container) -> None:
        """Best-effort kill; an already-gone container is not an error."""
        try:
            await asyncio.to_thread(container.kill)
        except docker.errors.NotFound:
            pass
        except docker.errors.APIError as exc:  # e.g. "container is not running"
            logger.debug("Could not kill container %s: %s", container.id, exc)
