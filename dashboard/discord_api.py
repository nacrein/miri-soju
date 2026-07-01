"""Thin async client for the bits of the Discord REST API the dashboard needs.

Two kinds of calls:
- **Bearer** (the logged-in user's OAuth token): who they are, what guilds they're
  in. Used only during the login callback.
- **Bot** (the bot's own token, reused from ``config.settings``): the bot's guild
  list, plus each guild's roles and channels for the config dropdowns.

Bot-auth results are cached with a short TTL (the same ``TTLCache`` the bot uses)
to stay well clear of Discord's rate limits, since roles/channels change rarely.
"""

from __future__ import annotations

import httpx

from config.settings import get_settings
from dashboard.config import get_dashboard_settings
from src.core.cache import TTLCache

API_BASE = "https://discord.com/api/v10"

# Permission bits that mean "can manage this server" for dashboard purposes.
PERM_ADMINISTRATOR = 0x8
PERM_MANAGE_GUILD = 0x20

# Channel types that can receive log/announcement messages.
TEXT_CHANNEL_TYPES = {0, 5}  # GUILD_TEXT, GUILD_ANNOUNCEMENT
VOICE_CHANNEL_TYPES = {2, 13}  # GUILD_VOICE, GUILD_STAGE_VOICE

# GET /users/@me/guilds returns at most 200 guilds per page; paginate with the
# ``after`` cursor (the highest snowflake seen so far) until a short page.
GUILDS_PAGE_LIMIT = 200

_bot_guilds_cache: TTLCache[str, set[int]] = TTLCache(ttl_seconds=120)
_roles_cache: TTLCache[int, list[dict]] = TTLCache(ttl_seconds=60)
_channels_cache: TTLCache[int, list[dict]] = TTLCache(ttl_seconds=60)
_voice_channels_cache: TTLCache[int, list[dict]] = TTLCache(ttl_seconds=60)


def _bot_headers() -> dict[str, str]:
    return {"Authorization": f"Bot {get_settings().bot_token}"}


def authorize_url(state: str) -> str:
    """The Discord consent URL to redirect the user to."""
    s = get_dashboard_settings()
    from urllib.parse import urlencode

    query = urlencode(
        {
            "client_id": s.discord_client_id,
            "redirect_uri": s.oauth_redirect_uri,
            "response_type": "code",
            "scope": "identify guilds",
            "state": state,
            "prompt": "none",
        }
    )
    return f"{API_BASE}/oauth2/authorize?{query}"


async def exchange_code(code: str) -> dict:
    """Trade an authorization code for an access token."""
    s = get_dashboard_settings()
    data = {
        "client_id": s.discord_client_id,
        "client_secret": s.discord_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": s.oauth_redirect_uri,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{API_BASE}/oauth2/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    resp.raise_for_status()
    return resp.json()


async def fetch_user(access_token: str) -> dict:
    """The authorizing user's account (id, username, avatar)."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{API_BASE}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    resp.raise_for_status()
    return resp.json()


async def fetch_user_guilds(access_token: str) -> list[dict]:
    """Every guild the user is in, each with their ``permissions`` bitfield.

    Paginated: a user in >200 guilds would otherwise have the tail silently
    dropped, hiding servers they can actually manage.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    guilds: list[dict] = []
    after = "0"
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            resp = await client.get(
                f"{API_BASE}/users/@me/guilds",
                headers=headers,
                params={"limit": GUILDS_PAGE_LIMIT, "after": after},
            )
            resp.raise_for_status()
            page = resp.json()
            guilds.extend(page)
            if len(page) < GUILDS_PAGE_LIMIT:
                break
            after = str(max(int(g["id"]) for g in page))
    return guilds


async def fetch_bot_guild_ids() -> set[int]:
    """The set of guild ids the bot itself is a member of (cached).

    Paginated: without the ``after`` loop a bot in >200 guilds would only see
    its first page, and auth would 403 admins of every omitted guild.
    """
    cached = _bot_guilds_cache.get("ids")
    if cached is not None:
        return cached
    ids: set[int] = set()
    after = "0"
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            resp = await client.get(
                f"{API_BASE}/users/@me/guilds",
                headers=_bot_headers(),
                params={"limit": GUILDS_PAGE_LIMIT, "after": after},
            )
            resp.raise_for_status()
            page = resp.json()
            for g in page:
                ids.add(int(g["id"]))
            if len(page) < GUILDS_PAGE_LIMIT:
                break
            after = str(max(int(g["id"]) for g in page))
    _bot_guilds_cache.set("ids", ids)
    return ids


async def fetch_guild_roles(guild_id: int) -> list[dict]:
    """Assignable roles for a guild, alphabetical. Excludes @everyone and
    integration-managed roles (bot/booster roles can't be handed out as rewards)."""
    cached = _roles_cache.get(guild_id)
    if cached is not None:
        return cached
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{API_BASE}/guilds/{guild_id}/roles", headers=_bot_headers()
        )
    resp.raise_for_status()
    roles = [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "color": r.get("color", 0),
            "managed": r.get("managed", False),
        }
        for r in resp.json()
        if str(r["id"]) != str(guild_id)  # @everyone shares the guild id
        and not r.get("managed", False)   # bot/integration/booster roles aren't assignable
    ]
    roles.sort(key=lambda r: r["name"].lower())
    _roles_cache.set(guild_id, roles)
    return roles


async def fetch_guild_channels(guild_id: int) -> list[dict]:
    """Text-capable channels for a guild, in display order."""
    cached = _channels_cache.get(guild_id)
    if cached is not None:
        return cached
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{API_BASE}/guilds/{guild_id}/channels", headers=_bot_headers()
        )
    resp.raise_for_status()
    channels = [
        {"id": str(c["id"]), "name": c["name"], "position": c.get("position", 0)}
        for c in resp.json()
        if c.get("type") in TEXT_CHANNEL_TYPES
    ]
    channels.sort(key=lambda c: c["position"])
    _channels_cache.set(guild_id, channels)
    return channels


async def fetch_guild_voice_channels(guild_id: int) -> list[dict]:
    """Voice channels for a guild, in display order (for VoiceMaster's select)."""
    cached = _voice_channels_cache.get(guild_id)
    if cached is not None:
        return cached
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{API_BASE}/guilds/{guild_id}/channels", headers=_bot_headers()
        )
    resp.raise_for_status()
    channels = [
        {"id": str(c["id"]), "name": c["name"], "position": c.get("position", 0)}
        for c in resp.json()
        if c.get("type") in VOICE_CHANNEL_TYPES
    ]
    channels.sort(key=lambda c: c["position"])
    _voice_channels_cache.set(guild_id, channels)
    return channels


def manageable(user_guild: dict) -> bool:
    """True if the user can manage this guild (owner, admin, or Manage Server)."""
    if user_guild.get("owner"):
        return True
    perms = int(user_guild.get("permissions", 0))
    return bool(perms & (PERM_ADMINISTRATOR | PERM_MANAGE_GUILD))
