"""The ,setup music panel: DJ role, command channel, default volume."""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.music import config, service


class _DjRoleSelect(discord.ui.RoleSelect):
    def __init__(self) -> None:
        super().__init__(
            placeholder="DJ role (controls playback)…", row=0, min_values=1, max_values=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: MusicSetupView = self.view  # type: ignore[assignment]
        await service.set_dj_role(view.guild_id, self.values[0].id)
        await view.refresh(interaction)


class _CommandChannelSelect(discord.ui.ChannelSelect):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Restrict commands to a channel…", row=1,
            channel_types=[discord.ChannelType.text], min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: MusicSetupView = self.view  # type: ignore[assignment]
        await service.set_command_channel(view.guild_id, self.values[0].id)
        await view.refresh(interaction)


class _VolumeModal(discord.ui.Modal, title="Default volume"):
    def __init__(self, view: MusicSetupView) -> None:
        super().__init__()
        self._view = view
        self.volume_in = discord.ui.TextInput(
            label="Default volume (0-100)", default=str(view.default_volume), max_length=3
        )
        self.add_item(self.volume_in)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self.volume_in.value).strip()
        if not raw.isdigit() or not 0 <= int(raw) <= 100:
            await interaction.response.send_message(
                embed=embeds.error("Give a whole number from 0 to 100."), ephemeral=True
            )
            return
        await service.set_default_volume(self._view.guild_id, int(raw))
        await self._view.refresh(interaction)


class MusicSetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self._cfg = None
        self.add_item(_DjRoleSelect())
        self.add_item(_CommandChannelSelect())

    @property
    def default_volume(self) -> int:
        return self._cfg.default_volume if self._cfg else config.DEFAULT_VOLUME

    async def load(self) -> None:
        self._cfg = await service.get_config(self.guild_id)

    def render(self) -> discord.Embed:
        cfg = self._cfg
        dj = f"<@&{cfg.dj_role_id}>" if cfg and cfg.dj_role_id else "anyone"
        chan = f"<#{cfg.command_channel_id}>" if cfg and cfg.command_channel_id else "any channel"
        e = embeds.info("", f"{Emojis.VOICE} Music Setup")
        e.add_field(name="DJ control", value=dj, inline=True)
        e.add_field(name="Command channel", value=chan, inline=True)
        e.add_field(name="Default volume", value=f"{self.default_volume}%", inline=True)
        return self._stamp(e)

    @discord.ui.button(label="Set volume", emoji="🔊", style=discord.ButtonStyle.secondary, row=2)
    async def _volume_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_VolumeModal(self))

    @discord.ui.button(label="Clear restrictions", style=discord.ButtonStyle.secondary, row=2)
    async def _clear_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_dj_role(self.guild_id, None)
        await service.set_command_channel(self.guild_id, None)
        await self.refresh(interaction)

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=3)
    async def _done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("Music setup saved.", "Done"), view=self
        )
        self.stop()

    @discord.ui.button(label="Close", emoji=Emojis.CLOSE, style=discord.ButtonStyle.danger, row=3)
    async def _close_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()
