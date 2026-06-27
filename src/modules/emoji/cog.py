"""Custom emoji management: add, steal, rename, list, remove, and bulk variants."""

from __future__ import annotations

import re

import discord
from discord.ext import commands

from src.core import embeds
from src.core.http import fetch_bytes

_CUSTOM = re.compile(r"<(a?):(\w+):(\d+)>")


class Emoji(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.group(name="emoji", invoke_without_command=True)
    @commands.guild_only()
    async def emoji(self, ctx) -> None:
        """Custom emoji management. Bare command lists the subcommands."""
        await ctx.send(embed=embeds.info(
            "`,emoji add` · `steal` · `addmany` · `rename` · `remove` · `removemany` · `enlarge` · `list`"
        ))

    @emoji.command(name="enlarge", aliases=["jumbo"])
    async def emoji_enlarge(self, ctx, emoji: discord.PartialEmoji) -> None:
        """Show a custom emoji at full size. (No permission required.)"""
        e = embeds.info("", emoji.name)
        e.set_image(url=emoji.url)
        await ctx.send(embed=e)

    @emoji.command(name="add", aliases=["create"])
    @commands.has_permissions(manage_expressions=True)
    @commands.bot_has_permissions(manage_expressions=True)
    async def emoji_add(self, ctx, emoji: str | None = None, name: str | None = None) -> None:
        """Add an emoji from another custom emoji, a URL, or an attachment."""
        data, default_name = await self._resolve(ctx, emoji)
        final = name or default_name
        if not final:
            raise commands.BadArgument("Give a name for the emoji.")
        created = await ctx.guild.create_custom_emoji(name=final, image=data, reason=f"by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Added {created}."))

    @emoji.command(name="steal")
    async def emoji_steal(self, ctx, emoji: discord.PartialEmoji, name: str | None = None) -> None:
        """Add a custom emoji from another server."""
        data = await fetch_bytes(str(emoji.url))
        created = await ctx.guild.create_custom_emoji(name=name or emoji.name, image=data, reason=f"by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Stole {created}."))

    @emoji.command(name="addmany", aliases=["stealmany"])
    async def emoji_addmany(self, ctx, *, emojis: str) -> None:
        """Add several custom emojis at once."""
        found = _CUSTOM.findall(emojis)
        if not found:
            raise commands.BadArgument("Give one or more custom emojis.")
        added = 0
        for animated, name, eid in found:
            url = f"https://cdn.discordapp.com/emojis/{eid}.{'gif' if animated else 'png'}"
            try:
                await ctx.guild.create_custom_emoji(name=name, image=await fetch_bytes(url), reason=f"by {ctx.author}")
                added += 1
            except (discord.HTTPException, ValueError):
                continue
        await ctx.send(embed=embeds.success(f"Added {added} emoji(s)."))

    @emoji.command(name="rename")
    async def emoji_rename(self, ctx, emoji: discord.Emoji, new_name: str) -> None:
        """Rename a server emoji."""
        if emoji.guild_id != ctx.guild.id:
            raise commands.BadArgument("That emoji isn't from this server.")
        await emoji.edit(name=new_name, reason=f"by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Renamed to `{new_name}` {emoji}."))

    @emoji.command(name="remove", aliases=["delete", "del"])
    async def emoji_remove(self, ctx, emoji: discord.Emoji) -> None:
        """Remove a server emoji."""
        if emoji.guild_id != ctx.guild.id:
            raise commands.BadArgument("That emoji isn't from this server.")
        name = emoji.name
        await emoji.delete(reason=f"by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Removed `{name}`."))

    @emoji.command(name="removemany")
    async def emoji_removemany(self, ctx, *, emojis: str) -> None:
        """Remove several server emojis at once."""
        ids = {int(eid) for _a, _n, eid in _CUSTOM.findall(emojis)}
        removed = 0
        for emoji in list(ctx.guild.emojis):
            if emoji.id in ids:
                try:
                    await emoji.delete(reason=f"by {ctx.author}")
                    removed += 1
                except discord.HTTPException:
                    continue
        await ctx.send(embed=embeds.success(f"Removed {removed} emoji(s)."))

    @emoji.command(name="list", aliases=["all"])
    async def emoji_list(self, ctx) -> None:
        """List the server's custom emojis. (No permission required.)"""
        if not ctx.guild.emojis:
            await ctx.send(embed=embeds.info("This server has no custom emojis."))
            return
        text = " ".join(str(e) for e in ctx.guild.emojis)
        await ctx.send(embed=embeds.info(text[:4000], f"Emojis ({len(ctx.guild.emojis)})"))

    async def _resolve(self, ctx, source: str | None) -> tuple[bytes, str | None]:
        """Return (image_bytes, default_name) from an emoji, URL, or attachment."""
        if source:
            m = _CUSTOM.fullmatch(source.strip())
            if m:
                animated, name, eid = m.groups()
                url = f"https://cdn.discordapp.com/emojis/{eid}.{'gif' if animated else 'png'}"
                return await fetch_bytes(url), name
            return await fetch_bytes(source.strip()), None
        if ctx.message.attachments:
            att = ctx.message.attachments[0]
            return await att.read(), att.filename.rsplit(".", 1)[0]
        raise commands.BadArgument("Give a custom emoji, an image URL, or attach an image.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Emoji(bot))
