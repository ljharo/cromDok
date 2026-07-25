"""SQLite implementation of RunnerRepository (SQLAlchemy 2.0 async)."""

from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cron_dok.adapters.output.persistence.models.runner import RunnerModel
from cron_dok.domain.entities.runner import OverlapPolicy, Runner, RunnerLanguage
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.domain.value_objects.resource_limits import ResourceLimits
from cron_dok.ports.repositories.runner_repository import RunnerRepository


class SqliteRunnerRepository(RunnerRepository):
    """Translates between RunnerModel rows and Runner domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, runner: Runner) -> Runner:
        if runner.id is None:
            model = RunnerModel()
            self._apply_to_model(runner, model)
            self._session.add(model)
            await self._session.flush()
            return self._to_entity(model)
        existing = await self._session.get(RunnerModel, runner.id)
        if existing is None:
            raise ValueError(f"Runner {runner.id} does not exist")
        self._apply_to_model(runner, existing)
        await self._session.flush()
        return self._to_entity(existing)

    async def get_by_id(self, runner_id: int) -> Runner | None:
        model = await self._session.get(RunnerModel, runner_id)
        return self._to_entity(model) if model is not None else None

    async def list_by_project(self, project_id: int) -> list[Runner]:
        result = await self._session.scalars(
            select(RunnerModel).where(RunnerModel.project_id == project_id).order_by(RunnerModel.id)
        )
        return [self._to_entity(model) for model in result]

    async def list_all(self) -> list[Runner]:
        result = await self._session.scalars(select(RunnerModel).order_by(RunnerModel.id))
        return [self._to_entity(model) for model in result]

    async def delete(self, runner_id: int) -> None:
        await self._session.execute(delete(RunnerModel).where(RunnerModel.id == runner_id))
        await self._session.flush()

    @staticmethod
    def _apply_to_model(runner: Runner, model: RunnerModel) -> None:
        model.project_id = runner.project_id
        model.name = runner.name
        model.script_content = runner.script_content
        model.language = runner.language
        model.cron_expression = runner.cron_expression.value
        model.memory_mb = runner.resource_limits.memory_mb
        model.cpu_quota = runner.resource_limits.cpu_quota
        model.pids_limit = runner.resource_limits.pids_limit
        model.network_enabled = runner.resource_limits.network_enabled
        model.is_enabled = runner.is_enabled
        model.timeout_seconds = runner.timeout_seconds
        model.on_overlap = runner.on_overlap

    @staticmethod
    def _to_entity(model: RunnerModel) -> Runner:
        return Runner(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            script_content=model.script_content,
            language=cast(RunnerLanguage, model.language),
            cron_expression=CronExpression(model.cron_expression),
            resource_limits=ResourceLimits(
                memory_mb=model.memory_mb,
                cpu_quota=model.cpu_quota,
                pids_limit=model.pids_limit,
                network_enabled=model.network_enabled,
            ),
            is_enabled=model.is_enabled,
            timeout_seconds=model.timeout_seconds,
            on_overlap=cast(OverlapPolicy, model.on_overlap),
        )
