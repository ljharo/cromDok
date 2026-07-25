"""User entity: an account with a role that accesses the UI and API (spec 9.4.1)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, get_args

UserRole = Literal["admin", "operator", "viewer"]
"""Roles, from most to least privileged: admin > operator > viewer (read-only)."""


@dataclass(kw_only=True)
class User:
    """A user account.

    ``password_hash`` holds an Argon2id hash (never the plaintext password).
    ``must_change_password`` is set by the first-boot bootstrap so the UI can
    force a password change on the first login.
    """

    id: int | None = None
    username: str
    password_hash: str
    role: UserRole = "viewer"
    is_active: bool = True
    must_change_password: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.username.strip():
            raise ValueError("Username must not be empty")
        if self.role not in get_args(UserRole):
            raise ValueError(f"Invalid role: {self.role!r}")
        if not self.password_hash:
            raise ValueError("password_hash must not be empty")
