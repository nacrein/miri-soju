"""Shared rendering for ranked "leaderboard" lists.

One look for every board in the bot: 🥇🥈🥉 on the top three, a plain `#n` token
below, the member's display name, and one value per row. Lives in core so the
leaderboard menu and the per-server ``,top`` command render identically without
importing each other.
"""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis

# Top three wear medals; everyone below gets a plain rank token.
_MEDALS = {1: Emojis.MEDAL_GOLD, 2: Emojis.MEDAL_SILVER, 3: Emojis.MEDAL_BRONZE}


def ranked_list(
    guild: discord.Guild | None,
    entries: list[tuple[int, str]],
    title: str,
    *,
    author: discord.abc.User | None = None,
    footer: str | None = None,
    empty: str = "No players yet.",
) -> discord.Embed:
    """Build a ranked list embed from ``[(user_id, value_str), ...]``.

    ``guild`` resolves the display names (falls back to ``User <id>`` when the
    member has left). ``author`` stamps the house invoker row so it survives the
    edit_message redraws a menu does (which bypass the send-time author hook)."""
    if not entries:
        e = embeds.info(empty)
    else:
        lines = []
        for i, (uid, value) in enumerate(entries, 1):
            member = guild.get_member(uid) if guild else None
            name = member.display_name if member else f"User {uid}"
            badge = _MEDALS.get(i, f"`#{i}`")
            lines.append(f"{badge} **{name}** · {value}")
        e = embeds.info("\n".join(lines), f"{Emojis.TROPHY} {title}")
    if footer:
        e.set_footer(text=footer)
    embeds.apply_author(e, author)
    return e
