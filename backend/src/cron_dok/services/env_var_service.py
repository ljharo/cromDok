"""EnvVar application service: secrets CRUD and resolution for runners.

Values are encrypted *before* persisting and decrypted only in memory
(spec 9.1). Listing never exposes values: the UI renders ``••••••••`` and
rotation is write-only (re-encrypt, never read).
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol

from cron_dok.domain.entities.env_var import EnvVar
from cron_dok.ports.unit_of_work import AbstractUnitOfWork
from cron_dok.services.errors import (
    EnvVarNotFoundError,
    ProjectNotFoundError,
    RunnerNotFoundError,
)


class Encryptor(Protocol):
    """Symmetric encryption contract used by the service.

    Implemented in production by the Fernet adapter
    (``cron_dok.adapters.output.security.encryption_service.EncryptionService``);
    services depend on this protocol, not on the adapter (spec 4.3).
    """

    def encrypt(self, plaintext: str) -> str:
        """Encrypt ``plaintext`` and return the token as text."""
        ...

    def decrypt(self, token: str) -> str:
        """Decrypt ``token`` back to its plaintext."""
        ...


@dataclass(frozen=True, kw_only=True)
class EnvVarSummary:
    """Read model of an env var without its value.

    The UI only shows the key and renders the value as ``••••••••``
    (spec 9.1), so the ciphertext never leaves the service layer.
    """

    id: int
    project_id: int
    key: str
    runner_id: int | None


class EnvVarService:
    """Use cases for environment variables (secrets).

    Every write runs inside ``async with uow:`` (spec 6.2). Key validation
    (format + system blacklist) is delegated to the domain entity
    :class:`~cron_dok.domain.entities.env_var.EnvVar`.
    """

    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
        encryptor: Encryptor,
    ) -> None:
        """Initialize the service.

        Args:
            uow_factory: zero-arg callable returning a fresh Unit of Work per
                operation.
            encryptor: symmetric encryption of values at rest.
        """
        self._uow_factory = uow_factory
        self._encryptor = encryptor

    async def create(
        self,
        *,
        project_id: int,
        key: str,
        value: str,
        runner_id: int | None = None,
    ) -> EnvVar:
        """Create an env var scoped to a project or to a single runner.

        The value is encrypted before persisting; plaintext never reaches
        the repository.

        Raises:
            ProjectNotFoundError: if ``project_id`` does not exist.
            RunnerNotFoundError: if ``runner_id`` does not exist or belongs
                to another project.
            InvalidEnvVarKeyError: if ``key`` has an invalid format or is
                blacklisted (domain validation).
        """
        async with self._uow_factory() as uow:
            if await uow.projects.get_by_id(project_id) is None:
                raise ProjectNotFoundError(project_id)
            if runner_id is not None:
                runner = await uow.runners.get_by_id(runner_id)
                if runner is None or runner.project_id != project_id:
                    raise RunnerNotFoundError(runner_id)
            env_var = EnvVar(
                project_id=project_id,
                key=key,
                encrypted_value=self._encryptor.encrypt(value),
                runner_id=runner_id,
            )
            return await uow.env_vars.save(env_var)

    async def list(
        self,
        project_id: int,
        *,
        runner_id: int | None = None,
    ) -> list[EnvVarSummary]:
        """Return the env vars of a project, without values (spec 9.1).

        With ``runner_id`` only that runner's vars are returned; without it,
        both project-scoped and runner-scoped vars of the project.

        Raises:
            ProjectNotFoundError: if ``project_id`` does not exist.
        """
        async with self._uow_factory() as uow:
            if await uow.projects.get_by_id(project_id) is None:
                raise ProjectNotFoundError(project_id)
            env_vars = await uow.env_vars.list_by_project(project_id)
        return [
            self._to_summary(v) for v in env_vars if runner_id is None or v.runner_id == runner_id
        ]

    async def delete(self, env_var_id: int) -> None:
        """Delete an env var.

        Raises:
            EnvVarNotFoundError: if the env var does not exist.
        """
        async with self._uow_factory() as uow:
            await self._get_or_raise(uow, env_var_id)
            await uow.env_vars.delete(env_var_id)

    async def resolve_for_runner(self, runner_id: int) -> dict[str, str]:
        """Decrypt in memory the effective env vars for a runner execution.

        Project-scoped vars apply to every runner of the project;
        runner-scoped vars override project vars with the same key
        (spec 9.1). This is the method the executor uses to inject env
        vars into the container.

        Raises:
            RunnerNotFoundError: if ``runner_id`` does not exist.
        """
        async with self._uow_factory() as uow:
            runner = await uow.runners.get_by_id(runner_id)
            if runner is None:
                raise RunnerNotFoundError(runner_id)
            env_vars = await uow.env_vars.list_by_project(runner.project_id)
        resolved: dict[str, str] = {}
        for var in env_vars:
            if var.runner_id is None:
                resolved[var.key] = self._encryptor.decrypt(var.encrypted_value)
        for var in env_vars:
            if var.runner_id == runner_id:
                resolved[var.key] = self._encryptor.decrypt(var.encrypted_value)
        return resolved

    async def rotate(self, env_var_id: int, new_value: str) -> EnvVar:
        """Re-encrypt an env var with a new value (write-only rotation).

        The previous value is never read or returned (spec 9.1: the UI
        allows rotating, never reading).

        Raises:
            EnvVarNotFoundError: if the env var does not exist.
        """
        async with self._uow_factory() as uow:
            env_var = await self._get_or_raise(uow, env_var_id)
            return await uow.env_vars.save(
                replace(env_var, encrypted_value=self._encryptor.encrypt(new_value))
            )

    @staticmethod
    async def _get_or_raise(uow: AbstractUnitOfWork, env_var_id: int) -> EnvVar:
        env_var = await uow.env_vars.get_by_id(env_var_id)
        if env_var is None:
            raise EnvVarNotFoundError(env_var_id)
        return env_var

    @staticmethod
    def _to_summary(env_var: EnvVar) -> EnvVarSummary:
        assert env_var.id is not None  # persisted entities always have an id
        return EnvVarSummary(
            id=env_var.id,
            project_id=env_var.project_id,
            key=env_var.key,
            runner_id=env_var.runner_id,
        )
