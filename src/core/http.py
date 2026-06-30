"""Fetch remote bytes for asset uploads (emoji, sticker, webhook avatars).

URLs come straight from guild users, so ``fetch_bytes`` is an SSRF surface: it
only allows http(s), refuses to follow redirects, resolves the host and rejects
private/loopback/link-local/reserved addresses (e.g. cloud metadata at
169.254.169.254, localhost, RFC1918 hosts), and caps the total request time.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

import aiohttp

_MAX_BYTES = 8 * 1024 * 1024  # Discord's asset ceiling
_TIMEOUT = aiohttp.ClientTimeout(total=15)  # stop slow/streaming URLs tying up the loop


def _reject_internal_host(host: str) -> None:
    """Resolve ``host`` and raise ValueError if any address is non-public."""
    if not host:
        raise ValueError("Couldn't download that link.")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError("Couldn't download that link.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise ValueError("That host isn't allowed.")


def _validate_url(url: str) -> None:
    """Allow only http(s) to a public host; reject everything else."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError("Only http(s) links are allowed.")
    _reject_internal_host(parts.hostname or "")


async def fetch_bytes(url: str, max_bytes: int = _MAX_BYTES) -> bytes:
    """Download a URL's body, rejecting anything over max_bytes.

    Validates the URL is http(s) to a public host before connecting and disables
    redirects so a public host can't 302 into the internal network.
    """
    _validate_url(url)
    async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
        async with session.get(url, allow_redirects=False) as resp:
            if resp.status != 200:
                raise ValueError("Couldn't download that link.")
            data = await resp.content.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError("That file is too large.")
            return data
