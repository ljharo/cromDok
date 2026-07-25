"""Runners API tests: CRUD, enable/disable, cron validation, scheduler sync."""

from typing import Any

from tests.api.conftest import API

RUNNER_PAYLOAD = {
    "name": "nightly",
    "script_content": "print('hi')",
    "language": "python",
    "cron_expression": "0 3 * * *",
}


async def _create_project(client, name="etl") -> int:
    response = await client.post(f"{API}/projects", json={"name": name})
    assert response.status_code == 201
    return int(response.json()["id"])


async def _create_runner(client, project_id: int, **overrides) -> dict[str, Any]:
    payload = {**RUNNER_PAYLOAD, "project_id": project_id, **overrides}
    response = await client.post(f"{API}/runners", json=payload)
    assert response.status_code == 201, response.text
    runner: dict[str, Any] = response.json()
    return runner


async def test_runner_crud_and_scheduler_sync(test_app, admin_client):
    project_id = await _create_project(admin_client)

    runner = await _create_runner(admin_client, project_id)
    assert runner["cron_expression"] == "0 3 * * *"
    assert runner["is_enabled"] is True
    assert runner["resource_limits"]["memory_mb"] == 256
    assert runner["id"] in test_app.scheduler.jobs

    listed = await admin_client.get(f"{API}/runners", params={"project_id": project_id})
    assert [r["name"] for r in listed.json()] == ["nightly"]

    updated = await admin_client.patch(
        f"{API}/runners/{runner['id']}", json={"timeout_seconds": 60}
    )
    assert updated.status_code == 200
    assert updated.json()["timeout_seconds"] == 60

    disabled = await admin_client.post(f"{API}/runners/{runner['id']}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["is_enabled"] is False
    assert runner["id"] not in test_app.scheduler.jobs

    enabled = await admin_client.post(f"{API}/runners/{runner['id']}/enable")
    assert enabled.json()["is_enabled"] is True
    assert runner["id"] in test_app.scheduler.jobs

    assert (await admin_client.delete(f"{API}/runners/{runner['id']}")).status_code == 204
    assert (await admin_client.get(f"{API}/runners/{runner['id']}")).status_code == 404
    assert runner["id"] not in test_app.scheduler.jobs


async def test_invalid_cron_returns_422(admin_client):
    project_id = await _create_project(admin_client)
    response = await admin_client.post(
        f"{API}/runners",
        json={
            **RUNNER_PAYLOAD,
            "project_id": project_id,
            "cron_expression": "not a cron",
        },
    )
    assert response.status_code == 422


async def test_runner_in_unknown_project_returns_404(admin_client):
    response = await admin_client.post(f"{API}/runners", json={**RUNNER_PAYLOAD, "project_id": 999})
    assert response.status_code == 404


async def test_duplicate_runner_name_in_project_returns_409(admin_client):
    project_id = await _create_project(admin_client)
    await _create_runner(admin_client, project_id)
    response = await admin_client.post(
        f"{API}/runners", json={**RUNNER_PAYLOAD, "project_id": project_id}
    )
    assert response.status_code == 409


async def test_unknown_runner_returns_404(admin_client):
    assert (await admin_client.get(f"{API}/runners/999")).status_code == 404
    assert (await admin_client.post(f"{API}/runners/999/enable")).status_code == 404
    assert (await admin_client.post(f"{API}/runners/999/disable")).status_code == 404
    assert (await admin_client.delete(f"{API}/runners/999")).status_code == 404
