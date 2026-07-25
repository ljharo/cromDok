"""API key management schemas (spec 9.4.2).

The ``key_hash`` of the domain entity is never exposed: responses only
carry the public metadata. The plaintext token appears exactly once, in
``ApiKeyCreatedResponse``.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from cron_dok.domain.entities.api_key import ApiKey, ApiKeyScope


class ApiKeyCreate(BaseModel):
    """Payload to issue an API key (session admin only)."""

    name: str = Field(min_length=1, max_length=100)
    scopes: list[ApiKeyScope] = Field(min_length=1)


class ApiKeyResponse(BaseModel):
    """Public metadata of an API key; never includes the hash nor the token."""

    id: int
    name: str
    scopes: list[ApiKeyScope]
    created_by: int
    created_at: datetime
    last_used_at: datetime | None
    revoked: bool

    @classmethod
    def from_entity(cls, api_key: ApiKey) -> "ApiKeyResponse":
        """Build the response from a persisted domain API key."""
        assert api_key.id is not None  # persisted entities always have an id
        return cls(
            id=api_key.id,
            name=api_key.name,
            scopes=list(api_key.scopes),
            created_by=api_key.created_by,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            revoked=api_key.is_revoked,
        )


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Creation response: the only place the plaintext token is ever shown."""

    token: str
