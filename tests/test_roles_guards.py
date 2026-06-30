"""Tests for the role-binding guards across button/reaction/booster roles.

Cover the bug-hunt fixes: duplicate-role rejection on a button message (DB-backed),
the persistent button callback's grant-time hierarchy/type revalidation, the
@everyone/managed rejection at add time, and the booster reposition position cap.

Pure/no live Discord (SimpleNamespace fakes), except the buttonrole add path which
exercises the real service against the test SQLite DB."""

from __future__ import annotations

from types import SimpleNamespace

import discord
import pytest

from src.database.base import Base
from src.database.session import engine
from src.modules.boosterrole import service as boost_service
from src.modules.boosterrole.cog import Boosterrole
from src.modules.buttonrole import service as br_service
from src.modules.buttonrole.cog import ButtonRoleButton, ButtonRoleCog
from src.modules.reactionrole.cog import ReactionRole


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── fakes ──────────────────────────────────────────────────────────────────────

class _Role:
    """A minimal stand-in for discord.Role with position-based comparison."""

    def __init__(self, rid: int, position: int = 5, *, managed=False, default=False) -> None:
        self.id = rid
        self.position = position
        self._managed = managed
        self._default = default
        self.mention = f"<@&{rid}>"

    @property
    def managed(self) -> bool:
        return self._managed

    def is_default(self) -> bool:
        return self._default

    def __ge__(self, other) -> bool:
        return self.position >= other.position

    def __lt__(self, other) -> bool:
        return self.position < other.position


class _Response:
    def __init__(self) -> None:
        self.sent: tuple | None = None

    async def send_message(self, *args, **kwargs) -> None:
        self.sent = (args, kwargs)


class _Ctx:
    def __init__(self, guild, bot_user_id: int) -> None:
        self.guild = guild
        self.bot = SimpleNamespace(user=SimpleNamespace(id=bot_user_id))
        self.sent: list = []

    async def send(self, *args, **kwargs) -> None:
        self.sent.append((args, kwargs))


# ── Finding 1: duplicate role on one message is rejected (DB-backed) ─────────────

async def test_buttonrole_add_rejects_duplicate_role_on_same_message():
    await _schema()
    guild_id, message_id, role_id = 90001, 91001, 92001
    bot_id = 93001
    # Seed the message with one button for the role via the real service.
    await br_service.add(guild_id, message_id, role_id, "Pick me", None, "secondary")

    cog = ButtonRoleCog(SimpleNamespace(user=SimpleNamespace(id=bot_id)))
    me_top = _Role(99999, position=100)
    guild = SimpleNamespace(id=guild_id, me=SimpleNamespace(top_role=me_top))
    role = _Role(role_id, position=5)
    message = SimpleNamespace(author=SimpleNamespace(id=bot_id), id=message_id, edit=None)
    ctx = _Ctx(guild, bot_id)

    with pytest.raises(discord.ext.commands.BadArgument):
        await cog.br_add.callback(cog, ctx, message, role, "secondary", None, label=None)

    # The duplicate must not have been persisted: still exactly one row.
    rows = await br_service.for_message(message_id)
    assert len(rows) == 1


async def test_buttonrole_add_rejects_everyone_and_managed():
    cog = ButtonRoleCog(SimpleNamespace(user=SimpleNamespace(id=1)))
    me_top = _Role(99999, position=100)
    guild = SimpleNamespace(id=1, me=SimpleNamespace(top_role=me_top))
    message = SimpleNamespace(author=SimpleNamespace(id=1), id=2)
    ctx = _Ctx(guild, 1)

    everyone = _Role(3, position=0, default=True)
    managed = _Role(4, position=5, managed=True)
    for role in (everyone, managed):
        with pytest.raises(discord.ext.commands.BadArgument):
            await cog.br_add.callback(cog, ctx, message, role, "secondary", None, label=None)


# ── Finding 2: the persistent button callback revalidates at grant time ──────────

