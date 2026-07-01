"""The web staff gate reads the same DB roster the bot's ``,staff promote``/``demote``
write, with ``OWNER_ID``/``STAFF_IDS`` as a bootstrap floor.

Auth path only — no bits change hands here, so the economy money-safety invariants
don't apply. We exercise ``dashboard.deps.require_staff`` / ``is_staff_user`` directly
(they are plain async callables; ``get_current_user`` is bypassed by passing ``user``).
``OWNER_ID`` is ``1`` (see ``tests/conftest.py``); no ``STAFF_IDS`` are set.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

import src.database.models  # noqa: F401 — registers every table on Base.metadata
from dashboard.deps import is_staff_user, require_staff
from src.core import staff_roster
from src.database.base import Base
from src.database.session import engine


async def _schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def test_db_promoted_user_passes_require_staff():
    await _schema()
    uid = 900_000_101  # not in the env floor; only reachable via the DB roster
    await staff_roster.set_tier(uid, "staff", added_by=1)
    assert await is_staff_user(uid) is True
    # No exception raised => authorized; the caller's user dict is returned unchanged.
    user = {"id": str(uid)}
    assert await require_staff(user=user) == user


async def test_non_staff_user_is_rejected():
    await _schema()
    uid = 900_000_102  # never promoted, not in the env floor
    assert await is_staff_user(uid) is False
    with pytest.raises(HTTPException) as exc:
        await require_staff(user={"id": str(uid)})
    assert exc.value.status_code == 403


async def test_owner_passes_via_env_floor_with_empty_table():
    await _schema()
    # OWNER_ID=1 with no staff_members row for the owner: the env floor still admits them.
    assert await staff_roster.is_staff_member(1) is False
    assert await is_staff_user(1) is True
    assert await require_staff(user={"id": "1"}) == {"id": "1"}


async def test_demote_revokes_web_access():
    await _schema()
    uid = 900_000_103
    await staff_roster.set_tier(uid, "admin", added_by=1)
    assert await is_staff_user(uid) is True
    await staff_roster.remove(uid)
    # The gate reads the roster fresh, so the demote takes effect immediately.
    assert await is_staff_user(uid) is False
    with pytest.raises(HTTPException) as exc:
        await require_staff(user={"id": str(uid)})
    assert exc.value.status_code == 403
