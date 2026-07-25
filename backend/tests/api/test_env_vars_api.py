"""Env vars API tests: values are write-only, blacklist and rotation."""

from tests.api.conftest import API


async def _create_project(client, name="etl") -> int:
    response = await client.post(f"{API}/projects", json={"name": name})
    assert response.status_code == 201
    return int(response.json()["id"])


async def test_env_var_values_never_exposed(admin_client):
    project_id = await _create_project(admin_client)

    created = await admin_client.post(
        f"{API}/env-vars",
        json={"project_id": project_id, "key": "API_KEY", "value": "super-secret"},
    )
    assert created.status_code == 201
    body = created.json()
    assert set(body) == {"id", "project_id", "key", "runner_id"}
    assert body["key"] == "API_KEY"

    listed = await admin_client.get(f"{API}/env-vars", params={"project_id": project_id})
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert "super-secret" not in listed.text
    assert all(set(item) == {"id", "project_id", "key", "runner_id"} for item in items)


async def test_blacklisted_and_invalid_keys_return_422(admin_client):
    project_id = await _create_project(admin_client)
    for key in ("PATH", "LD_PRELOAD", "HOME", "1INVALID"):
        response = await admin_client.post(
            f"{API}/env-vars",
            json={"project_id": project_id, "key": key, "value": "x"},
        )
        assert response.status_code == 422, key


async def test_rotate_and_delete(admin_client):
    project_id = await _create_project(admin_client)
    created = await admin_client.post(
        f"{API}/env-vars",
        json={"project_id": project_id, "key": "TOKEN", "value": "old"},
    )
    env_var_id = created.json()["id"]

    rotated = await admin_client.post(f"{API}/env-vars/{env_var_id}/rotate", json={"value": "new"})
    assert rotated.status_code == 200
    assert "new" not in rotated.text

    assert (await admin_client.delete(f"{API}/env-vars/{env_var_id}")).status_code == 204
    listed = await admin_client.get(f"{API}/env-vars", params={"project_id": project_id})
    assert listed.json() == []


async def test_env_var_not_found_returns_404(admin_client):
    assert (await admin_client.delete(f"{API}/env-vars/999")).status_code == 404
    assert (
        await admin_client.post(f"{API}/env-vars/999/rotate", json={"value": "x"})
    ).status_code == 404
    response = await admin_client.post(
        f"{API}/env-vars", json={"project_id": 999, "key": "K", "value": "v"}
    )
    assert response.status_code == 404
    assert (
        await admin_client.get(f"{API}/env-vars", params={"project_id": 999})
    ).status_code == 404
