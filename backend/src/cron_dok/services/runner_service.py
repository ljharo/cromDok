"""Runner application service: CRUD and enable/disable use cases."""

from collections.abc import Callable
from dataclasses import replace

from cron_dok.domain.entities.runner import OverlapPolicy, Runner, RunnerLanguage
from cron_dok.domain.services import cron_validator
from cron_dok.domain.value_objects.resource_limits import ResourceLimits
from cron_dok.ports.unit_of_work import AbstractUnitOfWork
from cron_dok.services.errors import (
    DuplicateNameError,
    ProjectNotFoundError,
    RunnerNotFoundError,
)
from cron_dok.services.scheduler_service import RunnerScheduler


class RunnerService:
    """CRUD and enable/disable use cases for runners.

    Every write runs inside ``async with uow:`` (spec 6.2). Cron expressions
    are validated by the domain (fail fast) and ``resource_limits`` defaults
    to the spec values (256 MB, 1 CPU, 100 pids, no network).

    When a ``scheduler`` hook is wired, every successful write notifies it
    **after** the database commit (DB first, scheduler second — spec 7), so
    the schedule always mirrors the persisted state.
    """

    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
        scheduler: RunnerScheduler | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            uow_factory: zero-arg callable returning a fresh Unit of Work per
                operation.
            scheduler: optional hook notified after runner writes so cron
                jobs stay in sync (see :class:`SchedulerService`).
        """
        self._uow_factory = uow_factory
        self._scheduler = scheduler

    async def create(
        self,
        *,
        project_id: int,
        name: str,
        script_content: str,
        language: RunnerLanguage,
        cron_expression: str,
        resource_limits: ResourceLimits | None = None,
        timeout_seconds: int = 300,
        on_overlap: OverlapPolicy = "skip",
        dependencies: str | None = None,
    ) -> Runner:
        """Create a runner in an existing project.

        Raises:
            ProjectNotFoundError: if ``project_id`` does not exist.
            DuplicateNameError: if the project already has a runner named
                ``name``.
            InvalidCronExpressionError: if ``cron_expression`` cannot be
                parsed (domain validation).
            ValueError: if ``name`` is empty or ``timeout_seconds`` is not
                positive (domain validation).
        """
        cron = cron_validator.validate(cron_expression)
        async with self._uow_factory() as uow:
            if await uow.projects.get_by_id(project_id) is None:
                raise ProjectNotFoundError(project_id)
            await self._ensure_name_available(uow, project_id, name)
            runner = Runner(
                project_id=project_id,
                name=name,
                script_content=script_content,
                language=language,
                cron_expression=cron,
                resource_limits=resource_limits or ResourceLimits(),
                timeout_seconds=timeout_seconds,
                on_overlap=on_overlap,
                dependencies=dependencies,
            )
            saved = await uow.runners.save(runner)
        self._notify_create(saved)
        return saved

    async def get(self, runner_id: int) -> Runner:
        """Return a runner by id.

        Raises:
            RunnerNotFoundError: if the runner does not exist.
        """
        async with self._uow_factory() as uow:
            return await self._get_or_raise(uow, runner_id)

    async def list_by_project(self, project_id: int) -> list[Runner]:
        """Return all runners of a project, oldest first.

        Raises:
            ProjectNotFoundError: if the project does not exist.
        """
        async with self._uow_factory() as uow:
            if await uow.projects.get_by_id(project_id) is None:
                raise ProjectNotFoundError(project_id)
            return await uow.runners.list_by_project(project_id)

    async def update(
        self,
        runner_id: int,
        *,
        name: str | None = None,
        script_content: str | None = None,
        language: RunnerLanguage | None = None,
        cron_expression: str | None = None,
        resource_limits: ResourceLimits | None = None,
        timeout_seconds: int | None = None,
        on_overlap: OverlapPolicy | None = None,
        dependencies: str | None = None,
    ) -> Runner:
        """Update a runner; ``None`` fields are left unchanged.

        Raises:
            RunnerNotFoundError: if the runner does not exist.
            DuplicateNameError: if ``name`` is taken by another runner of the
                same project.
            InvalidCronExpressionError: if ``cron_expression`` cannot be
                parsed (domain validation).
        """
        cron = cron_validator.validate(cron_expression) if cron_expression is not None else None
        async with self._uow_factory() as uow:
            runner = await self._get_or_raise(uow, runner_id)
            if name is not None and name != runner.name:
                await self._ensure_name_available(uow, runner.project_id, name)
            updated = replace(
                runner,
                name=runner.name if name is None else name,
                script_content=(
                    runner.script_content if script_content is None else script_content
                ),
                language=runner.language if language is None else language,
                cron_expression=runner.cron_expression if cron is None else cron,
                resource_limits=(
                    runner.resource_limits if resource_limits is None else resource_limits
                ),
                timeout_seconds=(
                    runner.timeout_seconds if timeout_seconds is None else timeout_seconds
                ),
                on_overlap=runner.on_overlap if on_overlap is None else on_overlap,
                dependencies=runner.dependencies if dependencies is None else dependencies,
            )
            saved = await uow.runners.save(updated)
        self._notify_update(saved)
        return saved

    async def delete(self, runner_id: int) -> None:
        """Delete a runner; its executions and runner-scoped env vars cascade.

        Raises:
            RunnerNotFoundError: if the runner does not exist.
        """
        async with self._uow_factory() as uow:
            await self._get_or_raise(uow, runner_id)
            await uow.runners.delete(runner_id)
        self._notify_unregister(runner_id)

    async def enable(self, runner_id: int) -> Runner:
        """Enable a runner (the scheduler will fire it).

        Raises:
            RunnerNotFoundError: if the runner does not exist.
        """
        return await self._set_enabled(runner_id, enabled=True)

    async def disable(self, runner_id: int) -> Runner:
        """Disable a runner (the scheduler will skip it).

        Raises:
            RunnerNotFoundError: if the runner does not exist.
        """
        return await self._set_enabled(runner_id, enabled=False)

    async def _set_enabled(self, runner_id: int, *, enabled: bool) -> Runner:
        async with self._uow_factory() as uow:
            runner = await self._get_or_raise(uow, runner_id)
            saved = await uow.runners.save(replace(runner, is_enabled=enabled))
        self._notify_update(saved)
        return saved

    def _notify_create(self, runner: Runner) -> None:
        if self._scheduler is not None:
            self._scheduler.register(runner)

    def _notify_update(self, runner: Runner) -> None:
        if self._scheduler is not None:
            self._scheduler.update(runner)

    def _notify_unregister(self, runner_id: int) -> None:
        if self._scheduler is not None:
            self._scheduler.unregister(runner_id)

    @staticmethod
    async def _get_or_raise(uow: AbstractUnitOfWork, runner_id: int) -> Runner:
        runner = await uow.runners.get_by_id(runner_id)
        if runner is None:
            raise RunnerNotFoundError(runner_id)
        return runner

    @staticmethod
    async def _ensure_name_available(uow: AbstractUnitOfWork, project_id: int, name: str) -> None:
        existing = await uow.runners.list_by_project(project_id)
        if any(r.name == name for r in existing):
            raise DuplicateNameError("runner", name)
