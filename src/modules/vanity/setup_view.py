"""The ``,setup vanity`` panel: enable, reward role, announce channel, and message."""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.vanity import service
from src.modules.vanity.gate import has_vanity


class _MessageModal(discord.ui.Modal, title="Thank-you message"):
    def __init__(self, view: VanitySetupView) -> None:
        super().__init__()
        self._view = view
        self.message_in = discord.ui.TextInput(
            label="Template", style=discord.TextStyle.paragraph, max_length=500, required=False,
            default=view.template, placeholder="Placeholders: {user} {vanity}",
        )
        self.add_item(self.message_in)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await service.set_message(self._view.guild_id, str(self.message_in.value)[:500] or None)
        await self._view.refresh(interaction)


class _RoleSelect(discord.ui.RoleSelect):
    def __init__(self) -> None:
        super().__init__(placeholder="Reward role…", row=1, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: VanitySetupView = self.view
        await service.set_role(view.guild_id, self.values[0].id)
        await view.refresh(interaction)


class _ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Thank-you channel…", row=2,
            channel_types=[discord.ChannelType.text], min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: VanitySetupView = self.view
        await service.set_channel(view.guild_id, self.values[0].id)
        await view.refresh(interaction)


class VanitySetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self._cfg = None
        self._count = 0
        self.add_item(_RoleSelect())
        self.add_item(_ChannelSelect())

    @property
    def _enabled(self) -> bool:
        return bool(self._cfg and self._cfg.enabled)

    @property
    def template(self) -> str:
        return (self._cfg.message_template if self._cfg else None) or ""

    async def load(self) -> None:
        self._cfg = await service.get_config(self.guild_id)
        self._count = await service.active_count(self.guild_id)
        self._sync()

    def _sync(self) -> None:
        self._enabled_btn.label = f"Vanity rep: {'On' if self._enabled else 'Off'}"
        self._enabled_btn.style = (
            discord.ButtonStyle.success if self._enabled else discord.ButtonStyle.secondary
        )

    def render(self) -> discord.Embed:
        role = self._cfg.role_id if self._cfg else None
        channel = self._cfg.channel_id if self._cfg else None
        e = embeds.info("", f"{Emojis.GEM} Vanity Setup")
        e.add_field(name="Status", value="On" if self._enabled else "Off")
        e.add_field(name="Reward role", value=f"<@&{role}>" if role else "Not set")
        e.add_field(name="Announce channel", value=f"<#{channel}>" if channel else "Not set")
        e.add_field(name="Currently repping", value=str(self._count))
        e.set_footer(text="Members rep by putting .gg/<vanity> in their custom status.")
        return self._stamp(e)

    @discord.ui.button(label="Vanity rep: Off", style=discord.ButtonStyle.secondary, row=0)
    async def _enabled_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self._enabled and not has_vanity(interaction.guild):
            await interaction.response.send_message(
                embed=embeds.error(
                    "This server has no vanity URL (needs Boost Level 3 or Partner/Verified)."
                ),
                ephemeral=True,
            )
            return
        await service.set_enabled(self.guild_id, not self._enabled)
        await self.refresh(interaction)

    @discord.ui.button(
        label="Message", emoji=Emojis.MESSAGE_EDIT, style=discord.ButtonStyle.secondary, row=0
    )
    async def _message_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_MessageModal(self))

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=3)
    async def _done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("Vanity setup saved.", "Done"), view=self
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
