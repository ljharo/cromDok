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
import hashlib
import json
import logging
import re
import shutil
import threading
import time
import uuid
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

_DEPS_MOUNT = "/deps"
_DEP_CACHE_DIRNAME = "dep_cache"
"""Lives under ``data_dir``, one subdirectory per runner id (spec: runner
dependencies) — same host-path-translation story as job workspaces."""

# Bash has no package manager in the sense requirements.txt/package.json
# imply; dependencies are only meaningful for python/node.
#
# Each script: wipe any previous install (files may be owned by `nobody`
# from a prior run — only a container running as that same user can clean
# them up; the host process never has permission to), write the manifest
# fresh, then install. $CRONDOK_DEPS_MANIFEST is an env var, never
# shell-interpolated, so its content can't break out of the script.
_DEPENDENCY_INSTALL_SCRIPTS: dict[RunnerLanguage, str] = {
    "python": (
        "rm -rf /deps/* /deps/.[!.]* 2>/dev/null; "
        'printf "%s" "$CRONDOK_DEPS_MANIFEST" > /deps/requirements.txt && '
        "pip install --no-cache-dir --target /deps -r /deps/requirements.txt"
    ),
    "node": (
        "rm -rf /deps/* /deps/.[!.]* 2>/dev/null; "
        'printf "%s" "$CRONDOK_DEPS_MANIFEST" > /deps/package.json && '
        "npm install --prefix /deps --no-audit --no-fund"
    ),
}


def parse_node_dependency(line: str) -> tuple[str, str]:
    """Parse one line of the dependencies textarea for a node runner.

    Accepts ``name``, ``name@version`` and scoped packages
    (``@scope/name@version``); a bare name defaults to ``"latest"``.
    """
    line = line.strip()
    if line.startswith("@"):
        at_index = line.find("@", 1)
        if at_index == -1:
            return line, "latest"
        return line[:at_index], line[at_index + 1 :]
    name, _, version = line.partition("@")
    return name, version or "latest"


def build_node_package_manifest(manifest: str) -> str:
    """Turn the dependencies textarea (one ``name``/``name@version`` per
    line) into the ``package.json`` content ``npm install`` expects."""
    dependencies = dict(
        parse_node_dependency(line) for line in manifest.splitlines() if line.strip()
    )
    return json.dumps(
        {"name": "crondok-runner-deps", "version": "0.0.0", "dependencies": dependencies}
    )


