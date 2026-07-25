"""SQLite implementation of ExecutionRepository (SQLAlchemy 2.0 async)."""

from datetime import datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cron_dok.adapters.output.persistence.models.execution import ExecutionModel
from cron_dok.domain.entities.execution import Execution, ExecutionStatus, TriggerType
from cron_dok.ports.repositories.execution_repository import ExecutionRepository


class SqliteExecutionRepository(ExecutionRepository):
    """Translates between ExecutionModel rows and Execution domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, execution: Execution) -> Execution:
        if execution.id is None:
            model = ExecutionModel()
            self._apply_to_model(execution, model)
            self._session.add(model)
            await self._session.flush()
            return self._to_entity(model)
        existing = await self._session.get(ExecutionModel, execution.id)
        if existing is None:
            raise ValueError(f"Execution {execution.id} does not exist")
        self._apply_to_model(execution, existing)
        await self._session.flush()
        return self._to_entity(existing)

    async def get_by_id(self, execution_id: int) -> Execution | None:
        model = await self._session.get(ExecutionModel, execution_id)
        return self._to_entity(model) if model is not None else None

    async def list_by_runner(self, runner_id: int) -> list[Execution]:
        result = await self._session.scalars(
            select(ExecutionModel)
            .where(ExecutionModel.runner_id == runner_id)
            .order_by(ExecutionModel.id)
        )
        return [self._to_entity(model) for model in result]

    async def list_finished_before(self, cutoff: datetime) -> list[Execution]:
        result = await self._session.scalars(
            select(ExecutionModel)
            .where(
                ExecutionModel.finished_at.is_not(None),
                ExecutionModel.finished_at < cutoff,
            )
            .order_by(ExecutionModel.id)
        )
        return [self._to_entity(model) for model in result]

    async def delete(self, execution_id: int) -> None:
        model = await self._session.get(ExecutionModel, execution_id)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    @staticmethod
    def _apply_to_model(execution: Execution, model: ExecutionModel) -> None:
        model.runner_id = execution.runner_id
        model.status = execution.status
        model.trigger_type = execution.trigger_type
        model.started_at = execution.started_at
        model.finished_at = execution.finished_at
        model.exit_code = execution.exit_code
        model.duration_ms = execution.duration_ms
        model.log_path = execution.log_path

    @staticmethod
    def _to_entity(model: ExecutionModel) -> Execution:
        return Execution(
            id=model.id,
            runner_id=model.runner_id,
            status=cast(ExecutionStatus, model.status),
            trigger_type=cast(TriggerType, model.trigger_type),
            started_at=model.started_at,
            finished_at=model.finished_at,
            exit_code=model.exit_code,
            duration_ms=model.duration_ms,
            log_path=model.log_path,
        )
