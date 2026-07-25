"""Unit tests for the User and Session domain entities."""

from datetime import UTC, datetime, timedelta

import pytest

from cron_dok.domain.entities.session import Session
from cron_dok.domain.entities.user import User


def test_user_defaults() -> None:
    user = User(username="alice", password_hash="hash")
    assert user.role == "viewer"
    assert user.is_active is True
    assert user.must_change_password is False
    assert user.created_at.tzinfo is not None


def test_user_rejects_empty_username() -> None:
    with pytest.raises(ValueError, match="Username"):
        User(username="   ", password_hash="hash")


@pytest.mark.parametrize("role", ["root", "Admin", "", "read-only"])
def test_user_rejects_invalid_role(role: str) -> None:
    with pytest.raises(ValueError, match="Invalid role"):
        User(username="alice", password_hash="hash", role=role)  # type: ignore[arg-type]


@pytest.mark.parametrize("role", ["admin", "operator", "viewer"])
def test_user_accepts_valid_roles(role: str) -> None:
    assert User(username="alice", password_hash="hash", role=role).role == role  # type: ignore[arg-type]


def test_user_rejects_empty_password_hash() -> None:
    with pytest.raises(ValueError, match="password_hash"):
        User(username="alice", password_hash="")


def test_session_requires_token_hash() -> None:
    with pytest.raises(ValueError, match="token_hash"):
        Session(token_hash="", user_id=1, expires_at=datetime.now(UTC) + timedelta(days=7))
