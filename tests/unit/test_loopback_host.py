"""Unit tests for HTTP loopback host detection (RV-002)."""

from __future__ import annotations

import pytest

from fl_mcp.cli.server import is_loopback_host


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", True),
        ("localhost", True),
        ("::1", True),
        ("[::1]", True),
        ("LOCALHOST", True),
        (" 127.0.0.1 ", True),
        ("0.0.0.0", False),
        ("192.168.1.1", False),
    ],
)
def test_is_loopback_host(host: str, expected: bool) -> None:
    assert is_loopback_host(host) is expected