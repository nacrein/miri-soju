"""The ``,setup automod`` panel: a live control panel for the automod config.

Mirrors the leveling/serverlog panels — toggles persist via ``service.set_*`` and
redraw; modals carry the numeric limits (validated in sync ``apply_*`` helpers that
raise ``ValueError``); a multi-select toggles the filters; Role/Channel selects add
exemptions; a modal adds banned words. Full list management lives in ``,automod``.
"""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.automod import config as amconfig
from src.modules.automod import service

# Model defaults, so the panel renders sensibly before a config row exists.
_DEFAULTS = dict(
    enabled=False, log_only=True, exempt_mods=True, strike_window_hours=24,
    filter_invites=False, filter_links=False, filter_spam=False, filter_mentions=False,
    filter_words=False, filter_caps=False, filter_emoji=False, block_everyone=True,
    mention_limit=5, caps_percent=70, caps_min_len=10, emoji_limit=10,
    spam_count=5, spam_interval=5, duplicate_threshold=3,
    timeout_at=2, timeout_minutes=10, timeout2_at=3, timeout2_minutes=60, kick_at=4, ban_at=5,
)


# ── validators (pure; raise ValueError) ────────────────────────────────────────

def _int(raw: str, label: str, lo: int, hi: int) -> int:
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.") from None
    if not lo <= n <= hi:
        raise ValueError(f"{label} must be between {lo} and {hi}.")
    return n


def _two_ints(raw: str, label: str) -> tuple[str, str]:
    parts = str(raw).replace("/", " ").split()
    if len(parts) != 2:
        raise ValueError(f"{label} needs two numbers, e.g. `5 10`.")
    return parts[0], parts[1]


def apply_filter_limits(mention, caps, emoji, spam, dup) -> dict:
    caps_pct, caps_len = _two_ints(caps, "Caps")
    spam_count, spam_int = _two_ints(spam, "Spam")
    return dict(
        mention_limit=_int(mention, "Mention limit", amconfig.MENTION_MIN, amconfig.MENTION_MAX),
        caps_percent=_int(caps_pct, "Caps percent", amconfig.CAPS_PCT_MIN, amconfig.CAPS_PCT_MAX),
        caps_min_len=_int(caps_len, "Caps min length", amconfig.CAPS_LEN_MIN, amconfig.CAPS_LEN_MAX),
        emoji_limit=_int(emoji, "Emoji limit", amconfig.EMOJI_MIN, amconfig.EMOJI_MAX),
        spam_count=_int(spam_count, "Spam count", amconfig.SPAM_COUNT_MIN, amconfig.SPAM_COUNT_MAX),
        spam_interval=_int(spam_int, "Spam interval", amconfig.SPAM_INTERVAL_MIN, amconfig.SPAM_INTERVAL_MAX),
        duplicate_threshold=_int(dup, "Duplicates", amconfig.DUP_MIN, amconfig.DUP_MAX),
    )


def apply_escalation(window, timeout, timeout2, kick, ban) -> dict:
    t1_at, t1_min = _two_ints(timeout, "Timeout 1")
    t2_at, t2_min = _two_ints(timeout2, "Timeout 2")
    return dict(
        strike_window_hours=_int(window, "Strike window", amconfig.WINDOW_MIN, amconfig.WINDOW_MAX),
        timeout_at=_int(t1_at, "Timeout 1 strikes", amconfig.STRIKE_MIN, amconfig.STRIKE_MAX),
        timeout_minutes=_int(t1_min, "Timeout 1 minutes", amconfig.MINUTES_MIN, amconfig.MINUTES_MAX),
        timeout2_at=_int(t2_at, "Timeout 2 strikes", amconfig.STRIKE_MIN, amconfig.STRIKE_MAX),
        timeout2_minutes=_int(t2_min, "Timeout 2 minutes", amconfig.MINUTES_MIN, amconfig.MINUTES_MAX),
        kick_at=_int(kick, "Kick at", amconfig.STRIKE_MIN, amconfig.STRIKE_MAX),
        ban_at=_int(ban, "Ban at", amconfig.STRIKE_MIN, amconfig.STRIKE_MAX),
    )


def apply_words(raw: str) -> list[str]:
    words = [w.strip() for w in str(raw).replace(",", "\n").splitlines() if w.strip()]
    if not words:
        raise ValueError("Enter at least one word.")
    return words


# ── modals ──────────────────────────────────────────────────────────────────────

