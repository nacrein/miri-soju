"""Central emoji registry. The single source for every emoji the bot uses.

Reference emoji as ``Emojis.NAME`` everywhere; never write a raw ``<:name:id>``
string in another file.

Plugging in custom art
----------------------
Every emoji is declared with a placeholder id of ``0`` and a unicode fallback::

    SUCCESS = _emoji("success", id=0, fallback="✅")

While the id stays ``0`` the fallback unicode is used, so the bot looks right
today and nothing (buttons included) breaks. Upload your custom emoji, copy its
numeric id, and drop it in::

    SUCCESS = _emoji("success", id=1234567890123456789, fallback="✅")

That one line now renders ``<:success:1234567890123456789>`` everywhere it's
used. Pass ``animated=True`` for an animated emoji (``<a:...>``). Calling code
never changes: these values stay plain strings.

These are the bot's identity and are the same in every server; they are not
per-server configurable.
"""

from __future__ import annotations


def _emoji(name: str, *, id: int = 0, fallback: str, animated: bool = False) -> str:
    """A custom-emoji mention string, or the unicode fallback until an id is set.

    ``id == 0`` is the "not uploaded yet" placeholder: we return the unicode
    fallback so every reference keeps rendering (and emoji-buttons keep working).
    Once a real id is filled in we return the custom token ``<:name:id>``, or
    ``<a:name:id>`` when ``animated`` is set.
    """
    if not id:
        return fallback
    return f"<{'a' if animated else ''}:{name}:{id}>"


class Emojis:
    # ── status ──────────────────────────────────────────────────────────────
    SUCCESS = _emoji("success", id=0, fallback="✅")
    ERROR = _emoji("error", id=0, fallback="❌")
    WARNING = _emoji("warning", id=0, fallback="⚠️")
    INFO = _emoji("info", id=0, fallback="ℹ️")
    QUESTION = _emoji("question", id=0, fallback="❔")
    LOADING = _emoji("loading", id=0, fallback="⏳")

    # ── moderation ──────────────────────────────────────────────────────────
    BAN = _emoji("ban", id=0, fallback="🔨")
    UNBAN = _emoji("unban", id=0, fallback="🔓")
    KICK = _emoji("kick", id=0, fallback="👢")
    TIMEOUT = _emoji("timeout", id=0, fallback="🔇")
    UNTIMEOUT = _emoji("untimeout", id=0, fallback="🔊")
    PURGE = _emoji("purge", id=0, fallback="🧹")
    WARN = _emoji("warn", id=0, fallback="📋")
    LOCK = _emoji("lock", id=0, fallback="🔒")
    UNLOCK = _emoji("unlock", id=0, fallback="🔓")
    SHIELD = _emoji("shield", id=0, fallback="🛡️")

    # ── server events (audit log) ───────────────────────────────────────────
    JOIN = _emoji("join", id=0, fallback="📥")
    LEAVE = _emoji("leave", id=0, fallback="📤")
    MESSAGE_DELETE = _emoji("message_delete", id=0, fallback="🗑️")
    MESSAGE_EDIT = _emoji("message_edit", id=0, fallback="✏️")
    CHANNEL = _emoji("channel", id=0, fallback="📺")
    ROLE = _emoji("role", id=0, fallback="🎭")

    # ── economy / currency ──────────────────────────────────────────────────
    BITS = _emoji("bits", id=0, fallback="🪙")
    GEM = _emoji("gem", id=0, fallback="💎")
    BANK = _emoji("bank", id=0, fallback="🏦")
    DAILY = _emoji("daily", id=0, fallback="📅")
    GIFT = _emoji("gift", id=0, fallback="🎁")
    SHOP = _emoji("shop", id=0, fallback="🛒")

    # ── gambling ────────────────────────────────────────────────────────────
    DICE = _emoji("dice", id=0, fallback="🎲")
    SLOTS = _emoji("slots", id=0, fallback="🎰")
    COIN_FLIP = _emoji("coin_flip", id=0, fallback="🪙")
    CARD = _emoji("card", id=0, fallback="🃏")
    WIN = _emoji("win", id=0, fallback="🎉")
    LOSE = _emoji("lose", id=0, fallback="💀")
    LADDER = _emoji("ladder", id=0, fallback="🪜")
    CRASH = _emoji("crash", id=0, fallback="📈")
    # slot-machine reel faces (the jackpot/diamond reels reuse SLOTS/GEM above)
    CHERRY = _emoji("cherry", id=0, fallback="🍒")
    LEMON = _emoji("lemon", id=0, fallback="🍋")
    BELL = _emoji("bell", id=0, fallback="🔔")
    # playing-card suits (cosmetic; rank decides the hand)
    SUIT_SPADE = _emoji("suit_spade", id=0, fallback="♠")
    SUIT_HEART = _emoji("suit_heart", id=0, fallback="♥")
    SUIT_DIAMOND = _emoji("suit_diamond", id=0, fallback="♦")
    SUIT_CLUB = _emoji("suit_club", id=0, fallback="♣")

    # ── activity / leveling ─────────────────────────────────────────────────
    XP = _emoji("xp", id=0, fallback="⭐")
    STAR = _emoji("star", id=0, fallback="⭐")  # starboard
    TADA = _emoji("tada", id=0, fallback="🎉")  # giveaways
    POLL = _emoji("poll", id=0, fallback="📊")  # polls
    LEVEL_UP = _emoji("level_up", id=0, fallback="🆙")
    VOICE = _emoji("voice", id=0, fallback="🎙️")
    MESSAGE = _emoji("message", id=0, fallback="💬")
    TROPHY = _emoji("trophy", id=0, fallback="🏆")
    MEDAL_GOLD = _emoji("medal_gold", id=0, fallback="🥇")
    MEDAL_SILVER = _emoji("medal_silver", id=0, fallback="🥈")
    MEDAL_BRONZE = _emoji("medal_bronze", id=0, fallback="🥉")
    RANK = _emoji("rank", id=0, fallback="📊")
    FIRE = _emoji("fire", id=0, fallback="🔥")

    # ── ui / navigation ─────────────────────────────────────────────────────
    ARROW_LEFT = _emoji("arrow_left", id=0, fallback="◀️")
    ARROW_RIGHT = _emoji("arrow_right", id=0, fallback="▶️")
    SEARCH = _emoji("search", id=0, fallback="🔍")
    CLOSE = _emoji("close", id=0, fallback="✖️")
    PIN = _emoji("pin", id=0, fallback="📌")
    FIRST = _emoji("first", id=0, fallback="⏮️")
    LAST = _emoji("last", id=0, fallback="⏭️")
    BULLET = _emoji("bullet", id=0, fallback="•")
    ONLINE = _emoji("online", id=0, fallback="🟢")
    IDLE = _emoji("idle", id=0, fallback="🟡")
    OFFLINE = _emoji("offline", id=0, fallback="⚫")
    SETTINGS = _emoji("settings", id=0, fallback="⚙️")
    CROWN = _emoji("crown", id=0, fallback="👑")
    CLOCK = _emoji("clock", id=0, fallback="🕒")
