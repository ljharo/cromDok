"""ApiKey entity: an opaque integration token stored hashed in the DB (spec 9.4.2)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, get_args

ApiKeyScope = Literal["runners:read", "runners:execute", "admin"]
"""API key scopes: read-only GETs, trigger executions, or full access (spec 9.4.2)."""


@dataclass(kw_only=True)
class ApiKey:
    """An API key issued to an external integration.

    Only the SHA-256 of the opaque token is persisted (``key_hash``), so a
    database leak does not expose usable tokens; the plaintext token is shown
    exactly once at creation. Setting ``revoked_at`` revokes the key
    immediately (spec 9.4.2).
    """

    id: int | None = None
    name: str
    key_hash: str
    scopes: list[ApiKeyScope]
    created_by: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("API key name must not be empty")
        if not self.key_hash:
            raise ValueError("key_hash must not be empty")
        if not self.scopes:
            raise ValueError("API key must have at least one scope")
        for scope in self.scopes:
            if scope not in get_args(ApiKeyScope):
                raise ValueError(f"Invalid API key scope: {scope!r}")

    @property
    def is_revoked(self) -> bool:
        """Return True once the key has been revoked."""
        return self.revoked_at is not None
