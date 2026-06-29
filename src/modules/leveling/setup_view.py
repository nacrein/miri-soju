"""The ``,setup levels`` panel: a live control panel for the leveling config.

It reads the current ``LevelConfig`` and renders a status embed (the same shape as
``,levels settings``); each control calls an existing ``service.set_*`` setter —
which already persists and invalidates the config cache — then reloads and redraws.
There is no separate save step. Rewards and channel multipliers stay command-only
(``,levels reward`` / ``,levels multiplier``); the panel just shows their counts.

The free-text validation lives in sync ``apply_*`` helpers (testable without a live
Discord) that raise ``ValueError``; the modal catches it and replies ephemerally.
"""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.leveling import config, service


def _parse_int(raw: str, label: str) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.") from None


def apply_xp(rate_raw: str, cooldown_raw: str) -> tuple[int, int]:
    """Validate the XP-settings modal. Returns (rate, cooldown) or raises ValueError."""
    rate = _parse_int(rate_raw, "XP per message")
    cooldown = _parse_int(cooldown_raw, "Cooldown")
    if not config.RATE_MIN <= rate <= config.RATE_MAX:
        raise ValueError(f"XP per message must be between {config.RATE_MIN} and {config.RATE_MAX}.")
    if not config.COOLDOWN_MIN <= cooldown <= config.COOLDOWN_MAX:
        raise ValueError(
            f"Cooldown must be between {config.COOLDOWN_MIN} and {config.COOLDOWN_MAX} seconds."
        )
    return rate, cooldown


def apply_message(text_raw: str) -> str:
    """Validate the level-up-message modal. Returns the cleaned text or raises ValueError."""
    text = str(text_raw).strip()
    if not text:
        raise ValueError("The level-up message can't be empty.")
    if len(text) > config.MESSAGE_MAX:
        raise ValueError(f"Keep the message under {config.MESSAGE_MAX} characters.")
    return text


# ── modals ────────────────────────────────────────────────────────────────────

class _XpModal(discord.ui.Modal, title="XP settings"):
    def __init__(self, view: LevelingSetupView) -> None:
        super().__init__()
        self._view = view
        self.rate_in = discord.ui.TextInput(
            label=f"XP per message ({config.RATE_MIN}-{config.RATE_MAX})",
            default=str(view.rate), max_length=4,
        )
        self.cooldown_in = discord.ui.TextInput(
            label=f"Cooldown seconds ({config.COOLDOWN_MIN}-{config.COOLDOWN_MAX})",
            default=str(view.cooldown), max_length=4,
        )
        for item in (self.rate_in, self.cooldown_in):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            rate, cooldown = apply_xp(str(self.rate_in.value), str(self.cooldown_in.value))
        except ValueError as exc:
            await interaction.response.send_message(embed=embeds.error(str(exc)), ephemeral=True)
            return
        await service.set_rate(self._view.guild_id, rate)
        await service.set_cooldown(self._view.guild_id, cooldown)
        await self._view.refresh(interaction)


class _MessageModal(discord.ui.Modal, title="Level-up message"):
    def __init__(self, view: LevelingSetupView) -> None:
        super().__init__()
        self._view = view
        self.message_in = discord.ui.TextInput(
            label="Message", style=discord.TextStyle.paragraph,
            max_length=config.MESSAGE_MAX, default=view.message_text,
            placeholder="Placeholders: {user} {user.name} {level} {server}",
        )
        self.add_item(self.message_in)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            text = apply_message(str(self.message_in.value))
        except ValueError as exc:
            await interaction.response.send_message(embed=embeds.error(str(exc)), ephemeral=True)
            return
        await service.set_message(self._view.guild_id, text)
        await self._view.refresh(interaction)


