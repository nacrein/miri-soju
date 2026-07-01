"""add starboard_config and starboard_entries tables

Revision ID: a17e9b0c0004
Revises: a17e9b0c0003
Create Date: 2026-06-30 09:15:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a17e9b0c0004'
down_revision: str | None = 'a17e9b0c0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'starboard_config',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=True),
        sa.Column('threshold', sa.Integer(), nullable=False),
        sa.Column('star_emoji', sa.String(length=64), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('self_star', sa.Boolean(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint('guild_id'),
    )
    op.create_table(
        'starboard_entries',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('board_message_id', sa.BigInteger(), nullable=False),
        sa.Column('star_count', sa.Integer(), nullable=False),
        sa.Column(
            'id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
            autoincrement=True, nullable=False,
        ),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'message_id', name='uq_starboard_guild_msg'),
    )


def downgrade() -> None:
    op.drop_table('starboard_entries')
    op.drop_table('starboard_config')
