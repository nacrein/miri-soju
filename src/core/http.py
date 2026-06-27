"""Fetch remote bytes for asset uploads (emoji, sticker, webhook avatars)."""

from __future__ import annotations

import aiohttp

_MAX_BYTES = 8 * 1024 * 1024  # Discord's asset ceiling


async def fetch_bytes(url: str, max_bytes: int = _MAX_BYTES) -> bytes:
    """Download a URL's body, rejecting anything over max_bytes."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise ValueError("Couldn't download that link.")
            data = await resp.content.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError("That file is too large.")
            return data
