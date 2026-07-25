"""API key application service: issue, list, revoke and resolve (spec 9.4.2).

API keys are opaque tokens (``crondok_<secrets.token_urlsafe(32)>``); only
the SHA-256 of the token is persisted, so a database leak does not expose
usable tokens. The plaintext token is returned exactly once, at creation.
Revocation is immediate (``revoked_at`` timestamp). The HTTP adapter
resolves ``Authorization: Bearer`` headers through this service; nothing
here depends on FastAPI.
"""

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from cron_dok.domain.entities.api_key import ApiKey, ApiKeyScope
from cron_dok.domain.entities.user import User
from cron_dok.ports.unit_of_work import AbstractUnitOfWork
from cron_dok.services.errors import ApiKeyNotFoundError

TOKEN_PREFIX = "crondok_"
"""Prefix of every opaque API key token (spec 9.4.2)."""

Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CreatedApiKey:
    """The outcome of issuing an API key.

    Attributes:
        api_key: the persisted entity (never carries the plaintext token).
        token: the plaintext token, shown to the caller exactly once.
    """

    api_key: ApiKey
    token: str


class ApiKeyService:
    """Issue, list, revoke and resolve API keys.

    Every operation runs inside ``async with uow:`` so reads and writes are
    consistent (spec 6.2).
    """

    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
        *,
        clock: Clock = _utcnow,
    ) -> None:
        """Initialize the service.

        Args:
            uow_factory: zero-arg callable returning a fresh Unit of Work per
                operation.
            clock: time source (injectable for tests); must return UTC-aware
                datetimes.
        """
        self._uow_factory = uow_factory
        self._clock = clock

    @staticmethod
    def hash_token(token: str) -> str:
        """Return the SHA-256 hex digest stored for an opaque API key token."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def create(self, name: str, scopes: list[ApiKeyScope], user: User) -> CreatedApiKey:
        """Issue a new API key owned by ``user``.

        Returns:
            The persisted entity plus the plaintext token (shown once).

        Raises:
            ValueError: if the name is empty or a scope is invalid.
        """
        assert user.id is not None  # only persisted users can issue keys
        token = TOKEN_PREFIX + secrets.token_urlsafe(32)
        async with self._uow_factory() as uow:
            api_key = await uow.api_keys.save(
                ApiKey(
                    name=name,
                    key_hash=self.hash_token(token),
                    scopes=list(scopes),
                    created_by=user.id,
                )
            )
        return CreatedApiKey(api_key=api_key, token=token)

    async def list(self) -> list[ApiKey]:
        """Return every API key (revoked included); hashes stay in the entity.

        The HTTP layer is responsible for never serializing ``key_hash``.
        """
        async with self._uow_factory() as uow:
            return await uow.api_keys.list_all()

    async def revoke(self, api_key_id: int) -> None:
        """Revoke a key immediately by stamping ``revoked_at``; idempotent.

        Raises:
            ApiKeyNotFoundError: if no key has that id.
        """
        async with self._uow_factory() as uow:
            api_key = await uow.api_keys.get_by_id(api_key_id)
            if api_key is None:
                raise ApiKeyNotFoundError(api_key_id)
            if api_key.revoked_at is None:
                await uow.api_keys.save(replace(api_key, revoked_at=self._clock()))

    async def resolve(self, token: str) -> ApiKey | None:
        """Return the non-revoked key behind ``token``, or None.

        On a hit, ``last_used_at`` is updated. Unknown tokens and revoked
        keys both resolve to None (revocation is immediate, spec 9.4.2).
        """
        async with self._uow_factory() as uow:
            api_key = await uow.api_keys.get_by_key_hash(self.hash_token(token))
            if api_key is None or api_key.revoked_at is not None:
                return None
            return await uow.api_keys.save(replace(api_key, last_used_at=self._clock()))
