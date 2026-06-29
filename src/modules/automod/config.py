"""AutoMod tuning: validation ranges, filter names, and the strike→action mapping.

Pure — no Discord, no DB. The ranges are shared by the ``,automod`` commands and the
``,setup automod`` panel so they can't drift; ``action_for`` is the escalation engine
and is unit-tested directly.
"""

from __future__ import annotations

# Validation ranges (min, max), inclusive.
MENTION_MIN, MENTION_MAX = 1, 50
CAPS_PCT_MIN, CAPS_PCT_MAX = 50, 100
CAPS_LEN_MIN, CAPS_LEN_MAX = 1, 200
EMOJI_MIN, EMOJI_MAX = 1, 50
SPAM_COUNT_MIN, SPAM_COUNT_MAX = 2, 30
SPAM_INTERVAL_MIN, SPAM_INTERVAL_MAX = 1, 60
DUP_MIN, DUP_MAX = 2, 20
WINDOW_MIN, WINDOW_MAX = 1, 168          # strike-decay window, hours (1h … 7d)
STRIKE_MIN, STRIKE_MAX = 0, 100          # an escalation threshold (0 disables the tier)
MINUTES_MIN, MINUTES_MAX = 1, 40320      # timeout minutes, capped at Discord's 28 days

# Filter names accepted by `,automod filter <name> <on|off>` and the panel select.
FILTER_FLAG = {
    "invites": "filter_invites",
    "links": "filter_links",
    "spam": "filter_spam",
    "mentions": "filter_mentions",
    "words": "filter_words",
    "caps": "filter_caps",
    "emoji": "filter_emoji",
}
FILTERS = tuple(FILTER_FLAG)


def action_for(strike_count: int, cfg) -> tuple[str, int | None]:
    """Map a strike count to ``(action, minutes)``.

    Picks the most severe tier whose threshold ``<= strike_count``; a tier whose
    threshold is 0/None is disabled. Below every threshold the action is ``warn``
    (message still deleted). Thresholds are expected to ascend
    timeout → timeout2 → kick → ban; a mod who inverts them just gets the more
    severe tier sooner, never a crash.
    """
    n = strike_count
    if cfg.ban_at and n >= cfg.ban_at:
        return ("ban", None)
    if cfg.kick_at and n >= cfg.kick_at:
        return ("kick", None)
    if cfg.timeout2_at and n >= cfg.timeout2_at:
        return ("timeout", cfg.timeout2_minutes)
    if cfg.timeout_at and n >= cfg.timeout_at:
        return ("timeout", cfg.timeout_minutes)
    return ("warn", None)
