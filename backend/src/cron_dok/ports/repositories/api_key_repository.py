"""Abstract repository port for ApiKey (spec 9.4.2)."""

from abc import ABC, abstractmethod

from cron_dok.domain.entities.api_key import ApiKey


class ApiKeyRepository(ABC):
    """Persistence contract for API keys.

    Keys are looked up by the SHA-256 of the opaque token; the plaintext
    token never reaches the repository.
    """

    @abstractmethod
    async def save(self, api_key: ApiKey) -> ApiKey:
        """Insert or update ``api_key``; return the stored entity."""

    @abstractmethod
    async def get_by_id(self, api_key_id: int) -> ApiKey | None:
        """Return the API key with that id, or None."""

    @abstractmethod
    async def get_by_key_hash(self, key_hash: str) -> ApiKey | None:
        """Return the API key for that token hash, or None."""

    @abstractmethod
    async def list_all(self) -> list[ApiKey]:
        """Return every API key, including revoked ones."""
