"""add polls and poll_votes tables

Revision ID: a17e9b0c0006
Revises: a17e9b0c0005
Create Date: 2026-06-30 09:25:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a17e9b0c0006'
down_revision: str | None = 'a17e9b0c0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'polls',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('author_id', sa.BigInteger(), nullable=False),
        sa.Column('question', sa.String(length=256), nullable=False),
        sa.Column('options_text', sa.String(length=1000), nullable=False),
        sa.Column('closed', sa.Boolean(), nullable=False),
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
    op.create_table(
        'poll_votes',
        sa.Column('poll_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('option_index', sa.Integer(), nullable=False),
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
        sa.UniqueConstraint('poll_id', 'user_id', name='uq_pollvote_poll_user'),
    )


def downgrade() -> None:
    op.drop_table('poll_votes')
    op.drop_table('polls')
