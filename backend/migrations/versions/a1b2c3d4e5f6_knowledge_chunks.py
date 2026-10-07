"""RAG knowledge_chunks table + pgvector extension (AI Phase 5).

Revision ID: a1b2c3d4e5f6
Revises: 20dacdbbe7fd
Create Date: 2026-07-11
"""

from __future__ import annotations

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "20dacdbbe7fd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(768), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("source", "chunk_index", name="uq_knowledge_source_chunk"),
    )
    op.create_index("ix_knowledge_source", "knowledge_chunks", ["source"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_source", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
