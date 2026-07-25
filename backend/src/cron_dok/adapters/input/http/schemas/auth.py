"""Auth request schemas (spec 9.4.1)."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials for ``POST /auth/login``."""

    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=500)
