"""add blacklists (bot-wide and economy-only user gates)

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f0
Create Date: 2026-07-01 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b2c3d4e5f6a1'
down_revision: str | None = 'a1b2c3d4e5f0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'blacklists',
        sa.Column('discord_id', sa.BigInteger(), nullable=False),
        sa.Column('scope', sa.String(length=16), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('added_by', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("scope in ('bot', 'economy')", name='chk_blacklist_scope'),
        sa.PrimaryKeyConstraint('discord_id', 'scope'),
    )


def downgrade() -> None:
    op.drop_table('blacklists')
