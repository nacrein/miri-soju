"""add music_config table

Revision ID: c0ffee5a1b2c
Revises: 0aaa4ab140bf
Create Date: 2026-06-29 11:40:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c0ffee5a1b2c'
down_revision: str | None = '0aaa4ab140bf'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'music_config',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('dj_role_id', sa.BigInteger(), nullable=True),
        sa.Column('command_channel_id', sa.BigInteger(), nullable=True),
        sa.Column('default_volume', sa.Integer(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint('guild_id'),
    )


def downgrade() -> None:
    op.drop_table('music_config')
