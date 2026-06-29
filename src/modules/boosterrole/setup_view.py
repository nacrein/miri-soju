"""The ``,setup boosterrole`` panel: enable, hoist direction, and the anchor role."""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.boosterrole import service


class _AnchorSelect(discord.ui.RoleSelect):
    def __init__(self) -> None:
        super().__init__(placeholder="Pick the anchor role…", row=1, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: BoosterRoleSetupView = self.view
        await service.set_anchor(view.guild_id, self.values[0].id)
        await view.refresh(interaction)


class BoosterRoleSetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self._cfg = None
        self._count = 0
        self.add_item(_AnchorSelect())

    @property
    def _enabled(self) -> bool:
        return bool(self._cfg and self._cfg.enabled)

    @property
    def _hoist_above(self) -> bool:
        return self._cfg.hoist_above if self._cfg else True

    @property
    def _anchor_id(self) -> int | None:
        return self._cfg.anchor_role_id if self._cfg else None

    async def load(self) -> None:
        self._cfg = await service.get_config(self.guild_id)
        self._count = len(await service.list_roles(self.guild_id))
        self._sync()

    def _sync(self) -> None:
        self._enabled_btn.label = f"Booster roles: {'On' if self._enabled else 'Off'}"
        self._enabled_btn.style = (
            discord.ButtonStyle.success if self._enabled else discord.ButtonStyle.secondary
        )
        self._hoist_btn.label = f"Hoist: {'Above anchor' if self._hoist_above else 'Below anchor'}"

    def render(self) -> discord.Embed:
        e = embeds.info("", f"{Emojis.GEM} Booster Role Setup")
        e.add_field(name="Status", value="On" if self._enabled else "Off")
        e.add_field(name="Hoist", value="Above anchor" if self._hoist_above else "Below anchor")
        e.add_field(name="Anchor", value=f"<@&{self._anchor_id}>" if self._anchor_id else "Not set")
        e.add_field(name="Booster roles", value=str(self._count))
        e.set_footer(text="Boosters create and style their role with ,br create")
        return self._stamp(e)

    @discord.ui.button(label="Booster roles: Off", style=discord.ButtonStyle.secondary, row=0)
    async def _enabled_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_enabled(self.guild_id, not self._enabled)
        await self.refresh(interaction)

    @discord.ui.button(label="Hoist: Above anchor", style=discord.ButtonStyle.secondary, row=0)
    async def _hoist_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_hoist_above(self.guild_id, not self._hoist_above)
        await self.refresh(interaction)

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=2)
    async def _done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("Booster-role setup saved.", "Done"), view=self
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
