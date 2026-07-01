"""add user_message_counts (per-guild per-user message tracking)

Revision ID: b1c2d3e4f5a6
Revises: a9f3c1d7e5b2
Create Date: 2026-07-01 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b1c2d3e4f5a6'
down_revision: str | None = 'a9f3c1d7e5b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'user_message_counts',
        sa.Column('guild_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('count', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('guild_id', 'user_id'),
    )
    op.create_index('ix_msgcount_user', 'user_message_counts', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_msgcount_user', table_name='user_message_counts')
    op.drop_table('user_message_counts')
