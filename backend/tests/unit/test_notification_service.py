"""Unit tests for NotificationService with a mocked httpx transport."""

import json
from datetime import UTC, datetime
from typing import Any

import httpx

from cron_dok.domain.entities.execution import Execution
from cron_dok.domain.entities.runner import Runner
from cron_dok.domain.value_objects.cron_expression import CronExpression
from cron_dok.services.notification_service import NotificationService

WEBHOOK_URL = "https://hooks.example.com/crondok"


def make_execution(**overrides: Any) -> Execution:
    defaults: dict[str, Any] = {
        "id": 7,
        "runner_id": 3,
        "status": "failed",
        "trigger_type": "manual",
        "exit_code": 3,
        "finished_at": datetime(2026, 7, 25, 12, 0, 0, tzinfo=UTC),
    }
    return Execution(**(defaults | overrides))


def make_runner() -> Runner:
    return Runner(
        id=3,
        project_id=1,
        name="nightly-etl",
        script_content="echo hi",
        language="bash",
        cron_expression=CronExpression("* * * * *"),
    )


class TransportSpy:
    """httpx.MockTransport handler recording requests and scripting outcomes."""

    def __init__(self, outcomes: list[httpx.Response | Exception]) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def payloads(self) -> list[dict[str, Any]]:
        return [json.loads(request.content) for request in self.requests]


def make_service(spy: TransportSpy, url: str | None = WEBHOOK_URL) -> NotificationService:
    client = httpx.AsyncClient(transport=httpx.MockTransport(spy.handler))
    return NotificationService(url, timeout=0.1, client=client)


async def test_posts_the_expected_payload() -> None:
    spy = TransportSpy([httpx.Response(200)])
    service = make_service(spy)

    await service.notify_failure(make_execution(), make_runner(), "boom at line 3")

    assert len(spy.requests) == 1
    request = spy.requests[0]
    assert request.url == WEBHOOK_URL
    assert request.method == "POST"
    assert spy.payloads()[0] == {
        "event": "execution.failed",
        "execution_id": 7,
        "runner_id": 3,
        "runner_name": "nightly-etl",
        "exit_code": 3,
        "timed_out": False,
        "finished_at": "2026-07-25T12:00:00+00:00",
        "log_excerpt": "boom at line 3",
    }


async def test_killed_execution_is_reported_as_timed_out() -> None:
    spy = TransportSpy([httpx.Response(200)])
    service = make_service(spy)

    await service.notify_failure(
        make_execution(status="killed", exit_code=-1), make_runner(), "partial output"
    )

    assert spy.payloads()[0]["timed_out"] is True
    assert spy.payloads()[0]["exit_code"] == -1


async def test_no_url_is_a_no_op() -> None:
    spy = TransportSpy([])
    service = make_service(spy, url=None)

    await service.notify_failure(make_execution(), make_runner(), "excerpt")

    assert spy.requests == []


async def test_transport_error_retries_once_and_does_not_propagate() -> None:
    spy = TransportSpy(
        [
            httpx.ConnectTimeout("slow"),
            httpx.ConnectError("down"),
        ]
    )
    service = make_service(spy)

    # First attempt + exactly one retry; the final error is swallowed.
    await service.notify_failure(make_execution(), make_runner(), "excerpt")

    assert len(spy.requests) == 2


async def test_retry_succeeds_on_second_attempt() -> None:
    spy = TransportSpy([httpx.ConnectTimeout("slow"), httpx.Response(200)])
    service = make_service(spy)

    await service.notify_failure(make_execution(), make_runner(), "excerpt")

    assert len(spy.requests) == 2


async def test_server_error_is_retried_once() -> None:
    spy = TransportSpy([httpx.Response(503), httpx.Response(200)])
    service = make_service(spy)

    await service.notify_failure(make_execution(), make_runner(), "excerpt")

    assert len(spy.requests) == 2


async def test_client_error_is_not_retried() -> None:
    spy = TransportSpy([httpx.Response(404)])
    service = make_service(spy)

    await service.notify_failure(make_execution(), make_runner(), "excerpt")

    assert len(spy.requests) == 1


async def test_unexpected_exception_inside_never_propagates() -> None:
    spy = TransportSpy([ValueError("totally broken"), ValueError("still broken")])
    service = make_service(spy)

    await service.notify_failure(make_execution(), make_runner(), "excerpt")

    assert len(spy.requests) == 2
