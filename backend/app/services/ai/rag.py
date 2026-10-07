"""RAG foundation (Phase 5): ingest → embed (3070/Ollama) → retrieve.

Corpus = docs/knowledge/** (finance explainers + the user's notes, mounted
read-only into the container) plus future distilled portfolio history. The
loop is deliberately resumable: ingestion never requires the GPU box to be
on; embedding catches up whenever it is.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.knowledge import KnowledgeChunk

logger = logging.getLogger("wealthpilot.ai")

_CHUNK_CHARS = 2000  # ~500 tokens
_EMBED_TIMEOUT_S = 30.0


def _chunk(text: str) -> list[str]:
    """Paragraph-packing chunker: split on blank lines, pack to ~_CHUNK_CHARS."""
    parts: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        if len(current) + len(para) > _CHUNK_CHARS and current:
            parts.append(current.strip())
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current.strip():
        parts.append(current.strip())
    return parts


async def ingest_knowledge_dir(db: AsyncSession) -> dict[str, int]:
    """Sync docs/knowledge/**.md into knowledge_chunks (idempotent upsert)."""
    root = Path(get_settings().knowledge_dir)
    added = 0
    seen = 0
    if not root.exists():
        return {"files": 0, "chunks_added": 0}

    for path in sorted(root.rglob("*.md")):
        seen += 1
        source = str(path.relative_to(root))
        title = path.stem.replace("-", " ").replace("_", " ").title()
        chunks = _chunk(path.read_text(encoding="utf-8", errors="ignore"))

        existing = {
            row.chunk_index: row
            for row in (
                await db.execute(
                    select(KnowledgeChunk).where(KnowledgeChunk.source == source)
                )
            ).scalars()
        }
        for i, content in enumerate(chunks):
            row = existing.get(i)
            if row is None:
                db.add(
                    KnowledgeChunk(
                        source=source, title=title, chunk_index=i, content=content
                    )
                )
                added += 1
            elif row.content != content:
                row.content = content
                row.embedding = None  # content changed → re-embed
    await db.commit()
    return {"files": seen, "chunks_added": added}


async def _embed(texts: list[str]) -> list[list[float]] | None:
    """Embed via the 3070's Ollama; None when it isn't reachable."""
    settings = get_settings()
    if not settings.ollama_url:
        return None
    try:
        async with httpx.AsyncClient(
            base_url=settings.ollama_url, timeout=_EMBED_TIMEOUT_S
        ) as client:
            out: list[list[float]] = []
            for text in texts:
                resp = await client.post(
                    "/api/embeddings",
                    json={"model": settings.embed_model, "prompt": text, "keep_alive": -1},
                )
                resp.raise_for_status()
                out.append(resp.json()["embedding"])
            return out
    except httpx.HTTPError as exc:
        logger.info("embedding skipped (ollama unreachable: %s)", exc)
        return None


async def embed_pending(db: AsyncSession, batch: int = 64) -> int:
    """Fill missing vectors — the resumable half of the learning loop."""
    rows = (
        (
            await db.execute(
                select(KnowledgeChunk)
                .where(KnowledgeChunk.embedding.is_(None))
                .limit(batch)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0
    vectors = await _embed([r.content for r in rows])
    if vectors is None:
        return 0
    for row, vec in zip(rows, vectors, strict=True):
        row.embedding = vec
    await db.commit()
    logger.info("embedded %d knowledge chunks", len(rows))
    return len(rows)


async def retrieve(db: AsyncSession, query: str, k: int = 4) -> list[KnowledgeChunk]:
    """Top-k chunks by cosine distance; empty when the query can't be embedded."""
    vectors = await _embed([query])
    if vectors is None:
        return []
    result = await db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.embedding.is_not(None))
        .order_by(KnowledgeChunk.embedding.cosine_distance(vectors[0]))
        .limit(k)
    )
    return list(result.scalars())


async def hybrid_retrieve(
    db: AsyncSession, query: str, k: int = 4
) -> list[KnowledgeChunk]:
    """Phase 14 — vector + keyword retrieval merged.

    Semantic (cosine) results lead; keyword (ILIKE, ranked by term frequency)
    results fill in and — crucially — keep retrieval working when the 3070 is
    off and embeddings are unavailable. Callers cite `chunk.source` inline.
    """
    import re

    from sqlalchemy import or_

    vec_hits = await retrieve(db, query, k)

    terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 3][:6]
    kw_hits: list[KnowledgeChunk] = []
    if terms:
        rows = (
            (
                await db.execute(
                    select(KnowledgeChunk)
                    .where(or_(*[KnowledgeChunk.content.ilike(f"%{t}%") for t in terms]))
                    .limit(k * 4)
                )
            )
            .scalars()
            .all()
        )
        kw_hits = sorted(
            rows,
            key=lambda c: sum(c.content.lower().count(t) for t in terms),
            reverse=True,
        )[:k]

    seen: set[tuple[str, int]] = set()
    out: list[KnowledgeChunk] = []
    for h in [*vec_hits, *kw_hits]:
        key = (h.source, h.chunk_index)
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out[:k]


async def retrieve_daily_notes(
    db: AsyncSession, query: str, k: int = 3
) -> list[KnowledgeChunk]:
    """Phase 10 — top-k *distilled daily portfolio notes* similar to the query.

    Restricted to `portfolio/daily-*` sources so Pilot can surface historical
    analogues ("your VaR looked like this on 2026-05-12") rather than generic
    finance docs. Empty until the nightly distillation has embedded some days.
    """
    vectors = await _embed([query])
    if vectors is None:
        return []
    result = await db.execute(
        select(KnowledgeChunk)
        .where(
            KnowledgeChunk.embedding.is_not(None),
            KnowledgeChunk.source.like("portfolio/daily-%"),
        )
        .order_by(KnowledgeChunk.embedding.cosine_distance(vectors[0]))
        .limit(k)
    )
    return list(result.scalars())
