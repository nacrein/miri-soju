"""The ``,setup moderation`` panel: set the jail role used by ``,jail``.

The jail role is the only per-guild moderation setting. A RoleSelect picks it (no
ID typing) and persists via the existing ``service.set_jail_role``.
"""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.moderation import service


class _JailRoleSelect(discord.ui.RoleSelect):
    def __init__(self) -> None:
        super().__init__(placeholder="Choose the jail role…", row=0, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ModerationSetupView = self.view
        await service.set_jail_role(view.guild_id, self.values[0].id)
        await view.refresh(interaction)


class ModerationSetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self._role_id: int | None = None
        self.add_item(_JailRoleSelect())

    async def load(self) -> None:
        self._role_id = await service.get_jail_role(self.guild_id)

    def render(self) -> discord.Embed:
        e = embeds.info("", f"{Emojis.SHIELD} Moderation Setup")
        e.add_field(
            name="Jail role",
            value=f"<@&{self._role_id}>" if self._role_id else "Not set",
            inline=False,
        )
        e.set_footer(text="Jail members with ,jail · release with ,unjail")
        return self._stamp(e)

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=1)
    async def _done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("Moderation setup saved.", "Done"), view=self
        )
        self.stop()

    @discord.ui.button(label="Close", emoji=Emojis.CLOSE, style=discord.ButtonStyle.danger, row=1)
    async def _close_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()
