"""Data access for moderation: cases, immune entries, temp roles, and jail state."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.case import ModCase
from src.database.models.immune import ImmuneEntry
from src.database.models.jail import JailedMember, ModerationConfig
from src.database.models.temprole import TempRole


class ModerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── cases ─────────────────────────────────────────────────────────────────

    def add(self, case: ModCase) -> None:
        self.session.add(case)

    async def cases_for_user(self, guild_id: int, user_id: int, limit: int = 15, offset: int = 0) -> list[ModCase]:
        stmt = (
            select(ModCase)
            .where(ModCase.guild_id == guild_id, ModCase.user_id == user_id)
            .order_by(ModCase.created_at.desc(), ModCase.id.desc())
            .limit(limit).offset(offset)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_for_user(self, guild_id: int, user_id: int) -> int:
        stmt = select(func.count()).select_from(ModCase).where(
            ModCase.guild_id == guild_id, ModCase.user_id == user_id
        )
        return int((await self.session.execute(stmt)).scalar_one())

    # ── staff-wide aggregates (dashboard analytics; not guild-scoped) ──

    async def total_cases(self) -> int:
        """Every moderation case ever logged, across all guilds."""
        stmt = select(func.count()).select_from(ModCase)
        return int((await self.session.execute(stmt)).scalar_one())

    async def action_breakdown(self) -> list[tuple[str, int]]:
        """Cases grouped by kind (ban/kick/timeout/warn…), most frequent first."""
        stmt = (
            select(ModCase.kind, func.count(ModCase.id))
            .group_by(ModCase.kind)
            .order_by(func.count(ModCase.id).desc())
        )
        return [(k, int(n)) for k, n in (await self.session.execute(stmt)).all()]

    async def actions_by_day(self, days: int = 14) -> list[tuple[str, int]]:
        """Moderation cases per calendar day for the last ``days`` days."""
        from datetime import UTC, timedelta

        since = datetime.now(UTC) - timedelta(days=days)
        day = func.date(ModCase.created_at)
        stmt = (
            select(day.label("day"), func.count(ModCase.id))
            .where(ModCase.created_at >= since)
            .group_by(day)
            .order_by(day)
        )
        return [(str(d), int(n)) for d, n in (await self.session.execute(stmt)).all()]

    async def count_recent_cases(
        self, guild_id: int, user_id: int, kind: str, since: datetime
    ) -> int:
        stmt = select(func.count()).select_from(ModCase).where(
            ModCase.guild_id == guild_id,
            ModCase.user_id == user_id,
            ModCase.kind == kind,
            ModCase.created_at >= since,
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def cases_by_kind(self, guild_id: int, user_id: int, kind: str) -> list[ModCase]:
        stmt = (
            select(ModCase)
            .where(ModCase.guild_id == guild_id, ModCase.user_id == user_id, ModCase.kind == kind)
            .order_by(ModCase.created_at.desc(), ModCase.id.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def case_by_id(self, guild_id: int, case_id: int) -> ModCase | None:
        stmt = select(ModCase).where(ModCase.id == case_id, ModCase.guild_id == guild_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def delete_case(self, case: ModCase) -> None:
        await self.session.delete(case)

    async def delete_cases_by_kind(self, guild_id: int, user_id: int, kind: str) -> int:
        stmt = delete(ModCase).where(
            ModCase.guild_id == guild_id, ModCase.user_id == user_id, ModCase.kind == kind
        )
        return (await self.session.execute(stmt)).rowcount or 0

    # ── immune ────────────────────────────────────────────────────────────────

    async def _immune_row(self, guild_id: int, target_id: int) -> ImmuneEntry | None:
        stmt = select(ImmuneEntry).where(
            ImmuneEntry.guild_id == guild_id, ImmuneEntry.target_id == target_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add_immune(self, guild_id: int, target_id: int, is_role: bool) -> None:
        if await self._immune_row(guild_id, target_id) is None:
            self.session.add(ImmuneEntry(guild_id=guild_id, target_id=target_id, is_role=is_role))

    async def remove_immune(self, guild_id: int, target_id: int) -> bool:
        row = await self._immune_row(guild_id, target_id)
        if row is None:
            return False
        await self.session.delete(row)
        return True

    async def list_immune(self, guild_id: int) -> list[tuple[int, bool]]:
        stmt = select(ImmuneEntry.target_id, ImmuneEntry.is_role).where(
            ImmuneEntry.guild_id == guild_id
        )
        return [(r[0], r[1]) for r in (await self.session.execute(stmt)).all()]

    # ── temp roles ────────────────────────────────────────────────────────────

    async def add_temprole(self, guild_id: int, user_id: int, role_id: int, expires_at: datetime) -> None:
        self.session.add(TempRole(guild_id=guild_id, user_id=user_id, role_id=role_id, expires_at=expires_at))

    async def due_temproles(self, now: datetime) -> list[tuple[int, int, int, int]]:
        rows = (await self.session.execute(select(TempRole).where(TempRole.expires_at <= now))).scalars().all()
        return [(r.id, r.guild_id, r.user_id, r.role_id) for r in rows]

    async def delete_temprole(self, entry_id: int) -> None:
        await self.session.execute(delete(TempRole).where(TempRole.id == entry_id))

    async def delete_temproles(self, entry_ids: list[int]) -> None:
        if not entry_ids:
            return
        await self.session.execute(delete(TempRole).where(TempRole.id.in_(entry_ids)))

    async def delete_temprole_for(self, guild_id: int, user_id: int, role_id: int) -> int:
        stmt = delete(TempRole).where(
            TempRole.guild_id == guild_id, TempRole.user_id == user_id, TempRole.role_id == role_id
        )
        return (await self.session.execute(stmt)).rowcount or 0

    async def list_temproles(self, guild_id: int) -> list[TempRole]:
        stmt = select(TempRole).where(TempRole.guild_id == guild_id).order_by(TempRole.expires_at.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    # ── jail (from List Five) ───────────────────────────────────────────────

    async def get_jail_role(self, guild_id: int) -> int | None:
        cfg = await self.session.get(ModerationConfig, guild_id)
        return cfg.jail_role_id if cfg else None

    async def set_jail_role(self, guild_id: int, role_id: int) -> None:
        cfg = await self.session.get(ModerationConfig, guild_id)
        if cfg is None:
            self.session.add(ModerationConfig(guild_id=guild_id, jail_role_id=role_id))
        else:
            cfg.jail_role_id = role_id

    async def is_jailed(self, guild_id: int, user_id: int) -> bool:
        stmt = select(JailedMember.id).where(
            JailedMember.guild_id == guild_id, JailedMember.user_id == user_id
        )
        return (await self.session.execute(stmt)).first() is not None

    async def add_jailed(self, guild_id: int, user_id: int, prior_roles: list[int]) -> None:
        self.session.add(JailedMember(guild_id=guild_id, user_id=user_id, prior_roles=prior_roles))

    async def pop_jailed(self, guild_id: int, user_id: int) -> list[int] | None:
        stmt = select(JailedMember).where(
            JailedMember.guild_id == guild_id, JailedMember.user_id == user_id
        )
        entry = (await self.session.execute(stmt)).scalar_one_or_none()
        if entry is None:
            return None
        roles = list(entry.prior_roles)
        await self.session.delete(entry)
        return roles

    async def list_jailed(self, guild_id: int) -> list[int]:
        stmt = select(JailedMember.user_id).where(JailedMember.guild_id == guild_id)
        return [row[0] for row in (await self.session.execute(stmt)).all()]
