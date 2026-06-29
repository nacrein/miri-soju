"""AutoMod: the message-scanning listener and the ``,automod`` configuration tree.

The listener fast-returns on every message that isn't actionable (DM, bot, webhook,
or a guild with automod disabled) before doing any work; everything else is gated by
the cached config. Actions, exemptions, and logging live in the service/enforcement
modules. All commands require manage_guild (via ``cog_check``).
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from src.core import embeds
from src.core.emojis import Emojis
from src.core.paginator import send_command_browser
from src.modules.automod import config as amconfig
from src.modules.automod import detector, enforcement, normalize, service
from src.modules.automod.detector import Violation
from src.modules.moderation import service as mod_service

log = logging.getLogger(__name__)


class Automod(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        from src.core.setup_registry import SetupEntry, register_setup
        from src.modules.automod.setup_view import AutomodSetupView

        register_setup(SetupEntry(
            key="automod", label="AutoMod", emoji=Emojis.SHIELD,
            description="Auto-filter spam, invites, mentions, and bad words with escalating strikes.",
            factory=lambda author_id, guild_id: AutomodSetupView(author_id, guild_id),
        ))

    def cog_unload(self) -> None:
        from src.core.setup_registry import unregister_setup

        unregister_setup("automod")

    async def cog_check(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if not ctx.author.guild_permissions.manage_guild:
            raise commands.MissingPermissions(["manage_guild"])
        return True

    # ── scanning ──────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._scan(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        # Discord edits a message to attach a link/embed unfurl; ignore those so the
        # same content isn't scanned (and double-counted) a second time.
        if before.content != after.content:
            await self._scan(after)

    async def _scan(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot or message.webhook_id is not None:
            return
        if message.type not in (discord.MessageType.default, discord.MessageType.reply):
            return
        if not isinstance(message.author, discord.Member):
            return
        # Hot path: a cached dict hit, and most guilds never enable automod.
        cfg = await service.get_config(message.guild.id)
        if cfg is None or not cfg.enabled:
            return
        lists = await service.get_lists(message.guild.id)
        if message.channel.id in lists["channels"]:
            return
        if await enforcement.is_exempt(
            self.bot, message.guild, message.author, cfg, lists["roles"], lists["channels"], message.channel.id
        ):
            return

        violation = self._stateful_violation(message, cfg)
        if violation is None:
            view = detector.MessageView(
                content=message.content,
                mention_count=len({m.id for m in message.mentions} | {r.id for r in message.role_mentions}),
                mentions_everyone=("@everyone" in message.content or "@here" in message.content),
                author_can_mention_everyone=message.channel.permissions_for(message.author).mention_everyone,
            )
            violation = detector.scan_static(view, cfg, lists["matcher"], lists["domains"])
        if violation is None:
            return
        try:
            await service.apply_violation(
                self.bot, message.guild, message.author, message.channel, message, violation, cfg, lists
            )
        except Exception:
            log.exception("automod enforcement failed in guild %s", message.guild.id)

    def _stateful_violation(self, message: discord.Message, cfg) -> Violation | None:
        if not cfg.filter_spam:
            return None
        gid, uid = message.guild.id, message.author.id
        if service.record_and_check_flood(gid, uid, cfg.spam_count, cfg.spam_interval):
            return Violation("spam", f"sent {cfg.spam_count}+ messages in {cfg.spam_interval}s")
        norm = normalize.normalize_text(message.content)
        if norm and service.record_and_check_duplicate(gid, uid, norm, cfg.duplicate_threshold):
            return Violation("duplicate", "repeated the same message")
        return None

    # ── config commands ───────────────────────────────────────────────────────

    @staticmethod
    def _range(value: int, lo: int, hi: int, label: str) -> int:
        if not lo <= value <= hi:
            raise commands.BadArgument(f"{label} must be between {lo} and {hi}.")
        return value

    @commands.group(name="automod", aliases=["am"], invoke_without_command=True)
    @commands.guild_only()
    async def automod(self, ctx: commands.Context) -> None:
        """Automatic moderation: filters, escalating strikes, and exemptions."""
        await send_command_browser(ctx, ctx.command)

    @automod.command(name="status")
    async def am_status(self, ctx: commands.Context) -> None:
        """Show this server's automod configuration."""
        cfg = await service.get_config(ctx.guild.id)
        if cfg is None or not cfg.enabled:
            await ctx.send(embed=embeds.info("AutoMod is off. `,automod enable` to start (it begins in dry-run)."))
            return
        lists = await service.get_lists(ctx.guild.id)
        active = [n for n in amconfig.FILTERS if getattr(cfg, amconfig.FILTER_FLAG[n])]
        e = embeds.info("", f"{Emojis.SHIELD} AutoMod Settings")
        e.add_field(name="Mode", value="Dry-run (logging only)" if cfg.log_only else "LIVE — enforcing")
        e.add_field(name="Exempt mods", value="Yes" if cfg.exempt_mods else "No")
        e.add_field(name="Strike window", value=f"{cfg.strike_window_hours}h")
        e.add_field(name="Filters on", value=", ".join(active) or "none", inline=False)
        e.add_field(
            name="Escalation",
            value=(f"timeout @{cfg.timeout_at}={cfg.timeout_minutes}m · "
                   f"timeout @{cfg.timeout2_at}={cfg.timeout2_minutes}m · "
                   f"kick @{cfg.kick_at} · ban @{cfg.ban_at}"),
            inline=False,
        )
        e.add_field(name="Words", value=str(len(lists["word_list"])))
        e.add_field(name="Allowed domains", value=str(len(lists["domains"])))
        e.add_field(name="Exempt", value=f"{len(lists['roles'])} role(s) · {len(lists['channels'])} channel(s)")
        await ctx.send(embed=e)

    @automod.command(name="enable")
    async def am_enable(self, ctx: commands.Context) -> None:
        """Turn automod on (starts in dry-run — it logs but takes no action)."""
        await service.set_enabled(ctx.guild.id, True)
        await ctx.send(embed=embeds.success(
            "AutoMod enabled in **dry-run** mode. Turn on filters, then `,automod live` to enforce."
        ))

    @automod.command(name="disable")
    async def am_disable(self, ctx: commands.Context) -> None:
        """Turn automod off."""
        await service.set_enabled(ctx.guild.id, False)
        await ctx.send(embed=embeds.success("AutoMod disabled."))

    @automod.command(name="live")
    async def am_live(self, ctx: commands.Context) -> None:
        """Leave dry-run: automod will start enforcing actions."""
        await service.set_log_only(ctx.guild.id, False)
        await ctx.send(embed=embeds.warning("AutoMod is now **LIVE** and will delete, timeout, kick, and ban."))

    @automod.command(name="dryrun", aliases=["logonly"])
    async def am_dryrun(self, ctx: commands.Context) -> None:
        """Return to dry-run: automod logs violations but takes no action."""
        await service.set_log_only(ctx.guild.id, True)
        await ctx.send(embed=embeds.success("AutoMod is in **dry-run** mode — it logs but won't action anyone."))

    @automod.command(name="filter")
    async def am_filter(self, ctx: commands.Context, name: str, state: bool) -> None:
        """Toggle a filter: invites, links, spam, mentions, words, caps, emoji."""
        flag = amconfig.FILTER_FLAG.get(name.lower())
        if flag is None:
            raise commands.BadArgument(f"Unknown filter. Choose: {', '.join(amconfig.FILTERS)}.")
        await service.set_filter(ctx.guild.id, flag, state)
        await ctx.send(embed=embeds.success(f"Filter `{name.lower()}` turned {'on' if state else 'off'}."))

    @automod.command(name="everyone")
    async def am_everyone(self, ctx: commands.Context, state: bool) -> None:
        """Toggle blocking @everyone/@here from members who lack the permission."""
        await service.set_filter(ctx.guild.id, "block_everyone", state)
        await ctx.send(embed=embeds.success(f"@everyone/@here blocking {'on' if state else 'off'}."))

    @automod.command(name="dm")
    async def am_dm(self, ctx: commands.Context, state: bool) -> None:
        """Toggle DMing a member when automod actions them."""
        await service.set_dm_on_action(ctx.guild.id, state)
        await ctx.send(embed=embeds.success(f"Action DMs {'on' if state else 'off'}."))

    @automod.command(name="exemptmods")
    async def am_exemptmods(self, ctx: commands.Context, state: bool) -> None:
        """Toggle exempting members with moderator permissions (recommended on)."""
        await service.set_exempt_mods(ctx.guild.id, state)
        await ctx.send(embed=embeds.success(f"Exempt-mods {'on' if state else 'off'}."))

    @automod.command(name="window")
    async def am_window(self, ctx: commands.Context, hours: int) -> None:
        """How long strikes count toward escalation (hours)."""
        self._range(hours, amconfig.WINDOW_MIN, amconfig.WINDOW_MAX, "Window")
        await service.set_strike_window(ctx.guild.id, hours)
        await ctx.send(embed=embeds.success(f"Strike window set to {hours}h."))

    @automod.command(name="mentions")
    async def am_mentions(self, ctx: commands.Context, limit: int) -> None:
        """Max user/role mentions allowed in one message."""
        self._range(limit, amconfig.MENTION_MIN, amconfig.MENTION_MAX, "Mention limit")
        await service.set_mention_limit(ctx.guild.id, limit)
        await ctx.send(embed=embeds.success(f"Mention limit set to {limit}."))

    @automod.command(name="caps")
    async def am_caps(self, ctx: commands.Context, percent: int, min_len: int) -> None:
        """Caps filter: % uppercase to trip, and the min message length to check."""
        self._range(percent, amconfig.CAPS_PCT_MIN, amconfig.CAPS_PCT_MAX, "Percent")
        self._range(min_len, amconfig.CAPS_LEN_MIN, amconfig.CAPS_LEN_MAX, "Min length")
        await service.set_caps(ctx.guild.id, percent, min_len)
        await ctx.send(embed=embeds.success(f"Caps filter set to {percent}% over {min_len} chars."))

    @automod.command(name="emoji")
    async def am_emoji(self, ctx: commands.Context, limit: int) -> None:
        """Max emoji allowed in one message."""
        self._range(limit, amconfig.EMOJI_MIN, amconfig.EMOJI_MAX, "Emoji limit")
        await service.set_emoji_limit(ctx.guild.id, limit)
        await ctx.send(embed=embeds.success(f"Emoji limit set to {limit}."))

    @automod.command(name="spam")
    async def am_spam(self, ctx: commands.Context, count: int, interval: int) -> None:
        """Flood filter: trip on `count` messages within `interval` seconds."""
        self._range(count, amconfig.SPAM_COUNT_MIN, amconfig.SPAM_COUNT_MAX, "Count")
        self._range(interval, amconfig.SPAM_INTERVAL_MIN, amconfig.SPAM_INTERVAL_MAX, "Interval")
        await service.set_spam(ctx.guild.id, count, interval)
        await ctx.send(embed=embeds.success(f"Spam filter set to {count} messages / {interval}s."))

    @automod.command(name="duplicates", aliases=["dupes"])
    async def am_duplicates(self, ctx: commands.Context, count: int) -> None:
        """How many identical messages in a row trip the duplicate filter."""
        self._range(count, amconfig.DUP_MIN, amconfig.DUP_MAX, "Duplicates")
        await service.set_duplicate_threshold(ctx.guild.id, count)
        await ctx.send(embed=embeds.success(f"Duplicate threshold set to {count}."))

    @automod.command(name="timeout")
    async def am_timeout(self, ctx: commands.Context, tier: int, at: int, duration: str) -> None:
        """Set a timeout tier: `,automod timeout 1 2 10m` = at 2 strikes, time out 10m."""
        if tier not in (1, 2):
            raise commands.BadArgument("Tier must be 1 or 2.")
        self._range(at, amconfig.STRIKE_MIN, amconfig.STRIKE_MAX, "Strikes")
        minutes = max(1, int(mod_service.parse_duration(duration).total_seconds() // 60))
        fields = (
            {"timeout_at": at, "timeout_minutes": minutes} if tier == 1
            else {"timeout2_at": at, "timeout2_minutes": minutes}
        )
        await service.set_thresholds(ctx.guild.id, **fields)
        verb = "disabled" if at == 0 else f"at {at} strike(s) → {minutes}m"
        await ctx.send(embed=embeds.success(f"Timeout tier {tier} {verb}."))

    @automod.command(name="kick")
    async def am_kick(self, ctx: commands.Context, at: int) -> None:
        """Strike count that triggers a kick (0 = off)."""
        self._range(at, amconfig.STRIKE_MIN, amconfig.STRIKE_MAX, "Strikes")
        await service.set_thresholds(ctx.guild.id, kick_at=at)
        await ctx.send(embed=embeds.success("Kick tier disabled." if at == 0 else f"Kick at {at} strike(s)."))

    @automod.command(name="ban")
    async def am_ban(self, ctx: commands.Context, at: int) -> None:
        """Strike count that triggers a ban (0 = off)."""
        self._range(at, amconfig.STRIKE_MIN, amconfig.STRIKE_MAX, "Strikes")
        await service.set_thresholds(ctx.guild.id, ban_at=at)
        await ctx.send(embed=embeds.success("Ban tier disabled." if at == 0 else f"Ban at {at} strike(s)."))

    # ── banned words ──────────────────────────────────────────────────────────

    @automod.group(name="words", invoke_without_command=True)
    async def am_words(self, ctx: commands.Context) -> None:
        """The banned-word list (matching resists leetspeak and spacing)."""
        await self._show_words(ctx)

    @am_words.command(name="add")
    async def am_words_add(self, ctx: commands.Context, *, words: str) -> None:
        """Add one or more banned words (comma- or newline-separated)."""
        items = [w.strip() for w in words.replace(",", "\n").splitlines() if w.strip()]
        added = sum([await service.add_word(ctx.guild.id, w) for w in items])
        await ctx.send(embed=embeds.success(f"Added {added} word(s)."))

    @am_words.command(name="remove", aliases=["rm"])
    async def am_words_remove(self, ctx: commands.Context, *, word: str) -> None:
        """Remove a banned word."""
        if not await service.remove_word(ctx.guild.id, word):
            raise commands.BadArgument("That word isn't on the list.")
        await ctx.send(embed=embeds.success("Removed."))

    async def _show_words(self, ctx: commands.Context) -> None:
        words = await service.list_words(ctx.guild.id)
        if not words:
            await ctx.send(embed=embeds.info("No banned words. `,automod words add <word>`"))
            return
        await ctx.send(embed=embeds.info(", ".join(f"`{w}`" for w in words), f"Banned words ({len(words)})"))

    # ── allowed domains ───────────────────────────────────────────────────────

    @automod.group(name="allow", invoke_without_command=True)
    async def am_allow(self, ctx: commands.Context) -> None:
        """Domains the link filter always permits."""
        await self._show_domains(ctx)

    @am_allow.command(name="add")
    async def am_allow_add(self, ctx: commands.Context, domain: str) -> None:
        """Allowlist a domain (e.g. youtube.com)."""
        if not await service.add_domain(ctx.guild.id, domain):
            raise commands.BadArgument("That domain is already allowed (or invalid).")
        await ctx.send(embed=embeds.success(f"Allowed `{domain}`."))

    @am_allow.command(name="remove", aliases=["rm"])
    async def am_allow_remove(self, ctx: commands.Context, domain: str) -> None:
        """Remove a domain from the allowlist."""
        if not await service.remove_domain(ctx.guild.id, domain):
            raise commands.BadArgument("That domain isn't allowlisted.")
        await ctx.send(embed=embeds.success("Removed."))

    async def _show_domains(self, ctx: commands.Context) -> None:
        domains = await service.list_domains(ctx.guild.id)
        if not domains:
            await ctx.send(embed=embeds.info("No allowlisted domains. `,automod allow add <domain>`"))
            return
        await ctx.send(embed=embeds.info(", ".join(f"`{d}`" for d in domains), f"Allowed domains ({len(domains)})"))

    # ── exemptions ────────────────────────────────────────────────────────────

    @automod.group(name="exempt", invoke_without_command=True)
    async def am_exempt(self, ctx: commands.Context) -> None:
        """Roles and channels the automod never acts on."""
        await self._show_exempt(ctx)

    @am_exempt.command(name="role")
    async def am_exempt_role(self, ctx: commands.Context, action: str, *, role: discord.Role) -> None:
        """`add` or `remove` an exempt role."""
        await self._exempt_change(ctx, action, role.mention,
                                  service.add_exempt_role, service.remove_exempt_role, role.id)

    @am_exempt.command(name="channel")
    async def am_exempt_channel(self, ctx: commands.Context, action: str, *, channel: discord.TextChannel) -> None:
        """`add` or `remove` an exempt channel."""
        await self._exempt_change(ctx, action, channel.mention,
                                  service.add_exempt_channel, service.remove_exempt_channel, channel.id)

    async def _exempt_change(self, ctx, action, mention, add_fn, remove_fn, target_id) -> None:
        act = action.lower()
        if act not in ("add", "remove"):
            raise commands.BadArgument("Use `add` or `remove`.")
        if act == "add":
            await add_fn(ctx.guild.id, target_id)
            await ctx.send(embed=embeds.success(f"{mention} is now exempt."))
        else:
            await remove_fn(ctx.guild.id, target_id)
            await ctx.send(embed=embeds.success(f"{mention} is no longer exempt."))

    async def _show_exempt(self, ctx: commands.Context) -> None:
        lists = await service.get_lists(ctx.guild.id)
        roles = " ".join(f"<@&{r}>" for r in lists["roles"]) or "none"
        channels = " ".join(f"<#{c}>" for c in lists["channels"]) or "none"
        e = embeds.info("", "AutoMod Exemptions")
        e.add_field(name="Roles", value=roles, inline=False)
        e.add_field(name="Channels", value=channels, inline=False)
        await ctx.send(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Automod(bot))
