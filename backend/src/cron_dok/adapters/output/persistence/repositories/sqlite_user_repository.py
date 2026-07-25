"""SQLite implementation of UserRepository (SQLAlchemy 2.0 async)."""

from datetime import UTC
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from cron_dok.adapters.output.persistence.models.user import UserModel
from cron_dok.domain.entities.user import User, UserRole
from cron_dok.ports.repositories.user_repository import UserRepository


class SqliteUserRepository(UserRepository):
    """Translates between UserModel rows and User domain entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, user: User) -> User:
        if user.id is None:
            model = UserModel(
                username=user.username,
                password_hash=user.password_hash,
                role=user.role,
                is_active=user.is_active,
                must_change_password=user.must_change_password,
            )
            self._session.add(model)
            await self._session.flush()
            return self._to_entity(model)
        existing = await self._session.get(UserModel, user.id)
        if existing is None:
            raise ValueError(f"User {user.id} does not exist")
        existing.username = user.username
        existing.password_hash = user.password_hash
        existing.role = user.role
        existing.is_active = user.is_active
        existing.must_change_password = user.must_change_password
        await self._session.flush()
        return self._to_entity(existing)

    async def get_by_id(self, user_id: int) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return self._to_entity(model) if model is not None else None

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.scalars(
            select(UserModel).where(UserModel.username == username)
        )
        model = result.one_or_none()
        return self._to_entity(model) if model is not None else None

    async def list_all(self) -> list[User]:
        result = await self._session.scalars(select(UserModel).order_by(UserModel.id))
        return [self._to_entity(model) for model in result]

    async def delete(self, user_id: int) -> None:
        await self._session.execute(delete(UserModel).where(UserModel.id == user_id))
        await self._session.flush()

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        created_at = model.created_at
        # SQLite may return naive datetimes; the domain convention is UTC.
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return User(
            id=model.id,
            username=model.username,
            password_hash=model.password_hash,
            role=cast(UserRole, model.role),
            is_active=model.is_active,
            must_change_password=model.must_change_password,
            created_at=created_at,
        )