class _AnnounceChannelSelect(discord.ui.ChannelSelect):
    """Pick the channel level-ups post in (sets announce mode to 'channel')."""

    def __init__(self) -> None:
        super().__init__(
            placeholder="Announce level-ups in a channel…",
            channel_types=[discord.ChannelType.text], row=2, min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: LevelingSetupView = self.view
        await service.set_channel(view.guild_id, "channel", self.values[0].id)
        await view.refresh(interaction)


# ── the panel ─────────────────────────────────────────────────────────────────

class LevelingSetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self._cfg = None
        self._reward_count = 0
        self._mult_count = 0
        self.add_item(_AnnounceChannelSelect())

    # ── state (filled by load; falls back to defaults when no row exists) ──────

    @property
    def enabled(self) -> bool:
        return bool(self._cfg and self._cfg.enabled)

    @property
    def rate(self) -> int:
        return self._cfg.xp_per_message if self._cfg else config.XP_PER_MESSAGE

    @property
    def cooldown(self) -> int:
        return self._cfg.message_cooldown if self._cfg else config.MESSAGE_COOLDOWN

    @property
    def mode(self) -> str:
        return self._cfg.announce_mode if self._cfg else "here"

    @property
    def channel_id(self) -> int | None:
        return self._cfg.announce_channel_id if self._cfg else None

    @property
    def message_text(self) -> str:
        return self._cfg.level_up_message if self._cfg else config.DEFAULT_LEVEL_MESSAGE

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def load(self) -> None:
        self._cfg = await service.get_config(self.guild_id)
        self._reward_count = len(await service.list_rewards(self.guild_id))
        self._mult_count = len(await service.list_multipliers(self.guild_id))
        self._sync()

    def _sync(self) -> None:
        self._enabled_btn.label = f"Leveling: {'On' if self.enabled else 'Off'}"
        self._enabled_btn.style = (
            discord.ButtonStyle.success if self.enabled else discord.ButtonStyle.secondary
        )
        self._here_btn.style = (
            discord.ButtonStyle.primary if self.mode == "here" else discord.ButtonStyle.secondary
        )
        self._dm_btn.style = (
            discord.ButtonStyle.primary if self.mode == "dm" else discord.ButtonStyle.secondary
        )

    def render(self) -> discord.Embed:
        where = {
            "here": "Where the member is active",
            "dm": "By direct message",
            "channel": f"<#{self.channel_id}>" if self.channel_id else "A channel (not set)",
        }.get(self.mode, "Where the member is active")
        e = embeds.info("", f"{Emojis.XP} Leveling Setup")
        e.add_field(name="Status", value="On" if self.enabled else "Off")
        e.add_field(name="XP / message", value=str(self.rate))
        e.add_field(name="Cooldown", value=f"{self.cooldown}s")
        e.add_field(name="Announce", value=where, inline=False)
        e.add_field(name="Level-up message", value=self.message_text, inline=False)
        e.add_field(name="Rewards", value=str(self._reward_count))
        e.add_field(name="Multipliers", value=str(self._mult_count))
        e.set_footer(text="Rewards & multipliers: ,levels reward · ,levels multiplier")
        return self._stamp(e)

    # ── controls ──────────────────────────────────────────────────────────────

    @discord.ui.button(label="Leveling: Off", style=discord.ButtonStyle.secondary, row=0)
    async def _enabled_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_enabled(self.guild_id, not self.enabled)
        await self.refresh(interaction)

    @discord.ui.button(
        label="XP settings", emoji=Emojis.SETTINGS, style=discord.ButtonStyle.secondary, row=0
    )
    async def _xp_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_XpModal(self))

    @discord.ui.button(
        label="Level-up message", emoji=Emojis.MESSAGE, style=discord.ButtonStyle.secondary, row=0
    )
    async def _message_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_MessageModal(self))

    @discord.ui.button(label="Announce: Here", style=discord.ButtonStyle.secondary, row=1)
    async def _here_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_channel(self.guild_id, "here", None)
        await self.refresh(interaction)

    @discord.ui.button(label="Announce: DM", style=discord.ButtonStyle.secondary, row=1)
    async def _dm_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_channel(self.guild_id, "dm", None)
        await self.refresh(interaction)

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=4)
    async def _done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("Leveling setup saved.", "Done"), view=self
        )
        self.stop()

    @discord.ui.button(label="Close", emoji=Emojis.CLOSE, style=discord.ButtonStyle.danger, row=4)
    async def _close_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()
