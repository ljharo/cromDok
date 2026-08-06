"""Unit tests for the sliding-window rate limiter."""

import time

from cron_dok.adapters.input.http.rate_limit import SlidingWindowRateLimiter


def test_allow_blocks_after_max_attempts() -> None:
    limiter = SlidingWindowRateLimiter(2, window_seconds=60.0)

    assert limiter.allow("ip-1") is True
    assert limiter.allow("ip-1") is True
    assert limiter.allow("ip-1") is False
    # A different identity is unaffected.
    assert limiter.allow("ip-2") is True
    assert limiter.retry_after("ip-1") >= 1


def test_window_slides_and_stale_keys_are_purged() -> None:
    limiter = SlidingWindowRateLimiter(1, window_seconds=0.05)

    assert limiter.allow("stale-ip") is True
    assert limiter.allow("stale-ip") is False
    time.sleep(0.06)

    # The attempt fell out of the window: allowed again, and the purge
    # triggered by this call drops identities with no recent attempts, so
    # the identity dict does not grow without bound.
    assert limiter.allow("fresh-ip") is True
    assert "stale-ip" not in limiter._attempts
