"""Executions API tests: trigger → 202, processing, logs polling, pagination."""

from pathlib import Path
from typing import Any

from tests.api.conftest import API


async def _create_runner(client, **overrides) -> dict[str, Any]:
    project = await client.post(f"{API}/projects", json={"name": "etl"})
    assert project.status_code == 201
    payload = {
        "project_id": project.json()["id"],
        "name": "nightly",
        "script_content": "print('hi')",
        "language": "python",
        "cron_expression": "0 3 * * *",
        **overrides,
    }
    response = await client.post(f"{API}/runners", json=payload)
    assert response.status_code == 201, response.text
    runner: dict[str, Any] = response.json()
    return runner


async def _wait_idle(test_app) -> None:
    await test_app.app.state.execution_queue.wait_idle()


async def test_trigger_returns_202_and_execution_is_processed(test_app, admin_client):
    runner = await _create_runner(admin_client)

    triggered = await admin_client.post(f"{API}/triggers/{runner['id']}")
    assert triggered.status_code == 202
    execution = triggered.json()
    assert execution["runner_id"] == runner["id"]
    assert execution["trigger_type"] == "manual"
    assert execution["status"] in {"queued", "running", "succeeded"}

    await _wait_idle(test_app)

    fetched = await admin_client.get(f"{API}/executions/{execution['id']}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["status"] == "succeeded"
    assert body["exit_code"] == 0
    assert body["log_path"] is not None
    assert body["log_path"].endswith(f"/{execution['id']}.log")


async def test_logs_incremental_polling(test_app, admin_client):
    runner = await _create_runner(admin_client)
    execution = (await admin_client.post(f"{API}/triggers/{runner['id']}")).json()
    await _wait_idle(test_app)

    first = await admin_client.get(f"{API}/executions/{execution['id']}/logs", params={"offset": 0})
    assert first.status_code == 200
    first_chunk = first.json()
    assert "fake output" in first_chunk["chunk"]
    assert first_chunk["offset"] == len(first_chunk["chunk"].encode())

    # Second poll only returns what was appended since the previous offset.
    log_path = Path(test_app.settings.log_dir) / f"{execution['id']}.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("second line\n")

    second = await admin_client.get(
        f"{API}/executions/{execution['id']}/logs",
        params={"offset": first_chunk["offset"]},
    )
    assert second.json() == {
        "chunk": "second line\n",
        "offset": first_chunk["offset"] + 12,
    }


async def test_executions_pagination(test_app, admin_client):
    runner = await _create_runner(admin_client, on_overlap="queue")
    for _ in range(3):
        assert (await admin_client.post(f"{API}/triggers/{runner['id']}")).status_code == 202
    await _wait_idle(test_app)

    page1 = await admin_client.get(
        f"{API}/runners/{runner['id']}/executions", params={"limit": 2, "offset": 0}
    )
    assert page1.status_code == 200
    assert len(page1.json()) == 2

    page2 = await admin_client.get(
        f"{API}/runners/{runner['id']}/executions", params={"limit": 2, "offset": 2}
    )
    assert len(page2.json()) == 1

    ids = [e["id"] for e in page1.json()] + [e["id"] for e in page2.json()]
    assert len(set(ids)) == 3


async def test_unknown_execution_returns_404(admin_client):
    assert (await admin_client.get(f"{API}/executions/999")).status_code == 404
    assert (await admin_client.get(f"{API}/executions/999/logs")).status_code == 404


async def test_executions_of_unknown_runner_returns_404(admin_client):
    assert (await admin_client.get(f"{API}/runners/999/executions")).status_code == 404


async def test_trigger_unknown_runner_returns_404(admin_client):
    assert (await admin_client.post(f"{API}/triggers/999")).status_code == 404
