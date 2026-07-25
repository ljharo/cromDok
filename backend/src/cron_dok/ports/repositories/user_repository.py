"""Abstract repository port for User (spec 9.4.1)."""

from abc import ABC, abstractmethod

from cron_dok.domain.entities.user import User


class UserRepository(ABC):
    """Persistence contract for users."""

    @abstractmethod
    async def save(self, user: User) -> User:
        """Insert (id is None) or update ``user``; return the stored entity."""

    @abstractmethod
    async def get_by_id(self, user_id: int) -> User | None:
        """Return the user or None if it does not exist."""

    @abstractmethod
    async def get_by_username(self, username: str) -> User | None:
        """Return the user with that exact username, or None."""

    @abstractmethod
    async def list_all(self) -> list[User]:
        """Return all users, oldest first."""

    @abstractmethod
    async def delete(self, user_id: int) -> None:
        """Delete a user; its sessions cascade via the FK."""
