"""AI insight severity/source/alert_key (Phase 7 proactive alerts).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_insights",
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
    )
    op.add_column(
        "ai_insights",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="model"),
    )
    op.add_column(
        "ai_insights",
        sa.Column("alert_key", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_insights", "alert_key")
    op.drop_column("ai_insights", "source")
    op.drop_column("ai_insights", "severity")
