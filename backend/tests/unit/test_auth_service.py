"""Unit tests for AuthService over in-memory fakes (no database)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from cron_dok.adapters.output.security.password_service import PasswordService
from cron_dok.domain.entities.session import Session
from cron_dok.domain.entities.user import User, UserRole
from cron_dok.services.auth_service import AuthService
from cron_dok.services.errors import InvalidCredentialsError
from tests.unit.fakes import FakeUnitOfWork

PASSWORD = "sup3r-secret-password"


@pytest.fixture(scope="module")
def password_service() -> PasswordService:
    return PasswordService()


@pytest.fixture
def fake_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def auth_service(fake_uow: FakeUnitOfWork, password_service: PasswordService) -> AuthService:
    return AuthService(lambda: fake_uow, password_service)


async def _create_user(
    fake_uow: FakeUnitOfWork,
    password_service: PasswordService,
    *,
    username: str = "alice",
    role: UserRole = "viewer",
    is_active: bool = True,
    password: str = PASSWORD,
) -> User:
    async with fake_uow:
        return await fake_uow.users.save(
            User(
                username=username,
                password_hash=password_service.hash(password),
                role=role,
                is_active=is_active,
            )
        )


async def test_login_returns_token_and_resolves_user(
    auth_service: AuthService,
    fake_uow: FakeUnitOfWork,
    password_service: PasswordService,
) -> None:
    user = await _create_user(fake_uow, password_service)

    result = await auth_service.login("alice", PASSWORD)

    assert result.token
    assert result.user.username == "alice"
    resolved = await auth_service.resolve_session(result.token)
    assert resolved is not None
    assert resolved.id == user.id


async def test_login_stores_only_the_token_hash(
    auth_service: AuthService,
    fake_uow: FakeUnitOfWork,
    password_service: PasswordService,
) -> None:
    await _create_user(fake_uow, password_service)

    result = await auth_service.login("alice", PASSWORD)

    session = await fake_uow.sessions.get_by_token_hash(AuthService.hash_token(result.token))
    assert session is not None
    assert session.token_hash != result.token
    assert session.expires_at > datetime.now(UTC) + timedelta(days=6)


async def test_login_rejects_wrong_password(
    auth_service: AuthService,
    fake_uow: FakeUnitOfWork,
    password_service: PasswordService,
) -> None:
    await _create_user(fake_uow, password_service)
    with pytest.raises(InvalidCredentialsError):
        await auth_service.login("alice", "wrong password!!")


async def test_login_rejects_unknown_username(auth_service: AuthService) -> None:
    with pytest.raises(InvalidCredentialsError):
        await auth_service.login("nobody", PASSWORD)


async def test_login_rejects_inactive_user(
    auth_service: AuthService,
    fake_uow: FakeUnitOfWork,
    password_service: PasswordService,
) -> None:
    await _create_user(fake_uow, password_service, is_active=False)
    with pytest.raises(InvalidCredentialsError):
        await auth_service.login("alice", PASSWORD)


async def test_logout_revokes_the_session(
    auth_service: AuthService,
    fake_uow: FakeUnitOfWork,
    password_service: PasswordService,
) -> None:
    await _create_user(fake_uow, password_service)
    result = await auth_service.login("alice", PASSWORD)

    await auth_service.logout(result.token)

    assert await auth_service.resolve_session(result.token) is None
    # Logout is idempotent: revoking twice or with an unknown token is a no-op.
    await auth_service.logout(result.token)
    await auth_service.logout("never-issued-token")


async def test_resolve_session_returns_none_for_unknown_token(
    auth_service: AuthService,
) -> None:
    assert await auth_service.resolve_session("no-such-token") is None


async def test_resolve_session_rejects_expired_session_and_cleans_it_up(
    auth_service: AuthService,
    fake_uow: FakeUnitOfWork,
    password_service: PasswordService,
) -> None:
    user = await _create_user(fake_uow, password_service)
    assert user.id is not None
    token = "expired-token"
    token_hash = AuthService.hash_token(token)
    async with fake_uow:
        await fake_uow.sessions.save(
            Session(
                token_hash=token_hash,
                user_id=user.id,
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )

    assert await auth_service.resolve_session(token) is None
    assert await fake_uow.sessions.get_by_token_hash(token_hash) is None


async def test_resolve_session_rejects_inactive_user(
    auth_service: AuthService,
    fake_uow: FakeUnitOfWork,
    password_service: PasswordService,
) -> None:
    user = await _create_user(fake_uow, password_service)
    result = await auth_service.login("alice", PASSWORD)

    async with fake_uow:
        await fake_uow.users.save(replace(user, is_active=False))

    assert await auth_service.resolve_session(result.token) is None


async def test_bootstrap_admin_creates_admin_once(
    auth_service: AuthService, fake_uow: FakeUnitOfWork
) -> None:
    password = await auth_service.bootstrap_admin()

    assert password is not None
    assert len(password) >= 12
    admin = await fake_uow.users.get_by_username("admin")
    assert admin is not None
    assert admin.role == "admin"
    assert admin.must_change_password is True
    # The returned password actually logs in.
    result = await auth_service.login("admin", password)
    assert result.user.username == "admin"

    # Idempotent: a second bootstrap is a no-op.
    assert await auth_service.bootstrap_admin() is None
    assert [u.username for u in await fake_uow.users.list_all()] == ["admin"]


async def test_bootstrap_admin_is_noop_when_users_exist(
    fake_uow: FakeUnitOfWork, password_service: PasswordService
) -> None:
    await _create_user(fake_uow, password_service, username="someone")
    auth_service = AuthService(lambda: fake_uow, password_service)

    assert await auth_service.bootstrap_admin() is None
    assert await fake_uow.users.get_by_username("admin") is None
