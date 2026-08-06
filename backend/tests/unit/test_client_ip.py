"""Unit tests for get_client_ip (trusted-proxies handling, spec 9.4.3)."""

from types import SimpleNamespace

from starlette.requests import Request

from cron_dok.adapters.input.http.dependencies import get_client_ip
from cron_dok.config import Settings


def _request(
    *,
    peer: str = "10.0.0.2",
    forwarded_for: str | None = None,
    trusted_proxies: str = "",
) -> Request:
    headers = [(b"x-forwarded-for", forwarded_for.encode())] if forwarded_for else []
    app = SimpleNamespace(state=SimpleNamespace(settings=Settings(trusted_proxies=trusted_proxies)))
    return Request({"type": "http", "headers": headers, "client": (peer, 1234), "app": app})


def test_peer_ip_is_used_by_default() -> None:
    request = _request(forwarded_for="1.2.3.4")
    assert get_client_ip(request) == "10.0.0.2"


def test_forwarded_for_is_never_trusted_from_an_undeclared_peer() -> None:
    request = _request(forwarded_for="1.2.3.4", trusted_proxies="10.0.0.9")
    assert get_client_ip(request) == "10.0.0.2"


def test_first_forwarded_for_entry_is_used_from_a_trusted_proxy() -> None:
    request = _request(forwarded_for="1.2.3.4, 10.0.0.2", trusted_proxies="10.0.0.2")
    assert get_client_ip(request) == "1.2.3.4"


def test_trusted_proxy_without_forwarded_for_falls_back_to_peer() -> None:
    request = _request(trusted_proxies="10.0.0.2")
    assert get_client_ip(request) == "10.0.0.2"
