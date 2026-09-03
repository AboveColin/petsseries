"""Shared fixtures for the petsseries tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def no_outbound_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that tries to resolve a name outside loopback.

    This is a tripwire, not a limit: nothing here talks to the Philips or Tuya
    clouds, so correct tests never notice it exists. It is here because this
    library dispenses food, and a test aimed at a real account looks exactly
    like one aimed at a fixture.

    The guard sits on getaddrinfo rather than on connect, because that is where
    every outbound connection starts and it is the last point at which the
    hostname is still readable.
    """
    import socket

    allowed = {"127.0.0.1", "::1", "localhost", ""}
    real_getaddrinfo = socket.getaddrinfo

    def guarded(host, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        if host is not None and str(host) not in allowed:
            raise AssertionError(
                f"a test tried to reach {host!r}. Tests must not talk to the "
                "Philips or Tuya clouds."
            )
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", guarded)
