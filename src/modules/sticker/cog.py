"""Custom sticker management: add, rename, list, remove."""

from __future__ import annotations

import io

import discord
from discord.ext import commands

from src.core import embeds
from src.core.http import fetch_bytes


class Sticker(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """Every subcommand touches ctx.guild, but the group's guild_only() is
        skipped for subcommands under invoke_without_command=True (discord.py
        dispatches straight to the subcommand). Guard them all here — the same
        fix the leaderboard cog uses for the same reason."""
        return ctx.guild is not None

    @commands.group(name="sticker", invoke_without_command=True)
    @commands.guild_only()
    async def sticker(self, ctx) -> None:
        """Custom sticker management. Bare command lists the subcommands."""
        await ctx.send(embed=embeds.info("`,sticker add` · `rename` · `remove` · `list`"))

    @sticker.command(name="add", aliases=["create"])
    @commands.has_permissions(manage_expressions=True)
    @commands.bot_has_permissions(manage_expressions=True)
    async def sticker_add(self, ctx, url: str | None = None, name: str | None = None) -> None:
        """Add a sticker from a URL or an attachment (PNG/APNG, 320x320)."""
        if url:
            data = await fetch_bytes(url)
            default = None
        elif ctx.message.attachments:
            att = ctx.message.attachments[0]
            data = await att.read()
            default = att.filename.rsplit(".", 1)[0]
        else:
            raise commands.BadArgument("Give an image URL or attach an image.")
        final = name or default
        if not final:
            raise commands.BadArgument("Give a name for the sticker.")
        file = discord.File(io.BytesIO(data), filename="sticker.png")
        created = await ctx.guild.create_sticker(
            name=final, description=final, emoji="⭐", file=file, reason=f"by {ctx.author}"
        )
        await ctx.send(embed=embeds.success(f"Added sticker **{created.name}**."))

    @sticker.command(name="rename")
    async def sticker_rename(self, ctx, old_name: str, new_name: str) -> None:
        """Rename a server sticker."""
        sticker = discord.utils.get(ctx.guild.stickers, name=old_name)
        if sticker is None:
            raise commands.BadArgument("No sticker by that name.")
        await sticker.edit(name=new_name, reason=f"by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Renamed to **{new_name}**."))

    @sticker.command(name="remove", aliases=["delete", "del"])
    async def sticker_remove(self, ctx, *, name: str) -> None:
        """Remove a server sticker."""
        sticker = discord.utils.get(ctx.guild.stickers, name=name)
        if sticker is None:
            raise commands.BadArgument("No sticker by that name.")
        await sticker.delete(reason=f"by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Removed **{name}**."))

    @sticker.command(name="list", aliases=["all"])
    async def sticker_list(self, ctx) -> None:
        """List the server's custom stickers. (No permission required.)"""
        if not ctx.guild.stickers:
            await ctx.send(embed=embeds.info("This server has no custom stickers."))
            return
        names = ", ".join(s.name for s in ctx.guild.stickers)
        await ctx.send(embed=embeds.info(names[:4000], f"Stickers ({len(ctx.guild.stickers)})"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Sticker(bot))
