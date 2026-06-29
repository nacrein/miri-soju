"""The ``,setup prefix`` panel: view and change this server's command prefix.

Changing the prefix is **server-owner-only**, exactly like ``,prefix`` — the modal
re-checks the owner before persisting, even though ``,setup`` itself only needs
``manage_guild``. Any admin can open the panel to *see* the current prefix.
"""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.prefix import service

_MAX_PREFIX_LEN = 5  # keep in sync with src/modules/prefix/cog.py


def apply_prefix(raw: str) -> str:
    """Validate a new prefix. Returns the cleaned value or raises ValueError."""
    new = str(raw).strip()
    if not new or len(new) > _MAX_PREFIX_LEN or any(c.isspace() for c in new):
        raise ValueError(f"Prefix must be 1–{_MAX_PREFIX_LEN} characters with no spaces.")
    return new


class _PrefixModal(discord.ui.Modal, title="Change prefix"):
    def __init__(self, view: PrefixSetupView) -> None:
        super().__init__()
        self._view = view
        self.prefix_in = discord.ui.TextInput(
            label="New prefix", default=view.prefix, max_length=_MAX_PREFIX_LEN,
            placeholder="e.g. !",
        )
        self.add_item(self.prefix_in)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        owner = interaction.guild.owner_id
        if interaction.user.id != owner and not await interaction.client.is_owner(interaction.user):
            await interaction.response.send_message(
                embed=embeds.error("Only the server owner can change the prefix."), ephemeral=True
            )
            return
        try:
            new = apply_prefix(str(self.prefix_in.value))
        except ValueError as exc:
            await interaction.response.send_message(embed=embeds.error(str(exc)), ephemeral=True)
            return
        await service.set_prefix(interaction.guild.id, new)
        await self._view.refresh(interaction)


class PrefixSetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self.prefix = service.DEFAULT_PREFIX

    async def load(self) -> None:
        self.prefix = await service.get_prefix(self.guild_id)

    def render(self) -> discord.Embed:
        e = embeds.info(
            f"My prefix here is `{self.prefix}`. You can always mention me instead.",
            f"{Emojis.SETTINGS} Prefix Setup",
        )
        e.set_footer(text="Only the server owner can change the prefix.")
        return self._stamp(e)

    @discord.ui.button(
        label="Change prefix", emoji=Emojis.SETTINGS, style=discord.ButtonStyle.primary, row=0
    )
    async def _change_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_modal(_PrefixModal(self))

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=0)
    async def _done_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("Prefix setup saved.", "Done"), view=self
        )
        self.stop()

    @discord.ui.button(label="Close", emoji=Emojis.CLOSE, style=discord.ButtonStyle.danger, row=0)
    async def _close_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()
