"""Starboard: when a message gets enough star reactions, mirror it to a board channel.

Reactions are watched raw (so old messages count too). A source message that crosses
the threshold is posted to the board and kept in sync as the count changes; dropping
back below the threshold removes it. Bot messages and reactions in the board channel
itself are ignored."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.paginator import send_command_browser
from src.modules.starboard import service


def board_text(message: discord.Message, count: int, emoji: str) -> str:
    """The board post's content line: emoji, count, and the source channel."""
    return f"{emoji} **{count}** · {message.channel.mention}"


def board_embed(message: discord.Message) -> discord.Embed:
    """The board post's embed: the original author, content, jump link, first image."""
    e = embeds.info(message.content or "")
    e.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
    e.add_field(name="Source", value=f"[Jump to message]({message.jump_url})", inline=False)
    for att in message.attachments:
        if att.content_type and att.content_type.startswith("image"):
            e.set_image(url=att.url)
            break
    e.timestamp = message.created_at
    return e


class Starboard(commands.Cog, name="Starboard"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.starboard.setup_view import StarboardSetupView

        register_setup(SetupEntry(
            key="starboard", label="Starboard", emoji=Emojis.STAR,
            description="Mirror well-starred messages to a board channel.",
            factory=lambda author_id, guild_id: StarboardSetupView(author_id, guild_id),
        ))

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        unregister_setup("starboard")

    # ── configuration ───────────────────────────────────────────────────────
    @commands.group(name="starboard", aliases=["sb"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def starboard(self, ctx) -> None:
        """Configure the starboard."""
        await send_command_browser(ctx, ctx.command)

    @starboard.command(name="channel")
    async def sb_channel(self, ctx, channel: discord.TextChannel) -> None:
        """Set the board channel (enables the starboard)."""
        await service.set_channel(ctx.guild.id, channel.id)
        await ctx.send(embed=embeds.success(f"Starred messages will post in {channel.mention}."))

    @starboard.command(name="threshold", aliases=["count"])
    async def sb_threshold(self, ctx, threshold: int) -> None:
        """Set how many stars a message needs to reach the board."""
        actual = await service.set_threshold(ctx.guild.id, threshold)
        await ctx.send(embed=embeds.success(f"Threshold set to **{actual}** stars."))

    @starboard.command(name="emoji")
    async def sb_emoji(self, ctx, emoji: str) -> None:
        """Set the star emoji to watch for (default ⭐)."""
        await service.set_emoji(ctx.guild.id, emoji)
        await ctx.send(embed=embeds.success(f"Now counting {emoji} reactions."))

    @starboard.command(name="selfstar")
    async def sb_selfstar(self, ctx, allowed: bool) -> None:
        """Allow (or not) a message author's own star to count."""
        await service.set_self_star(ctx.guild.id, allowed)
        state = "count" if allowed else "not count"
        await ctx.send(embed=embeds.success(f"Authors' own stars will {state}."))

    @starboard.command(name="disable", aliases=["off"])
    async def sb_disable(self, ctx) -> None:
        """Turn the starboard off."""
        await service.disable(ctx.guild.id)
        await ctx.send(embed=embeds.success("Starboard disabled."))

    @starboard.command(name="status")
    async def sb_status(self, ctx) -> None:
        """Show the current starboard settings."""
        s = await service.get_summary(ctx.guild.id)
        if not s["enabled"] or s["channel_id"] is None:
            await ctx.send(embed=embeds.info(
                "Starboard is off. Use `,starboard channel #channel` to enable it."
            ))
            return
        e = embeds.info("", f"{Emojis.STAR} Starboard")
        e.add_field(name="Channel", value=f"<#{s['channel_id']}>")
        e.add_field(name="Threshold", value=str(s["threshold"]))
        e.add_field(name="Emoji", value=s["star_emoji"])
        e.add_field(name="Self-stars", value="count" if s["self_star"] else "ignored")
        await ctx.send(embed=e)

    # ── reaction listeners ──────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        await self._handle(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        await self._handle(payload)

    async def _handle(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.guild_id is None:
            return
        config = await service.get_config(payload.guild_id)
        if config is None or not config.enabled or config.channel_id is None:
            return
        if str(payload.emoji) != config.star_emoji or payload.channel_id == config.channel_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        source = guild.get_channel_or_thread(payload.channel_id)
        if not isinstance(source, (discord.TextChannel, discord.Thread)):
            return
        try:
            message = await source.fetch_message(payload.message_id)
        except discord.HTTPException:
            return
        if message.author.bot:
            return
        board = guild.get_channel(config.channel_id)
        if not isinstance(board, discord.TextChannel):
            return
        count = await self._count_stars(message, config)
        await self._sync_board(guild.id, board, message, count, config)

    async def _count_stars(self, message: discord.Message, config) -> int:
        for reaction in message.reactions:
            if str(reaction.emoji) != config.star_emoji:
                continue
            if config.self_star:
                return reaction.count
            try:
                return sum([1 async for user in reaction.users() if user.id != message.author.id])
            except discord.HTTPException:
                return reaction.count
        return 0

    async def _sync_board(self, guild_id, board, message, count, config) -> None:
        entry = await service.get_entry(guild_id, message.id)
        if count >= config.threshold:
            text = board_text(message, count, config.star_emoji)
            embed = board_embed(message)
            if entry is not None:
                try:
                    board_msg = await board.fetch_message(entry.board_message_id)
                    await board_msg.edit(content=text, embed=embed)
                    await service.upsert_entry(guild_id, message.id, entry.board_message_id, count)
                    return
                except discord.HTTPException:
                    pass  # board post vanished — fall through and repost
            try:
                posted = await board.send(text, embed=embed)
            except discord.HTTPException:
                return
            await service.upsert_entry(guild_id, message.id, posted.id, count)
        elif entry is not None:
            try:
                board_msg = await board.fetch_message(entry.board_message_id)
                await board_msg.delete()
            except discord.HTTPException:
                pass
            await service.delete_entry(guild_id, message.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Starboard(bot))
