"""Failure notification webhook (step 3.4; spec 6.4).

When ``CRONDOK_WEBHOOK_URL`` is set, every execution that finishes as
``failed`` (or ``killed`` by timeout — see ``services/execution_queue.py``)
triggers a JSON POST to that URL with a summary and a masked log excerpt.

The service is strictly **fire-and-forget**: each attempt uses a short
timeout, at most one retry is made, and every failure (timeout, connection
error, HTTP error status) is logged but never propagated, so a down webhook
can never break the execution queue consumer.
"""

import logging
from typing import Any, Protocol

import httpx

from cron_dok.domain.entities.execution import Execution
from cron_dok.domain.entities.runner import Runner

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 2
"""Total POST attempts: the first try plus exactly one retry."""


class FailureNotifier(Protocol):
    """Contract the ExecutionQueue depends on for failure notifications."""

    async def notify_failure(self, execution: Execution, runner: Runner, log_excerpt: str) -> None:
        """Notify that ``execution`` failed; must never raise."""


class NotificationService:
    """Posts ``execution.failed`` events to a configured webhook.

    Args:
        webhook_url: destination URL; when ``None`` every call is a no-op.
        timeout: per-attempt HTTP timeout in seconds.
        client: optional prebuilt ``httpx.AsyncClient`` (tests inject one
            with a mock transport); when omitted, a short-lived client is
            created per attempt.
    """

    def __init__(
        self,
        webhook_url: str | None,
        *,
        timeout: float = 5.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = webhook_url
        self._timeout = timeout
        self._client = client

    async def notify_failure(self, execution: Execution, runner: Runner, log_excerpt: str) -> None:
        """POST the failure event, swallowing every error (fire-and-forget).

        Args:
            execution: the finished execution (``failed``, or ``killed`` by
                timeout).
            runner: the runner the execution belongs to.
            log_excerpt: tail of the execution log, already masked with the
                execution's env var values.
        """
        if self._url is None:
            return
        payload = self._build_payload(execution, runner, log_excerpt)
        try:
            await self._post_with_retry(payload)
        except Exception:
            logger.exception(
                "Failure webhook for execution %s gave up; notification lost",
                execution.id,
            )

    @staticmethod
    def _build_payload(execution: Execution, runner: Runner, log_excerpt: str) -> dict[str, Any]:
        """Build the JSON body of the ``execution.failed`` event.

        ``timed_out`` is derived from the status: the queue only notifies
        ``killed`` executions when the kill was caused by the runner timeout.
        """
        return {
            "event": "execution.failed",
            "execution_id": execution.id,
            "runner_id": runner.id,
            "runner_name": runner.name,
            "exit_code": execution.exit_code,
            "timed_out": execution.status == "killed",
            "finished_at": (
                execution.finished_at.isoformat() if execution.finished_at is not None else None
            ),
            "log_excerpt": log_excerpt,
        }

    async def _post_with_retry(self, payload: dict[str, Any]) -> None:
        """POST ``payload`` up to ``_MAX_ATTEMPTS`` times.

        Retries happen on transport errors and 5xx responses; 4xx responses
        are logged and accepted as final (retrying them is pointless).
        """
        assert self._url is not None  # guaranteed by notify_failure
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = await self._post_once(payload)
            except Exception:
                if attempt == _MAX_ATTEMPTS:
                    raise
                logger.warning(
                    "Failure webhook POST %s failed (attempt %d/%d); retrying",
                    self._url,
                    attempt,
                    _MAX_ATTEMPTS,
                )
                continue
            if response.status_code < 500:
                if response.status_code >= 400:
                    logger.warning(
                        "Failure webhook %s responded %s; not retrying",
                        self._url,
                        response.status_code,
                    )
                return
            logger.warning(
                "Failure webhook %s responded %s (attempt %d/%d)",
                self._url,
                response.status_code,
                attempt,
                _MAX_ATTEMPTS,
            )

    async def _post_once(self, payload: dict[str, Any]) -> httpx.Response:
        """Perform a single POST attempt with the configured timeout."""
        assert self._url is not None
        if self._client is not None:
            return await self._client.post(self._url, json=payload, timeout=self._timeout)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            return await client.post(self._url, json=payload)
