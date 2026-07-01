"""drop economy (players, transactions) and narrow blacklist scope to bot

Removes the economy subsystem's tables now that all economy code is gone, and
narrows the ``blacklists`` CHECK constraint from ('bot', 'economy') to 'bot' only
(the 'economy' scope no longer exists).

DESTRUCTIVE: player balances and the transaction ledger are permanently deleted.
The downgrade recreates the table *structure* only — data is not restored.

Revision ID: a9f3c1d7e5b2
Revises: b2c3d4e5f6a1
Create Date: 2026-07-01 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a9f3c1d7e5b2'
down_revision: str | None = 'b2c3d4e5f6a1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the economy ledger + player tables (their indexes go with them).
    op.drop_index('ix_transactions_user_time', table_name='transactions')
    op.drop_index('ix_transactions_type', table_name='transactions')
    op.drop_index('ix_transactions_game_session', table_name='transactions')
    op.drop_table('transactions')
    op.drop_index('ix_players_net_worth', table_name='players')
    op.drop_table('players')

    # 'economy' is no longer a valid blacklist scope: purge those rows, then narrow
    # the CHECK. batch_alter_table recreates the table on SQLite (tests) and issues a
    # plain drop/add on Postgres (prod).
    op.execute("DELETE FROM blacklists WHERE scope = 'economy'")
    with op.batch_alter_table('blacklists', schema=None) as batch:
        batch.drop_constraint('chk_blacklist_scope', type_='check')
        batch.create_check_constraint('chk_blacklist_scope', "scope = 'bot'")


def downgrade() -> None:
    # Widen the blacklist scope back to ('bot', 'economy').
    with op.batch_alter_table('blacklists', schema=None) as batch:
        batch.drop_constraint('chk_blacklist_scope', type_='check')
        batch.create_check_constraint('chk_blacklist_scope', "scope in ('bot', 'economy')")

    # Recreate the economy tables (structure only; balances/ledger are not restored).
    op.create_table(
        'players',
        sa.Column('discord_id', sa.BigInteger(), nullable=False),
        sa.Column('wallet', sa.BigInteger(), nullable=False),
        sa.Column('vault', sa.BigInteger(), nullable=False),
        sa.Column('vault_capacity', sa.BigInteger(), nullable=False),
        sa.Column('generator_tier', sa.Integer(), nullable=False),
        sa.Column('generator_claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_daily_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_work_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_pray_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_steal_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('daily_streak', sa.Integer(), nullable=False),
        sa.Column('tos_accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('vault <= vault_capacity', name='chk_player_vault_within_cap'),
        sa.CheckConstraint('vault >= 0', name='chk_player_vault_nonneg'),
        sa.CheckConstraint('vault_capacity >= 0', name='chk_player_vault_cap_nonneg'),
        sa.CheckConstraint('wallet >= 0', name='chk_player_wallet_nonneg'),
        sa.PrimaryKeyConstraint('discord_id'),
    )
    op.create_index(
        'ix_players_net_worth', 'players',
        [sa.literal_column('(wallet + vault) DESC')], unique=False,
    )
    op.create_table(
        'transactions',
        sa.Column('discord_id', sa.BigInteger(), nullable=False),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('amount', sa.BigInteger(), nullable=False),
        sa.Column('balance_after', sa.BigInteger(), nullable=False),
        sa.Column('counterparty_id', sa.BigInteger(), nullable=True),
        sa.Column('note', sa.String(length=128), nullable=True),
        sa.Column('game_session_id', sa.String(length=32), nullable=True),
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_transactions_game_session', 'transactions', ['game_session_id'], unique=False)
    op.create_index('ix_transactions_type', 'transactions', ['kind'], unique=False)
    op.create_index('ix_transactions_user_time', 'transactions', ['discord_id', 'created_at'], unique=False)
