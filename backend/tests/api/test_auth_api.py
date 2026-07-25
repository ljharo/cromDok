"""Auth API tests: bootstrap, login/me/logout flow and login rate limit."""

from tests.api.conftest import API, login, make_user


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
