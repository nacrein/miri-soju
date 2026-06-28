"""The leaderboard menu: one dropdown switches between the global boards, styled
like the help menu. Every board here is global (across all servers); per-server
level ranking lives in the leveling module's ``,top``.

Locked to the invoker; the dropdown disables itself after 2 minutes idle.
"""

from __future__ import annotations

import discord

from src.core import embeds, rankings
from src.core.emojis import Emojis
from src.modules.economy import service as economy

_TIMEOUT = 120
_FOOTER = "Global · across every server"


# Each board: (dropdown label, dropdown emoji, embed title, async fetch → [(uid, value)]).
async def _networth() -> list[tuple[int, str]]:
    rows = await economy.leaderboard(10)
    return [(uid, f"{Emojis.BITS} {value:,}") for uid, value in rows]


async def _voice() -> list[tuple[int, str]]:
    from src.modules.leveling import service as leveling  # lazy: avoid a feature import cycle
    return await leveling.leaderboard_voice_global(10)


async def _generators() -> list[tuple[int, str]]:
    rows = await economy.leaderboard_generator(10)
    return [(uid, f"T{tier} · {rate:,}/hr") for uid, tier, rate in rows]


_BOARDS: dict[str, tuple[str, str, str, object]] = {
    "networth": ("Net Worth", Emojis.BITS, "Net Worth", _networth),
    "voice": ("Voice Time", Emojis.VOICE, "Voice Time", _voice),
    "generator": ("Generators", Emojis.SETTINGS, "Generators", _generators),
}


class _BoardSelect(discord.ui.Select):
    def __init__(self, current: str | None) -> None:
        super().__init__(
            placeholder="Pick a board…",
            options=[
                discord.SelectOption(label=label, value=key, emoji=emoji, default=(key == current))
                for key, (label, emoji, _title, _fetch) in _BOARDS.items()
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.show(interaction, self.values[0])


class LeaderboardMenu(discord.ui.View):
    def __init__(self, author_id: int, guild: discord.Guild, invoker: discord.abc.User,
                 board: str | None = None) -> None:
        super().__init__(timeout=_TIMEOUT)
        self._author_id = author_id
        self._guild = guild
        self._invoker = invoker
        self._board = board  # None → the landing card; a key → that board
        self.message: discord.Message | None = None
        self.add_item(_BoardSelect(board))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    def _landing(self) -> discord.Embed:
        """The intro card shown before a board is chosen — lists what's on offer,
        like the help menu's landing."""
        choices = "\n".join(f"{emoji} **{label}**" for label, emoji, _t, _f in _BOARDS.values())
        e = embeds.info(
            f"Pick a board from the menu below.\n\n{choices}", f"{Emojis.TROPHY} Leaderboards"
        )
        e.set_footer(text=_FOOTER)
        embeds.apply_author(e, self._invoker)
        return e

    async def embed(self) -> discord.Embed:
        if self._board is None:
            return self._landing()
        _label, _emoji, title, fetch = _BOARDS[self._board]
        entries = await fetch()
        return rankings.ranked_list(self._guild, entries, title, author=self._invoker, footer=_FOOTER)

    async def show(self, interaction: discord.Interaction, board: str) -> None:
        self._board = board
        self.clear_items()
        self.add_item(_BoardSelect(board))  # rebuild so the checked option follows
        # Ack first (the 3s window), then run the board's DB fetch and edit, so a
        # slow/failing query can't leave the interaction unanswered.
        await interaction.response.defer()
        try:
            e = await self.embed()
        except Exception:  # noqa: BLE001 — a board fetch failing shouldn't kill the menu
            e = embeds.error("Couldn't load that board. Try again.")
        await interaction.edit_original_response(embed=e, view=self)

    async def start(self, ctx) -> None:
        self.message = await ctx.send(embed=await self.embed(), view=self)
