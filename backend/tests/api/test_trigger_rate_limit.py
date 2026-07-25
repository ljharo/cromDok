"""Trigger endpoint rate limiting (spec 9.4.3, plan 3.2)."""

import asyncio

from cron_dok.adapters.input.http.rate_limit import SlidingWindowRateLimiter
from tests.api.conftest import API, login, make_user


async def _create_runner(client) -> int:
    project = await client.post(f"{API}/projects", json={"name": "etl"})
    assert project.status_code == 201
    payload = {
        "project_id": project.json()["id"],
        "name": "nightly",
        "script_content": "print('hi')",
        "language": "python",
        "cron_expression": "0 3 * * *",
    }
    response = await client.post(f"{API}/runners", json=payload)
    assert response.status_code == 201, response.text
    runner_id: int = response.json()["id"]
    return runner_id


async def test_request_over_limit_returns_429_with_retry_after(test_app, admin_client):
    test_app.app.state.trigger_rate_limiter = SlidingWindowRateLimiter(max_attempts=2)
    runner_id = await _create_runner(admin_client)

    for _ in range(2):
        assert (await admin_client.post(f"{API}/triggers/{runner_id}")).status_code == 202

    limited = await admin_client.post(f"{API}/triggers/{runner_id}")
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 1


async def test_distinct_identities_have_independent_counters(
    test_app, admin_client, client_factory
):
    test_app.app.state.trigger_rate_limiter = SlidingWindowRateLimiter(max_attempts=1)
    runner_id = await _create_runner(admin_client)

    assert (await admin_client.post(f"{API}/triggers/{runner_id}")).status_code == 202
    assert (await admin_client.post(f"{API}/triggers/{runner_id}")).status_code == 429

    await make_user(test_app, "fixture-admin-2", "admin")
    async with client_factory() as other_client:
        await login(other_client, "fixture-admin-2")
        assert (await other_client.post(f"{API}/triggers/{runner_id}")).status_code == 202


async def test_window_resets_after_expiry(test_app, admin_client):
    test_app.app.state.trigger_rate_limiter = SlidingWindowRateLimiter(
        max_attempts=1, window_seconds=0.05
    )
    runner_id = await _create_runner(admin_client)

    assert (await admin_client.post(f"{API}/triggers/{runner_id}")).status_code == 202
    assert (await admin_client.post(f"{API}/triggers/{runner_id}")).status_code == 429

    await asyncio.sleep(0.1)
    assert (await admin_client.post(f"{API}/triggers/{runner_id}")).status_code == 202
