"""Projects API tests: CRUD, 404/409/422 mapping."""

from tests.api.conftest import API


async def test_project_crud(admin_client):
    created = await admin_client.post(
        f"{API}/projects", json={"name": "etl", "description": "pipes"}
    )
    assert created.status_code == 201
    project = created.json()
    assert project["name"] == "etl"
    assert project["description"] == "pipes"

    listed = await admin_client.get(f"{API}/projects")
    assert [p["name"] for p in listed.json()] == ["etl"]

    fetched = await admin_client.get(f"{API}/projects/{project['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == project["id"]

    updated = await admin_client.patch(
        f"{API}/projects/{project['id']}", json={"description": "renamed pipes"}
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "renamed pipes"
    assert updated.json()["name"] == "etl"

    assert (await admin_client.delete(f"{API}/projects/{project['id']}")).status_code == 204
    assert (await admin_client.get(f"{API}/projects/{project['id']}")).status_code == 404


async def test_duplicate_project_name_returns_409(admin_client):
    assert (await admin_client.post(f"{API}/projects", json={"name": "etl"})).status_code == 201
    assert (await admin_client.post(f"{API}/projects", json={"name": "etl"})).status_code == 409


async def test_empty_project_name_returns_422(admin_client):
    assert (await admin_client.post(f"{API}/projects", json={"name": ""})).status_code == 422


async def test_unknown_project_returns_404(admin_client):
    assert (await admin_client.get(f"{API}/projects/999")).status_code == 404
    assert (await admin_client.patch(f"{API}/projects/999", json={"name": "x"})).status_code == 404
    assert (await admin_client.delete(f"{API}/projects/999")).status_code == 404
