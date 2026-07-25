"""Unit tests for the RBAC helpers (hierarchy admin > operator > viewer)."""

import pytest

from cron_dok.domain.entities.user import User, UserRole
from cron_dok.services.errors import InsufficientRoleError
from cron_dok.services.rbac import (
    can_manage_users,
    can_write,
    has_at_least,
    require_role,
)


def _user(role: UserRole) -> User:
    return User(username="u", password_hash="hash", role=role)


def test_admin_outranks_everything() -> None:
    admin = _user("admin")
    assert has_at_least(admin, "admin")
    assert has_at_least(admin, "operator")
    assert has_at_least(admin, "viewer")


def test_operator_outranks_viewer_only() -> None:
    operator = _user("operator")
    assert has_at_least(operator, "operator")
    assert has_at_least(operator, "viewer")
    assert not has_at_least(operator, "admin")


def test_viewer_is_read_only() -> None:
    viewer = _user("viewer")
    assert has_at_least(viewer, "viewer")
    assert not has_at_least(viewer, "operator")
    assert not can_write(viewer)
    assert not can_manage_users(viewer)


def test_can_write_and_manage_users() -> None:
    assert can_write(_user("operator"))
    assert can_write(_user("admin"))
    assert can_manage_users(_user("admin"))
    assert not can_manage_users(_user("operator"))


def test_require_role_passes_at_or_above_minimum() -> None:
    require_role(_user("admin"), "operator")
    require_role(_user("operator"), "operator")


def test_require_role_raises_below_minimum() -> None:
    with pytest.raises(InsufficientRoleError) as exc_info:
        require_role(_user("viewer"), "operator")
    assert exc_info.value.required == "operator"
    assert exc_info.value.actual == "viewer"