class SecretMasker:
    """Masks secret values in log chunks before they hit the LogSink (spec 9.1).

    Only values of at least ``_MIN_SECRET_LENGTH`` characters are masked.
    The masker is STREAMING: ``mask`` withholds a trailing region that could
    still grow into a secret (a suffix that is a proper prefix of some
    value, plus any complete occurrence overlapping it), so a secret split
    across two stream chunks is still caught. The withheld region comes back
    on the next ``mask`` call or on ``flush`` at end of stream. For one-shot
    texts use ``mask_all``.

    Note: with overlapping secrets (one value starting where another ends,
    e.g. ``abc``/``bcd``) the exact masked output may depend on chunking —
    a documented, acceptable edge; non-overlapping secrets mask identically
    for any chunking.
    """

    def __init__(self, secrets: Iterable[str]) -> None:
        """Build a masker for the given raw secret values.

        Args:
            secrets: plaintext values to mask; values shorter than
                ``_MIN_SECRET_LENGTH`` are ignored. Longer values are matched
                first so overlapping secrets mask maximally.
        """
        values = sorted({s for s in secrets if len(s) >= _MIN_SECRET_LENGTH}, key=len, reverse=True)
        self._values = values
        self._pattern = re.compile("|".join(re.escape(v) for v in values)) if values else None
        self._max_len = max((len(v) for v in values), default=0)
        self._carry = ""

    @classmethod
    def from_env(cls, env_vars: dict[str, str]) -> "SecretMasker":
        """Build a masker covering every value of an env var mapping."""
        return cls(env_vars.values())

    def _proper_prefix_suffix_len(self, buffer: str) -> int:
        """Length of the longest buffer suffix that is a proper prefix of a secret."""
        limit = min(self._max_len - 1, len(buffer))
        for length in range(limit, 0, -1):
            suffix = buffer[-length:]
            if any(len(value) > length and value.startswith(suffix) for value in self._values):
                return length
        return 0

    def mask(self, text: str) -> str:
        """Mask secrets in ``text``, withholding a tail that may be a partial match.

        The withheld region (a proper-prefix suffix plus any complete
        occurrence overlapping it, so no occurrence is ever split across
        emissions) is prepended to the next ``mask`` call; call ``flush`` at
        end of stream to emit it.
        """
        if self._pattern is None:
            return text
        buffer = self._carry + text
        region_start = len(buffer) - self._proper_prefix_suffix_len(buffer)
        # Regex matches never overlap each other, so at most one occurrence
        # can cross the region boundary; pull it wholly into the carry.
        for match in self._pattern.finditer(buffer):
            if match.start() < region_start < match.end():
                region_start = match.start()
        emit, self._carry = buffer[:region_start], buffer[region_start:]
        return self._pattern.sub(MASK, emit)

    def flush(self) -> str:
        """Emit and mask whatever tail is still buffered (end of stream)."""
        if self._pattern is None:
            return ""
        tail, self._carry = self._carry, ""
        return self._pattern.sub(MASK, tail)

    def mask_all(self, text: str) -> str:
        """Mask a complete (non-streamed) text in one shot."""
        return self.mask(text) + self.flush()


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
        self._settings = settings
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
        script_dir = self._new_workspace_dir()
        await asyncio.to_thread(script_dir.mkdir, parents=True)
        try:
            script_path = await asyncio.to_thread(self._write_script, runner, script_dir)
            await self._ensure_image(client, self._images[runner.language])
            deps_dir = await self._ensure_dependencies(client, runner, log_sink)
            kwargs = self._build_container_kwargs(runner, env_vars, script_path, deps_dir)
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
        finally:
            await asyncio.to_thread(shutil.rmtree, script_dir, ignore_errors=True)
        return ExecutionResult(
            exit_code=exit_code,
            duration_ms=int((time.monotonic() - started) * 1000),
            timed_out=timed_out,
        )

    def _new_workspace_dir(self) -> Path:
        """Allocate a fresh workspace directory under ``data_dir``.

        Not a system tempdir: when CronDok itself runs in a container with
        the host's Docker socket mounted (Docker-out-of-Docker, spec 9.3),
        the daemon resolves bind-mount sources against the HOST filesystem,
        not this process's. Living under ``data_dir`` keeps the workspace
        inside the volume that's already bind-mounted from a known host
        path, so :meth:`_host_bind_source` can translate it.
        """
        return Path(self._settings.data_dir).resolve() / "workspaces" / uuid.uuid4().hex

    def _host_bind_source(self, script_dir: Path) -> str:
        """Return the bind-mount source path as the Docker daemon must see it.

        When ``host_data_dir`` is configured, ``script_dir`` (inside this
        process) is translated to the equivalent path on the host that backs
        ``data_dir`` (e.g. the left side of a ``./data:/app/data`` compose
        volume). Without it, this process runs directly on the host (dev),
        so its own path is already what the daemon expects.
        """
        if self._settings.host_data_dir is None:
            return str(script_dir)
        data_dir = Path(self._settings.data_dir).resolve()
        relative = script_dir.relative_to(data_dir)
        return str(Path(self._settings.host_data_dir) / relative)

    def _dependency_paths(self, runner_id: int) -> tuple[Path, Path]:
        """Return ``(cache_dir, hash_marker)`` for a runner's dependency cache.

        ``cache_dir`` is what gets mounted at ``/deps``; the hash marker is a
        sibling file (not inside it) recording the manifest last installed
        there, so a rerun with the same dependencies skips installing again.
        """
        root = Path(self._settings.data_dir).resolve() / _DEP_CACHE_DIRNAME / str(runner_id)
        return root / "pkgs", root / "pkgs.hash"

    async def _ensure_dependencies(
        self, client: docker.DockerClient, runner: Runner, log_sink: LogSink
    ) -> Path | None:
        """Install ``runner.dependencies`` into a cached per-runner directory.

        Reuses the cache when the manifest is unchanged since the last
        install (hash comparison) — the execution container itself stays
        ephemeral either way; only the *dependencies* persist across runs,
        not the container or its filesystem (spec 9.2's per-execution
        isolation still holds for the actual script).

        Returns:
            The cache directory to mount at ``/deps`` in the execution
            container, or ``None`` when the runner declares no dependencies
            (or its language doesn't support them, i.e. bash).

        Raises:
            RuntimeError: dependencies are declared but the runner has no
                network (installing needs it), or the install itself fails
                or times out.
        """
        manifest = (runner.dependencies or "").strip()
        if not manifest or runner.language not in _DEPENDENCY_INSTALL_SCRIPTS:
            return None

        assert runner.id is not None  # enqueued runners are persisted
        cache_dir, marker_path = self._dependency_paths(runner.id)
        manifest_hash = hashlib.sha256(manifest.encode("utf-8")).hexdigest()

        def _cached_hash() -> str | None:
            return marker_path.read_text().strip() if marker_path.exists() else None

        if await asyncio.to_thread(_cached_hash) == manifest_hash:
            return cache_dir

        if not runner.resource_limits.network_enabled:
            message = (
                "El runner declara dependencias pero tiene la red desactivada; "
                "actívala para poder instalarlas.\n"
            )
            await log_sink.write(message)
            raise RuntimeError(message.strip())

        await log_sink.write(f"Instalando dependencias ({runner.language})...\n")
        await asyncio.to_thread(cache_dir.mkdir, parents=True, exist_ok=True)
        # World-writable so the container's ``nobody`` can install packages,
        # but with the sticky bit (like /tmp) so other host users cannot
        # delete or replace the cached dependencies afterwards.
        await asyncio.to_thread(cache_dir.chmod, 0o1777)

        manifest_content = (
            build_node_package_manifest(manifest) if runner.language == "node" else manifest
        )
        install_kwargs = {
            "image": self._images[runner.language],
            "command": ["sh", "-c", _DEPENDENCY_INSTALL_SCRIPTS[runner.language]],
            "detach": True,
            "environment": {
                # nobody's $HOME (/nonexistent in Debian-based images) isn't
                # writable, but npm/pip both want a writable cache dir under
                # it; point HOME at the (writable) deps mount itself.
                "HOME": _DEPS_MOUNT,
                "CRONDOK_DEPS_MANIFEST": manifest_content,
            },
            "mem_limit": f"{runner.resource_limits.memory_mb}m",
            "nano_cpus": int(runner.resource_limits.cpu_quota * 1_000_000_000),
            "pids_limit": runner.resource_limits.pids_limit,
            "network_disabled": False,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges"],
            "user": _NOBODY,
            "working_dir": _DEPS_MOUNT,
            "volumes": {self._host_bind_source(cache_dir): {"bind": _DEPS_MOUNT, "mode": "rw"}},
            "labels": {"crondok.managed": "true"},
        }
        container = await asyncio.to_thread(client.containers.create, **install_kwargs)
        try:
            await asyncio.to_thread(container.start)
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(container.wait), timeout=runner.timeout_seconds
                )
            except TimeoutError:
                await self._kill(container)
                message = "Instalación de dependencias: tiempo de espera agotado.\n"
                await log_sink.write(message)
                raise RuntimeError(message.strip()) from None
            exit_code = int(result.get("StatusCode", _NO_EXIT_CODE))
            if exit_code != 0:
                output = await asyncio.to_thread(container.logs, stdout=True, stderr=True)
                await log_sink.write(output.decode("utf-8", errors="replace"))
                raise RuntimeError(f"Falló la instalación de dependencias (exit code {exit_code})")
        finally:
            await asyncio.to_thread(container.remove, force=True)

        await asyncio.to_thread(marker_path.write_text, manifest_hash)
        await log_sink.write("Dependencias instaladas correctamente.\n")
        return cache_dir

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
        user can traverse it and read the script; the sticky bit keeps other
        host users from deleting or replacing its files.
        """
        script_dir.chmod(0o1777)
        filename, _ = _SCRIPT_COMMANDS[runner.language]
        script_path = script_dir / filename
        script_path.write_text(runner.script_content, encoding="utf-8")
        script_path.chmod(0o644)
        return script_path

    def _build_container_kwargs(
        self,
        runner: Runner,
        env_vars: dict[str, str],
        script_path: Path,
        deps_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Build the ``containers.create`` kwargs applying the spec 9.2 sandbox."""
        limits = runner.resource_limits
        _, command = _SCRIPT_COMMANDS[runner.language]
        volumes = {
            self._host_bind_source(script_path.parent): {"bind": _WORKSPACE, "mode": "rw"},
        }
        environment = dict(env_vars)
        if deps_dir is not None:
            # Read-only: the script consumes the cache, it never writes to it.
            volumes[self._host_bind_source(deps_dir)] = {"bind": _DEPS_MOUNT, "mode": "ro"}
            if runner.language == "python":
                environment["PYTHONPATH"] = _DEPS_MOUNT
            elif runner.language == "node":
                environment["NODE_PATH"] = f"{_DEPS_MOUNT}/node_modules"
        return {
            "image": self._images[runner.language],
            "command": command,
            "auto_remove": True,
            "detach": True,
            "environment": environment,
            "mem_limit": f"{limits.memory_mb}m",
            "nano_cpus": int(limits.cpu_quota * 1_000_000_000),
            "pids_limit": limits.pids_limit,
            "network_disabled": not limits.network_enabled,
            # Defense in depth on top of the nobody user (spec 9.2): no Linux
            # capabilities and no way to gain new privileges via setuid/file
            # capabilities inside the job container.
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges"],
            "user": _NOBODY,
            "working_dir": _WORKSPACE,
            "volumes": volumes,
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

        async def _flush_mask_tail() -> None:
            # Tail withheld by the masker (possible partial secret): emit it.
            tail = masker.flush()
            if tail:
                await log_sink.write(tail)

        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    await _flush_mask_tail()
                    return True
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=remaining)
                except TimeoutError:
                    await _flush_mask_tail()
                    return True
                if item is _STREAM_END:
                    await _flush_mask_tail()
                    return False
                masked = masker.mask(cast(str, item))
                if masked:
                    await log_sink.write(masked)
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
