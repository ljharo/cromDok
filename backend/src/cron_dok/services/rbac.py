"""Role-based authorization helpers (spec 9.4.1).

Hierarchy: ``admin`` > ``operator`` > ``viewer``. Viewers are read-only;
operators manage projects/runners and trigger executions; admins additionally
manage users and API keys. The FastAPI dependencies (step 1.6) build on these
pure functions, so authorization logic stays testable without HTTP.
"""

from typing import Final

from cron_dok.domain.entities.user import User, UserRole
from cron_dok.services.errors import InsufficientRoleError

_ROLE_RANK: Final[dict[UserRole, int]] = {"viewer": 0, "operator": 1, "admin": 2}


def has_at_least(user: User, required: UserRole) -> bool:
    """Return True if ``user``'s role ranks at or above ``required``.

    Args:
        user: the authenticated user.
        required: the minimum role the operation needs.
    """
    return _ROLE_RANK[user.role] >= _ROLE_RANK[required]


def require_role(user: User, required: UserRole) -> None:
    """Raise unless ``user``'s role ranks at or above ``required``.

    Raises:
        InsufficientRoleError: if the user's role is below ``required``.
    """
    if not has_at_least(user, required):
        raise InsufficientRoleError(required=required, actual=user.role)


def can_write(user: User) -> bool:
    """Return True if the user can mutate state (operators and admins)."""
    return has_at_least(user, "operator")


def can_manage_users(user: User) -> bool:
    """Return True if the user can manage users and API keys (admins only)."""
    return has_at_least(user, "admin")
