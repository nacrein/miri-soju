"""The ``,setup voicemaster`` panel: enable, the create channel, and the panel channel."""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.voicemaster import service
from src.modules.voicemaster.views import VoicePanelView, delete_old_panel, panel_embed


class _CreateChannelSelect(discord.ui.ChannelSelect):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Create (lobby) voice channel…", row=1,
            channel_types=[discord.ChannelType.voice], min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: VoiceMasterSetupView = self.view
        await service.set_create_channel(view.guild_id, self.values[0].id)
        await view.refresh(interaction)


class _PanelChannelSelect(discord.ui.ChannelSelect):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Channel to post the control panel…", row=2,
            channel_types=[discord.ChannelType.text], min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: VoiceMasterSetupView = self.view
        channel = interaction.guild.get_channel(self.values[0].id)
        if channel is None:
            await interaction.response.send_message(
                embed=embeds.error("I couldn't access that channel."), ephemeral=True
            )
            return
        await delete_old_panel(interaction.guild)
        try:
            msg = await channel.send(embed=panel_embed(), view=VoicePanelView())
        except discord.HTTPException:
            await interaction.response.send_message(
                embed=embeds.error("I couldn't post the panel there. Check my permissions."),
                ephemeral=True,
            )
            return
        await service.set_panel_message(view.guild_id, channel.id, msg.id)
        await view.refresh(interaction)


class VoiceMasterSetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self._cfg = None
        self._tracked = 0
        self.add_item(_CreateChannelSelect())
        self.add_item(_PanelChannelSelect())

    @property
    def _enabled(self) -> bool:
        return bool(self._cfg and self._cfg.enabled)

    async def load(self) -> None:
        self._cfg = await service.get_config(self.guild_id)
        self._tracked = len(await service.list_tracked(self.guild_id))
        self._sync()

    def _sync(self) -> None:
        self._enabled_btn.label = f"VoiceMaster: {'On' if self._enabled else 'Off'}"
        self._enabled_btn.style = (
            discord.ButtonStyle.success if self._enabled else discord.ButtonStyle.secondary
        )

    def render(self) -> discord.Embed:
        create = self._cfg.create_channel_id if self._cfg else None
        panel = self._cfg.panel_message_id if self._cfg else None
        e = embeds.info("", f"{Emojis.VOICE} VoiceMaster Setup")
        e.add_field(name="Status", value="On" if self._enabled else "Off")
        e.add_field(name="Create channel", value=f"<#{create}>" if create else "Not set")
        e.add_field(name="Panel", value="Posted" if panel else "Not posted")
        e.add_field(name="Active channels", value=str(self._tracked))
        e.set_footer(text="Pick a create channel and a panel channel, then toggle On.")
        return self._stamp(e)

    @discord.ui.button(label="VoiceMaster: Off", style=discord.ButtonStyle.secondary, row=0)
    async def _enabled_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_enabled(self.guild_id, not self._enabled)
        await self.refresh(interaction)

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=3)
    async def _done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("VoiceMaster setup saved.", "Done"), view=self
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
