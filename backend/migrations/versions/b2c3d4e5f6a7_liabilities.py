"""Liabilities — net worth stops meaning gross assets.

Revision ID: b2c3d4e5f6a7
Revises: f2a3b4c5d6e7
Create Date: 2026-08-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "liabilities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("principal", sa.Float(), nullable=False),
        sa.Column("outstanding", sa.Float(), nullable=False),
        # Nullable by design: a gold loan is often bullet/interest-only, so EMI
        # may not exist, and the rate may not be to hand when the row is first
        # entered. The payoff projection degrades rather than inventing values.
        sa.Column("rate_pct", sa.Float(), nullable=True),
        sa.Column("emi", sa.Float(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("term_months", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("liabilities")
