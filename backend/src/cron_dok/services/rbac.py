"""Role-based authorization helpers (spec 9.4.1 and 9.4.2).

Hierarchy: ``admin`` > ``operator`` > ``viewer``. Viewers are read-only;
operators manage projects/runners and trigger executions; admins additionally
manage users and API keys. The FastAPI dependencies (step 1.6) build on these
pure functions, so authorization logic stays testable without HTTP.

The helpers accept any :class:`RoleHolder` — a session ``User`` or the
unified ``Identity`` (which maps API key scopes to a role, spec 9.4.2) — so
the same checks serve both credential kinds.
"""

from typing import Final, Protocol

from cron_dok.domain.entities.user import UserRole
from cron_dok.services.errors import InsufficientRoleError

_ROLE_RANK: Final[dict[UserRole, int]] = {"viewer": 0, "operator": 1, "admin": 2}


class RoleHolder(Protocol):
    """Structural type of anything carrying an authorization role."""

    @property
    def role(self) -> UserRole:
        """The effective role used for authorization checks."""


def has_at_least(holder: RoleHolder, required: UserRole) -> bool:
    """Return True if ``holder``'s role ranks at or above ``required``.

    Args:
        holder: the authenticated identity (user or API key context).
        required: the minimum role the operation needs.
    """
    return _ROLE_RANK[holder.role] >= _ROLE_RANK[required]


def require_role(holder: RoleHolder, required: UserRole) -> None:
    """Raise unless ``holder``'s role ranks at or above ``required``.

    Raises:
        InsufficientRoleError: if the holder's role is below ``required``.
    """
    if not has_at_least(holder, required):
        raise InsufficientRoleError(required=required, actual=holder.role)


def can_write(holder: RoleHolder) -> bool:
    """Return True if the holder can mutate state (operators and admins)."""
    return has_at_least(holder, "operator")


def can_manage_users(holder: RoleHolder) -> bool:
    """Return True if the holder can manage users and API keys (admins only)."""
    return has_at_least(holder, "admin")
