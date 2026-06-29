"""Gif routing for the reaction commands, backed by the nekos.best API.

``GET https://nekos.best/api/v2/{action}`` returns ``{"results": [{"url": ...}]}``.
We hold a single :class:`aiohttp.ClientSession` for the whole module (one connection
pool, reused across commands) and close it on cog unload so aiohttp never logs the
"unclosed client session" warning.

The fetch is best-effort: a hiccup degrades to ``None`` and the caller sends a
gif-less embed. We retry exactly once on a timeout or a 5xx, honour ``Retry-After``
on a 429, and route any action the API does not support through ``ENDPOINT_FALLBACKS``
to a related one (so ``pinch`` borrows ``pat`` instead of being special-cased).
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

from src.modules.fun import config

log = logging.getLogger(__name__)

_BASE = "https://nekos.best/api/v2"
# nekos.best returns 403 to requests with no User-Agent, so we always send one.
_USER_AGENT = "miri-discord-bot (https://github.com/nacrein/miri-soju)"
# Cap on how long we'll wait out a 429 before giving up to the gif-less fallback;
# a longer Retry-After means the upstream wants more of a break than a chat command
# should ever block for.
_MAX_RETRY_AFTER = 5.0

# Actions the API has no endpoint for, mapped to the closest one it does. The
# command keeps its own verb ("pinches"); only the gif source is borrowed. Add a
# row here to support a new reaction without an upstream endpoint.
ENDPOINT_FALLBACKS = {
    "pinch": "pat",
}

_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    """The lazily-created module-wide session, with a real total timeout and the
    User-Agent the API requires. Recreated if a prior one was closed."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=config.GIF_TIMEOUT_SECONDS),
            headers={"User-Agent": _USER_AGENT},
        )
    return _session


async def close_session() -> None:
    """Close the shared session. Called from the cog's unload so we never leak it."""
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
    _session = None


async def fetch_gif(action: str) -> str | None:
    """Return a gif URL for ``action``, or ``None`` if the upstream wouldn't give
    us one. Unsupported actions are routed through ``ENDPOINT_FALLBACKS`` first."""
    endpoint = ENDPOINT_FALLBACKS.get(action, action)
    session = _get_session()
    url = f"{_BASE}/{endpoint}"

    # attempt 0 is the real try; attempt 1 is the single retry we allow.
    for attempt in range(2):
        try:
            async with session.get(url) as resp:
                if resp.status == 429:
                    retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                    if attempt == 0 and 0 < retry_after <= _MAX_RETRY_AFTER:
                        await asyncio.sleep(retry_after)
                        continue
                    log.warning("nekos.best rate limited %s (retry=%s)", endpoint, retry_after)
                    return None
                if resp.status >= 500:
                    if attempt == 0:
                        continue  # transient upstream blip: one more shot
                    return None
                if resp.status != 200:
                    return None
                data = await resp.json()
                results = data.get("results") or []
                if results and isinstance(results[0], dict):
                    return results[0].get("url")
                return None
        except (aiohttp.ClientError, TimeoutError):
            if attempt == 0:
                continue  # timeout or connection error: retry once
            log.warning("nekos.best fetch failed for %s", endpoint, exc_info=True)
            return None
    return None


def _parse_retry_after(value: str | None) -> float:
    """Seconds from a ``Retry-After`` header, or 0 if absent or non-numeric.

    nekos.best sends the delta-seconds form; a malformed or HTTP-date value just
    falls through to 0, which routes us to the gif-less fallback."""
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0
