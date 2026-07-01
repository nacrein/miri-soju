"""The ,setup starboard panel: board channel, threshold, and the self-star toggle.

Picking a channel enables the starboard; the ± buttons nudge the threshold and the
self-star button toggles whether an author's own star counts. The star emoji itself
is changed with ``,starboard emoji`` (kept off the panel to avoid a modal)."""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.starboard import service


class _BoardChannelSelect(discord.ui.ChannelSelect):
    def __init__(self) -> None:
        super().__init__(
            placeholder="Board channel…", channel_types=[discord.ChannelType.text],
            row=0, min_values=1, max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: StarboardSetupView = self.view
        await service.set_channel(view.guild_id, self.values[0].id)
        await view.refresh(interaction)


class StarboardSetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self.summary: dict = {}
        self.add_item(_BoardChannelSelect())

    async def load(self) -> None:
        self.summary = await service.get_summary(self.guild_id)
        self._sync()

    @property
    def _on(self) -> bool:
        return bool(self.summary.get("enabled") and self.summary.get("channel_id"))

    def _sync(self) -> None:
        for btn in (self._lower, self._higher, self._selfstar, self._disable_btn):
            btn.disabled = not self._on
        on = self._on and bool(self.summary.get("self_star"))
        self._selfstar.style = (
            discord.ButtonStyle.success if on else discord.ButtonStyle.secondary
        )

    def render(self) -> discord.Embed:
        if not self._on:
            return self._stamp(embeds.info(
                "Pick a board channel below to enable the starboard.",
                f"{Emojis.STAR} Starboard Setup",
            ))
        e = embeds.info("", f"{Emojis.STAR} Starboard Setup")
        e.add_field(name="Channel", value=f"<#{self.summary['channel_id']}>")
        e.add_field(name="Threshold", value=str(self.summary["threshold"]))
        e.add_field(name="Emoji", value=self.summary["star_emoji"])
        e.add_field(name="Self-stars", value="count" if self.summary["self_star"] else "ignored")
        return self._stamp(e)

    @discord.ui.button(label="− threshold", style=discord.ButtonStyle.secondary, row=1)
    async def _lower(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_threshold(self.guild_id, self.summary.get("threshold", 3) - 1)
        await self.refresh(interaction)

    @discord.ui.button(label="+ threshold", style=discord.ButtonStyle.secondary, row=1)
    async def _higher(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_threshold(self.guild_id, self.summary.get("threshold", 3) + 1)
        await self.refresh(interaction)

    @discord.ui.button(label="Self-stars", style=discord.ButtonStyle.secondary, row=1)
    async def _selfstar(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_self_star(self.guild_id, not self.summary.get("self_star"))
        await self.refresh(interaction)

    @discord.ui.button(label="Disable", style=discord.ButtonStyle.secondary, row=2)
    async def _disable_btn(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.disable(self.guild_id)
        await self.refresh(interaction)

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=3)
    async def _done(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("Starboard setup saved.", "Done"), view=self
        )
        self.stop()

    @discord.ui.button(label="Close", emoji=Emojis.CLOSE, style=discord.ButtonStyle.danger, row=3)
    async def _close(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            pass
        self.stop()
