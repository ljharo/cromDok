"""RBAC API tests: public endpoints, 401 without session, role enforcement."""

from tests.api.conftest import API, login, make_user


async def test_health_is_public(client):
    response = await client.get(f"{API}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_protected_endpoints_require_session(client):
    for method, url in [
        ("GET", "/projects"),
        ("GET", "/users"),
        ("GET", "/auth/me"),
        ("POST", "/projects"),
        ("POST", "/triggers/1"),
        ("GET", "/executions/1"),
        ("GET", "/env-vars?project_id=1"),
    ]:
        response = await client.request(method, f"{API}{url}")
        assert response.status_code == 401, f"{method} {url}"


async def test_viewer_is_read_only(test_app, client_factory):
    await make_user(test_app, "viewer1", "viewer")
    async with client_factory() as client:
        await login(client, "viewer1")

        assert (await client.get(f"{API}/projects")).status_code == 200
        assert (await client.post(f"{API}/projects", json={"name": "x"})).status_code == 403
        assert (await client.post(f"{API}/triggers/1")).status_code == 403
        assert (
            await client.post(
                f"{API}/env-vars",
                json={"project_id": 1, "key": "K", "value": "v"},
            )
        ).status_code == 403


async def test_operator_writes_but_cannot_manage_users(test_app, client_factory):
    await make_user(test_app, "op1", "operator")
    async with client_factory() as client:
        await login(client, "op1")

        assert (await client.post(f"{API}/projects", json={"name": "etl"})).status_code == 201
        assert (await client.get(f"{API}/users")).status_code == 403
        assert (
            await client.post(
                f"{API}/users",
                json={"username": "x", "password": "x" * 12, "role": "viewer"},
            )
        ).status_code == 403


async def test_admin_user_management_lifecycle(test_app, client_factory):
    await make_user(test_app, "root1", "admin")
    async with client_factory() as admin:
        await login(admin, "root1")

        created = await admin.post(
            f"{API}/users",
            json={
                "username": "newbie",
                "password": "newbie-pass-123",
                "role": "viewer",
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["username"] == "newbie"
        assert "password" not in body
        assert "password_hash" not in body
        newbie_id = body["id"]

        duplicate = await admin.post(
            f"{API}/users",
            json={
                "username": "newbie",
                "password": "newbie-pass-123",
                "role": "viewer",
            },
        )
        assert duplicate.status_code == 409

        weak = await admin.post(
            f"{API}/users",
            json={"username": "weakling", "password": "short", "role": "viewer"},
        )
        assert weak.status_code == 422

        usernames = [u["username"] for u in (await admin.get(f"{API}/users")).json()]
        assert "newbie" in usernames

        reset = await admin.post(
            f"{API}/users/{newbie_id}/password",
            json={"password": "newbie-pass-456"},
        )
        assert reset.status_code == 204

    async with client_factory() as newbie:
        await login(newbie, "newbie", "newbie-pass-456")

    async with client_factory() as admin:
        await login(admin, "root1")
        assert (await admin.delete(f"{API}/users/{newbie_id}")).status_code == 204
        assert (await admin.delete(f"{API}/users/{newbie_id}")).status_code == 404

    async with client_factory() as newbie:
        response = await newbie.post(
            f"{API}/auth/login",
            json={"username": "newbie", "password": "newbie-pass-456"},
        )
        assert response.status_code == 401
