"""Help categories: the broad groups the help menu shows.

This is the one place to organize the menu. Each entry maps a display category to
a dropdown emoji, a one-line description (shown under the option), and the cogs it
contains. A cog not listed here falls into ``DEFAULT_CATEGORY``, so a brand-new
module still appears automatically; to place it deliberately, just add its cog
class name to the right bucket below.

Keep the number of categories small (≤ ~7); that's the whole point: a short,
human-curated menu instead of one entry per cog.
"""

from __future__ import annotations

from src.core.emojis import Emojis

# Display category -> (dropdown emoji, description, [cog class names grouped under it]).
# Insertion order is the order options appear in the dropdown.
CATEGORIES: dict[str, tuple[str, str, list[str]]] = {
    "Economy": (
        Emojis.BITS,
        "Earn, gamble, and manage your bits.",
        ["Economy", "Leaderboard"],
    ),
    "Leveling": (
        Emojis.XP,
        "XP, ranks, and level rewards.",
        ["Leveling"],
    ),
    "Moderation": (
        Emojis.SHIELD,
        "Keep your server safe and tidy.",
        ["Moderation", "Staff", "ServerLog", "Automod"],
    ),
    "Server Setup": (
        Emojis.SETTINGS,
        "Configure the bot for your server.",
        ["Setup", "Prefix", "ButtonRole", "ReactionRole", "StickyMessage", "Webhook", "Embed",
         "Boosterrole", "Voicemaster", "Vanity"],
    ),
    "Utility": (
        Emojis.INFO,
        "Everyday tools and information.",
        ["Info", "Snipe", "Afk", "Ask", "Reminder", "Timer", "Emoji", "Sticker"],
    ),
    "Music": (
        Emojis.VOICE,
        "Play music in voice channels.",
        ["Music"],
    ),
    "Fun": (
        Emojis.WIN,
        "Reaction gifs and internet-culture nonsense.",
        ["Fun"],
    ),
    "Bot": (
        Emojis.CROWN,
        "About the bot and owner tools.",
        ["Help", "Meta", "Owner"],
    ),
}

# Where an unmapped cog (e.g. a freshly added module) lands until it's assigned.
# Must be a key of CATEGORIES.
DEFAULT_CATEGORY = "Utility"


def category_emoji(name: str) -> str | None:
    """The dropdown emoji for a category, or None if it has none."""
    entry = CATEGORIES.get(name)
    return entry[0] if entry else None


def category_description(name: str) -> str | None:
    """The one-line blurb shown under a category in the dropdown."""
    entry = CATEGORIES.get(name)
    return entry[1] if entry else None


def cog_to_category() -> dict[str, str]:
    """Reverse lookup: cog class name -> the display category it belongs to."""
    mapping: dict[str, str] = {}
    for category, (_emoji, _desc, cog_names) in CATEGORIES.items():
        for cog_name in cog_names:
            mapping[cog_name] = category
    return mapping
