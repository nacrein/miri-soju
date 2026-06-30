"""DB-backed tests for the moderation service: immune cache, temproles, cases, jail.

These exercise behavior the rest of the suite misses: the immune-cache
invalidation-after-write contract (the named common bug class), temprole expiry
boundaries, case reason edits, and the idempotent-jail guard. They use the test
SQLite engine via the same ``_schema()`` pattern as ``test_integration_flows``.
"""

from __future__ import annotations

from datetime import timedelta

from src.database.base import Base
from src.database.session import engine
from src.modules.moderation import service


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── immune list (by id, by role, and the cache-invalidation contract) ──────────

async def test_is_immune_by_user_id():
    await _schema()
    gid = 70_001
    assert await service.is_immune(gid, 100, []) is False
    await service.add_immune(gid, 100, is_role=False)
    assert await service.is_immune(gid, 100, []) is True
    # A different, unprotected user is still actionable.
    assert await service.is_immune(gid, 101, []) is False


async def test_is_immune_by_role_id():
    await _schema()
    gid = 70_002
    await service.add_immune(gid, 555, is_role=True)
    # The user id isn't immune, but they hold the immune role.
    assert await service.is_immune(gid, 200, [999]) is False
    assert await service.is_immune(gid, 200, [999, 555]) is True


async def test_add_then_remove_immune_invalidates_cache():
    """Regression: add/remove must flip a *subsequent* is_immune (cache not stale)."""
    await _schema()
    gid = 70_003
    # Prime the negative cache with a read.
    assert await service.is_immune(gid, 300, []) is False
    # Add: the next read must reflect it, proving add_immune invalidated the cache.
    await service.add_immune(gid, 300, is_role=False)
    assert await service.is_immune(gid, 300, []) is True
    # Remove: the next read must reflect that too.
    assert await service.remove_immune(gid, 300) is True
    assert await service.is_immune(gid, 300, []) is False
    # Removing again reports nothing was there.
    assert await service.remove_immune(gid, 300) is False


# ── temproles (expiry boundary) ────────────────────────────────────────────────

async def test_due_temproles_expired_vs_not_yet():
    await _schema()
    gid = 71_001
    expired_at = service._now() - timedelta(minutes=1)
    future_at = service._now() + timedelta(days=1)
    await service.add_temprole(gid, 10, 1, expired_at)
    await service.add_temprole(gid, 11, 2, future_at)

    due = await service.due_temproles()
    due_users = {uid for _id, _gid, uid, _rid in due if _gid == gid}
    assert 10 in due_users          # past its expiry
    assert 11 not in due_users      # still in the future


async def test_delete_temproles_batch_removes_only_given_ids():
    await _schema()
    gid = 71_002
    expired_at = service._now() - timedelta(minutes=1)
    await service.add_temprole(gid, 20, 1, expired_at)
    await service.add_temprole(gid, 21, 2, expired_at)

    due = [(eid, uid) for eid, g, uid, _r in await service.due_temproles() if g == gid]
    assert len(due) == 2
    # Retire only the first id; the second must survive (loop keeps failed rows).
    await service.delete_temproles([due[0][0]])

    survivors = {uid for _e, g, uid, _r in await service.due_temproles() if g == gid}
    assert survivors == {due[1][1]}


# ── cases (reason edit) ────────────────────────────────────────────────────────

async def test_edit_case_reason_updates_and_reports_missing():
    await _schema()
    gid = 72_001
    case_id = await service.add_case(gid, 1, 2, "warn", "original")
    assert await service.edit_case_reason(gid, case_id, "edited") is True
    rows = await service.list_warnings(gid, 1)
    assert rows[0].reason == "edited"
    # Unknown case id (and wrong-guild scoping) reports False.
    assert await service.edit_case_reason(gid, 999_999, "x") is False
    assert await service.edit_case_reason(gid + 1, case_id, "x") is False


# ── jail (idempotent re-jail guard) ────────────────────────────────────────────

async def test_is_jailed_tracks_store_and_release():
    await _schema()
    gid = 73_001
    assert await service.is_jailed(gid, 1) is False
    await service.store_jailed(gid, 1, [10, 11])
    assert await service.is_jailed(gid, 1) is True
    # Releasing returns the prior roles and clears the jailed state.
    assert await service.release_jailed(gid, 1) == [10, 11]
    assert await service.is_jailed(gid, 1) is False
