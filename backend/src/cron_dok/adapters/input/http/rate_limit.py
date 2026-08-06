"""Generic in-memory sliding-window rate limiter (spec 9.4.3, plan 3.2).

Shared by the login endpoint (10 attempts/minute per IP) and the manual
trigger endpoint (100 requests/minute per identity). One instance per
application (stored in ``app.state``); process-local by design — valid for
the single-node MVP, documented as a known limitation for multi-node
deployments (spec section 10).
"""

import math
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """Sliding-window limiter keyed by an arbitrary string identity."""

    def __init__(self, max_attempts: int, window_seconds: float = 60.0) -> None:
        """Initialize the limiter.

        Args:
            max_attempts: attempts allowed per window and key.
            window_seconds: sliding window length in seconds.
        """
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Record an attempt for ``key``; return False when the limit is hit."""
        self.purge_stale_keys()
        now = time.monotonic()
        attempts = self._attempts[key]
        while attempts and now - attempts[0] >= self._window_seconds:
            attempts.popleft()
        if len(attempts) >= self._max_attempts:
            return False
        attempts.append(now)
        return True

    def retry_after(self, key: str) -> int:
        """Seconds until ``key``'s oldest attempt falls out of the window."""
        attempts = self._attempts[key]
        if not attempts:
            return 0
        remaining = self._window_seconds - (time.monotonic() - attempts[0])
        return max(1, math.ceil(remaining))

    def purge_stale_keys(self) -> None:
        """Drop keys whose attempts all fell out of the window.

        The identity dict would otherwise grow without bound — every distinct
        client IP / identity ever seen stays around as an empty deque. Cheap
        to call opportunistically (e.g. on every allowed attempt) since the
        dict only holds identities active within the last window.
        """
        now = time.monotonic()
        stale = [
            key
            for key, attempts in self._attempts.items()
            if not attempts or now - attempts[-1] >= self._window_seconds
        ]
        for key in stale:
            del self._attempts[key]
