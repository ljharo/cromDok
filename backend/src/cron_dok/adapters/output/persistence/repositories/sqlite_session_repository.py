"""SQLite implementation of SessionRepository (SQLAlchemy 2.0 async)."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cron_dok.adapters.output.persistence.models.session import SessionModel
from cron_dok.domain.entities.session import Session
from cron_dok.ports.repositories.session_repository import SessionRepository


class SqliteSessionRepository(SessionRepository):
    """Translates between SessionModel rows and Session domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, session: Session) -> Session:
        model = SessionModel(
            token_hash=session.token_hash,
            user_id=session.user_id,
            expires_at=session.expires_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        result = await self._session.scalars(
            select(SessionModel).where(SessionModel.token_hash == token_hash)
        )
        model = result.one_or_none()
        return self._to_entity(model) if model is not None else None

    async def delete_by_token_hash(self, token_hash: str) -> None:
        await self._session.execute(
            delete(SessionModel).where(SessionModel.token_hash == token_hash)
        )
        await self._session.flush()

    @staticmethod
    def _to_entity(model: SessionModel) -> Session:
        # SQLite may return naive datetimes; the domain convention is UTC.
        expires_at = _as_utc(model.expires_at)
        created_at = _as_utc(model.created_at)
        return Session(
            id=model.id,
            token_hash=model.token_hash,
            user_id=model.user_id,
            expires_at=expires_at,
            created_at=created_at,
        )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
