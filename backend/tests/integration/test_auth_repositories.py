"""Integration tests for the user/session repositories and the auth flow (real SQLite)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from cron_dok.adapters.output.security.password_service import PasswordService
from cron_dok.domain.entities.session import Session
from cron_dok.domain.entities.user import User
from cron_dok.services.auth_service import AuthService

PASSWORD = "int3gration-password"


def _user(username: str = "alice", **overrides) -> User:
    return User(username=username, password_hash="argon2-hash", **overrides)


def _session(user_id: int, token_hash: str = "deadbeef") -> Session:
    return Session(
        token_hash=token_hash,
        user_id=user_id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )


async def test_user_save_get_update_list_delete(uow) -> None:
    async with uow:
        user = await uow.users.save(_user(role="operator", must_change_password=True))
        assert user.id is not None
        assert user.created_at.tzinfo is not None

        assert await uow.users.get_by_id(user.id) == user
        assert await uow.users.get_by_username("alice") == user
        assert await uow.users.get_by_username("nobody") is None

        await uow.users.save(_user("bob"))
        assert [u.username for u in await uow.users.list_all()] == ["alice", "bob"]

        updated = await uow.users.save(
            User(
                id=user.id,
                username="alice",
                password_hash="new-hash",
                role="admin",
                is_active=False,
                must_change_password=False,
            )
        )
        stored = await uow.users.get_by_id(user.id)
        assert stored == updated
        assert stored.role == "admin"
        assert stored.is_active is False

        await uow.users.delete(user.id)
        assert await uow.users.get_by_id(user.id) is None


async def test_user_username_is_unique(uow) -> None:
    with pytest.raises(IntegrityError):
        async with uow:
            await uow.users.save(_user())
            await uow.users.save(_user())


async def test_session_roundtrip_and_delete(uow) -> None:
    async with uow:
        user = await uow.users.save(_user())
        session = await uow.sessions.save(_session(user.id))
        assert session.id is not None
        assert session.created_at.tzinfo is not None
        assert session.expires_at.tzinfo is not None

        assert await uow.sessions.get_by_token_hash("deadbeef") == session
        assert await uow.sessions.get_by_token_hash("unknown") is None

        await uow.sessions.delete_by_token_hash("deadbeef")
        assert await uow.sessions.get_by_token_hash("deadbeef") is None
        # Idempotent.
        await uow.sessions.delete_by_token_hash("deadbeef")


async def test_session_delete_by_user_revokes_only_their_sessions(uow) -> None:
    async with uow:
        alice = await uow.users.save(_user())
        bob = await uow.users.save(_user("bob"))
        assert alice.id is not None and bob.id is not None
        await uow.sessions.save(_session(alice.id, "alice-1"))
        await uow.sessions.save(_session(alice.id, "alice-2"))
        await uow.sessions.save(_session(bob.id, "bob-1"))

        await uow.sessions.delete_by_user(alice.id)

        assert await uow.sessions.get_by_token_hash("alice-1") is None
        assert await uow.sessions.get_by_token_hash("alice-2") is None
        assert await uow.sessions.get_by_token_hash("bob-1") is not None
        # Idempotent.
        await uow.sessions.delete_by_user(alice.id)


async def test_session_token_hash_is_unique(uow) -> None:
    with pytest.raises(IntegrityError):
        async with uow:
            user = await uow.users.save(_user())
            await uow.sessions.save(_session(user.id))
            await uow.sessions.save(_session(user.id))


async def test_deleting_user_cascades_sessions(uow) -> None:
    async with uow:
        user = await uow.users.save(_user())
        await uow.sessions.save(_session(user.id))

        await uow.users.delete(user.id)

        assert await uow.sessions.get_by_token_hash("deadbeef") is None


async def test_auth_flow_end_to_end(uow_factory) -> None:
    passwords = PasswordService()
    auth = AuthService(uow_factory, passwords)

    password = await auth.bootstrap_admin()
    assert password is not None
    assert await auth.bootstrap_admin() is None  # idempotent

    result = await auth.login("admin", password)
    assert result.user.must_change_password is True

    resolved = await auth.resolve_session(result.token)
    assert resolved is not None
    assert resolved.username == "admin"

    await auth.logout(result.token)
    assert await auth.resolve_session(result.token) is None


async def test_auth_service_persists_across_transactions(uow_factory) -> None:
    passwords = PasswordService()
    auth = AuthService(uow_factory, passwords)

    async with uow_factory() as uow:
        await uow.users.save(
            User(
                username="carol",
                password_hash=passwords.hash(PASSWORD),
                role="operator",
            )
        )

    # Each call opens and commits its own transaction (spec 6.2).
    result = await auth.login("carol", PASSWORD)
    assert result.user.role == "operator"
    resolved = await auth.resolve_session(result.token)
    assert resolved is not None
    assert resolved.username == "carol"
