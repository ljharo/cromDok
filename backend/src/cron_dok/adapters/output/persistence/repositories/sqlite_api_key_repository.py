"""SQLite implementation of ApiKeyRepository (SQLAlchemy 2.0 async)."""

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cron_dok.adapters.output.persistence.models.api_key import ApiKeyModel
from cron_dok.domain.entities.api_key import ApiKey, ApiKeyScope
from cron_dok.ports.repositories.api_key_repository import ApiKeyRepository


class SqliteApiKeyRepository(ApiKeyRepository):
    """Translates between ApiKeyModel rows and ApiKey domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, api_key: ApiKey) -> ApiKey:
        if api_key.id is None:
            model = ApiKeyModel(
                name=api_key.name,
                key_hash=api_key.key_hash,
                scopes=list(api_key.scopes),
                created_by=api_key.created_by,
                created_at=api_key.created_at,
                last_used_at=api_key.last_used_at,
                revoked_at=api_key.revoked_at,
            )
            self._session.add(model)
            await self._session.flush()
            return self._to_entity(model)
        existing = await self._session.get(ApiKeyModel, api_key.id)
        if existing is None:
            raise ValueError(f"ApiKey {api_key.id} does not exist")
        existing.name = api_key.name
        existing.key_hash = api_key.key_hash
        existing.scopes = list(api_key.scopes)
        existing.created_by = api_key.created_by
        existing.last_used_at = api_key.last_used_at
        existing.revoked_at = api_key.revoked_at
        await self._session.flush()
        return self._to_entity(existing)

    async def get_by_id(self, api_key_id: int) -> ApiKey | None:
        model = await self._session.get(ApiKeyModel, api_key_id)
        return self._to_entity(model) if model is not None else None

    async def get_by_key_hash(self, key_hash: str) -> ApiKey | None:
        result = await self._session.scalars(
            select(ApiKeyModel).where(ApiKeyModel.key_hash == key_hash)
        )
        model = result.one_or_none()
        return self._to_entity(model) if model is not None else None

    async def list_all(self) -> list[ApiKey]:
        result = await self._session.scalars(select(ApiKeyModel).order_by(ApiKeyModel.id))
        return [self._to_entity(model) for model in result]

    @staticmethod
    def _to_entity(model: ApiKeyModel) -> ApiKey:
        return ApiKey(
            id=model.id,
            name=model.name,
            key_hash=model.key_hash,
            scopes=[cast(ApiKeyScope, scope) for scope in model.scopes],
            created_by=model.created_by,
            created_at=_as_utc(model.created_at),
            last_used_at=_as_utc(model.last_used_at) if model.last_used_at else None,
            revoked_at=_as_utc(model.revoked_at) if model.revoked_at else None,
        )


def _as_utc(value: datetime) -> datetime:
    # SQLite may return naive datetimes; the domain convention is UTC.
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
