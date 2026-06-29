"""The ``,setup logging`` panel: a live control panel for audit logging.

Reads ``get_config_summary`` and renders the same status as ``,serverlog status``;
picking a channel enables logging, the event buttons toggle each flag, and Disable
turns it off — each via the existing ``service`` setters. When logging is off the
summary hides the flag values, so the event toggles grey out until a channel is set.
"""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.serverlog import service

# Button label, summary key, and the GuildConfig flag column (matches ,serverlog toggle).
_EVENTS = [
    ("Joins", "joins", "log_joins"),
    ("Leaves", "leaves", "log_leaves"),
    ("Deletes", "deletes", "log_message_delete"),
    ("Edits", "edits", "log_message_edit"),
    ("Mod actions", "mod", "log_mod_actions"),
]


class _LogChannelSelect(discord.ui.ChannelSelect):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Send audit logs to…", channel_types=[discord.ChannelType.text],
            row=0, min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ServerLogSetupView = self.view
        await service.set_log_channel(view.guild_id, self.values[0].id)
        await view.refresh(interaction)


class _EventToggle(discord.ui.Button):
    def __init__(self, label: str, summary_key: str, flag: str) -> None:
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=1)
        self.summary_key = summary_key
        self.flag = flag

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ServerLogSetupView = self.view
        current = bool(view.summary.get(self.summary_key))
        await service.set_event_flag(view.guild_id, self.flag, not current)
        await view.refresh(interaction)


class ServerLogSetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self.summary: dict = {"enabled": False}
        self._toggles: list[_EventToggle] = []
        self.add_item(_LogChannelSelect())
        for label, key, flag in _EVENTS:
            toggle = _EventToggle(label, key, flag)
            self._toggles.append(toggle)
            self.add_item(toggle)

    @property
    def enabled(self) -> bool:
        return bool(self.summary.get("enabled"))

    async def load(self) -> None:
        self.summary = await service.get_config_summary(self.guild_id)
        self._sync()

    def _sync(self) -> None:
        for toggle in self._toggles:
            toggle.disabled = not self.enabled
            on = self.enabled and bool(self.summary.get(toggle.summary_key))
            toggle.style = discord.ButtonStyle.success if on else discord.ButtonStyle.secondary
        self._disable_btn.disabled = not self.enabled

    def render(self) -> discord.Embed:
        if not self.enabled:
            return self._stamp(embeds.info(
                "Audit logging is **off**. Pick a channel below to enable it, then choose "
                "which events to log.",
                f"{Emojis.CHANNEL} Logging Setup",
            ))
        e = embeds.info("", f"{Emojis.CHANNEL} Logging Setup")
        e.add_field(name="Channel", value=f"<#{self.summary['channel_id']}>", inline=False)
        for label, key, _flag in _EVENTS:
            e.add_field(name=label, value="On" if self.summary.get(key) else "Off")
        return self._stamp(e)

    @discord.ui.button(label="Disable logging", style=discord.ButtonStyle.secondary, row=2)
    async def _disable_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.disable_logging(self.guild_id)
        await self.refresh(interaction)

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=2)
    async def _done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("Logging setup saved.", "Done"), view=self
        )
        self.stop()

    @discord.ui.button(label="Close", emoji=Emojis.CLOSE, style=discord.ButtonStyle.danger, row=2)
    async def _close_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()
