"""Fun: anime reaction gifs and internet-culture verdicts. All stateless.

Two families share one cog:

* Reaction commands (``hug``, ``kiss`` ...) post an anime gif of one member doing
  a thing to another, sourced from nekos.best via :mod:`.gifs`. A short per-user
  cooldown also shields the upstream API.
* Culture commands (``rizz``, ``aura`` ...) hand out a verdict. The scored ones are
  seeded per user, per UTC day (see ``_seed``) so a score holds for the day and
  rerolls tomorrow, which makes it feel real and worth screenshotting. The chaos
  ones (``ratio``, ``sus``, ``caught``) stay fully random every time.

Tuning (lists, tiers, colours, cooldown, timeout) all lives in :mod:`.config`.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime

import discord
from discord.ext import commands

from src.core import embeds
from src.modules.fun import config, gifs


def _seed(command: str, user_id: int) -> random.Random:
    """A per-user, per-day RNG: same person + same command + same UTC day gives the
    same rolls, so a daily verdict is stable until midnight UTC then rerolls."""
    today = datetime.now(UTC).date().toordinal()
    return random.Random(f"{command}:{user_id}:{today}")


def _tier(value: int, tiers: list[tuple[int, str]]) -> str:
    """Label for ``value`` from an ascending ``(min, label)`` table: the highest
    tier whose minimum the value reaches."""
    label = tiers[0][1]
    for threshold, name in tiers:
        if value >= threshold:
            label = name
        else:
            break
    return label


def _subject(author: discord.abc.User, target: discord.abc.User) -> tuple[str, str]:
    """``(subject, to_be)`` that reads cleanly when someone targets themselves:
    ('You', 'are') for self, else (mention, 'is')."""
    if target.id == author.id:
        return "You", "are"
    return target.mention, "is"


def _possessive(author: discord.abc.User, target: discord.abc.User) -> str:
    """'Your' for a self-target, else the target's mention in possessive form."""
    return "Your" if target.id == author.id else f"{target.mention}'s"


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_unload(self) -> None:
        # Close the shared gif session so aiohttp doesn't log an unclosed-session warning.
        await gifs.close_session()

    # ── reaction gifs ────────────────────────────────────────────────────────────

    async def _react(
        self, ctx: commands.Context, action: str, verb: str, target: discord.Member
    ) -> None:
        """Post a '{author} {verb} {target}' embed with a gif of the action. Falls
        back to a gif-less embed if the upstream wouldn't hand one over."""
        url = await gifs.fetch_gif(action)
        e = embeds.info(f"{ctx.author.mention} {verb} {target.mention}")
        if url:
            e.set_image(url=url)
        await ctx.send(embed=e)

    @commands.command(name="hug", extras={"example": "hug @user"})
    @commands.guild_only()
    @commands.cooldown(1, config.GIF_COOLDOWN_SECONDS, commands.BucketType.user)
    async def hug(self, ctx: commands.Context, member: discord.Member) -> None:
        """Hug someone."""
        await self._react(ctx, "hug", "hugs", member)

    @commands.command(name="kiss", extras={"example": "kiss @user"})
    @commands.guild_only()
    @commands.cooldown(1, config.GIF_COOLDOWN_SECONDS, commands.BucketType.user)
    async def kiss(self, ctx: commands.Context, member: discord.Member) -> None:
        """Kiss someone."""
        await self._react(ctx, "kiss", "kisses", member)

    @commands.command(name="slap", extras={"example": "slap @user"})
    @commands.guild_only()
    @commands.cooldown(1, config.GIF_COOLDOWN_SECONDS, commands.BucketType.user)
    async def slap(self, ctx: commands.Context, member: discord.Member) -> None:
        """Slap someone."""
        await self._react(ctx, "slap", "slaps", member)

    @commands.command(name="punch", extras={"example": "punch @user"})
    @commands.guild_only()
    @commands.cooldown(1, config.GIF_COOLDOWN_SECONDS, commands.BucketType.user)
    async def punch(self, ctx: commands.Context, member: discord.Member) -> None:
        """Punch someone."""
        await self._react(ctx, "punch", "punches", member)

    @commands.command(name="pinch", extras={"example": "pinch @user"})
    @commands.guild_only()
    @commands.cooldown(1, config.GIF_COOLDOWN_SECONDS, commands.BucketType.user)
    async def pinch(self, ctx: commands.Context, member: discord.Member) -> None:
        """Pinch someone."""
        # nekos.best has no pinch endpoint; gifs.ENDPOINT_FALLBACKS borrows pat.
        await self._react(ctx, "pinch", "pinches", member)

    @commands.command(name="pat", extras={"example": "pat @user"})
    @commands.guild_only()
    @commands.cooldown(1, config.GIF_COOLDOWN_SECONDS, commands.BucketType.user)
    async def pat(self, ctx: commands.Context, member: discord.Member) -> None:
        """Pat someone."""
        await self._react(ctx, "pat", "pats", member)

    @commands.command(name="poke", extras={"example": "poke @user"})
    @commands.guild_only()
    @commands.cooldown(1, config.GIF_COOLDOWN_SECONDS, commands.BucketType.user)
    async def poke(self, ctx: commands.Context, member: discord.Member) -> None:
        """Poke someone."""
        await self._react(ctx, "poke", "pokes", member)

    @commands.command(name="bite", extras={"example": "bite @user"})
    @commands.guild_only()
    @commands.cooldown(1, config.GIF_COOLDOWN_SECONDS, commands.BucketType.user)
    async def bite(self, ctx: commands.Context, member: discord.Member) -> None:
        """Bite someone."""
        await self._react(ctx, "bite", "bites", member)

    @commands.command(name="cuddle", extras={"example": "cuddle @user"})
    @commands.guild_only()
    @commands.cooldown(1, config.GIF_COOLDOWN_SECONDS, commands.BucketType.user)
    async def cuddle(self, ctx: commands.Context, member: discord.Member) -> None:
        """Cuddle someone."""
        await self._react(ctx, "cuddle", "cuddles", member)

    @commands.command(name="bonk", extras={"example": "bonk @user"})
    @commands.guild_only()
    @commands.cooldown(1, config.GIF_COOLDOWN_SECONDS, commands.BucketType.user)
    async def bonk(self, ctx: commands.Context, member: discord.Member) -> None:
        """Bonk someone."""
        await self._react(ctx, "bonk", "bonks", member)

    # ── internet culture ─────────────────────────────────────────────────────────

    def _is_bot(self, member: discord.abc.User) -> bool:
        return self.bot.user is not None and member.id == self.bot.user.id

    async def _bot_egg(self, ctx: commands.Context, member: discord.Member, command: str) -> bool:
        """If the target is me, send the canned reply and report it handled."""
        if not self._is_bot(member):
            return False
        reply = config.BOT_REPLIES.get(command, config.GENERIC_BOT_REPLY)
        await ctx.send(embed=embeds.info(reply))
        return True

    @commands.command(name="rizz", extras={"example": "rizz @user"})
    @commands.guild_only()
    async def rizz(self, ctx: commands.Context, member: discord.Member) -> None:
        """Rate someone's rizz out of 100. Resets daily."""
        if await self._bot_egg(ctx, member, "rizz"):
            return
        score = _seed("rizz", member.id).randint(0, 100)
        e = embeds.info(
            f"{_possessive(ctx.author, member)} rizz is **{score}/100**.\n"
            f"> {_tier(score, config.RIZZ_TIERS)}",
            "Rizz Check",
        )
        e.colour = config.COLOR_RIZZ
        await ctx.send(embed=e)

    @commands.command(name="npc", extras={"example": "npc @user"})
    @commands.guild_only()
    async def npc(self, ctx: commands.Context, member: discord.Member) -> None:
        """Declare someone a certified NPC, with their trait of the day."""
        if await self._bot_egg(ctx, member, "npc"):
            return
        trait = _seed("npc", member.id).choice(config.NPC_TRAITS)
        subject, to_be = _subject(ctx.author, member)
        e = embeds.info(f"{subject} {to_be} a certified NPC.\nTrait: {trait}", "NPC Detected")
        e.colour = config.COLOR_NPC
        await ctx.send(embed=e)

    @commands.command(name="sigma", extras={"example": "sigma @user"})
    @commands.guild_only()
    async def sigma(self, ctx: commands.Context, member: discord.Member) -> None:
        """Measure someone's sigma grindset, with a quote. Resets daily."""
        if await self._bot_egg(ctx, member, "sigma"):
            return
        rng = _seed("sigma", member.id)
        score = rng.randint(0, 100)
        quote = rng.choice(config.SIGMA_QUOTES)
        e = embeds.info(
            f"{_possessive(ctx.author, member)} sigma rating: "
            f"**{score}/100** ({_tier(score, config.SIGMA_TIERS)})\n\n> {quote}",
            "Sigma Rating",
        )
        e.colour = config.COLOR_SIGMA
        await ctx.send(embed=e)

    @commands.command(name="ratio", extras={"example": "ratio @user"})
    @commands.guild_only()
    async def ratio(self, ctx: commands.Context, member: discord.Member) -> None:
        """Hit someone with a fake ratio. Stays random."""
        if await self._bot_egg(ctx, member, "ratio"):
            return
        likes = random.randint(12, 480)
        replies = likes * random.randint(3, 12) + random.randint(0, 99)
        e = embeds.info(
            f"{_possessive(ctx.author, member)} post just got ratioed.\n"
            f"Likes: **{likes:,}**  |  Replies: **{replies:,}**\n"
            f"The ratio is mathematically undeniable.",
            "Ratio",
        )
        e.colour = config.COLOR_RATIO
        await ctx.send(embed=e)

    @commands.command(name="sus", extras={"example": "sus @user"})
    @commands.guild_only()
    async def sus(self, ctx: commands.Context, member: discord.Member) -> None:
        """Accuse someone of being the impostor. Stays random."""
        if await self._bot_egg(ctx, member, "sus"):
            return
        colour_name = random.choice(list(config.AMONG_US_COLORS))
        task = random.choice(config.AMONG_US_TASKS)
        subject, to_be = _subject(ctx.author, member)
        e = embeds.info(
            f"{subject} {to_be} acting kind of sus.\n"
            f"Suspect: **{colour_name}**\n"
            f"Last seen: {task}",
            "Emergency Meeting",
        )
        e.colour = discord.Color.from_str(config.AMONG_US_COLORS[colour_name])
        await ctx.send(embed=e)

    @commands.command(name="skill", extras={"example": "skill @user"})
    @commands.guild_only()
    async def skill(self, ctx: commands.Context, member: discord.Member) -> None:
        """Diagnose a skill issue, with severity. Resets daily."""
        if await self._bot_egg(ctx, member, "skill"):
            return
        score = _seed("skill", member.id).randint(0, 100)
        e = embeds.info(
            f"{_possessive(ctx.author, member)} problem? Skill issue.\n"
            f"Severity: **{score}/100** ({_tier(score, config.SKILL_TIERS)})",
            "Skill Issue",
        )
        e.colour = config.COLOR_SKILL
        await ctx.send(embed=e)

    @commands.command(name="glazing", extras={"example": "glazing @user"})
    @commands.guild_only()
    async def glazing(self, ctx: commands.Context, member: discord.Member) -> None:
        """Measure how hard someone is glazing, and over what. Resets daily."""
        if await self._bot_egg(ctx, member, "glazing"):
            return
        rng = _seed("glazing", member.id)
        pct = rng.randint(0, 100)
        subject = rng.choice(config.GLAZING_SUBJECTS)
        who, to_be = _subject(ctx.author, member)
        e = embeds.info(
            f"{who} {to_be} **{pct}%** busy glazing {subject}.\n"
            f"> {_tier(pct, config.GLAZING_TIERS)}",
            "Glaze Meter",
        )
        e.colour = config.COLOR_GLAZING
        await ctx.send(embed=e)

    @commands.command(name="aura", extras={"example": "aura @user"})
    @commands.guild_only()
    async def aura(self, ctx: commands.Context, member: discord.Member) -> None:
        """Read someone's aura points, which can go negative. Resets daily."""
        if await self._bot_egg(ctx, member, "aura"):
            return
        points = _seed("aura", member.id).randint(config.AURA_MIN, config.AURA_MAX)
        e = embeds.info(
            f"{_possessive(ctx.author, member)} aura: **{points:+,}** points\n"
            f"> {_tier(points, config.AURA_TIERS)}",
            "Aura Check",
        )
        e.colour = config.COLOR_AURA
        await ctx.send(embed=e)

    @commands.command(name="based", extras={"example": "based"})
    @commands.guild_only()
    async def based(self, ctx: commands.Context) -> None:
        """Get your own based rating for the day."""
        score = _seed("based", ctx.author.id).randint(0, 100)
        e = embeds.info(
            f"Your based rating: **{score}/100**\n> {_tier(score, config.BASED_TIERS)}",
            "Based?",
        )
        e.colour = config.COLOR_BASED
        await ctx.send(embed=e)

    @commands.command(name="caught", extras={"example": "caught @user"})
    @commands.guild_only()
    async def caught(self, ctx: commands.Context, member: discord.Member) -> None:
        """Catch someone in 4K, with the evidence. Stays random."""
        if await self._bot_egg(ctx, member, "caught"):
            return
        evidence = random.choice(config.CAUGHT_EVIDENCE)
        subject, to_be = _subject(ctx.author, member)
        e = embeds.info(
            f"{subject} {to_be} caught in 4K.\n"
            f"Evidence: {evidence}\n"
            f"No getting out of this one.",
            "Caught in 4K",
        )
        e.colour = config.COLOR_CAUGHT
        await ctx.send(embed=e)

    @commands.command(name="ick", extras={"example": "ick @user"})
    @commands.guild_only()
    async def ick(self, ctx: commands.Context, member: discord.Member) -> None:
        """Reveal someone's ick of the day."""
        if await self._bot_egg(ctx, member, "ick"):
            return
        the_ick = _seed("ick", member.id).choice(config.ICKS)
        e = embeds.info(f"{_possessive(ctx.author, member)} ick of the day: {the_ick}.", "The Ick")
        e.colour = config.COLOR_ICK
        await ctx.send(embed=e)

    @commands.command(name="delulu", extras={"example": "delulu @user"})
    @commands.guild_only()
    async def delulu(self, ctx: commands.Context, member: discord.Member) -> None:
        """Measure someone's delulu percentage. Resets daily."""
        if await self._bot_egg(ctx, member, "delulu"):
            return
        pct = _seed("delulu", member.id).randint(0, 100)
        e = embeds.info(
            f"{_possessive(ctx.author, member)} delulu level: **{pct}%**\n"
            f"> {_tier(pct, config.DELULU_TIERS)}",
            "Delulu Meter",
        )
        e.colour = config.COLOR_DELULU
        await ctx.send(embed=e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
