"""add staff_members (runtime admin/staff permission tiers)

Revision ID: a1b2c3d4e5f0
Revises: e2f3a4b5c6d7
Create Date: 2026-07-01 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f0'
down_revision: str | None = 'e2f3a4b5c6d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'staff_members',
        sa.Column('discord_id', sa.BigInteger(), nullable=False),
        sa.Column('tier', sa.String(length=16), nullable=False),
        sa.Column('added_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("tier in ('staff', 'admin')", name='chk_staff_member_tier'),
        sa.PrimaryKeyConstraint('discord_id'),
    )


def downgrade() -> None:
    op.drop_table('staff_members')
