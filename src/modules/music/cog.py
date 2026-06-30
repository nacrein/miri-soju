"""Music: Lavalink-backed playback in voice channels, driven by commands and a
persistent now-playing panel.

This is the documented exception to the cog -> service -> repository pattern. Queue and
playback state live in ``wavelink.Player`` (backed by the node), reachable as
``ctx.voice_client``, so the cog holds that state directly. The service owns only the
per-guild config and pure helpers and never touches discord or wavelink. Everything
under ``,m`` / ``,music`` (the bare group opens a command browser).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

import discord
import wavelink
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.errors import BotError
from src.core.paginator import Paginator, send_command_browser
from src.core.views import OwnerView
from src.modules.music import config, panel, service

log = logging.getLogger(__name__)

_LOOP_NAMES = {
    wavelink.QueueMode.normal: "off",
    wavelink.QueueMode.loop: "track",
    wavelink.QueueMode.loop_all: "queue",
}


class _SearchSelect(discord.ui.Select):
    def __init__(self, tracks: list[wavelink.Playable]) -> None:
        self._tracks = tracks
        super().__init__(
            placeholder="Pick a track to queue…", min_values=1, max_values=1,
            options=[
                discord.SelectOption(label=f"{i + 1}. {t.title[:90]}", value=str(i))
                for i, t in enumerate(tracks)
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: _SearchView = self.view  # type: ignore[assignment]
        await view.cog.queue_picked(interaction, self._tracks[int(self.values[0])])


class _SearchView(OwnerView):
    """The ,m search selection menu (invoker-locked)."""

    def __init__(
        self, cog: Music, author_id: int, tracks: list[wavelink.Playable], *, invoker
    ) -> None:
        super().__init__(author_id, invoker=invoker)
        self.cog = cog
        self.add_item(_SearchSelect(tracks))


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._connect_task: asyncio.Task | None = None
        self._idle_timers: dict[int, asyncio.Task] = {}      # guild_id -> idle disconnect task
        self._connect_locks: dict[int, asyncio.Lock] = {}    # guild_id -> connect guard
        self._skip_votes: dict[int, set[int]] = {}           # guild_id -> voter ids (this track)
        self._panels: dict[int, discord.Message] = {}        # guild_id -> now-playing message
        self._nightcore: set[int] = set()                    # guilds with nightcore toggled on

    # ── lifecycle ────────────────────────────────────────────────────────────────

    async def cog_load(self) -> None:
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.music.setup_view import MusicSetupView

        register_setup(SetupEntry(
            key="music", label="Music", emoji=Emojis.VOICE,
            description="Lavalink playback: DJ role, command channel, default volume.",
            factory=lambda author_id, guild_id: MusicSetupView(author_id, guild_id),
        ))
        # One shared persistent view serves every guild's panel via its static custom_ids.
        self.bot.add_view(panel.NowPlayingView())
        self._connect_task = asyncio.create_task(self._connect_node())

    async def _connect_node(self) -> None:
        """Connect the Lavalink pool in the background.

        Deliberately NOT awaited in cog_load: awaiting ``Pool.connect`` blocks forever
        on an unreachable node (wavelink's websocket retry loop), which would hang cog
        load and any test that loads cogs. Running it as a task keeps load instant; the
        connect retries with backoff until Lavalink is reachable, and cog_unload cancels
        it. ``inactive_player_timeout=None`` disables wavelink's own idle timer so this
        module fully owns idle-disconnect behaviour (see ``_start_idle_timer``)."""
        try:
            node = wavelink.Node(
                uri=config.LAVALINK_URI, password=config.LAVALINK_PASSWORD,
                inactive_player_timeout=None,
            )
            await wavelink.Pool.connect(nodes=[node], client=self.bot, cache_capacity=100)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Music: failed to connect to Lavalink at %s", config.LAVALINK_URI)

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        if self._connect_task is not None:
            self._connect_task.cancel()
        for task in self._idle_timers.values():
            task.cancel()
        self._idle_timers.clear()
        unregister_setup("music")

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        return True

    # ── wavelink events ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        log.info("Music: Lavalink node '%s' ready", payload.node.identifier)

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        player = payload.player
        if player is None:
            return
        self._cancel_idle_timer(player.guild.id)
        await self._refresh_panel(player)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        player = payload.player
        if player is None or not player.connected:
            return
        # The votes were for the track that just ended.
        self._skip_votes.pop(player.guild.id, None)
        # We drive the queue ourselves (autoplay is disabled), so advance here. Using
        # queue.get() respects loop/loop_all; an empty queue raises and we go idle.
        try:
            nxt = player.queue.get()
        except wavelink.QueueEmpty:
            self._start_idle_timer(player)
            return
        with contextlib.suppress(wavelink.WavelinkException):
            await player.play(nxt)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        if member.bot:
            return  # the bot being moved is handled by wavelink's own player voice handling
        player = member.guild.voice_client
        if player is None or player.channel is None:
            return
        ids = {getattr(before.channel, "id", None), getattr(after.channel, "id", None)}
        if player.channel.id not in ids:
            return  # this human event didn't touch the bot's channel
        if any(not m.bot for m in player.channel.members):
            self._cancel_idle_timer(member.guild.id)
        else:
            self._start_idle_timer(player)

    # ── idle disconnect ──────────────────────────────────────────────────────────

    def _start_idle_timer(self, player: wavelink.Player) -> None:
        self._cancel_idle_timer(player.guild.id)
        self._idle_timers[player.guild.id] = asyncio.create_task(self._idle_runner(player))

    def _cancel_idle_timer(self, guild_id: int) -> None:
        task = self._idle_timers.pop(guild_id, None)
        if task is not None:
            task.cancel()

    async def _idle_runner(self, player: wavelink.Player) -> None:
        try:
            await asyncio.sleep(config.IDLE_DISCONNECT_SECONDS)
        except asyncio.CancelledError:
            return
        self._idle_timers.pop(player.guild.id, None)
        if player.connected and not player.playing:
            with contextlib.suppress(Exception):
                player.queue.clear()
                await player.disconnect()
            self._panels.pop(player.guild.id, None)

    # ── helpers ──────────────────────────────────────────────────────────────────

    async def _refresh_panel(self, player: wavelink.Player) -> None:
        msg = self._panels.get(player.guild.id)
        if msg is not None:
            with contextlib.suppress(discord.HTTPException):
                await msg.edit(embed=panel.panel_embed(player))

    async def _enforce_channel(self, ctx: commands.Context) -> None:
        cfg = await service.get_config(ctx.guild.id)
        if cfg and cfg.command_channel_id and ctx.channel.id != cfg.command_channel_id:
            raise BotError(f"Use music commands in <#{cfg.command_channel_id}>.")

    async def _dj_check(self, ctx: commands.Context) -> None:
        if not await panel.passes_dj(ctx.guild, ctx.author):
            raise BotError("You need the DJ role to control playback.")

    def _require_player(self, ctx: commands.Context) -> wavelink.Player:
        player = ctx.voice_client
        if player is None:
            raise BotError("Nothing is playing.")
        return player  # type: ignore[return-value]

    async def _connect_to(self, channel: discord.VoiceChannel, guild_id: int) -> wavelink.Player:
        player: wavelink.Player = await channel.connect(cls=wavelink.Player)
        player.autoplay = wavelink.AutoPlayMode.disabled  # we advance the queue in on_track_end
        cfg = await service.get_config(guild_id)
        await player.set_volume(cfg.default_volume if cfg else config.DEFAULT_VOLUME)
        return player

    async def _ensure_player(self, ctx: commands.Context) -> wavelink.Player:
        player = ctx.voice_client
        if player is not None:
            return player  # type: ignore[return-value]
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            raise BotError("You need to be in a voice channel.")
        # Guard the connect so two simultaneous ,play invocations can't open it twice.
        lock = self._connect_locks.setdefault(ctx.guild.id, asyncio.Lock())
        async with lock:
            player = ctx.voice_client
            if player is None:
                try:
                    player = await self._connect_to(ctx.author.voice.channel, ctx.guild.id)
                except wavelink.InvalidNodeException:
                    raise BotError("Music isn't available right now (no audio node).") from None
                except discord.ClientException as exc:
                    raise BotError("I couldn't join your voice channel.") from exc
        return player  # type: ignore[return-value]

    def _listeners(self, player: wavelink.Player) -> int:
        if player.channel is None:
            return 0
        return len([m for m in player.channel.members if not m.bot])

    async def _search(self, query: str) -> wavelink.Search:
        tracks = await wavelink.Playable.search(query, source=config.DEFAULT_SOURCE)
        if not tracks:  # reliable source came up empty — fall back to YouTube
            tracks = await wavelink.Playable.search(query, source=config.FALLBACK_SOURCE)
        if not tracks:
            raise BotError("No results for that.")
        return tracks

    async def queue_picked(
        self, interaction: discord.Interaction, track: wavelink.Playable
    ) -> None:
        """Queue a track chosen from the ,m search menu (the picker is the gated invoker)."""
        player = interaction.guild.voice_client
        if player is None:
            voice = getattr(interaction.user, "voice", None)
            if voice is None or voice.channel is None:
                await interaction.response.edit_message(
                    embed=embeds.error("You need to be in a voice channel."), view=None)
                return
            try:
                player = await self._connect_to(voice.channel, interaction.guild.id)
            except wavelink.InvalidNodeException:
                await interaction.response.edit_message(
                    embed=embeds.error("Music isn't available right now."), view=None)
                return
        if player.queue.count >= config.MAX_QUEUE_LENGTH:
            await interaction.response.edit_message(
                embed=embeds.error("The queue is full."), view=None)
            return
        track.extras = {"requester": interaction.user.id}
        player.queue.put(track)
        if not player.playing:
            await player.play(player.queue.get())
            msg = f"Now playing **{track.title}**."
        else:
            msg = f"Queued **{track.title}** · position {player.queue.count}."
        await interaction.response.edit_message(embed=embeds.success(msg), view=None)

    # ── group ──────────────────────────────────────────────────────────────────

    @commands.group(name="music", aliases=["m"], invoke_without_command=True)
    async def music(self, ctx: commands.Context) -> None:
        """Play music in voice channels. Try `,m play <song>`."""
        await send_command_browser(ctx, ctx.command)

    # ── playback ─────────────────────────────────────────────────────────────────

    @music.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        """Play a track (search terms or a URL). Queues it if something's already playing."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = await self._ensure_player(ctx)
        result = await self._search(query)
        space = config.MAX_QUEUE_LENGTH - player.queue.count
        if space <= 0:
            raise BotError(f"The queue is full ({config.MAX_QUEUE_LENGTH} tracks).")
        if isinstance(result, wavelink.Playlist):
            result.track_extras(requester=ctx.author.id)
            added = player.queue.put(list(result.tracks)[:space])
            label = f"**{result.name}** ({added} track{'s' if added != 1 else ''})"
        else:
            track = result[0]
            track.extras = {"requester": ctx.author.id}
            player.queue.put(track)
            label = f"**{track.title}**"
        if not player.playing:
            await player.play(player.queue.get())
            await ctx.send(embed=embeds.success(f"Now playing {label}."))
        else:
            await ctx.send(embed=embeds.success(f"Queued {label} · position {player.queue.count}."))

    @music.command(name="search")
    async def search(self, ctx: commands.Context, *, query: str) -> None:
        """Show up to 5 results to pick from."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        result = await self._search(query)
        if isinstance(result, wavelink.Playlist):
            result = list(result.tracks)
        tracks = list(result)[:5]
        lines = [
            f"`{i + 1}.` **{t.title}** — {t.author or 'Unknown'} "
            f"`[{service.format_duration(t.length)}]`"
            for i, t in enumerate(tracks)
        ]
        embed = embeds.info("\n".join(lines), f"{Emojis.SEARCH} Search results")
        await _SearchView(self, ctx.author.id, tracks, invoker=ctx.author).start(ctx, embed)

    @music.command(name="pause")
    async def pause(self, ctx: commands.Context) -> None:
        """Pause playback."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        await self._require_player(ctx).pause(True)
        await ctx.send(embed=embeds.success("Paused."))

    @music.command(name="resume", aliases=["unpause"])
    async def resume(self, ctx: commands.Context) -> None:
        """Resume playback."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        await self._require_player(ctx).pause(False)
        await ctx.send(embed=embeds.success("Resumed."))

    @music.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context) -> None:
        """Skip the current track. DJs skip instantly; everyone else votes."""
        await self._enforce_channel(ctx)
        player = self._require_player(ctx)
        if player.current is None:
            raise BotError("Nothing is playing.")
        if await panel.passes_dj(ctx.guild, ctx.author):
            await player.skip(force=True)
            await ctx.send(embed=embeds.success("Skipped."))
            return
        votes = self._skip_votes.setdefault(ctx.guild.id, set())
        votes.add(ctx.author.id)
        needed = service.needs_votes(self._listeners(player))
        if len(votes) >= needed:
            await player.skip(force=True)
            await ctx.send(embed=embeds.success("Vote passed — skipped."))
        else:
            await ctx.send(
                embed=embeds.info(f"Skip vote: **{len(votes)}/{needed}**.", "Vote to skip"))

    @music.command(name="skipto", aliases=["jump"])
    async def skipto(self, ctx: commands.Context, position: int) -> None:
        """Jump to a queue position (skips everything before it)."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        if not 1 <= position <= player.queue.count:
            raise BotError(f"Pick a position between 1 and {player.queue.count}.")
        for _ in range(position - 1):
            player.queue.get()  # discard the skipped-over tracks
        await player.skip(force=True)  # track_end then plays the new head
        await ctx.send(embed=embeds.success(f"Skipped to queue position {position}."))

    @music.command(name="seek")
    async def seek(self, ctx: commands.Context, *, timestamp: str) -> None:
        """Seek the current track to a timestamp, e.g. `1:30`."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        if player.current is None:
            raise BotError("Nothing is playing.")
        if not player.current.is_seekable:
            raise BotError("This track can't be seeked.")
        ms = service.parse_timestamp(timestamp)
        await player.seek(ms)
        await ctx.send(embed=embeds.success(f"Seeked to `{service.format_duration(ms)}`."))
        await self._refresh_panel(player)

    @music.command(name="stop")
    async def stop(self, ctx: commands.Context) -> None:
        """Clear the queue and disconnect."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        player.queue.clear()
        await player.disconnect()
        self._panels.pop(ctx.guild.id, None)
        self._cancel_idle_timer(ctx.guild.id)
        await ctx.send(embed=embeds.success("Stopped and disconnected."))

    @music.command(name="disconnect", aliases=["dc", "leave"])
    async def disconnect(self, ctx: commands.Context) -> None:
        """Disconnect from voice."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        await self._require_player(ctx).disconnect()
        self._panels.pop(ctx.guild.id, None)
        self._cancel_idle_timer(ctx.guild.id)
        await ctx.send(embed=embeds.success("Disconnected."))

    # ── queue ────────────────────────────────────────────────────────────────────

    @music.command(name="queue", aliases=["q"])
    async def queue_(self, ctx: commands.Context) -> None:
        """Show the queue (paginated)."""
        await self._enforce_channel(ctx)
        player = self._require_player(ctx)
        if player.current is None and player.queue.is_empty:
            raise BotError("The queue is empty.")
        lines: list[str] = []
        if player.current is not None:
            now = service.format_duration(player.current.length)
            lines.append(f"**Now:** {player.current.title} `[{now}]`")
        for i, track in enumerate(player.queue, start=1):
            lines.append(f"`{i}.` {track.title} `[{service.format_duration(track.length)}]`")
        pages = [
            embeds.info("\n".join(lines[start:start + 10]), f"{Emojis.VOICE} Queue")
            for start in range(0, len(lines), 10)
        ]
        if len(pages) == 1:
            await ctx.send(embed=pages[0])
        else:
            await Paginator(ctx.author.id, pages).start(ctx)

    @music.command(name="remove", aliases=["rm"])
    async def remove(self, ctx: commands.Context, position: int) -> None:
        """Remove a track from the queue by position."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        if not 1 <= position <= player.queue.count:
            raise BotError(f"Pick a position between 1 and {player.queue.count}.")
        track = player.queue.peek(position - 1)
        player.queue.delete(position - 1)
        await ctx.send(embed=embeds.success(f"Removed **{track.title}**."))

    @music.command(name="move")
    async def move(self, ctx: commands.Context, from_pos: int, to_pos: int) -> None:
        """Move a queued track from one position to another."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        count = player.queue.count
        if not (1 <= from_pos <= count and 1 <= to_pos <= count):
            raise BotError(f"Positions must be between 1 and {count}.")
        track = player.queue.peek(from_pos - 1)
        player.queue.delete(from_pos - 1)
        player.queue.put_at(to_pos - 1, track)
        await ctx.send(embed=embeds.success(f"Moved **{track.title}** to position {to_pos}."))

    @music.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context) -> None:
        """Shuffle the queue."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        if player.queue.is_empty:
            raise BotError("The queue is empty.")
        player.queue.shuffle()
        await ctx.send(embed=embeds.success("Queue shuffled."))

    @music.command(name="clear")
    async def clear(self, ctx: commands.Context) -> None:
        """Clear the queue without stopping the current track."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        self._require_player(ctx).queue.clear()
        await ctx.send(embed=embeds.success("Queue cleared."))

    @music.command(name="loop", aliases=["repeat"])
    async def loop(self, ctx: commands.Context) -> None:
        """Cycle loop mode: off -> track -> queue."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        player.queue.mode = panel.next_loop_mode(player.queue.mode)
        await ctx.send(embed=embeds.success(f"Loop: **{_LOOP_NAMES[player.queue.mode]}**."))

    # ── now playing ────────────────────────────────────────────────────────────

    @music.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context) -> None:
        """Post the persistent now-playing panel."""
        await self._enforce_channel(ctx)
        player = self._require_player(ctx)
        msg = await ctx.send(embed=panel.panel_embed(player), view=panel.NowPlayingView())
        self._panels[ctx.guild.id] = msg

    # ── volume + filters ─────────────────────────────────────────────────────────

    @music.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, level: int) -> None:
        """Set playback volume (0-100)."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        if not 0 <= level <= 100:
            raise BotError("Volume must be between 0 and 100.")
        await player.set_volume(level)
        await ctx.send(embed=embeds.success(f"Volume set to {level}%."))
        await self._refresh_panel(player)

    @music.command(name="bass")
    async def bass(self, ctx: commands.Context, level: int) -> None:
        """Boost the low end (0-100, 0 = flat)."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        if not 0 <= level <= 100:
            raise BotError("Bass level must be between 0 and 100.")
        filters = player.filters
        gain = (level / 100) * config.BASS_MAX_GAIN
        filters.equalizer.set(bands=[{"band": b, "gain": gain} for b in config.BASS_BANDS])
        await player.set_filters(filters)
        await ctx.send(embed=embeds.success(f"Bass set to {level}%."))

    @music.command(name="nightcore")
    async def nightcore(self, ctx: commands.Context) -> None:
        """Toggle the nightcore (speed + pitch) filter."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        filters = player.filters
        if ctx.guild.id in self._nightcore:
            filters.timescale.set(speed=1.0, pitch=1.0, rate=1.0)  # neutral; keep other filters
            self._nightcore.discard(ctx.guild.id)
            state = "off"
        else:
            filters.timescale.set(**config.NIGHTCORE)
            self._nightcore.add(ctx.guild.id)
            state = "on"
        await player.set_filters(filters)
        await ctx.send(embed=embeds.success(f"Nightcore **{state}**."))

    @music.command(name="filters")
    async def filters(self, ctx: commands.Context, action: str = "reset") -> None:
        """Reset all audio filters: `,m filters reset`."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        if action.lower() != "reset":
            raise BotError("Usage: `,m filters reset`.")
        await player.set_filters()  # None clears every filter
        self._nightcore.discard(ctx.guild.id)
        await ctx.send(embed=embeds.success("All filters reset."))

    # ── session ──────────────────────────────────────────────────────────────────

    @music.command(name="history", aliases=["hist"])
    async def history(self, ctx: commands.Context) -> None:
        """Show the tracks played this session."""
        await self._enforce_channel(ctx)
        player = self._require_player(ctx)
        played = list(player.queue.history)[-10:]
        if not played:
            raise BotError("No history yet this session.")
        lines = [f"`{i + 1}.` {t.title}" for i, t in enumerate(reversed(played))]
        await ctx.send(embed=embeds.info("\n".join(lines), f"{Emojis.VOICE} Recently played"))

    @music.command(name="replay")
    async def replay(self, ctx: commands.Context) -> None:
        """Re-queue the most recently played track."""
        await self._enforce_channel(ctx)
        await self._dj_check(ctx)
        player = self._require_player(ctx)
        played = list(player.queue.history)
        if not played:
            raise BotError("Nothing to replay.")
        last = played[-1]
        last.extras = {"requester": ctx.author.id}
        player.queue.put(last)
        if not player.playing:
            await player.play(player.queue.get())
        await ctx.send(embed=embeds.success(f"Re-queued **{last.title}**."))

    # ── config (manage_guild) ────────────────────────────────────────────────────

    @music.command(name="dj")
    @commands.has_permissions(manage_guild=True)
    async def dj(self, ctx: commands.Context, role: discord.Role | None = None) -> None:
        """Set (or clear, with no argument) the DJ role."""
        await service.set_dj_role(ctx.guild.id, role.id if role else None)
        msg = (f"DJ role set to {role.mention}." if role
               else "DJ role cleared — anyone can control playback.")
        await ctx.send(embed=embeds.success(msg))

    @music.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def channel(
        self, ctx: commands.Context, channel: discord.TextChannel | None = None
    ) -> None:
        """Restrict music commands to one channel (no argument clears it)."""
        await service.set_command_channel(ctx.guild.id, channel.id if channel else None)
        msg = (f"Music commands restricted to {channel.mention}." if channel
               else "Music command channel cleared.")
        await ctx.send(embed=embeds.success(msg))

    @music.command(name="defaultvolume", aliases=["defaultvol"])
    @commands.has_permissions(manage_guild=True)
    async def defaultvolume(self, ctx: commands.Context, level: int) -> None:
        """Set the volume new players start at (0-100)."""
        if not 0 <= level <= 100:
            raise BotError("Default volume must be between 0 and 100.")
        await service.set_default_volume(ctx.guild.id, level)
        await ctx.send(embed=embeds.success(f"Default volume set to {level}%."))

    @music.command(name="status")
    @commands.has_permissions(manage_guild=True)
    async def status(self, ctx: commands.Context) -> None:
        """Show this server's music configuration."""
        cfg = await service.get_config(ctx.guild.id)
        dj = f"<@&{cfg.dj_role_id}>" if cfg and cfg.dj_role_id else "anyone"
        chan = f"<#{cfg.command_channel_id}>" if cfg and cfg.command_channel_id else "any channel"
        vol = cfg.default_volume if cfg else config.DEFAULT_VOLUME
        embed = embeds.info("", f"{Emojis.SETTINGS} Music config")
        embed.add_field(name="DJ control", value=dj)
        embed.add_field(name="Command channel", value=chan)
        embed.add_field(name="Default volume", value=f"{vol}%")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
