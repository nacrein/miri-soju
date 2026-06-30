"""Tags: per-guild custom text snippets recalled by name.

`,tag <name>` posts the snippet; the subcommands manage them. Anyone may create a
tag; only its author or a member with Manage Server may edit or delete it. There is
deliberately no global message listener — lookups go through the explicit `,tag`
command so tags can never shadow real commands."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.paginator import Paginator, paginate_lines, send_command_browser
from src.modules.tags import service

_MAX_NAME = 100
_MAX_CONTENT = 2000
# Names that would collide with a subcommand and never resolve via `,tag <name>`.
_RESERVED = {"create", "add", "edit", "delete", "del", "remove", "info", "list", "raw"}


def _clean_name(name: str) -> str:
    name = name.strip().lower()
    if not name:
        raise commands.BadArgument("Give a tag name.")
    if len(name) > _MAX_NAME:
        raise commands.BadArgument(f"Tag names are at most {_MAX_NAME} characters.")
    if name in _RESERVED:
        raise commands.BadArgument(f"`{name}` is a reserved word; pick another name.")
    return name


class Tags(commands.Cog, name="Tags"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.group(name="tag", aliases=["t"], invoke_without_command=True)
    @commands.guild_only()
    async def tag(self, ctx, *, name: str | None = None) -> None:
        """Show a tag by name, or list the subcommands when called bare."""
        if name is None:
            await send_command_browser(ctx, ctx.command)
            return
        content = await service.use(ctx.guild.id, name.strip().lower())
        if content is None:
            raise commands.BadArgument(f"No tag named `{name.strip().lower()}`.")
        await ctx.send(content, allowed_mentions=discord.AllowedMentions.none())

    @tag.command(name="create", aliases=["add"])
    async def tag_create(self, ctx, name: str, *, content: str) -> None:
        """Create a tag. Quote the name if it has spaces."""
        name = _clean_name(name)
        if len(content) > _MAX_CONTENT:
            raise commands.BadArgument(f"Tag content is at most {_MAX_CONTENT} characters.")
        if not await service.create(ctx.guild.id, name, content, ctx.author.id):
            raise commands.BadArgument(f"A tag named `{name}` already exists.")
        await ctx.send(embed=embeds.success(f"Created the tag `{name}`."))

    @tag.command(name="edit")
    async def tag_edit(self, ctx, name: str, *, content: str) -> None:
        """Edit a tag you own (or any, with Manage Server)."""
        name = _clean_name(name)
        if len(content) > _MAX_CONTENT:
            raise commands.BadArgument(f"Tag content is at most {_MAX_CONTENT} characters.")
        await self._guard(ctx, name)
        await service.set_content(ctx.guild.id, name, content)
        await ctx.send(embed=embeds.success(f"Edited the tag `{name}`."))

    @tag.command(name="delete", aliases=["del", "remove"])
    async def tag_delete(self, ctx, *, name: str) -> None:
        """Delete a tag you own (or any, with Manage Server)."""
        name = _clean_name(name)
        await self._guard(ctx, name)
        await service.delete(ctx.guild.id, name)
        await ctx.send(embed=embeds.success(f"Deleted the tag `{name}`."))

    @tag.command(name="info")
    async def tag_info(self, ctx, *, name: str) -> None:
        """Show who made a tag and how often it's used."""
        tag = await service.get(ctx.guild.id, name.strip().lower())
        if tag is None:
            raise commands.BadArgument(f"No tag named `{name.strip().lower()}`.")
        e = embeds.info("", f"Tag · {tag.name}")
        e.add_field(name="Author", value=f"<@{tag.author_id}>")
        e.add_field(name="Uses", value=str(tag.uses))
        e.add_field(name="Created", value=discord.utils.format_dt(tag.created_at, "R"))
        await ctx.send(embed=e)

    @tag.command(name="raw")
    async def tag_raw(self, ctx, *, name: str) -> None:
        """Show a tag's raw source (escaped), handy before editing."""
        tag = await service.get(ctx.guild.id, name.strip().lower())
        if tag is None:
            raise commands.BadArgument(f"No tag named `{name.strip().lower()}`.")
        escaped = discord.utils.escape_markdown(tag.content)
        await ctx.send(escaped, allowed_mentions=discord.AllowedMentions.none())

    @tag.command(name="list", aliases=["all"])
    async def tag_list(self, ctx) -> None:
        """List this server's tags."""
        names = await service.list_names(ctx.guild.id)
        if not names:
            await ctx.send(
                embed=embeds.info("No tags yet. Make one with `,tag create <name> <text>`.")
            )
            return
        pages = paginate_lines([f"`{n}`" for n in names], f"Tags ({len(names)})")
        await Paginator(ctx.author.id, pages).start(ctx)

    async def _guard(self, ctx, name: str) -> None:
        """Ensure the tag exists and the invoker may modify it."""
        tag = await service.get(ctx.guild.id, name)
        if tag is None:
            raise commands.BadArgument(f"No tag named `{name}`.")
        if tag.author_id != ctx.author.id and not ctx.author.guild_permissions.manage_guild:
            raise commands.BadArgument("That tag isn't yours (Manage Server can edit any tag).")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Tags(bot))
