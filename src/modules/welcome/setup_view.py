"""The ,setup welcome panel: pick the welcome/goodbye channels and toggle them.

Picking a channel enables that kind; the Disable buttons turn it off. The greeting
text itself is set with ``,welcome message`` / ``,goodbye message`` (kept off the
panel to avoid a modal), and the panel shows the current channels."""

from __future__ import annotations

import discord

from src.core import embeds
from src.core.emojis import Emojis
from src.core.views import WizardView
from src.modules.welcome import service


class _ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, kind: str, row: int) -> None:
        super().__init__(
            placeholder=f"{kind.title()} channel…",
            channel_types=[discord.ChannelType.text],
            row=row, min_values=1, max_values=1,
        )
        self.kind = kind

    async def callback(self, interaction: discord.Interaction) -> None:
        view: WelcomeSetupView = self.view
        await service.set_channel(view.guild_id, self.kind, self.values[0].id)
        await view.refresh(interaction)


class WelcomeSetupView(WizardView):
    def __init__(self, author_id: int, guild_id: int) -> None:
        super().__init__(author_id)
        self.guild_id = guild_id
        self.summary: dict = {}
        self.add_item(_ChannelSelect("welcome", row=0))
        self.add_item(_ChannelSelect("goodbye", row=1))

    async def load(self) -> None:
        self.summary = await service.get_summary(self.guild_id)
        self._sync()

    def _sync(self) -> None:
        self._welcome_off.disabled = not self.summary.get("welcome", {}).get("enabled")
        self._goodbye_off.disabled = not self.summary.get("goodbye", {}).get("enabled")

    def _line(self, kind: str) -> str:
        s = self.summary.get(kind, {})
        if not s.get("enabled") or s.get("channel_id") is None:
            return "Off"
        return f"<#{s['channel_id']}>"

    def render(self) -> discord.Embed:
        e = embeds.info(
            "Pick a channel to enable each. Set the text with "
            "`,welcome message …` / `,goodbye message …`.",
            f"{Emojis.JOIN} Welcome & Goodbye",
        )
        e.add_field(name="Welcome", value=self._line("welcome"), inline=False)
        e.add_field(name="Goodbye", value=self._line("goodbye"), inline=False)
        return self._stamp(e)

    @discord.ui.button(label="Disable welcome", style=discord.ButtonStyle.secondary, row=2)
    async def _welcome_off(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_enabled(self.guild_id, "welcome", False)
        await self.refresh(interaction)

    @discord.ui.button(label="Disable goodbye", style=discord.ButtonStyle.secondary, row=2)
    async def _goodbye_off(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await service.set_enabled(self.guild_id, "goodbye", False)
        await self.refresh(interaction)

    @discord.ui.button(label="Done", emoji=Emojis.SUCCESS, style=discord.ButtonStyle.success, row=3)
    async def _done(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=embeds.success("Welcome setup saved.", "Done"), view=self
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
