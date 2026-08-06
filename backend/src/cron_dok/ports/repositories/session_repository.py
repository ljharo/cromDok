"""Abstract repository port for Session (spec 9.4.1)."""

from abc import ABC, abstractmethod

from cron_dok.domain.entities.session import Session


class SessionRepository(ABC):
    """Persistence contract for login sessions.

    Sessions are looked up and revoked by the SHA-256 of the opaque token;
    the plaintext token never reaches the repository.
    """

    @abstractmethod
    async def save(self, session: Session) -> Session:
        """Insert ``session``; return the stored entity."""

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        """Return the session for that token hash, or None."""

    @abstractmethod
    async def delete_by_token_hash(self, token_hash: str) -> None:
        """Delete the session for that token hash (logout); idempotent."""

    @abstractmethod
    async def delete_by_user(self, user_id: int) -> None:
        """Delete every session of ``user_id`` (credential revocation); idempotent."""
