"""Central emoji registry. The single source for every emoji the bot uses.

Reference emoji as Emojis.NAME everywhere; never write a raw <:name:id> string
in other files. Every value starts as a unicode default so the bot works now.
To use custom art later, upload it and replace the one line here with its string
(format: "<:name:1234567890>" or "<a:name:1234567890>" for animated). Calling
code never changes.

These are the bot's identity and are the same in every server; they are not
per-server configurable.
"""

from __future__ import annotations


class Emojis:
    # ── status ──────────────────────────────────────────────────────────────
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    QUESTION = "❔"
    LOADING = "⏳"

    # ── moderation ──────────────────────────────────────────────────────────
    BAN = "🔨"
    UNBAN = "🔓"
    KICK = "👢"
    TIMEOUT = "🔇"
    UNTIMEOUT = "🔊"
    PURGE = "🧹"
    WARN = "📋"
    LOCK = "🔒"
    UNLOCK = "🔓"
    SHIELD = "🛡️"

    # ── server events (audit log) ───────────────────────────────────────────
    JOIN = "📥"
    LEAVE = "📤"
    MESSAGE_DELETE = "🗑️"
    MESSAGE_EDIT = "✏️"
    CHANNEL = "📺"
    ROLE = "🎭"

    # ── economy / currency ──────────────────────────────────────────────────
    BITS = "🪙"
    GEM = "💎"
    BANK = "🏦"
    DAILY = "📅"
    GIFT = "🎁"
    SHOP = "🛒"

    # ── gambling ────────────────────────────────────────────────────────────
    DICE = "🎲"
    SLOTS = "🎰"
    COIN_FLIP = "🪙"
    CARD = "🃏"
    WIN = "🎉"
    LOSE = "💀"

    # ── activity / leveling ─────────────────────────────────────────────────
    XP = "⭐"
    LEVEL_UP = "🆙"
    VOICE = "🎙️"
    MESSAGE = "💬"
    TROPHY = "🏆"
    RANK = "📊"
    FIRE = "🔥"

    # ── ui / navigation ─────────────────────────────────────────────────────
    ARROW_LEFT = "◀️"
    ARROW_RIGHT = "▶️"
    FIRST = "⏮️"
    LAST = "⏭️"
    BULLET = "•"
    ONLINE = "🟢"
    IDLE = "🟡"
    OFFLINE = "⚫"
    SETTINGS = "⚙️"
    CROWN = "👑"
    CLOCK = "🕒"
