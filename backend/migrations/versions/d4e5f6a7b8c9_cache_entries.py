"""Postgres-backed TTL cache table (replaces the Redis container locally).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cache_entries",
        sa.Column("key", sa.String(length=256), primary_key=True),
        sa.Column("value", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cache_expires", "cache_entries", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_cache_expires", table_name="cache_entries")
    op.drop_table("cache_entries")
