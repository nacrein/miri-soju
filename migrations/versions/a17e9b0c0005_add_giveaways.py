"""add giveaways and giveaway_entries tables

Revision ID: a17e9b0c0005
Revises: a17e9b0c0004
Create Date: 2026-06-30 09:20:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a17e9b0c0005'
down_revision: str | None = 'a17e9b0c0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'giveaways',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('prize', sa.String(length=256), nullable=False),
        sa.Column('winners', sa.Integer(), nullable=False),
        sa.Column('host_id', sa.BigInteger(), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended', sa.Boolean(), nullable=False),
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
    )
    op.create_index('ix_giveaways_ends_at', 'giveaways', ['ends_at'], unique=False)
    op.create_table(
        'giveaway_entries',
        sa.Column('giveaway_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
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
        sa.UniqueConstraint('giveaway_id', 'user_id', name='uq_giveaway_entry'),
    )


def downgrade() -> None:
    op.drop_table('giveaway_entries')
    op.drop_index('ix_giveaways_ends_at', table_name='giveaways')
    op.drop_table('giveaways')
