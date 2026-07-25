"""Unified caller identity: a session user or an API key (spec 9.4.2).

``resolve_identity`` (HTTP adapter) authenticates the caller either by the
session cookie or by an ``Authorization: Bearer crondok_...`` API key and
wraps the result in :class:`Identity`, so the rest of the authorization
chain (``require_role``/``require_write``) works unchanged for both.

Scope → role mapping for API keys (spec 9.4.2, plan 3.1):

- ``admin`` → ``admin`` (everything **except** managing users/API keys,
  which always requires a user session),
- ``runners:execute`` → ``operator`` (POST triggers and mutations),
- ``runners:read`` → ``viewer`` (read-only GETs).
"""

from dataclasses import dataclass

from cron_dok.domain.entities.api_key import ApiKey
from cron_dok.domain.entities.user import User, UserRole


@dataclass(frozen=True)
class Identity:
    """The authenticated caller: exactly one of ``user`` or ``api_key``.

    Attributes:
        user: the session user, when authenticated via cookie.
        api_key: the resolved API key, when authenticated via Bearer token.
    """

    user: User | None = None
    api_key: ApiKey | None = None

    def __post_init__(self) -> None:
        if (self.user is None) == (self.api_key is None):
            raise ValueError("Identity requires exactly one of user or api_key")

    @property
    def role(self) -> UserRole:
        """Effective authorization role (scope mapping for API keys)."""
        if self.user is not None:
            return self.user.role
        assert self.api_key is not None  # guaranteed by __post_init__
        scopes = self.api_key.scopes
        if "admin" in scopes:
            return "admin"
        if "runners:execute" in scopes:
            return "operator"
        return "viewer"

    @property
    def is_api_key(self) -> bool:
        """Return True when the caller authenticated with an API key."""
        return self.api_key is not None

    @property
    def rate_limit_key(self) -> str:
        """Stable per-caller key for rate limiting (plan 3.2)."""
        if self.user is not None:
            return f"user:{self.user.id}"
        assert self.api_key is not None  # guaranteed by __post_init__
        return f"apikey:{self.api_key.id}"
