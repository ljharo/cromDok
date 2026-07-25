"""Session entity: an opaque login token stored hashed in the DB (spec 9.4.1)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(kw_only=True)
class Session:
    """A login session owned by a user.

    Only the SHA-256 of the opaque token is persisted (``token_hash``), so a
    database leak does not expose usable tokens. Deleting the row revokes the
    session immediately (logout).
    """

    id: int | None = None
    token_hash: str
    user_id: int
    expires_at: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.token_hash:
            raise ValueError("token_hash must not be empty")
