"""Auth request schemas (spec 9.4.1)."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials for ``POST /auth/login``."""

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=500)


class PasswordChange(BaseModel):
    """Payload for ``POST /auth/password`` (self-service change)."""

    current_password: str = Field(min_length=1, max_length=500)
    new_password: str = Field(min_length=1, max_length=500)
