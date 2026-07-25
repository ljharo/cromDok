"""User management schemas (spec 9.4.1).

The ``password_hash`` of the domain entity is never exposed: responses only
carry the public profile fields.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from cron_dok.domain.entities.user import User, UserRole


class UserCreate(BaseModel):
    """Payload to create a user (admin only)."""

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=500)
    role: UserRole = "viewer"


class PasswordReset(BaseModel):
    """Payload to reset a user's password (admin only)."""

    password: str = Field(min_length=1, max_length=500)


class UserResponse(BaseModel):
    """Public profile of a user; never includes the password hash."""

    id: int
    username: str
    role: UserRole
    is_active: bool
    must_change_password: bool
    created_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> "UserResponse":
        """Build the response from a persisted domain user."""
        assert user.id is not None  # persisted entities always have an id
        return cls(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            created_at=user.created_at,
        )
