"""Realized exit ledger for the legacy sell-off.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "realized_exit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("avg_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=False),
        sa.Column("proceeds", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("full_exit", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("exited_on", sa.Date(), nullable=False),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("symbol", "exited_on", name="uq_realized_exit_symbol_day"),
    )
    op.create_index("ix_realized_exit_symbol", "realized_exit", ["symbol"])
    op.create_index("ix_realized_exit_exited_on", "realized_exit", ["exited_on"])


def downgrade() -> None:
    op.drop_index("ix_realized_exit_exited_on", table_name="realized_exit")
    op.drop_index("ix_realized_exit_symbol", table_name="realized_exit")
    op.drop_table("realized_exit")
