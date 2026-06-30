"""Tests for the SSRF guard in ``fetch_bytes``.

URLs come from guild users, so the fetch must refuse non-http(s) schemes and any
host that resolves to a private/loopback/link-local/reserved address, and must
not follow redirects into the internal network.
"""

from __future__ import annotations

import pytest

from src.core import http


def _patch_resolve(monkeypatch, ip: str) -> None:
    """Make every host resolve to ``ip`` so we can drive the IP-class checks."""
    monkeypatch.setattr(
        http.socket,
        "getaddrinfo",
        lambda host, port: [(None, None, None, "", (ip, 0))],
    )


async def test_rejects_non_http_scheme(monkeypatch):
    _patch_resolve(monkeypatch, "1.1.1.1")  # public, so only scheme can fail
    for url in ("file:///etc/passwd", "ftp://example.com/x", "gopher://x"):
        with pytest.raises(ValueError, match="http"):
            await http.fetch_bytes(url)


async def test_rejects_loopback_host(monkeypatch):
    _patch_resolve(monkeypatch, "127.0.0.1")
    with pytest.raises(ValueError, match="allowed"):
        await http.fetch_bytes("http://localhost/secret")


async def test_rejects_ipv6_loopback(monkeypatch):
    _patch_resolve(monkeypatch, "::1")
    with pytest.raises(ValueError, match="allowed"):
        await http.fetch_bytes("http://[::1]/secret")


async def test_rejects_link_local_metadata(monkeypatch):
    _patch_resolve(monkeypatch, "169.254.169.254")  # cloud metadata endpoint
    with pytest.raises(ValueError, match="allowed"):
        await http.fetch_bytes("http://169.254.169.254/latest/meta-data/")


async def test_rejects_private_rfc1918(monkeypatch):
    _patch_resolve(monkeypatch, "10.0.0.5")
    with pytest.raises(ValueError, match="allowed"):
        await http.fetch_bytes("http://internal.example/x")


async def test_rejects_unresolvable_host(monkeypatch):
    def boom(host, port):
        raise http.socket.gaierror("nope")

    monkeypatch.setattr(http.socket, "getaddrinfo", boom)
    with pytest.raises(ValueError):
        await http.fetch_bytes("http://does-not-exist.invalid/x")


async def test_public_host_passes_validation_then_downloads(monkeypatch):
    """A public host clears validation; the rest of the download path runs as before."""
    _patch_resolve(monkeypatch, "93.184.216.34")  # example.com, public
    calls: dict[str, object] = {}

    class _Resp:
        status = 200

        class content:
            @staticmethod
            async def read(n):
                return b"hello"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    class _Session:
        def __init__(self, *a, **k):
            calls["timeout"] = k.get("timeout")

        def get(self, url, allow_redirects=True):
            calls["allow_redirects"] = allow_redirects
            return _Resp()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(http.aiohttp, "ClientSession", _Session)
    data = await http.fetch_bytes("https://example.com/avatar.png")
    assert data == b"hello"
    # redirects are disabled and a total timeout is set
    assert calls["allow_redirects"] is False
    assert calls["timeout"] is http._TIMEOUT
