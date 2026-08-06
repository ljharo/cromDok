"""Authentication application service: login, sessions and bootstrap (spec 9.4.1).

Sessions use opaque tokens (``secrets.token_urlsafe(32)``); only the SHA-256
of the token is persisted, so a database leak does not expose usable tokens.
Sessions expire after 7 days and logout deletes the row (immediate
revocation). The HTTP adapter (cookies, middleware) consumes this service;
nothing here depends on FastAPI.
"""

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from cron_dok.adapters.output.security.password_service import PasswordService
from cron_dok.domain.entities.session import Session
from cron_dok.domain.entities.user import User
from cron_dok.ports.unit_of_work import AbstractUnitOfWork
from cron_dok.services.errors import InvalidCredentialsError

SESSION_TTL = timedelta(days=7)

BOOTSTRAP_ADMIN_USERNAME = "admin"

# A valid Argon2id hash of a throwaway password. ``login`` verifies against it
# when the username does not exist so the response time does not reveal
# whether the account exists (user-enumeration hardening).
_DUMMY_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$sQHh4tlCZRLEOv6RW+0Dbw$63Kc9Ul8BjguNKKTQrGuowyImdvH0ZJuFpd5LP0ddZY"  # noqa: E501

Clock = Callable[[], datetime]


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class LoginResult:
    """The outcome of a successful login.

    Attributes:
        token: the opaque session token in plaintext (only its SHA-256 is
            persisted); the caller delivers it as an HttpOnly cookie.
        user: the authenticated user.
    """

    token: str
    user: User


class AuthService:
    """Login, logout, session resolution and first-boot admin bootstrap.

    Every operation runs inside ``async with uow:`` so reads and writes are
    consistent (spec 6.2).
    """

    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
        password_service: PasswordService,
        *,
        clock: Clock = _utcnow,
    ) -> None:
        """Initialize the service.

        Args:
            uow_factory: zero-arg callable returning a fresh Unit of Work per
                operation.
            password_service: Argon2id hasher used for credential checks.
            clock: time source (injectable for tests); must return UTC-aware
                datetimes.
        """
        self._uow_factory = uow_factory
        self._passwords = password_service
        self._clock = clock

    @staticmethod
    def hash_token(token: str) -> str:
        """Return the SHA-256 hex digest stored for an opaque session token."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def login(self, username: str, password: str) -> LoginResult:
        """Authenticate and open a session that expires in 7 days.

        Returns:
            The opaque token (plaintext, shown once) and the user.

        Raises:
            InvalidCredentialsError: if the username is unknown, the password
                does not match, or the account is inactive. The error does not
                reveal which check failed.
        """
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_username(username)
            if user is None:
                # Equalize timing against the unknown-username path.
                self._passwords.verify(password, _DUMMY_PASSWORD_HASH)
                raise InvalidCredentialsError()
            if not self._passwords.verify(password, user.password_hash):
                raise InvalidCredentialsError()
            if not user.is_active:
                raise InvalidCredentialsError()
            assert user.id is not None
            token = secrets.token_urlsafe(32)
            await uow.sessions.save(
                Session(
                    token_hash=self.hash_token(token),
                    user_id=user.id,
                    expires_at=self._clock() + SESSION_TTL,
                )
            )
            return LoginResult(token=token, user=user)

    async def logout(self, token: str) -> None:
        """Revoke the session for ``token``; idempotent (unknown tokens are a no-op)."""
        async with self._uow_factory() as uow:
            await uow.sessions.delete_by_token_hash(self.hash_token(token))

    async def change_password(self, user_id: int, current_password: str, new_password: str) -> User:
        """Change a user's own password and revoke every session of theirs.

        All sessions — including the one used for the request — are deleted
        so no session can outlive a credential change; the caller must log
        in again with the new password. Clears ``must_change_password``.

        Returns:
            The updated user.

        Raises:
            InvalidCredentialsError: if the user does not exist or the
                current password does not match.
            WeakPasswordError: if the new password is too weak (raised by
                the password hasher, mapped to 422 by the HTTP adapter).
        """
        new_hash = self._passwords.hash(new_password)
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None or not self._passwords.verify(current_password, user.password_hash):
                raise InvalidCredentialsError()
            user = await uow.users.save(
                replace(user, password_hash=new_hash, must_change_password=False)
            )
            await uow.sessions.delete_by_user(user_id)
            return user

    async def resolve_session(self, token: str) -> User | None:
        """Return the user behind ``token``, or None.

        A session resolves to None when the token is unknown, the session has
        expired (expired rows are deleted as a cleanup), or the user no longer
        exists or is inactive.
        """
        async with self._uow_factory() as uow:
            session = await uow.sessions.get_by_token_hash(self.hash_token(token))
            if session is None:
                return None
            if session.expires_at <= self._clock():
                await uow.sessions.delete_by_token_hash(session.token_hash)
                return None
            user = await uow.users.get_by_id(session.user_id)
            if user is None or not user.is_active:
                return None
            return user

    async def bootstrap_admin(self) -> str | None:
        """Create the initial ``admin`` user if the system has no users.

        The generated password is returned in plaintext exactly once so the
        caller can print it to the container logs (Gitea/Portainer pattern);
        only its Argon2id hash is stored. The created user has
        ``must_change_password=True``.

        Returns:
            The generated admin password, or None when users already exist
            (idempotent: subsequent calls are a no-op).
        """
        async with self._uow_factory() as uow:
            if await uow.users.list_all():
                return None
            password = secrets.token_urlsafe(16)
            await uow.users.save(
                User(
                    username=BOOTSTRAP_ADMIN_USERNAME,
                    password_hash=self._passwords.hash(password),
                    role="admin",
                    must_change_password=True,
                )
            )
            return password
