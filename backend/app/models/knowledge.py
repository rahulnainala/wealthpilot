"""RAG knowledge chunks (Phase 5, docs/AI_ROADMAP.md).

Embeddings are nullable: ingestion stores chunks immediately; the embed pass
fills vectors whenever the 3070's Ollama is reachable. Retrieval only
considers embedded rows.
"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

EMBED_DIM = 768  # nomic-embed-text


class KnowledgeChunk(Base, TimestampMixin):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("source", "chunk_index", name="uq_knowledge_source_chunk"),
        Index("ix_knowledge_source", "source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(512))  # file path or logical origin
    title: Mapped[str] = mapped_column(String(256))
    chunk_index: Mapped[int] = mapped_column(default=0)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