class _LimitsModal(discord.ui.Modal, title="Filter limits"):
    def __init__(self, view: AutomodSetupView) -> None:
        super().__init__()
        self._view = view
        self.mention = discord.ui.TextInput(label="Max mentions per message", default=str(view.get("mention_limit")))
        self.caps = discord.ui.TextInput(label="Caps: percent and min length", default=f"{view.get('caps_percent')} {view.get('caps_min_len')}")
        self.emoji = discord.ui.TextInput(label="Max emoji per message", default=str(view.get("emoji_limit")))
        self.spam = discord.ui.TextInput(label="Spam: messages and seconds", default=f"{view.get('spam_count')} {view.get('spam_interval')}")
        self.dup = discord.ui.TextInput(label="Duplicate messages to trip", default=str(view.get("duplicate_threshold")))
        for item in (self.mention, self.caps, self.emoji, self.spam, self.dup):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            fields = apply_filter_limits(self.mention.value, self.caps.value, self.emoji.value, self.spam.value, self.dup.value)
        except ValueError as exc:
            await interaction.response.send_message(embed=embeds.error(str(exc)), ephemeral=True)
            return
        await service.set_thresholds(self._view.guild_id, **fields)
        await self._view.refresh(interaction)


class _EscalationModal(discord.ui.Modal, title="Escalation thresholds"):
    def __init__(self, view: AutomodSetupView) -> None:
        super().__init__()
        self._view = view
        # NB: do NOT name a field ``self.timeout`` — that shadows Modal's reserved
        # timeout attribute (float | None) and makes discord.py crash on send_modal.
        self.window = discord.ui.TextInput(label="Strike window (hours)", default=str(view.get("strike_window_hours")))
        self.timeout1 = discord.ui.TextInput(label="Timeout 1: strikes and minutes", default=f"{view.get('timeout_at')} {view.get('timeout_minutes')}")
        self.timeout2 = discord.ui.TextInput(label="Timeout 2: strikes and minutes", default=f"{view.get('timeout2_at')} {view.get('timeout2_minutes')}")
        self.kick = discord.ui.TextInput(label="Kick at strikes (0 = off)", default=str(view.get("kick_at")))
        self.ban = discord.ui.TextInput(label="Ban at strikes (0 = off)", default=str(view.get("ban_at")))
        for item in (self.window, self.timeout1, self.timeout2, self.kick, self.ban):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            fields = apply_escalation(self.window.value, self.timeout1.value, self.timeout2.value, self.kick.value, self.ban.value)
        except ValueError as exc:
            await interaction.response.send_message(embed=embeds.error(str(exc)), ephemeral=True)
            return
        await service.set_thresholds(self._view.guild_id, **fields)
        await self._view.refresh(interaction)


class _WordsModal(discord.ui.Modal, title="Add banned words"):
    def __init__(self, view: AutomodSetupView) -> None:
        super().__init__()
        self._view = view
        self.words = discord.ui.TextInput(
            label="Words (one per line, or comma-separated)",
            style=discord.TextStyle.paragraph, max_length=1000,
            placeholder="slur1\nbadphrase\n…",
        )
        self.add_item(self.words)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            words = apply_words(self.words.value)
        except ValueError as exc:
            await interaction.response.send_message(embed=embeds.error(str(exc)), ephemeral=True)
            return
        for word in words:
            await service.add_word(self._view.guild_id, word)
        await self._view.refresh(interaction)


# ── selects ──────────────────────────────────────────────────────────────────────

class _FilterSelect(discord.ui.Select):
    def __init__(self) -> None:
        super().__init__(placeholder="Choose which filters are on…", row=1,
                         min_values=0, max_values=len(amconfig.FILTERS),
                         options=[discord.SelectOption(label=n.capitalize(), value=n) for n in amconfig.FILTERS])

    async def callback(self, interaction: discord.Interaction) -> None:
        view: AutomodSetupView = self.view
        chosen = set(self.values)
        await service.set_filters(view.guild_id, **{flag: (name in chosen) for name, flag in amconfig.FILTER_FLAG.items()})
        await view.refresh(interaction)


class _ExemptRoleSelect(discord.ui.RoleSelect):
    def __init__(self) -> None:
        super().__init__(placeholder="Add exempt roles…", row=2, min_values=0, max_values=10)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: AutomodSetupView = self.view
        for role in self.values:
            await service.add_exempt_role(view.guild_id, role.id)
        await view.refresh(interaction)


class _ExemptChannelSelect(discord.ui.ChannelSelect):
    def __init__(self) -> None:
        super().__init__(placeholder="Add exempt channels…", row=3, min_values=0, max_values=10,
                         channel_types=[discord.ChannelType.text])

    async def callback(self, interaction: discord.Interaction) -> None:
        view: AutomodSetupView = self.view
        for ch in self.values:
            await service.add_exempt_channel(view.guild_id, ch.id)
        await view.refresh(interaction)


# ── the panel ─────────────────────────────────────────────────────────────────

class AutomodSetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self._cfg = None
        self._counts = {"words": 0, "domains": 0, "roles": 0, "channels": 0}
        self._filter_select = _FilterSelect()
        self.add_item(self._filter_select)
        self.add_item(_ExemptRoleSelect())
        self.add_item(_ExemptChannelSelect())

    def get(self, field: str):
        return getattr(self._cfg, field) if self._cfg is not None else _DEFAULTS[field]

    async def load(self) -> None:
        self._cfg = await service.get_config(self.guild_id)
        lists = await service.get_lists(self.guild_id)
        self._counts = {
            "words": len(lists["word_list"]), "domains": len(lists["domains"]),
            "roles": len(lists["roles"]), "channels": len(lists["channels"]),
        }
        self._sync()

    def _sync(self) -> None:
        on = self.get("enabled")
        self._enabled_btn.label = f"AutoMod: {'On' if on else 'Off'}"
        self._enabled_btn.style = discord.ButtonStyle.success if on else discord.ButtonStyle.secondary
        dry = self.get("log_only")
        self._mode_btn.label = f"Mode: {'Dry-run' if dry else 'LIVE'}"
        self._mode_btn.style = discord.ButtonStyle.secondary if dry else discord.ButtonStyle.danger
        exm = self.get("exempt_mods")
        self._exemptmods_btn.label = f"Exempt mods: {'On' if exm else 'Off'}"
        self._exemptmods_btn.style = discord.ButtonStyle.success if exm else discord.ButtonStyle.secondary
        for opt in self._filter_select.options:
            opt.default = self.get(amconfig.FILTER_FLAG[opt.value])

    def render(self) -> discord.Embed:
        active = [n for n in amconfig.FILTERS if self.get(amconfig.FILTER_FLAG[n])]
        e = embeds.info("", f"{Emojis.SHIELD} AutoMod Setup")
        e.add_field(name="Status", value="On" if self.get("enabled") else "Off")
        e.add_field(
            name="Mode", value="Dry-run (safe)" if self.get("log_only") else "LIVE (enforcing)",
        )
        e.add_field(name="Exempt mods", value="Yes" if self.get("exempt_mods") else "No")
        e.add_field(name="Filters on", value=", ".join(active) or "none", inline=False)
        e.add_field(
            name="Limits",
            value=(f"mentions ≤{self.get('mention_limit')} · caps {self.get('caps_percent')}%/"
                   f"{self.get('caps_min_len')} · emoji ≤{self.get('emoji_limit')} · "
                   f"spam {self.get('spam_count')}/{self.get('spam_interval')}s · "
                   f"dup {self.get('duplicate_threshold')}"),
            inline=False,
        )
        e.add_field(
            name=f"Escalation (window {self.get('strike_window_hours')}h)",
            value=(f"timeout @{self.get('timeout_at')}={self.get('timeout_minutes')}m · "
                   f"timeout @{self.get('timeout2_at')}={self.get('timeout2_minutes')}m · "
                   f"kick @{self.get('kick_at')} · ban @{self.get('ban_at')}  (0 = off)"),
            inline=False,
        )
        e.add_field(name="Banned words", value=str(self._counts["words"]))
        e.add_field(name="Allowed domains", value=str(self._counts["domains"]))
        e.add_field(name="Exempt", value=f"{self._counts['roles']} role(s) · {self._counts['channels']} channel(s)")
        e.set_footer(text="Manage lists with ,automod words / allow / exempt")
        return self._stamp(e)

    # ── row 0 toggles ───────────────────────────────────────────────────────────

    @discord.ui.button(label="AutoMod: Off", style=discord.ButtonStyle.secondary, row=0)
    async def _enabled_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_enabled(self.guild_id, not self.get("enabled"))
        await self.refresh(interaction)

    @discord.ui.button(label="Mode: Dry-run", style=discord.ButtonStyle.secondary, row=0)
    async def _mode_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_log_only(self.guild_id, not self.get("log_only"))
        await self.refresh(interaction)

    @discord.ui.button(label="Exempt mods: On", style=discord.ButtonStyle.success, row=0)
    async def _exemptmods_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_exempt_mods(self.guild_id, not self.get("exempt_mods"))
        await self.refresh(interaction)

    # ── row 4 modals + done/close ────────────────────────────────────────────────

    @discord.ui.button(label="Limits", emoji=Emojis.SETTINGS, style=discord.ButtonStyle.secondary, row=4)
    async def _limits_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_LimitsModal(self))

    @discord.ui.button(label="Escalation", style=discord.ButtonStyle.secondary, row=4)
    async def _escalation_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_EscalationModal(self))

    @discord.ui.button(label="Add words", style=discord.ButtonStyle.secondary, row=4)
    async def _words_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_WordsModal(self))

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=4)
    async def _done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embeds.success("AutoMod setup saved.", "Done"), view=self)
        self.stop()

    @discord.ui.button(label="Close", emoji=Emojis.CLOSE, style=discord.ButtonStyle.danger, row=4)
    async def _close_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()
