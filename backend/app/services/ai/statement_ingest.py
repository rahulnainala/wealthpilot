"""Phase 23 — statement / CAS ingestion.

Extracts the text of an uploaded broker/CAS PDF and adds it to the RAG corpus
(source `portfolio/uploads/*`) so Pilot can reference the owner's real records.
Deliberately text-level, not a fragile structured reconciler — CAS PDFs are
often password-protected and vary by format; optional password is supported.
Embedding happens whenever the 3070 is up (same resumable loop as the corpus).
"""

from __future__ import annotations

import io
import logging

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk
from app.services.ai.rag import _chunk, embed_pending

logger = logging.getLogger("wealthpilot.ai")


def _extract_text(pdf_bytes: bytes, password: str | None) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    if reader.is_encrypted:
        reader.decrypt(password or "")
    return "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()


async def ingest_statement(
    db: AsyncSession, filename: str, pdf_bytes: bytes, password: str | None = None
) -> dict:
    """Parse a statement PDF to text and (re)ingest it into the knowledge base."""
    try:
        text = _extract_text(pdf_bytes, password)
    except Exception as exc:  # noqa: BLE001 — surface a clean message, don't 500
        logger.info("statement parse failed: %s", exc)
        return {"error": "Could not read the PDF (wrong password or unsupported format).", "chunks_added": 0}
    if not text:
        return {"error": "No extractable text — the PDF may be a scanned image.", "chunks_added": 0}

    safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in filename)[:80]
    source = f"portfolio/uploads/{safe}"
    title = f"Statement {safe}"
    # Idempotent: replace any prior ingest of the same file.
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source == source))
    chunks = _chunk(text)
    for i, content in enumerate(chunks):
        db.add(KnowledgeChunk(source=source, title=title, chunk_index=i, content=content))
    await db.commit()

    embedded = await embed_pending(db, batch=256)
    return {"source": source, "chars": len(text), "chunks_added": len(chunks), "embedded": embedded}
