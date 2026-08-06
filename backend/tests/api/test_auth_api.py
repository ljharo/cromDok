"""Auth API tests: bootstrap, login/me/logout flow and login rate limit."""

from cron_dok.domain.entities.user import User
from tests.api.conftest import API, DEFAULT_PASSWORD, login, make_user


async def test_bootstrap_creates_admin_with_must_change_password(test_app, client):
    await make_user(test_app, "alice", "admin")
    await login(client, "alice")

    users = (await client.get(f"{API}/users")).json()

    admin = next(u for u in users if u["username"] == "admin")
    assert admin["role"] == "admin"
    assert admin["must_change_password"] is True


async def test_login_me_logout_flow(test_app, client):
    await make_user(test_app, "bob", "operator")

    await login(client, "bob")
    assert "crondok_session" in client.cookies

    me = await client.get(f"{API}/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "bob"
    assert me.json()["role"] == "operator"

    logout = await client.post(f"{API}/auth/logout")
    assert logout.status_code == 204
    assert "crondok_session" not in client.cookies

    assert (await client.get(f"{API}/auth/me")).status_code == 401


async def test_logout_without_session_is_idempotent(client):
    assert (await client.post(f"{API}/auth/logout")).status_code == 204


async def test_login_wrong_password_returns_401(test_app, client):
    await make_user(test_app, "carol", "viewer")
    response = await client.post(
        f"{API}/auth/login",
        json={"username": "carol", "password": "wrong-password-1"},
    )
    assert response.status_code == 401
    assert "crondok_session" not in client.cookies


async def test_login_unknown_user_returns_401(client):
    response = await client.post(
        f"{API}/auth/login",
        json={"username": "ghost", "password": "whatever-12345"},
    )
    assert response.status_code == 401


async def test_login_rate_limited_after_ten_attempts(client):
    # Spec 9.4.3: 10 attempts/minute per IP on /auth/login.
    for _ in range(10):
        response = await client.post(
            f"{API}/auth/login",
            json={"username": "ghost", "password": "whatever-12345"},
        )
        assert response.status_code == 401

    response = await client.post(
        f"{API}/auth/login",
        json={"username": "ghost", "password": "whatever-12345"},
    )
    assert response.status_code == 429


async def test_change_password_flow_revokes_sessions(test_app, client):
    await make_user(test_app, "dave", "viewer")
    await login(client, "dave")

    # Wrong current password: 400 (not 401, so the SPA does not log the
    # user out over a typo) and the session survives.
    bad = await client.post(
        f"{API}/auth/password",
        json={
            "current_password": "not-the-password",  # pragma: allowlist secret
            "new_password": "brand-new-pass-1",  # pragma: allowlist secret
        },
    )
    assert bad.status_code == 400
    assert (await client.get(f"{API}/auth/me")).status_code == 200

    # Weak new password: 422.
    weak = await client.post(
        f"{API}/auth/password",
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": "short",  # pragma: allowlist secret
        },
    )
    assert weak.status_code == 422

    # Success: 204, the cookie is cleared and every session is revoked.
    ok = await client.post(
        f"{API}/auth/password",
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": "brand-new-pass-1",  # pragma: allowlist secret
        },
    )
    assert ok.status_code == 204
    assert "crondok_session" not in client.cookies
    assert (await client.get(f"{API}/auth/me")).status_code == 401

    await login(client, "dave", "brand-new-pass-1")
    assert (await client.get(f"{API}/auth/me")).status_code == 200


async def test_change_password_requires_a_user_session(test_app, client):
    assert (
        await client.post(
            f"{API}/auth/password",
            json={"current_password": "x", "new_password": "brand-new-pass-1"},
        )
    ).status_code == 401


async def test_must_change_password_confines_user_to_password_flow(test_app, client):
    password_service = test_app.app.state.password_service
    async with test_app.app.state.uow_factory() as uow:
        await uow.users.save(
            User(
                username="temp-admin",
                password_hash=password_service.hash(DEFAULT_PASSWORD),
                role="admin",
                must_change_password=True,
            )
        )
    await login(client, "temp-admin")

    # Everything except /auth/me and /auth/password answers 403.
    assert (await client.get(f"{API}/projects")).status_code == 403
    assert (await client.get(f"{API}/users")).status_code == 403
    assert (await client.get(f"{API}/auth/me")).status_code == 200

    change = await client.post(
        f"{API}/auth/password",
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": "brand-new-pass-1",  # pragma: allowlist secret
        },
    )
    assert change.status_code == 204

    # After changing it and logging back in, the API works again.
    await login(client, "temp-admin", "brand-new-pass-1")
    assert (await client.get(f"{API}/projects")).status_code == 200


async def test_admin_reset_revokes_user_sessions(test_app, client_factory):
    await make_user(test_app, "erin", "viewer")
    await make_user(test_app, "root2", "admin")
    async with client_factory() as erin, client_factory() as admin:
        await login(erin, "erin")
        await login(admin, "root2")
        users = (await admin.get(f"{API}/users")).json()
        erin_id = next(u["id"] for u in users if u["username"] == "erin")

        reset = await admin.post(
            f"{API}/users/{erin_id}/password",
            json={"password": "reset-pass-12345"},  # pragma: allowlist secret
        )
        assert reset.status_code == 204

        # Erin's pre-reset session no longer works.
        assert (await erin.get(f"{API}/auth/me")).status_code == 401
        await login(erin, "erin", "reset-pass-12345")


async def test_login_cookie_is_not_secure_by_default(test_app, client):
    # Plain-HTTP default: the Secure flag would break login without TLS.
    await make_user(test_app, "frank", "viewer")
    response = await client.post(
        f"{API}/auth/login", json={"username": "frank", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 200
    assert "secure" not in response.headers["set-cookie"].lower()


async def test_login_cookie_secure_flag_when_enabled(test_app, client):
    await make_user(test_app, "grace", "viewer")
    test_app.app.state.settings.cookie_secure = True
    response = await client.post(
        f"{API}/auth/login", json={"username": "grace", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()
