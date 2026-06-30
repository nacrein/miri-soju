"""The persistent now-playing panel, plus the DJ gate shared with the cog.

The panel is one shared view (``timeout=None``) registered once on cog load; every
guild's panel message routes through it via static custom_ids, so the controls keep
working after a restart. Each handler resolves the guild's player at click time
(``interaction.guild.voice_client``) and runs the same DJ gate as the commands.
"""

from __future__ import annotations

import contextlib

import discord
import wavelink

from src.core import embeds
from src.modules.music import config, service

_PANEL_TITLE = "🎵 Now playing"


async def passes_dj(guild: discord.Guild, member: discord.Member) -> bool:
    """The DJ gate: no role set -> anyone may control; else manage_guild or the role."""
    cfg = await service.get_config(guild.id)
    if cfg is None or cfg.dj_role_id is None:
        return True
    if member.guild_permissions.manage_guild:
        return True
    return discord.utils.get(member.roles, id=cfg.dj_role_id) is not None


def next_loop_mode(mode: wavelink.QueueMode) -> wavelink.QueueMode:
    """Cycle normal -> loop (track) -> loop_all (queue) -> normal."""
    order = [wavelink.QueueMode.normal, wavelink.QueueMode.loop, wavelink.QueueMode.loop_all]
    return order[(order.index(mode) + 1) % len(order)]


def _requester(track: wavelink.Playable) -> str:
    rid = getattr(track.extras, "requester", None)
    return f"<@{rid}>" if rid else "unknown"


def _progress_bar(position: int, length: int, width: int = 16) -> str:
    if not length or length <= 0:
        return "🔴 LIVE"
    filled = min(width - 1, max(0, int(position / length * width)))
    return "▬" * filled + "🔘" + "▬" * (width - 1 - filled)


def panel_embed(player: wavelink.Player | None) -> discord.Embed:
    """Build the now-playing embed from the player's live state."""
    track = player.current if player else None
    if track is None:
        return embeds.info("Nothing is playing. Queue a track with `,m play`.", _PANEL_TITLE)
    pos, dur = service.format_duration(player.position), service.format_duration(track.length)
    e = embeds.info(f"**[{track.title}]({track.uri})**", _PANEL_TITLE)
    e.add_field(name="Artist", value=(track.author or "Unknown")[:100], inline=True)
    e.add_field(name="Requested by", value=_requester(track), inline=True)
    e.add_field(name="Volume", value=f"{player.volume}%", inline=True)
    e.add_field(
        name="Progress", value=f"`{pos} / {dur}`\n{_progress_bar(player.position, track.length)}",
        inline=False,
    )
    mode = player.queue.mode.name.replace("_", " ")
    e.add_field(name="Queue", value=f"{player.queue.count} up next · loop: {mode}", inline=False)
    return e


class NowPlayingView(discord.ui.View):
    """One shared, persistent view serving every guild's now-playing panel."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    async def _gate(self, interaction: discord.Interaction) -> wavelink.Player | None:
        """Resolve the guild's player and run the DJ gate; reply + return None on failure."""
        player = interaction.guild.voice_client if interaction.guild else None
        if player is None or player.current is None:
            await interaction.response.send_message(
                embed=embeds.error("Nothing is playing right now."), ephemeral=True
            )
            return None
        if not await passes_dj(interaction.guild, interaction.user):
            await interaction.response.send_message(
                embed=embeds.error("You need the DJ role to control playback."), ephemeral=True
            )
            return None
        return player  # type: ignore[return-value]

    async def _refresh(self, interaction: discord.Interaction, player: wavelink.Player) -> None:
        with contextlib.suppress(discord.HTTPException):
            await interaction.response.edit_message(embed=panel_embed(player), view=self)

    @discord.ui.button(
        emoji="⏯️", style=discord.ButtonStyle.secondary, custom_id="music:playpause", row=0
    )
    async def _playpause(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        player = await self._gate(interaction)
        if player is not None:
            await player.pause(not player.paused)
            await self._refresh(interaction, player)

    @discord.ui.button(
        emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="music:skip", row=0
    )
    async def _skip(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        player = await self._gate(interaction)
        if player is not None:
            await player.skip(force=True)  # track_end -> the cog advances the queue and refreshes
            with contextlib.suppress(discord.HTTPException):
                await interaction.response.defer()

    @discord.ui.button(
        emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="music:shuffle", row=0
    )
    async def _shuffle(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        player = await self._gate(interaction)
        if player is not None:
            player.queue.shuffle()
            await self._refresh(interaction, player)

    @discord.ui.button(
        emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="music:loop", row=0
    )
    async def _loop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        player = await self._gate(interaction)
        if player is not None:
            player.queue.mode = next_loop_mode(player.queue.mode)
            await self._refresh(interaction, player)

    @discord.ui.button(
        emoji="🔉", style=discord.ButtonStyle.secondary, custom_id="music:voldown", row=1
    )
    async def _voldown(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        player = await self._gate(interaction)
        if player is not None:
            await player.set_volume(max(0, player.volume - config.VOLUME_STEP))
            await self._refresh(interaction, player)

    @discord.ui.button(
        emoji="🔊", style=discord.ButtonStyle.secondary, custom_id="music:volup", row=1
    )
    async def _volup(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        player = await self._gate(interaction)
        if player is not None:
            await player.set_volume(min(100, player.volume + config.VOLUME_STEP))
            await self._refresh(interaction, player)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="music:dc", row=1)
    async def _disconnect(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        player = await self._gate(interaction)
        if player is not None:
            player.queue.clear()
            await player.disconnect()
            with contextlib.suppress(discord.HTTPException):
                await interaction.response.edit_message(
                    embed=embeds.info("Disconnected. Thanks for listening!", _PANEL_TITLE),
                    view=None,
                )
