"""End-to-end listener-flow tests with a fake gateway (no live Discord).

These drive the cogs' real event handlers through fake guild/member/channel objects
and assert the real behavior the unit tests miss: voice-channel spawn/cleanup/transfer
and vanity grant. They also lock in fixes from the bug hunt (spawn records the row
before moving the member; grant doesn't re-announce when the role already exists).

Pattern (from test_leveling_voice): build the cog via ``Cog.__new__`` to skip the
loop-starting ``__init__``, set the in-memory state by hand, and use the test SQLite.
"""

from __future__ import annotations

from types import SimpleNamespace

import discord

from src.database.base import Base
from src.database.session import engine
from src.modules.vanity import service as van_service
from src.modules.vanity.cog import Vanity
from src.modules.voicemaster import service as vm_service
from src.modules.voicemaster.cog import Voicemaster


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── fakes ────────────────────────────────────────────────────────────────────

class _Voice:
    def __init__(self, cid: int, guild, members=None, category=None) -> None:
        self.id = cid
        self.guild = guild
        self.members = members if members is not None else []
        self.category = category
        self.deleted = False
        guild.channels[cid] = self

    async def delete(self, reason=None) -> None:
        self.deleted = True
        self.guild.channels.pop(self.id, None)


class _Guild:
    def __init__(self, gid: int, *, vanity=None) -> None:
        self.id = gid
        self.channels: dict[int, _Voice] = {}
        self.members: dict[int, object] = {}
        self.me = SimpleNamespace(top_role=999)
        self.vanity_url_code = vanity
        self.features: list[str] = []
        self.chunked = True
        self.roles: dict[int, object] = {}
        self._seq = 9000

    def get_channel(self, cid):
        return self.channels.get(cid)

    def get_member(self, uid):
        return self.members.get(uid)

    def get_role(self, rid):
        return self.roles.get(rid)

    async def create_voice_channel(self, name, category=None, overwrites=None, reason=None):
        self._seq += 1
        return _Voice(self._seq, self, members=[], category=category)


class _Member:
    def __init__(self, uid: int, guild, *, bot=False, roles=None) -> None:
        self.id = uid
        self.guild = guild
        self.bot = bot
        self.display_name = f"u{uid}"
        self.mention = f"<@{uid}>"
        self.roles = roles if roles is not None else []
        self.moved_to = None
        self.added_role = None
        self.removed_role = None
        guild.members[uid] = self

    async def move_to(self, channel, reason=None):
        self.moved_to = channel
        channel.members.append(self)

    async def add_roles(self, role, reason=None):
        self.added_role = role
        self.roles.append(role)

    async def remove_roles(self, role, reason=None):
        self.removed_role = role
        if role in self.roles:
            self.roles.remove(role)


def _presence_member(uid, guild, *, status, repping_code=None):
    activities = [discord.CustomActivity(name=f".gg/{repping_code}")] if repping_code else []
    return SimpleNamespace(id=uid, guild=guild, status=status, activities=activities)


def _vm_cog(bot=None):
    cog = Voicemaster.__new__(Voicemaster)
    cog.bot = bot or SimpleNamespace()
    cog._order = {}
    cog._sweep_task = None
    return cog


def _vanity_cog():
    cog = Vanity.__new__(Vanity)
    cog.bot = SimpleNamespace(intents=SimpleNamespace(presences=True))
    cog._repping = {}
    cog._pending = {}
    cog._semaphores = {}
    return cog


# ── voicemaster ──────────────────────────────────────────────────────────────

async def test_join_create_channel_spawns_and_tracks_before_move():
    await _schema()
    g = _Guild(50001)
    create = _Voice(70001, g, category=SimpleNamespace())
    await vm_service.set_create_channel(g.id, create.id)
    await vm_service.set_enabled(g.id, True)

    cog = _vm_cog()
    member = _Member(80001, g)
    create.members.append(member)
    await cog._handle_join(member, create)

    assert member.moved_to is not None                       # moved into the new room
    new_id = member.moved_to.id
    record = await vm_service.get_channel_by_id(g.id, new_id)
    assert record is not None and record.owner_id == member.id   # row written (before the move)
    assert cog._order[new_id] == [member.id]


async def test_empty_tracked_channel_is_deleted_and_untracked():
    await _schema()
    g = _Guild(50002)
    await vm_service.set_create_channel(g.id, 70002)
    await vm_service.set_enabled(g.id, True)
    ch = _Voice(70003, g, members=[])                        # tracked, now empty
    await vm_service.create_channel(g.id, 80002, ch.id)
    cog = _vm_cog()
    cog._order[ch.id] = []

    leaver = _Member(80002, g)
    await cog._handle_leave(leaver, ch)

    assert ch.deleted is True
    assert await vm_service.get_channel_by_id(g.id, ch.id) is None


async def test_owner_leaving_nonempty_channel_transfers_ownership():
    await _schema()
    g = _Guild(50003)
    await vm_service.set_create_channel(g.id, 70004)
    await vm_service.set_enabled(g.id, True)
    owner, other = _Member(80003, g), _Member(80004, g)
    ch = _Voice(70005, g, members=[other])                   # owner already left; other remains
    await vm_service.create_channel(g.id, owner.id, ch.id)
    cog = _vm_cog()
    cog._order[ch.id] = [owner.id, other.id]

    await cog._handle_leave(owner, ch)

    assert ch.deleted is False                               # still occupied
    record = await vm_service.get_channel_by_id(g.id, ch.id)
    assert record.owner_id == other.id                       # passed to the next by join order


# ── vanity ───────────────────────────────────────────────────────────────────

async def test_presence_repping_grants_role_and_tracks():
    await _schema()
    g = _Guild(60001, vanity="myserver")
    role = SimpleNamespace(id=61001)
    g.roles[role.id] = role
    await van_service.set_role(g.id, role.id)
    await van_service.set_enabled(g.id, True)

    cog = _vanity_cog()
    before = _presence_member(80010, g, status=discord.Status.online)              # not repping
    after = _Member(80010, g)                                                       # repping now
    after.status = discord.Status.online
    after.activities = [discord.CustomActivity(name="join .gg/myserver")]

    await cog.on_presence_update(before, after)

    assert after.added_role is role                                  # role granted
    assert 80010 in await van_service.get_active_ids(g.id)           # durable tracker written


async def test_grant_does_not_reannounce_when_role_already_held():
    await _schema()
    g = _Guild(60002, vanity="myserver")
    role = SimpleNamespace(id=61002)
    g.roles[role.id] = role
    await van_service.set_role(g.id, role.id)
    await van_service.set_enabled(g.id, True)

    cog = _vanity_cog()
    member = _Member(80011, g, roles=[role])      # already holds the role (e.g. after a restart)
    announced: list[bool] = []

    async def _fake_announce(guild, m):
        announced.append(True)

    cog._announce = _fake_announce

    async def _fake_log(guild, m, *, granted):
        announced.append(True)

    cog._log = _fake_log
    await cog._grant(g, member, await van_service.get_config(g.id))

    assert member.added_role is None      # didn't re-add the role it already had
    assert announced == []                # and didn't post a duplicate thank-you / log
    assert 80011 in await van_service.get_active_ids(g.id)
