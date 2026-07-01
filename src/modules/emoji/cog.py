"""Custom emoji management: add, rename, remove, list, and enlarge.

`add` and `remove` each take one or several emojis, so there are no separate bulk
commands."""

from __future__ import annotations

import re

import discord
from discord.ext import commands

from src.core import embeds
from src.core.http import fetch_bytes
from src.core.paginator import send_command_browser
from src.core.views import confirm_prompt

_CUSTOM = re.compile(r"<(a?):(\w+):(\d+)>")


class Emoji(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """Subcommands touch ctx.guild, but the group's guild_only() is skipped
        for them under invoke_without_command=True. Guard the whole cog here.
        The same fix the leaderboard cog uses for the same reason."""
        return ctx.guild is not None

    @commands.group(name="emoji", invoke_without_command=True)
    @commands.guild_only()
    async def emoji(self, ctx) -> None:
        """Custom emoji management. Bare command lists the subcommands."""
        await send_command_browser(ctx, ctx.command)

    @emoji.command(name="enlarge", aliases=["jumbo"])
    async def emoji_enlarge(self, ctx, emoji: discord.PartialEmoji) -> None:
        """Show a custom emoji at full size. (No permission required.)"""
        e = embeds.info("", emoji.name)
        e.set_image(url=emoji.url)
        await ctx.send(embed=e)

    @emoji.command(name="add", aliases=["create", "steal", "addmany", "stealmany"])
    @commands.has_permissions(manage_expressions=True)
    @commands.bot_has_permissions(manage_expressions=True)
    async def emoji_add(self, ctx, *, emojis: str | None = None) -> None:
        """Add one or more emojis.

        Give one source (a custom emoji, an image URL, or an attachment) with an
        optional name, or paste several custom emojis to add them all at once
        (each keeps its own name).
        """
        tokens = _CUSTOM.findall(emojis or "")
        if len(tokens) >= 2:  # bulk: each custom emoji added under its own name
            added = 0
            for animated, name, eid in tokens:
                url = f"https://cdn.discordapp.com/emojis/{eid}.{'gif' if animated else 'png'}"
                try:
                    await ctx.guild.create_custom_emoji(
                        name=name, image=await fetch_bytes(url), reason=f"by {ctx.author}"
                    )
                    added += 1
                except (discord.HTTPException, ValueError):
                    continue
            await ctx.send(embed=embeds.success(f"Added {added} emoji(s)."))
            return
        # single source, with an optional trailing name
        parts = (emojis or "").split()
        source = parts[0] if parts else None
        name = parts[1] if len(parts) > 1 else None
        data, default_name = await self._resolve(ctx, source)
        final = name or default_name
        if not final:
            raise commands.BadArgument("Give a name for the emoji.")
        created = await ctx.guild.create_custom_emoji(
            name=final, image=data, reason=f"by {ctx.author}"
        )
        await ctx.send(embed=embeds.success(f"Added {created}."))

    @emoji.command(name="rename")
    @commands.has_permissions(manage_expressions=True)
    @commands.bot_has_permissions(manage_expressions=True)
    async def emoji_rename(self, ctx, emoji: discord.Emoji, new_name: str) -> None:
        """Rename a server emoji."""
        if emoji.guild_id != ctx.guild.id:
            raise commands.BadArgument("That emoji isn't from this server.")
        await emoji.edit(name=new_name, reason=f"by {ctx.author}")
        await ctx.send(embed=embeds.success(f"Renamed to `{new_name}` {emoji}."))

    @emoji.command(name="remove", aliases=["delete", "del", "removemany"])
    @commands.has_permissions(manage_expressions=True)
    @commands.bot_has_permissions(manage_expressions=True)
    async def emoji_remove(self, ctx, emojis: commands.Greedy[discord.Emoji]) -> None:
        """Remove one or more server emojis."""
        if not emojis:
            raise commands.BadArgument("Give one or more server emojis.")
        targets = [e for e in emojis if e.guild_id == ctx.guild.id]
        if not targets:
            raise commands.BadArgument("None of those are emojis from this server.")
        label = f"`{targets[0].name}`" if len(targets) == 1 else f"{len(targets)} emojis"
        if not await confirm_prompt(ctx, f"Remove {label}? This can't be undone."):
            return
        removed = []
        for emoji in targets:
            try:
                await emoji.delete(reason=f"by {ctx.author}")
                removed.append(emoji.name)
            except discord.HTTPException:
                continue
        if not removed:
            raise commands.BadArgument("Couldn't remove those emojis.")
        if len(removed) == 1:
            await ctx.send(embed=embeds.success(f"Removed `{removed[0]}`."))
        else:
            await ctx.send(embed=embeds.success(f"Removed {len(removed)} emojis."))

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
