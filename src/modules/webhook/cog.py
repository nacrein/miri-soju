"""Managed webhooks: create, list, send, edit, avatar, delete."""

from __future__ import annotations

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.http import fetch_bytes
from src.core.paginator import send_command_browser
from src.modules.webhook import service


class Webhook(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _resolve_hook(self, ctx, short_id: str) -> discord.Webhook | None:
        found = await service.resolve(ctx.guild.id, short_id)
        if found is None:
            return None
        channel_id, webhook_id = found
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return None
        for wh in await channel.webhooks():
            if wh.id == webhook_id:
                return wh
        return None

    @commands.group(name="webhook", invoke_without_command=True)
    @commands.has_permissions(manage_webhooks=True)
    @commands.bot_has_permissions(manage_webhooks=True)
    @commands.guild_only()
    async def webhook(self, ctx) -> None:
        """Manage webhooks the bot owns."""
        await send_command_browser(ctx, ctx.command)

    @webhook.command(name="create")
    @commands.has_permissions(manage_webhooks=True)
    @commands.bot_has_permissions(manage_webhooks=True)
    async def webhook_create(self, ctx, *, name: str) -> None:
        """Create a webhook in this channel."""
        hook = await ctx.channel.create_webhook(name=name, reason=f"by {ctx.author}")
        short = await service.record(ctx.guild.id, ctx.channel.id, hook.id)
        await ctx.send(embed=embeds.success(f"Created webhook **{name}** with id `{short}`."))

    @webhook.command(name="list")
    @commands.has_permissions(manage_webhooks=True)
    async def webhook_list(self, ctx) -> None:
        """List managed webhooks."""
        rows = await service.all_for(ctx.guild.id)
        if not rows:
            await ctx.send(embed=embeds.info("No managed webhooks."))
            return
        lines = [f"`{r.short_id}` · <#{r.channel_id}>" for r in rows]
        await ctx.send(embed=embeds.info("\n".join(lines), f"Webhooks ({len(rows)})"))

    @webhook.command(name="send")
    @commands.has_permissions(manage_webhooks=True)
    @commands.bot_has_permissions(manage_webhooks=True)
    async def webhook_send(self, ctx, short_id: str, *, content: str) -> None:
        """Send a message through a managed webhook."""
        hook = await self._resolve_hook(ctx, short_id)
        if hook is None:
            raise commands.BadArgument("No webhook with that id.")
        await hook.send(content=content, allowed_mentions=discord.AllowedMentions.none())
        await ctx.message.add_reaction(Emojis.SUCCESS)

    @webhook.command(name="edit")
    @commands.has_permissions(manage_webhooks=True)
    @commands.bot_has_permissions(manage_webhooks=True)
    async def webhook_edit(self, ctx, channel: discord.TextChannel, message_id: int, *, content: str) -> None:
        """Edit a message a managed webhook sent in a channel."""
        for wh in await channel.webhooks():
            try:
                await wh.edit_message(message_id, content=content)
                await ctx.message.add_reaction(Emojis.SUCCESS)
                return
            except discord.HTTPException:
                continue
        raise commands.BadArgument("Couldn't edit that message through any webhook here.")

    @webhook.command(name="avatar")
    @commands.has_permissions(manage_webhooks=True)
    @commands.bot_has_permissions(manage_webhooks=True)
    async def webhook_avatar(self, ctx, short_id: str, url: str | None = None) -> None:
        """Set a managed webhook's avatar from a URL or an attachment."""
        hook = await self._resolve_hook(ctx, short_id)
        if hook is None:
            raise commands.BadArgument("No webhook with that id.")
        if url:
            data = await fetch_bytes(url)
        elif ctx.message.attachments:
            data = await ctx.message.attachments[0].read()
        else:
            raise commands.BadArgument("Give an image URL or attach one.")
        await hook.edit(avatar=data, reason=f"by {ctx.author}")
        await ctx.send(embed=embeds.success("Updated the webhook avatar."))

    @webhook.command(name="delete", aliases=["del"])
    @commands.has_permissions(manage_webhooks=True)
    @commands.bot_has_permissions(manage_webhooks=True)
    async def webhook_delete(self, ctx, short_id: str) -> None:
        """Delete a managed webhook."""
        hook = await self._resolve_hook(ctx, short_id)
        if hook is not None:
            try:
                await hook.delete(reason=f"by {ctx.author}")
            except discord.HTTPException:
                pass
        if not await service.forget(ctx.guild.id, short_id):
            raise commands.BadArgument("No webhook with that id.")
        await ctx.send(embed=embeds.success(f"Deleted webhook `{short_id}`."))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Webhook(bot))
