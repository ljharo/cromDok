"""Auth router: login, logout and current-user (spec 9.4.1 and 9.4.3).

``POST /auth/login`` is public and rate-limited (10 attempts/minute per
client IP, in-memory sliding window — the MVP is single-node, so a
process-local counter is enough). Sessions are delivered as an HttpOnly,
``SameSite=Lax`` cookie holding the opaque token.
"""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, Response, status

from cron_dok.adapters.input.http.dependencies import (
    SESSION_COOKIE_NAME,
    AuthServiceDep,
    CurrentUser,
)
from cron_dok.adapters.input.http.schemas.auth import LoginRequest
from cron_dok.adapters.input.http.schemas.users import UserResponse
from cron_dok.services.auth_service import SESSION_TTL

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRateLimiter:
    """In-memory sliding-window limiter for login attempts (spec 9.4.3).

    One instance per application (stored in ``app.state``); process-local
    by design, which matches the single-node MVP.
    """

    def __init__(self, max_attempts: int = 10, window_seconds: float = 60.0) -> None:
        """Initialize the limiter.

        Args:
            max_attempts: attempts allowed per window and client key.
            window_seconds: sliding window length in seconds.
        """
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Record an attempt for ``key``; return False when the limit is hit.

        Args:
            key: client identity (IP address).
        """
        now = time.monotonic()
        attempts = self._attempts[key]
        while attempts and now - attempts[0] >= self._window_seconds:
            attempts.popleft()
        if len(attempts) >= self._max_attempts:
            return False
        attempts.append(now)
        return True


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    auth_service: AuthServiceDep,
) -> UserResponse:
    """Authenticate and set the session cookie (public, rate-limited).

    Raises:
        HTTPException: 429 when the client IP exceeded the attempt limit;
            401 (via the ``InvalidCredentialsError`` handler) on bad
            credentials.
    """
    limiter: LoginRateLimiter = request.app.state.login_rate_limiter
    client_ip = request.client.host if request.client is not None else "unknown"
    if not limiter.allow(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts; try again later",
        )
    result = await auth_service.login(body.username, body.password)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        result.token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        path="/",
    )
    return UserResponse.from_entity(result.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, auth_service: AuthServiceDep) -> Response:
    """Revoke the session and clear the cookie; idempotent (public)."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is not None:
        await auth_service.logout(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response


@router.get("/me")
async def me(user: CurrentUser) -> UserResponse:
    """Return the profile of the authenticated user."""
    return UserResponse.from_entity(user)
