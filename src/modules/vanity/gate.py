"""The vanity feature gate. Discord-aware (takes a Guild), so it lives outside the
discord-free service and is shared by the cog and the setup panel."""

from __future__ import annotations

import discord


def has_vanity(guild: discord.Guild) -> bool:
    """A vanity URL unlocks at Boost Level 3 (14 boosts) or with Partner/Verified
    status. Check the feature flag, never a hardcoded level."""
    return bool(guild.vanity_url_code) or "VANITY_URL" in guild.features