def _interaction(guild, member, role):
    return SimpleNamespace(
        guild=guild,
        user=member,
        response=_Response(),
    )


async def test_button_callback_refuses_role_above_bot():
    button = ButtonRoleButton(50)
    me_top = _Role(999, position=10)
    role = _Role(50, position=10)  # equal -> >= bot top
    guild = SimpleNamespace(me=SimpleNamespace(top_role=me_top), get_role=lambda _id: role)
    member = SimpleNamespace(roles=[])
    interaction = _interaction(guild, member, role)

    await button.callback(interaction)

    assert interaction.response.sent is not None
    assert "can't manage" in interaction.response.sent[0][0]


async def test_button_callback_refuses_managed_role():
    button = ButtonRoleButton(51)
    me_top = _Role(999, position=100)
    role = _Role(51, position=5, managed=True)
    guild = SimpleNamespace(me=SimpleNamespace(top_role=me_top), get_role=lambda _id: role)
    member = SimpleNamespace(roles=[])
    interaction = _interaction(guild, member, role)

    await button.callback(interaction)

    assert interaction.response.sent is not None
    assert "can't manage" in interaction.response.sent[0][0]


async def test_button_callback_grants_a_normal_role():
    button = ButtonRoleButton(52)
    me_top = _Role(999, position=100)
    role = _Role(52, position=5)
    added: list = []

    async def _add_roles(r, reason=None):
        added.append(r)

    member = SimpleNamespace(roles=[], add_roles=_add_roles)
    guild = SimpleNamespace(me=SimpleNamespace(top_role=me_top), get_role=lambda _id: role)
    interaction = _interaction(guild, member, role)

    await button.callback(interaction)

    assert added == [role]
    assert interaction.response.sent is not None


# ── Finding 3: reactionrole add rejects @everyone / managed roles ────────────────

async def test_reactionrole_add_rejects_everyone_and_managed():
    cog = ReactionRole(SimpleNamespace())
    me_top = _Role(999, position=100)
    guild = SimpleNamespace(id=1, me=SimpleNamespace(top_role=me_top))
    ctx = SimpleNamespace(guild=guild)
    message = SimpleNamespace()

    everyone = _Role(3, position=0, default=True)
    managed = _Role(4, position=5, managed=True)
    for role in (everyone, managed):
        with pytest.raises(discord.ext.commands.BadArgument):
            await cog.rr_add.callback(cog, ctx, message, "x", role=role)


# ── Finding 4: booster reposition never targets a slot at/above the bot ──────────

async def test_booster_reposition_clamps_below_bot_top_role(monkeypatch):
    cog = Boosterrole.__new__(Boosterrole)  # skip loop-starting __init__

    anchor = _Role(700, position=9)          # anchor sits just below the bot
    me_top = _Role(999, position=10)
    cohort = [_Role(701, position=3), _Role(702, position=4), _Role(703, position=5)]

    roles_by_id = {r.id: r for r in [anchor, me_top, *cohort]}
    guild = SimpleNamespace(
        id=70000,
        get_role=lambda rid: roles_by_id.get(rid),
        me=SimpleNamespace(top_role=me_top),
    )

    async def _fake_list_roles(_gid):
        return [SimpleNamespace(role_id=r.id) for r in cohort]

    monkeypatch.setattr(boost_service, "list_roles", _fake_list_roles)

    captured: dict = {}

    async def _edit_positions(positions=None, reason=None):
        captured["positions"] = positions

    guild.edit_role_positions = _edit_positions

    cfg = SimpleNamespace(anchor_role_id=anchor.id, hoist_above=True, enabled=True)
    await cog._reposition(guild, cfg)

    # hoist_above would push base+1, base+2, base+3 = 10, 11, 12 — all at/above the
    # bot's position (10). Every target must be clamped to me.top_role.position - 1.
    assert captured["positions"], "expected a bulk reposition"
    for pos in captured["positions"].values():
        assert pos <= me_top.position - 1
