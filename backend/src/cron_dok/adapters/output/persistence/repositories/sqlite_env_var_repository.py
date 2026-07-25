"""SQLite implementation of EnvVarRepository (SQLAlchemy 2.0 async)."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cron_dok.adapters.output.persistence.models.env_var import EnvVarModel
from cron_dok.domain.entities.env_var import EnvVar
from cron_dok.ports.repositories.env_var_repository import EnvVarRepository


class SqliteEnvVarRepository(EnvVarRepository):
    """Translates between EnvVarModel rows and EnvVar domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, env_var: EnvVar) -> EnvVar:
        if env_var.id is None:
            model = EnvVarModel(
                project_id=env_var.project_id,
                runner_id=env_var.runner_id,
                key=env_var.key,
                encrypted_value=env_var.encrypted_value,
            )
            self._session.add(model)
            await self._session.flush()
            return self._to_entity(model)
        existing = await self._session.get(EnvVarModel, env_var.id)
        if existing is None:
            raise ValueError(f"EnvVar {env_var.id} does not exist")
        existing.project_id = env_var.project_id
        existing.runner_id = env_var.runner_id
        existing.key = env_var.key
        existing.encrypted_value = env_var.encrypted_value
        await self._session.flush()
        return self._to_entity(existing)

    async def get_by_id(self, env_var_id: int) -> EnvVar | None:
        model = await self._session.get(EnvVarModel, env_var_id)
        return self._to_entity(model) if model is not None else None

    async def list_by_project(self, project_id: int) -> list[EnvVar]:
        result = await self._session.scalars(
            select(EnvVarModel).where(EnvVarModel.project_id == project_id).order_by(EnvVarModel.id)
        )
        return [self._to_entity(model) for model in result]

    async def delete(self, env_var_id: int) -> None:
        await self._session.execute(delete(EnvVarModel).where(EnvVarModel.id == env_var_id))
        await self._session.flush()

    @staticmethod
    def _to_entity(model: EnvVarModel) -> EnvVar:
        return EnvVar(
            id=model.id,
            project_id=model.project_id,
            runner_id=model.runner_id,
            key=model.key,
            encrypted_value=model.encrypted_value,
        )
